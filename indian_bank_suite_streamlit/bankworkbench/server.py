import hmac
import json
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from pfm.security import ValidationError,ConflictError,NotFoundError,strict_fields

ROOT=Path(__file__).resolve().parent.parent


class WorkServer(ThreadingHTTPServer):
 daemon_threads=True
 def __init__(self,port,engine):
  super().__init__(('127.0.0.1',port),Handler)
  self.engine=engine;self.sessions={};self.reviews={};self.attempts=[];self.lock=threading.Lock()
  self.disabled=engine.store.path.parent/'WORKBENCH_DISABLED'


class Handler(BaseHTTPRequestHandler):
 server_version='BankWorkbenchLocal/1'
 def log_message(self,*args):pass
 def setup(self):
  super().setup();self.connection.settimeout(10)
 def response(self,status,data,mime='application/json; charset=utf-8',cookie=None,download=None):
  body=json.dumps(data,ensure_ascii=False).encode() if isinstance(data,(dict,list)) else data
  self.send_response(status)
  headers={'Content-Type':mime,'Content-Length':str(len(body)),'Cache-Control':'no-store, max-age=0','Pragma':'no-cache','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer',
   'Permissions-Policy':'camera=(), microphone=(), geolocation=(), payment=()',
   'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}
  if cookie:headers['Set-Cookie']=cookie
  if download:headers['Content-Disposition']='attachment; filename="'+download+'"'
  for key,value in headers.items():self.send_header(key,value)
  self.end_headers();self.wfile.write(body)
 def do_GET(self):self.route(False)
 def do_POST(self):self.route(True)
 def do_PUT(self):self.response(405,{'error':'Use the reviewed workflow.'})
 do_DELETE=do_PUT;do_PATCH=do_PUT
 def route(self,post):
  try:
   port=self.server.server_port
   if self.headers.get('Host') not in (f'127.0.0.1:{port}',f'localhost:{port}'):
    self.response(403,{'error':'Invalid local host.'});return
   parsed=urlsplit(self.path);path=parsed.path;params=parse_qs(parsed.query,max_num_fields=10)
   if not post and path in ('/','/app.js','/style.css'):
    name,mime={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}[path]
    self.response(200,(ROOT/'workbench_web'/name).read_bytes(),mime);return
   if self.server.disabled.exists():self.response(503,{'error':'Workbench paused by local service control.'});return
   body={}
   if post:
    if self.headers.get('X-Workbench-Request')!='1':self.response(403,{'error':'Missing request guard.'});return
    origin=self.headers.get('Origin')
    if origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}') or self.headers.get('Sec-Fetch-Site')=='cross-site':
     self.response(403,{'error':'Cross-origin request denied.'});return
    if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[]))!=1 or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError()
    length=int(self.headers.get('Content-Length','0'))
    if not 1<=length<=16384:raise ValueError()
    def pairs(items):
     data={}
     for k,v in items:
      if k in data:raise ValueError()
      data[k]=v
     return data
    body=json.loads(self.rfile.read(length),object_pairs_hook=pairs)
    if not isinstance(body,dict):raise ValueError()
   now=time.monotonic()
   if post and path=='/api/login':
    strict_fields(body,('persona','password','privacy_ack'),('persona','password','privacy_ack'))
    uid,password=body['persona'],body['password']
    if not isinstance(uid,str) or not isinstance(password,str) or len(uid)>40 or len(password)>128:raise ValueError()
    if body['privacy_ack'] is not True:raise ValidationError({'privacy_ack':'Acknowledge the synthetic-data notice.'})
    with self.server.lock:
     self.server.attempts=[t for t in self.server.attempts if now-t<60]
     if len(self.server.attempts)>=10:self.response(429,{'error':'Too many sign-in attempts. Wait one minute.'});return
     self.server.attempts.append(now)
    if not self.server.engine.store.authenticate_staff(uid,password):self.response(401,{'error':'The persona or password is incorrect.'});return
    sid=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
    with self.server.lock:
     self.server.sessions={k:v for k,v in self.server.sessions.items() if v['uid']!=uid and v['expires']>now and now-v['last']<600}
     self.server.sessions[sid]={'uid':uid,'csrf':csrf,'expires':now+1800,'last':now,'requests':[]}
    self.server.engine.store.consent(uid,'workbench-privacy-1')
    self.server.engine.store.audit(uid,'staff_login',{'policy':'workbench-privacy-1'})
    self.response(200,{'csrf':csrf,'profile':self.server.engine.profile(uid),'idle_timeout':600,'expires_in':1800},cookie=f'workbench_session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=1800');return
   cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''));sid=cookies['workbench_session'].value if 'workbench_session'in cookies else ''
   with self.server.lock:
    session=self.server.sessions.get(sid)
    if session and (session['expires']<=now or now-session['last']>=600):self.server.sessions.pop(sid,None);session=None
    if session:
     session['last']=now;session['requests']=[t for t in session['requests'] if now-t<60]
     if len(session['requests'])>=120:self.response(429,{'error':'Too many requests. Wait a moment.'});return
     session['requests'].append(now)
   if not session:self.response(401,{'error':'Your session ended. Sign in again.'},cookie='workbench_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0');return
   uid=session['uid']
   if post and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session['csrf']):self.response(403,{'error':'Session verification failed.'});return
   if not post and path=='/api/board':self.response(200,self.server.engine.board(uid))
   elif not post and path=='/api/case':self.response(200,self.server.engine.detail(uid,params.get('id',[''])[0]))
   elif not post and path=='/api/report':
    report=self.server.engine.report(uid,params.get('id',[''])[0]);ident=report['source']['case']['id']
    self.server.engine.store.audit(uid,'report_download',{'case_id':ident})
    self.response(200,report,download=ident+'-internal-report.json')
   elif post and path=='/api/review':
    kind=body.get('kind')
    if kind=='create':
     strict_fields(body,('kind','module','scenario','title','reason'),('kind','module','scenario','title','reason'))
     draft=self.server.engine.validate_create(uid,{k:v for k,v in body.items() if k!='kind'})
     label='Create synthetic case'
    elif kind=='action':
     strict_fields(body,('kind','id','version','action','reason','evidence'),('kind','id','version','action','reason','evidence'))
     draft=self.server.engine.validate_action(uid,{k:v for k,v in body.items() if k!='kind'});label=draft['label']
    else:raise ValueError()
    token=secrets.token_urlsafe(24)
    with self.server.lock:
     self.server.reviews={k:v for k,v in self.server.reviews.items() if v['expires']>now and v['sid'] in self.server.sessions}
     if sum(v['sid']==sid for v in self.server.reviews.values())>=20:self.response(429,{'error':'Too many pending reviews. Wait five minutes.'});return
     self.server.reviews[token]={'sid':sid,'uid':uid,'kind':kind,'draft':draft,'expires':now+300}
    self.response(200,{'review_id':token,'kind':kind,'label':label,'draft':draft,'expires_in':300})
   elif post and path=='/api/confirm':
    strict_fields(body,('review_id',),('review_id',))
    if not isinstance(body['review_id'],str):raise ValueError()
    with self.server.lock:
     review=self.server.reviews.get(body['review_id'])
     if not review or review['sid']!=sid or review['expires']<=now:raise ConflictError('Review expired or unavailable. Review again.')
     self.server.reviews.pop(body['review_id'])
    ident=self.server.engine.create(uid,review['draft']) if review['kind']=='create' else self.server.engine.commit(uid,review['draft'])
    self.response(201 if review['kind']=='create' else 200,{'case_id':ident})
   elif post and path=='/api/logout':
    strict_fields(body,())
    with self.server.lock:
     self.server.sessions.pop(sid,None);self.server.reviews={k:v for k,v in self.server.reviews.items() if v['sid']!=sid}
    self.response(200,{'ok':True},cookie='workbench_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
   else:self.response(404,{'error':'Service not found.'})
  except ValidationError as e:self.response(400,{'error':str(e),'fields':e.fields})
  except ConflictError as e:self.response(409,{'error':str(e)})
  except NotFoundError:self.response(404,{'error':'Case not found.'})
  except (ValueError,TypeError,KeyError,OverflowError,UnicodeError):self.response(400,{'error':'Invalid request. Check the values.'})
  except Exception:self.response(500,{'error':'The operation could not be completed. Refresh before retrying; no success is confirmed.'})
