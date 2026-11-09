"""Loopback synthetic-data application. Customer deployment requires Bank infrastructure."""
import hmac
import json
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .adapter import money
from .security import (POLICY_VERSION, ConflictError, NotFoundError, ValidationError,
                       masked, redact, strict_fields)

ROOT = Path(__file__).resolve().parent.parent


def customer_view(data):
    """Whitelist outbound data; never expose source account/customer fields."""
    data = dict(data)
    data['customer_label'] = 'Demo customer ' + masked(data.pop('customer_id'))
    for collection in ('goals','archived_goals'):
        data[collection] = [{k:v for k,v in g.items() if k not in ('customer_id','target_paise','saved_paise')} for g in data[collection]]
    fields = {'id','posted_on','direction','amount','merchant','kind','category','reason'}
    data['transactions'] = [{k:(redact(v) if isinstance(v,str) else v) for k,v in t.items() if k in fields} for t in data['transactions']]
    data['recurring'] = [{**r,'merchant':redact(r['merchant'])} for r in data['recurring']]
    return data


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, port, engine, disabled_path):
        super().__init__(('127.0.0.1', port), Handler)
        self.engine, self.disabled_path = engine, Path(disabled_path)
        self.sessions, self.attempts, self.reviews = {}, {}, {}
        self.lock = threading.Lock()
        self.idle_seconds, self.absolute_seconds = 600, 1800


