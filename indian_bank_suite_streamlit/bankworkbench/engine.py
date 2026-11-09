import copy
import hashlib
import json
import re
from datetime import date,datetime,timedelta
from decimal import Decimal
from pathlib import Path
from pfm.adapter import money,paise
from pfm.security import ValidationError,ConflictError,NotFoundError,check_text
from .fixtures import MODULES,PERSONAS,SCENARIOS,template

ROOT=Path(__file__).resolve().parent.parent


def finding(code,severity,title,detail,evidence):
 return {'code':code,'severity':severity,'title':title,'detail':detail,'evidence':evidence}


class WorkEngine:
 def __init__(self,store,as_of='2026-11-06T12:00:00'):
  self.store=store;self.as_of=datetime.fromisoformat(as_of)
  self.policy=json.loads((ROOT/'data/workbench/policy.json').read_text())

 def profile(self,uid):
  if uid not in PERSONAS:raise NotFoundError('Persona not found.')
  return {'id':uid,'name':PERSONAS[uid]['name'],'role':PERSONAS[uid]['role'],'modules':PERSONAS[uid]['modules']}

 def evidence_ids(self,p):
  result=[d['id'] for d in p.get('documents',[])]
  for key in ('transactions','title_chain','comparables','history'):result += [r['id'] for r in p.get(key,[])]
  return result

 def analyze(self,case):
  p=case['payload'];m=case['module'];findings=[];metrics=[];draft='';graph=[];details=[]
  ids=self.evidence_ids(p)
  if m=='onboarding':
   kinds={d['type'] for d in p['documents']}
   for kind in ('IDENTITY','ADDRESS','APPLICATION'):
    if kind not in kinds:findings.append(finding('MISSING_'+kind,'blocker','Missing '+kind.lower()+' evidence','Add the approved verification result before a CBS handoff can be prepared.',[]))
   for d in p['documents']:
    fields=d['fields'];details.append({'reference':d['id'],'subject':d['type'],'value':' · '.join(k.replace('_',' ').title()+': '+str(v) for k,v in fields.items())})
    if fields.get('applicant_alias')!=p['applicant']:findings.append(finding('ALIAS_MISMATCH','blocker','Cross-document alias mismatch','Application and source document identify different synthetic applicants.',[d['id'],'KYC-FORM-01']))
    if d['status']!='SIMULATED_VERIFIED':findings.append(finding('UNVERIFIED','blocker','Unverified fixture','Verification status is incomplete.',[d['id']]))
   if not p['consent']:findings.append(finding('CONSENT','blocker','Intake consent missing','No verification/activation preparation is allowed without recorded consent.',[]))
   if p['screening']!='SIMULATED_CLEAR':findings.append(finding('SCREENING','blocker','Screening review required','External screening is represented by a synthetic status only.',[]))
   metrics=[('Product',p['product']),('Evidence items',str(len(p['documents']))),('Applicant',p['applicant']),('CBS connection','Not connected')]
   draft=f"Application {case['id']} for {p['applicant']}, product {p['product']}. "
   draft+=f"{len(p['documents'])} synthetic evidence items assessed; {len(findings)} exceptions. "
   draft+='Request package only: account creation, CPV and activation require Bank-approved interfaces and authorization.'
  elif m=='property':
   chain=sorted(p['title_chain'],key=lambda r:r['date'])
   for i,row in enumerate(chain):
    details.append({'reference':row['id'],'subject':row['date'],'value':row['from']+' → '+row['to']})
    if i and row['from']!=chain[i-1]['to']:findings.append(finding('TITLE_GAP','blocker','Title continuity gap','Transferor does not match the preceding recorded transferee.',[chain[i-1]['id'],row['id']]))
   if not chain or chain[-1]['to']!=p['owner']:findings.append(finding('OWNER_MISMATCH','blocker','Current-owner reconciliation required','The declared owner does not match the final title entry.',[r['id'] for r in chain]))
   values=sorted(paise(r['value']) for r in p['comparables']);median=values[len(values)//2]
   declared=paise(p['declared_value']);variance=(Decimal(declared-median)/median*100).quantize(Decimal('.01'))
   if abs(variance)>Decimal(self.policy['property_variance_pct']):findings.append(finding('VALUATION','review','Valuation variance exceeds demo threshold',f'Declared value differs by {variance}% from the synthetic median. This is not a market valuation.',[r['id'] for r in p['comparables']]))
   for key in ('registry_status','litigation_status'):
    if p[key]!='SIMULATED_CLEAR':findings.append(finding(key.upper(),'blocker','Search result remains pending','Independent legal/registry investigation is required. No clearance is established.',['EC-01']))
   metrics=[('Declared value','INR '+money(declared)),('Comparable median','INR '+money(median)),('Variance',str(variance)+'%'),('Title entries',str(len(chain)))]
   draft=f"Property {p['property']}: {len(chain)} title entries reconstructed. Declared INR {money(declared)}; synthetic comparable median INR {money(median)}; variance {variance}%. "
   draft+='Review findings: '+('; '.join(f['title'] for f in findings) or 'No configured fixture inconsistencies detected')+'. '
   draft+='This report records evidence and gaps; it is not title certification, valuation advice or a lending decision.'
  elif m=='leads':
   consent=p['consent'] and not p['dnc'] and date.fromisoformat(p['consent_expires'])>=self.as_of.date()
   factors=[('Callback requested',30 if p['requested_callback'] else 0),('Recent engagement',min(30,p['engagements_7d']*10)),('Need confirmed',30 if p['need_confirmed'] else 0),('Recent contact',10 if p['days_since_contact']<=7 else 0)]
   score=sum(v for _,v in factors)
   if not consent:findings.append(finding('CONSENT_SUPPRESSED','blocker','Contact suppressed','Consent is missing, expired or do-not-contact is active. No outreach draft or handoff is permitted.',['CONSENT-DEMO-01']))
   if p['days_since_contact']>30:findings.append(finding('DORMANT','review','Dormant prospect','Review contact permission and relevance before planning engagement.',['ENG-01']))
   if score<self.policy['lead_handoff_score']:findings.append(finding('LOW_PRIORITY','review','Below demo handoff threshold','Rule score is below the demo threshold; retain for qualification rather than automatic RM handoff.',['ENG-01']))
   metrics=[('Rule score',str(score)+'/100'),('Contact permission','Allowed by fixture' if consent else 'Suppressed'),('Preferred channel',p['channel']),('Product interest',p['product'])]
   details=[{'reference':'SCORE-'+str(i+1),'subject':label,'value':str(points)+' points'} for i,(label,points) in enumerate(factors)]
   draft=(f"Draft only — {p['channel']}: Hello {p['prospect']}, you asked for information about {p['product'].lower().replace('_',' ')} options. An authorised relationship manager can explain current terms, eligibility and suitability. No rate or benefit is promised." if consent else 'No engagement draft: contact is suppressed by the synthetic consent record.')
   for h in p['history']:details.append({'reference':h['id'],'subject':h['date'],'value':h['event']})
  elif m=='grievance':
   description=p['description'].lower();category='Payments' if any(w in description for w in ('upi','payment')) else 'ATM / card' if any(w in description for w in ('atm','card')) else 'Service'
   urgent=p['vulnerable_support'] or p['regulatory_exception'] or 'urgent' in description
   hours=self.policy['grievance_target_hours']['urgent' if urgent else 'standard'];due=datetime.fromisoformat(p['reported_at'])+timedelta(hours=hours)
   potential=[]
   for other in self.store.cases(['grievance']):
    if other['id']!=case['id'] and other['payload']['customer']==p['customer'] and other['payload']['amount']==p['amount'] and other['payload']['description'].casefold()==p['description'].casefold():potential.append(other['id'])
   if potential or p['related_case']:findings.append(finding('POSSIBLE_DUPLICATE','review','Possible related complaint','Link and investigate; do not silently reject or close repeated complaints.',['ACK-01']+potential))
   if urgent:findings.append(finding('HUMAN_ESCALATION','blocker','Human exception review required','Vulnerability or policy/regulatory exception flag requires accountable human handling.',['ACK-01']))
   if p['transaction_status']!='SIMULATED_REVERSAL_CONFIRMED':findings.append(finding('PAYMENT_PENDING','blocker','Transaction outcome not confirmed','A complaint must not be closed as reversed while evidence is pending.',['PAY-01']))
   if self.as_of>due:findings.append(finding('DEMO_TARGET_OVERDUE','review','Demo service target exceeded','Escalate against the configurable demonstration clock; this is not a statutory deadline.',['ACK-01']))
   metrics=[('Classification',category),('Priority','Urgent' if urgent else 'Standard'),('Demo target',due.isoformat(timespec='minutes')),('Disputed amount','INR '+money(paise(p['amount'])))]
   details=[{'reference':'PAY-01','subject':'Verification outcome','value':p['transaction_status']},{'reference':'ACK-01','subject':'Intake statement','value':p['description']}]
   draft=(f"Complaint {case['id']}: {category}; disputed INR {p['amount']}. "
    +('Synthetic payment trace records a confirmed reversal. A reviewer must validate the evidence and customer-facing resolution before internal closure.' if p['transaction_status']=='SIMULATED_REVERSAL_CONFIRMED' else 'Payment outcome remains pending. Escalate for investigation; do not state that a refund was completed.')
    +' No real refund, customer message or grievance closure has been sent to Bank systems.')
  elif m=='str':
   txs=sorted(p['transactions'],key=lambda r:r['at']);large=paise(self.policy['str_large_amount_inr']);window=timedelta(hours=self.policy['str_window_hours']);ratio=Decimal(self.policy['str_pass_through_pct'])/100
   for t in txs:
    if paise(t['amount'])>=large:findings.append(finding('LARGE_DEMO_AMOUNT','review','Amount exceeds demo triage threshold','Threshold is arbitrary demonstration configuration, not a reporting rule.',[t['id']]))
   for incoming in txs:
    outgoing=[t for t in txs if t['from']==incoming['to'] and datetime.fromisoformat(incoming['at'])<=datetime.fromisoformat(t['at'])<=datetime.fromisoformat(incoming['at'])+window and t['id']!=incoming['id']]
    total=sum(paise(t['amount']) for t in outgoing)
    if outgoing and total>=Decimal(paise(incoming['amount']))*ratio:
     findings.append(finding('PASS_THROUGH','review','Rapid onward movement in fixture',f'Outgoing transactions total INR {money(total)} within the configured window. This is an investigation signal, not proof of wrongdoing.',[incoming['id']]+[t['id'] for t in outgoing]))
   # Bounded, time-ordered cycle tracing; fixtures and approved synthetic intakes have at most 40 edges.
   cycles=[]
   def walk(start,node,path,last_time):
    if len(path)>=6:return
    for edge in txs:
     if edge['from']!=node or edge['id'] in path or edge['at']<last_time:continue
     new=path+[edge['id']]
     if edge['to']==start and len(new)>1:cycles.append(new)
     else:walk(start,edge['to'],new,edge['at'])
   for start in {t['from'] for t in txs}:walk(start,start,[],'')
   if cycles:findings.append(finding('CIRCULAR_PATH','review','Time-ordered circular path identified','A chain returns to an earlier entity. Investigators must validate context and source coverage.',cycles[0]))
   total=sum(paise(t['amount']) for t in txs);nodes=sorted({t[k] for t in txs for k in ('from','to')})
   metrics=[('Transactions',str(len(txs))),('Gross edge volume','INR '+money(total)),('Entities',str(len(nodes))),('Filing authority','Not available in demo')]
   graph=[{'id':t['id'],'from':t['from'],'to':t['to'],'label':'INR '+t['amount'],'at':t['at']} for t in txs]
   details=[{'reference':t['id'],'subject':t['at'],'value':t['from']+' → '+t['to']+' | INR '+t['amount']} for t in txs]
   draft=f"INTERNAL DRAFT — NOT FILED. Alert {p['alert']}, case {case['id']}. {len(txs)} synthetic transaction edges across {len(nodes)} entities, gross edge volume INR {money(total)} (may count the same funds more than once). "
   draft+='Observed configured signals: '+(', '.join(sorted({f['title'] for f in findings})) or 'none')+'. '
   draft+='Sources: '+', '.join(t['id'] for t in txs)+'. No conclusion of criminality is drawn. Source completeness, customer context and investigator rationale require independent compliance review. No regulatory format or submission is asserted.'
  return {'findings':findings,'metrics':[{'label':a,'value':b} for a,b in metrics], 'details':details,'draft':draft,'graph':graph,
   'blockers':sum(f['severity']=='blocker' for f in findings),'evidence_ids':ids,
   'policy_version':self.policy['policy_version'],'as_of':self.as_of.isoformat(),'method':'Deterministic fixture analysis; no trained model, OCR or external verification.'}

 def specs(self,module):
  reviewer='rm' if module=='leads' else 'compliance' if module=='str' else 'checker'
  prepare={'onboarding':'Prepare CBS handoff package','property':'Prepare findings report','leads':'Prepare engagement draft','grievance':'Prepare investigation / resolution draft','str':'Prepare investigation narrative'}[module]
  approve={'onboarding':'Review handoff readiness','property':'Sign off findings review','leads':'Accept RM handoff','grievance':'Approve internal resolution','str':'Review internal STR draft'}[module]
  result={
   'prepare':{'label':prepare,'roles':['maker'],'states':['NEW','RETURNED']},
   'request_review':{'label':'Submit for independent review','roles':['maker'],'states':['PREPARED']},
   'approve':{'label':approve,'roles':[reviewer],'states':['PENDING_REVIEW']},
   'return':{'label':'Return for correction','roles':[reviewer],'states':['PENDING_REVIEW']},
   'add_note':{'label':'Add evidence-backed note','roles':['maker',reviewer],'states':['*']}}
  if module in ('onboarding','property','grievance'):
   result['correct_fixture']={'label':'Load corrected synthetic evidence','roles':['maker'],'states':['NEW','RETURNED']}
  if module=='leads':result['withdraw_consent']={'label':'Record consent withdrawal / suppress','roles':['maker','rm'],'states':['NEW','PREPARED','PENDING_REVIEW','RETURNED','HANDOFF_ACCEPTED']}
  if module=='grievance':
   result['escalate']={'label':'Escalate for exception review','roles':['maker'],'states':['NEW','PREPARED','PENDING_REVIEW','RETURNED']}
   result['review_escalation']={'label':'Record exception review','roles':['checker'],'states':['ESCALATED']}
  return result

 def guard(self,case,uid,action):
  profile=self.profile(uid);spec=self.specs(case['module']).get(action)
  if not spec:raise ValidationError({'action':'Unknown workflow action.'})
  if profile['role'] not in spec['roles']:raise ConflictError('This action requires the designated independent reviewer or operational role.')
  if '*' not in spec['states'] and case['state'] not in spec['states']:raise ConflictError('This action is not available in the current case state.')
  a=self.analyze(case);m=case['module'];p=case['payload']
  if action in ('approve','return','review_escalation') and case['requested_by']==uid:raise ConflictError('The preparer cannot independently review the same case.')
  if action=='correct_fixture' and ((m=='grievance' and (p['regulatory_exception'] or p['vulnerable_support'])) or (m=='onboarding' and not p['consent'])):
   raise ConflictError('Consent and human-exception flags cannot be bypassed by replacing a fixture.')
  if m=='onboarding' and action in ('prepare','request_review','approve') and a['blockers']:raise ConflictError('Resolve document/consent exceptions before handoff readiness can advance.')
  if m=='leads' and action in ('prepare','request_review','approve'):
   if any(f['code']=='CONSENT_SUPPRESSED' for f in a['findings']):raise ConflictError('Contact is suppressed. Consent cannot be bypassed.')
   if action in ('request_review','approve') and any(f['code']=='LOW_PRIORITY' for f in a['findings']):raise ConflictError('Below the demo qualification threshold; no automatic RM handoff.')
  if m=='grievance' and action=='approve' and a['blockers']:raise ConflictError('Unconfirmed payment or exception cases require escalation, not resolution closure.')
  return spec,a

 def available(self,case,uid):
  result=[]
  for action,spec in self.specs(case['module']).items():
   try:self.guard(case,uid,action);allowed=True;why=''
   except (ValueError,ConflictError) as e:allowed=False;why=str(e)
   result.append({'id':action,'label':spec['label'],'enabled':allowed,'why':why,'roles':spec['roles']})
  return result

 def board(self,uid):
  profile=self.profile(uid);cases=self.store.cases(profile['modules']);rows=[]
  for c in cases:
   a=self.analyze(c)
   rows.append({k:c[k] for k in ('id','module','title','state','version','updated_at')}|{'blockers':a['blockers'],'findings':len(a['findings']),'evidence_count':len(a['evidence_ids'])})
  return {'profile':profile,'modules':{m:MODULES[m] for m in profile['modules']},'cases':rows,'scenarios':{m:SCENARIOS[m] for m in profile['modules']},'as_of':self.as_of.isoformat(),'policy':self.policy,'demo':True}

 def detail(self,uid,ident):
  c=self.store.case(ident,self.profile(uid)['modules']);a=self.analyze(c)
  public={k:c[k] for k in ('id','module','title','state','version','updated_at')}
  return {'case':public,'facts':{k:v for k,v in c['payload'].items() if k not in ('documents','title_chain','comparables','transactions','history')},'analysis':a,'documents':c['payload'].get('documents',[]),'actions':self.available(c,uid),'events':self.store.events(ident),
   'connector':{'status':'NOT_CONNECTED','message':'Bank-approved integration required. No live verification, account creation, outreach, refund or STR filing is available.'}}

 def validate_create(self,uid,data):
  profile=self.profile(uid)
  if profile['role']!='maker':raise ConflictError('New intakes require the Operations analyst persona.')
  m=data.get('module');scenario=data.get('scenario')
  if m not in profile['modules'] or scenario not in SCENARIOS.get(m,{}):raise ValidationError({'scenario':'Choose an available synthetic scenario.'})
  title=check_text(data.get('title'),'title',80,name=True)
  reason=check_text(data.get('reason'),'reason',1200)
  if len(reason)<12:raise ValidationError({'reason':'Provide at least 12 characters of operational rationale.'})
  return {'module':m,'scenario':scenario,'title':title,'reason':reason}

 def create(self,uid,draft):
  v=self.validate_create(uid,draft)
  return self.store.create(v['module'],v['title'],template(v['module'],v['scenario']),uid,self.profile(uid)['role'],v['reason'])

 def validate_action(self,uid,data):
  c=self.store.case(data.get('id'),self.profile(uid)['modules'])
  version=data.get('version')
  if type(version) is not int or version<1:raise ValidationError({'version':'Refresh the case before acting.'})
  if c['version']!=version:raise ConflictError('This case changed. Refresh and review again.')
  action=data.get('action');spec,a=self.guard(c,uid,action)
  reason=check_text(data.get('reason'),'reason',1200)
  if len(reason)<20:raise ValidationError({'reason':'Provide at least 20 characters of review rationale.'})
  evidence=data.get('evidence')
  if not isinstance(evidence,list) or not evidence or len(evidence)>20 or any(not isinstance(x,str) or x not in a['evidence_ids'] for x in evidence):raise ValidationError({'evidence':'Select 1–20 actual evidence references from this case.'})
  return {'id':c['id'],'version':version,'action':action,'reason':reason,'evidence':list(dict.fromkeys(evidence)),'label':spec['label']}

 def commit(self,uid,draft):
  v=self.validate_action(uid,draft);profile=self.profile(uid)
  def transition(c):
   self.guard(c,uid,v['action']);p=copy.deepcopy(c['payload']);state=c['state'];requested=c['requested_by'];action=v['action']
   if action=='prepare':state='PREPARED'
   elif action=='request_review':state='PENDING_REVIEW';requested=uid
   elif action=='return':state='RETURNED';requested=None
   elif action=='approve':state={'onboarding':'READY_FOR_CBS_INTEGRATION','property':'FINDINGS_REVIEWED','leads':'HANDOFF_ACCEPTED','grievance':'INTERNAL_RESOLUTION_REVIEWED','str':'DRAFT_REVIEWED_NOT_FILED'}[c['module']]
   elif action=='correct_fixture':
    replacement=template(c['module'],'standard');replacement['correction_notice']='Synthetic replacement fixture only; no external source was contacted.';p=replacement;state='NEW';requested=None
   elif action=='withdraw_consent':p['consent']=False;p['dnc']=True;state='CONTACT_SUPPRESSED';requested=None
   elif action=='escalate':state='ESCALATED';requested=uid
   elif action=='review_escalation':state='EXCEPTION_REVIEWED';p['exception_review']='Independent demo review recorded; no real complaint closure.'
   return {'state':state,'payload':p,'requested_by':requested}
  return self.store.mutate(v['id'],v['version'],uid,profile['role'],v['action'],v['reason'],v['evidence'],transition,profile['modules'])

 def report(self,uid,ident):
  detail=self.detail(uid,ident)
  content={'classification':'SYNTHETIC_DEMO_ONLY','artifact':'Internal decision-support report, not external submission','source':detail,'payload_versions':self.store.versions(ident),'notice':'No regulatory format, legal title clearance, credit approval or live bank action is certified.'}
  content['content_sha256']=hashlib.sha256(json.dumps(content,sort_keys=True).encode()).hexdigest()
  return content
