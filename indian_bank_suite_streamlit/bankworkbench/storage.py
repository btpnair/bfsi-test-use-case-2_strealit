import hashlib
import hmac
import json
import secrets
from datetime import datetime,timezone
from pfm.storage import Store
from pfm.security import ConflictError,NotFoundError
from .fixtures import PERSONAS,SCENARIOS,template


def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')


class WorkStore(Store):
 def __init__(self,path):
  super().__init__(path)
  with self.connect() as db:
   db.executescript('''
   CREATE TABLE IF NOT EXISTS staff(id TEXT PRIMARY KEY,salt TEXT,digest TEXT,role TEXT);
   CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,module TEXT,title TEXT,state TEXT,version INTEGER,payload TEXT,created_by TEXT,requested_by TEXT,updated_at TEXT);
   CREATE TABLE IF NOT EXISTS case_versions(case_id TEXT,version INTEGER,state TEXT,payload TEXT,at TEXT,PRIMARY KEY(case_id,version));
   CREATE TABLE IF NOT EXISTS case_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,case_id TEXT,at TEXT,subject TEXT,role TEXT,action TEXT,reason TEXT,evidence TEXT,version INTEGER);
   ''')

 def seed(self):
  with self.connect() as db:
   for uid,profile in PERSONAS.items():
    if not db.execute('SELECT 1 FROM staff WHERE id=?',(uid,)).fetchone():
     salt=secrets.token_hex(16);digest=hashlib.pbkdf2_hmac('sha256',profile['password'].encode(),bytes.fromhex(salt),600000).hex()
     db.execute('INSERT INTO staff VALUES(?,?,?,?)',(uid,salt,digest,profile['role']))
  for module,scenarios in SCENARIOS.items():
   for i,scenario in enumerate(scenarios):
    ident=f'{module.upper()}-DEMO-{i+1:03}'
    with self.connect() as db:
     if not db.execute('SELECT 1 FROM cases WHERE id=?',(ident,)).fetchone():
      self._insert(db,ident,module,scenarios[scenario],template(module,scenario),'operator','maker','Seeded fictional scenario')

 def _insert(self,db,ident,module,title,payload,uid,role,reason):
  db.execute('INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?)',(ident,module,title,'NEW',1,json.dumps(payload),uid,None,now()))
  db.execute('INSERT INTO case_versions VALUES(?,?,?,?,?)',(ident,1,'NEW',json.dumps(payload),now()))
  self._event(db,ident,uid,role,'case_created',reason,[])

 def authenticate_staff(self,uid,password):
  with self.connect() as db:row=db.execute('SELECT * FROM staff WHERE id=?',(uid,)).fetchone()
  salt=row['salt'] if row else '00'*16
  digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
  return bool(row and hmac.compare_digest(row['digest'],digest))

 def cases(self,modules):
  if not modules:return []
  with self.connect() as db:
   rows=db.execute('SELECT * FROM cases WHERE module IN ('+','.join('?' for _ in modules)+') ORDER BY updated_at DESC,id',tuple(modules)).fetchall()
  return [self.decode(r) for r in rows]

 def decode(self,row):
  result=dict(row);result['payload']=json.loads(result['payload']);return result

 def case(self,ident,modules):
  with self.connect() as db:row=db.execute('SELECT * FROM cases WHERE id=?',(ident,)).fetchone()
  if not row or row['module'] not in modules:raise NotFoundError('Case not found.')
  return self.decode(row)

 def events(self,ident):
  with self.connect() as db:
   return [dict(r) for r in db.execute('SELECT at,subject,role,action,reason,evidence,version FROM case_events WHERE case_id=? ORDER BY seq',(ident,))]

 def versions(self,ident):
  with self.connect() as db:return [{'version':r['version'],'state':r['state'],'at':r['at'],'payload':json.loads(r['payload'])} for r in db.execute('SELECT * FROM case_versions WHERE case_id=? ORDER BY version',(ident,))]

 def _event(self,db,ident,uid,role,action,reason,evidence):
  version=db.execute('SELECT version FROM cases WHERE id=?',(ident,)).fetchone()[0]
  db.execute('INSERT INTO case_events(case_id,at,subject,role,action,reason,evidence,version) VALUES(?,?,?,?,?,?,?,?)',(ident,now(),self.subject(uid),role,action,reason,json.dumps(evidence),version))
  db.execute('INSERT INTO audit(customer_id,action,metadata) VALUES(?,?,?)',(self.subject(uid),action,json.dumps({'case_id':ident,'evidence_count':len(evidence)})))

 def create(self,module,title,payload,uid,role,reason):
  ident=module.upper()+'-'+secrets.token_hex(5).upper()
  with self.connect() as db:
   db.execute('BEGIN IMMEDIATE')
   count=db.execute('SELECT count(*) FROM cases WHERE module=?',(module,)).fetchone()[0]
   if count>=200:raise ConflictError('Demo case limit reached for this module.')
   self._insert(db,ident,module,title,payload,uid,role,reason)
  return ident

 def mutate(self,ident,version,uid,role,action,reason,evidence,fn,modules):
  # Read, authorize and recalculate business rules under the same write transaction.
  with self.connect() as db:
   db.execute('BEGIN IMMEDIATE')
   row=db.execute('SELECT * FROM cases WHERE id=?',(ident,)).fetchone()
   if not row or row['module'] not in modules:raise NotFoundError('Case not found.')
   case=self.decode(row)
   if case['version']!=version:raise ConflictError('This case changed. Refresh and review again.')
   changes=fn(case)
   db.execute('UPDATE cases SET state=?,payload=?,requested_by=?,version=version+1,updated_at=? WHERE id=?',
    (changes['state'],json.dumps(changes['payload']),changes['requested_by'],now(),ident))
   db.execute('INSERT INTO case_versions VALUES(?,?,?,?,?)',(ident,version+1,changes['state'],json.dumps(changes['payload']),now()))
   self._event(db,ident,uid,role,action,reason,evidence)
  return ident