class Handler(BaseHTTPRequestHandler):
    server_version = 'PFMLocal/2'

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, fmt, *args):
        pass  # no chat, identities, query strings, financial records or secrets in access logs

    def response(self, status, data, content_type='application/json; charset=utf-8', cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode() if isinstance(data,(dict,list)) else data
        self.send_response(status)
        for name,value in {
            'Content-Type':content_type,'Content-Length':str(len(body)),
            'Cache-Control':'no-store, max-age=0','Pragma':'no-cache',
            'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
            'Referrer-Policy':'no-referrer',
            'Permissions-Policy':'camera=(), microphone=(), geolocation=(), payment=()',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"
        }.items():
            self.send_header(name,value)
        if cookie:
            self.send_header('Set-Cookie',cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self): self.handle_request(False)
    def do_POST(self): self.handle_request(True)
    def do_PUT(self): self.response(405,{'error':'Use the review and confirmation workflow.'})
    do_DELETE = do_PUT
    do_PATCH = do_PUT

    def handle_request(self, post):
        try:
            port = self.server.server_port
            if self.headers.get('Host') not in (f'127.0.0.1:{port}',f'localhost:{port}'):
                self.response(403,{'error':'Invalid local host.'}); return
            path_parts = urlsplit(self.path)
            path, params = path_parts.path, parse_qs(path_parts.query,max_num_fields=10)
            if not post and path in ('/','/app.js','/style.css'):
                name,mime = {'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}[path]
                self.response(200,(ROOT/'web'/name).read_bytes(),mime); return
            if self.server.disabled_path.exists():
                self.response(503,{'error':'Service paused. Please try again later.'}); return
            data = {}
            if post:
                if self.headers.get('X-PFM-Request') != '1':
                    self.response(403,{'error':'Missing request guard.'}); return
                origin = self.headers.get('Origin')
                if origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
                    self.response(403,{'error':'Cross-origin request denied.'}); return
                if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                    self.response(403,{'error':'Cross-site request denied.'}); return
                if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[])) != 1:
                    raise ValueError()
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    raise ValueError()
                length = int(self.headers.get('Content-Length','0'))
                if not 1 <= length <= 8192: raise ValueError()
                # Reject duplicate JSON keys instead of silently accepting conflicting values.
                def pairs(items):
                    result = {}
                    for k,v in items:
                        if k in result: raise ValueError()
                        result[k] = v
                    return result
                data = json.loads(self.rfile.read(length),object_pairs_hook=pairs)
                if not isinstance(data,dict): raise ValueError()
            now = time.monotonic()
            if post and path == '/api/login':
                strict_fields(data,('customer_id','password','privacy_ack'),('customer_id','password','privacy_ack'))
                uid,password = data['customer_id'],data['password']
                if not isinstance(uid,str) or not isinstance(password,str) or len(uid)>64 or len(password)>128:
                    raise ValueError()
                if data['privacy_ack'] is not True:
                    raise ValidationError({'privacy_ack':'Please acknowledge the demo data and privacy notice.'})
                with self.server.lock:
                    attempts = [t for t in self.server.attempts.get(self.client_address[0],[]) if now-t<60]
                    self.server.attempts[self.client_address[0]] = attempts
                    if len(attempts)>=10:
                        self.response(429,{'error':'Too many sign-in attempts. Wait one minute.'}); return
                    attempts.append(now)
                if not self.server.engine.store.authenticate(uid,password):
                    self.response(401,{'error':'The customer ID or password is incorrect.'}); return
                sid, csrf = secrets.token_urlsafe(32),secrets.token_urlsafe(32)
                with self.server.lock:
                    # One active local session per customer; successful re-login revokes the previous one.
                    self.server.sessions = {k:v for k,v in self.server.sessions.items() if v['uid']!=uid and v['expires']>now and now-v['last']<self.server.idle_seconds}
                    self.server.sessions[sid] = {'uid':uid,'csrf':csrf,'expires':now+self.server.absolute_seconds,'last':now,'requests':[]}
                self.server.engine.store.consent(uid,POLICY_VERSION)
                self.server.engine.store.audit(uid,'login',{'policy':POLICY_VERSION})
                self.response(200,{'csrf':csrf,'customer_label':'Demo customer '+masked(uid),
                    'expires_in':1800,'idle_timeout':600,'policy':POLICY_VERSION},
                    cookie=f'pfm_session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=1800')
                return
            cookies = SimpleCookie()
            cookies.load(self.headers.get('Cookie',''))
            sid = cookies['pfm_session'].value if 'pfm_session' in cookies else ''
            with self.server.lock:
                session = self.server.sessions.get(sid)
                if session and (session['expires']<=now or now-session['last']>=self.server.idle_seconds):
                    self.server.sessions.pop(sid,None); session = None
                if session:
                    session['last'] = now
                    session['requests'] = [t for t in session['requests'] if now-t<60]
                    if len(session['requests'])>=120:
                        self.response(429,{'error':'Too many requests. Wait a moment and try again.'}); return
                    session['requests'].append(now)
            if not session:
                self.response(401,{'error':'Your session has ended. Please sign in again.'},cookie='pfm_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'); return
            uid = session['uid']
            if post and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']):
                self.response(403,{'error':'Session verification failed. Sign in again.'}); return
            if post and path == '/api/logout':
                strict_fields(data,())
                with self.server.lock:
                    self.server.sessions.pop(sid,None)
                    self.server.reviews = {k:v for k,v in self.server.reviews.items() if v['sid']!=sid}
                self.server.engine.store.audit(uid,'logout',{})
                self.response(200,{'ok':True},cookie='pfm_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            elif not post and path == '/api/dashboard':
                self.response(200,customer_view(self.server.engine.dashboard(uid,params.get('month',['2026-10'])[0])))
            elif post and path == '/api/chat':
                strict_fields(data,('message','month'),('message','month'))
                self.response(200,self.server.engine.chat(uid,data['message'],data['month']))
            elif post and path == '/api/goals/review':
                strict_fields(data,('action','id','version','name','target','saved','due_on'),('action',))
                action = data['action']
                if action not in ('create','edit','archive','restore'):
                    raise ValueError()
                ident,version = data.get('id'),data.get('version')
                if action != 'create':
                    if not isinstance(ident,str) or type(version) is not int or version<1: raise ValueError()
                    goal = self.server.engine.store.goal(uid,ident)
                    if goal['version']!=version: raise ConflictError('This goal changed. Refresh and review it again.')
                    if action=='edit' and goal['archived']: raise ConflictError('Restore this goal before editing it.')
                elif ident is not None or version is not None:
                    raise ValueError()
                if action in ('create','edit'):
                    draft = self.server.engine.validate_goal(uid,data.get('name'),data.get('target'),data.get('saved'),data.get('due_on'),ident)
                else:
                    if set(data)-{'action','id','version'}: raise ValueError()
                    draft = {'name':redact(goal['name']),'target':money(goal['target_paise']),'saved':money(goal['saved_paise']),'due_on':goal['due_on']}
                review = secrets.token_urlsafe(24)
                with self.server.lock:
                    self.server.reviews = {k:v for k,v in self.server.reviews.items() if v['expires']>now}
                    if sum(v['sid']==sid for v in self.server.reviews.values())>=20:
                        self.response(429,{'error':'Too many pending reviews. Wait five minutes.'}); return
                    self.server.reviews[review] = {'sid':sid,'uid':uid,'action':action,'id':ident,'version':version,'draft':draft,'expires':now+300}
                self.response(200,{'review_id':review,'action':action,'draft':draft,'expires_in':300})
            elif post and path == '/api/goals/confirm':
                strict_fields(data,('review_id',),('review_id',))
                if not isinstance(data['review_id'],str): raise ValueError()
                with self.server.lock:
                    review = self.server.reviews.get(data['review_id'])
                    if not review or review['sid']!=sid or review['expires']<=now:
                        raise ConflictError('This review expired or is unavailable. Review the goal again.')
                    self.server.reviews.pop(data['review_id'])
                action,draft = review['action'],review['draft']
                if action=='create':
                    ident = self.server.engine.add_goal(uid,draft['name'],draft['target'],draft['saved'],draft['due_on'])
                elif action=='edit':
                    ident = self.server.engine.edit_goal(uid,review['id'],review['version'],draft['name'],draft['target'],draft['saved'],draft['due_on'])
                else:
                    ident = self.server.engine.archive_goal(uid,review['id'],review['version'],action=='archive')
                self.response(201 if action=='create' else 200,{'goal_id':ident,'action':action})
            else:
                self.response(404,{'error':'This service is unavailable. Use the goal review workflow.'})
        except ValidationError as error:
            self.response(400,{'error':str(error),'fields':error.fields})
        except ConflictError as error:
            self.response(409,{'error':str(error)})
        except NotFoundError:
            self.response(404,{'error':'Goal not found.'})
        except (ValueError,TypeError,KeyError,OverflowError,UnicodeError):
            self.response(400,{'error':'Invalid request. Check the values and try again.'})
        except Exception:
            self.response(500,{'error':'Unable to complete this request. No success is confirmed; refresh before retrying.'})
