import hashlib
import os
from contextlib import contextmanager
import hmac
import json
import secrets
import sqlite3
from pathlib import Path

DEMO_USERS = {'CUST001': 'demo-1234', 'CUST002': 'demo-5678'}


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        key_path = self.path.with_suffix('.audit-key')
        try:
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as key_file:
                key_file.write(secrets.token_bytes(32))
        except FileExistsError:
            pass
        self.audit_key = key_path.read_bytes()
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS transactions (
              id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, account_id TEXT NOT NULL,
              posted_on TEXT NOT NULL, direction TEXT NOT NULL, amount_paise INTEGER NOT NULL,
              narration TEXT NOT NULL, merchant TEXT NOT NULL, kind TEXT NOT NULL, original_id TEXT);
            CREATE INDEX IF NOT EXISTS customer_date ON transactions(customer_id, posted_on);
            CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, salt TEXT, digest TEXT);
            CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, customer_id TEXT,
              name TEXT, target_paise INTEGER, saved_paise INTEGER, due_on TEXT);
            CREATE TABLE IF NOT EXISTS context (customer_id TEXT PRIMARY KEY, topic TEXT);
            CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT,
              at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), customer_id TEXT,
              action TEXT, metadata TEXT);
            ''')
        with self.connect() as db:
            existing = {r['name'] for r in db.execute('PRAGMA table_info(goals)')}
            for column, definition in [('version','INTEGER NOT NULL DEFAULT 1'), ('archived','INTEGER NOT NULL DEFAULT 0'),
                                       ('created_at',"TEXT NOT NULL DEFAULT ''"), ('updated_at',"TEXT NOT NULL DEFAULT ''")]:
                if column not in existing:
                    db.execute(f'ALTER TABLE goals ADD COLUMN {column} {definition}')
            db.execute('CREATE TABLE IF NOT EXISTS consent (subject TEXT, policy TEXT, at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(subject,policy))')
            user_columns = {r['name'] for r in db.execute('PRAGMA table_info(users)')}
            if 'iterations' not in user_columns:
                db.execute('ALTER TABLE users ADD COLUMN iterations INTEGER NOT NULL DEFAULT 200000')
            # Migrate old audit subjects to keyed pseudonyms without retaining raw identities.
            for row in db.execute("SELECT DISTINCT customer_id FROM audit WHERE customer_id NOT LIKE 'subject:%'").fetchall():
                db.execute('UPDATE audit SET customer_id=? WHERE customer_id=?', (self.subject(row[0]),row[0]))
            db.execute("DELETE FROM audit WHERE at < strftime('%Y-%m-%dT%H:%M:%fZ','now','-90 days')")
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            with db:
                yield db
        finally:
            db.close()

    def import_transactions(self, transactions):
        # Entire validated export is committed atomically; changed duplicate IDs fail.
        with self.connect() as db:
            for t in transactions:
                data = t.__dict__
                owner = db.execute('SELECT customer_id FROM transactions WHERE account_id=? LIMIT 1', (t.account_id,)).fetchone()
                if owner and owner['customer_id'] != t.customer_id:
                    raise ValueError('Account owner conflicts with existing data.')
                existing = db.execute('SELECT * FROM transactions WHERE id=?', (t.id,)).fetchone()
                if existing:
                    if dict(existing) != data:
                        raise ValueError('An existing transaction ID has different data.')
                    continue
                columns = ','.join(data)
                db.execute(f'INSERT INTO transactions ({columns}) VALUES ({",".join("?" for _ in data)})', tuple(data.values()))

            invalid_refund = db.execute('''
                SELECT p.id FROM transactions p JOIN transactions r ON r.original_id=p.id
                WHERE r.kind='REFUND' GROUP BY p.id,p.amount_paise
                HAVING SUM(r.amount_paise)>p.amount_paise LIMIT 1
            ''').fetchone()
            if invalid_refund:
                raise ValueError('Cumulative refunds exceed original payment across imports.')

    def seed_demo_users(self):
        with self.connect() as db:
            for uid, password in DEMO_USERS.items():
                salt = secrets.token_hex(16)
                digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
                db.execute('INSERT OR IGNORE INTO users(id,salt,digest,iterations) VALUES (?,?,?,?)', (uid, salt, digest,600000))

    def authenticate(self, uid, password):
        with self.connect() as db:
            user = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
        salt = user['salt'] if user else '0' * 32
        iterations = user['iterations'] if user else 600000
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), iterations).hex()
        valid = bool(user and hmac.compare_digest(user['digest'], digest))
        if valid and iterations < 600000:
            new_salt = secrets.token_hex(16)
            new_digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(new_salt), 600000).hex()
            with self.connect() as db:
                db.execute('UPDATE users SET salt=?,digest=?,iterations=? WHERE id=?',(new_salt,new_digest,600000,uid))
        return valid

    def transactions(self, uid):
        with self.connect() as db:
            return [dict(t) for t in db.execute('SELECT * FROM transactions WHERE customer_id=? ORDER BY posted_on,id', (uid,))]

    def subject(self, uid):
        return 'subject:' + hmac.new(self.audit_key, str(uid).encode(), hashlib.sha256).hexdigest()[:24]

    def consent(self, uid, policy):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO consent(subject,policy) VALUES (?,?)', (self.subject(uid),policy))

    def goals(self, uid, include_archived=False):
        with self.connect() as db:
            return [dict(g) for g in db.execute('SELECT * FROM goals WHERE customer_id=? AND (archived=0 OR ?=1) ORDER BY due_on,id', (uid,int(include_archived)))]

    def goal(self, uid, ident):
        with self.connect() as db:
            row = db.execute('SELECT * FROM goals WHERE customer_id=? AND id=?',(uid,ident)).fetchone()
        if not row:
            from .security import NotFoundError
            raise NotFoundError('Goal not found.')
        return dict(row)

    def save_goal(self, uid, name, target, saved, due, ident=None, version=None, archived=None):
        from .security import ConflictError, NotFoundError, ValidationError
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = None
            if ident:
                current = db.execute('SELECT * FROM goals WHERE id=? AND customer_id=?',(ident,uid)).fetchone()
                if not current:
                    raise NotFoundError('Goal not found.')
                if current['version'] != version:
                    raise ConflictError('This goal changed in another tab. Refresh and review it again.')
                if archived is None and current['archived']:
                    raise ConflictError('Restore this goal before editing it.')
            active = int(archived if archived is not None else (current['archived'] if current else 0)) == 0
            if active:
                candidates = db.execute('SELECT id,name FROM goals WHERE customer_id=? AND archived=0 AND id!=?',(uid,ident or '')).fetchall()
                duplicate = any(' '.join(row['name'].split()).casefold() == name.casefold() for row in candidates)
                if duplicate:
                    raise ValidationError({'name':'You already have an active goal with this name.'})
                count = db.execute('SELECT count(*) FROM goals WHERE customer_id=? AND archived=0 AND id!=?',(uid,ident or '')).fetchone()[0]
                if count >= 20:
                    raise ValidationError({'name':'You can keep up to 20 active goals. Archive a goal first.'})
            action = 'goal_created'
            if current:
                next_archived = int(archived if archived is not None else current['archived'])
                db.execute("UPDATE goals SET name=?,target_paise=?,saved_paise=?,due_on=?,archived=?,version=version+1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=? AND customer_id=?",(name,target,saved,due,next_archived,ident,uid))
                action = ('goal_archived' if next_archived else 'goal_restored') if archived is not None else 'goal_updated'
            else:
                ident = secrets.token_hex(8)
                db.execute("INSERT INTO goals(id,customer_id,name,target_paise,saved_paise,due_on,created_at,updated_at) VALUES(?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'),strftime('%Y-%m-%dT%H:%M:%fZ','now'))",(ident,uid,name,target,saved,due))
            db.execute('INSERT INTO audit(customer_id,action,metadata) VALUES (?,?,?)',(self.subject(uid),action,json.dumps({'goal_id':ident,'version':(version+1 if current else 1)})))
        return ident

    def topic(self, uid, value=None):
        with self.connect() as db:
            if value is not None:
                db.execute('INSERT OR REPLACE INTO context VALUES (?,?)', (uid, value))
            row = db.execute('SELECT topic FROM context WHERE customer_id=?', (uid,)).fetchone()
        return row['topic'] if row else 'summary'

    def audit(self, uid, action, metadata):
        # No raw chat, passwords, tokens, customer names, or narrations in audit.
        with self.connect() as db:
            db.execute('INSERT INTO audit(customer_id,action,metadata) VALUES (?,?,?)',
                       (self.subject(uid), action, json.dumps(metadata, sort_keys=True)))
