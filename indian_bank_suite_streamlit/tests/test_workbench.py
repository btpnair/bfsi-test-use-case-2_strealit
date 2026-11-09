import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from bankworkbench.engine import WorkEngine
from bankworkbench.fixtures import MODULES,PERSONAS,template
from bankworkbench.server import WorkServer
from bankworkbench.storage import WorkStore
from pfm.security import ConflictError,NotFoundError,ValidationError


class WorkFixture(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.base=tempfile.TemporaryDirectory()
  cls.base_path=Path(cls.base.name)/'base.sqlite3'
  store=WorkStore(cls.base_path);store.seed()
 @classmethod
 def tearDownClass(cls):cls.base.cleanup()
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  path=Path(self.temp.name)/'workbench.sqlite3'
  shutil.copyfile(self.base_path,path);shutil.copyfile(self.base_path.with_suffix('.audit-key'),path.with_suffix('.audit-key'))
  self.store=WorkStore(path);self.engine=WorkEngine(self.store)
 def case(self,module='onboarding',index=1):return self.store.case(f'{module.upper()}-DEMO-{index:03}',list(MODULES))
 def draft(self,case,action,uid='operator',reason='Reviewed the cited synthetic evidence and documented the proposed action.'):
  return self.engine.validate_action(uid,{'id':case['id'],'version':case['version'],'action':action,'reason':reason,'evidence':self.engine.evidence_ids(case['payload'])[:2]})
 def act(self,module,action,uid='operator',index=1):
  c=self.case(module,index);self.engine.commit(uid,self.draft(c,action,uid));return self.case(module,index)
 def pending(self,module='onboarding',index=1):
  self.act(module,'prepare',index=index);return self.act(module,'request_review',index=index)


class AnalysisTests(WorkFixture):
 def test_seeded_all_five_modules_and_15_cases(self):
  board=self.engine.board('operator')
  self.assertEqual(set(board['modules']),set(MODULES));self.assertEqual(len(board['cases']),15)
 def test_onboarding_consistent_fixture(self):
  a=self.engine.analyze(self.case());self.assertEqual(a['blockers'],0);self.assertEqual(len(a['evidence_ids']),3)
 def test_onboarding_mismatch_identified(self):
  a=self.engine.analyze(self.case(index=2));self.assertTrue(any(f['code']=='ALIAS_MISMATCH' for f in a['findings']))
 def test_onboarding_missing_docs_identified(self):
  a=self.engine.analyze(self.case(index=3));self.assertEqual(a['blockers'],2)
 def test_property_chain_gap(self):
  a=self.engine.analyze(self.case('property',2));self.assertTrue(any(f['code']=='TITLE_GAP' for f in a['findings']))
 def test_property_median_and_variance(self):
  a=self.engine.analyze(self.case('property'));metrics={r['label']:r['value'] for r in a['metrics']}
  self.assertEqual(metrics['Comparable median'],'INR 8200000.00');self.assertEqual(metrics['Variance'],'3.66%')
 def test_property_pending_search_and_valuation(self):
  codes={f['code'] for f in self.engine.analyze(self.case('property',3))['findings']}
  self.assertIn('VALUATION',codes);self.assertIn('LITIGATION_STATUS',codes)
 def test_lead_score_explained(self):
  a=self.engine.analyze(self.case('leads'));self.assertEqual(a['metrics'][0]['value'],'100/100')
  self.assertEqual(sum(int(r['value'].split()[0]) for r in a['details'] if r['reference'].startswith('SCORE-')),100)
 def test_unconsented_lead_no_outreach_draft(self):
  a=self.engine.analyze(self.case('leads',2));self.assertIn('No engagement draft',a['draft']);self.assertEqual(a['blockers'],1)
 def test_dormant_lead_flagged(self):
  self.assertIn('DORMANT',{f['code'] for f in self.engine.analyze(self.case('leads',3))['findings']})
 def test_grievance_category_and_target(self):
  a=self.engine.analyze(self.case('grievance'));metrics={r['label']:r['value'] for r in a['metrics']}
  self.assertEqual(metrics['Classification'],'Payments');self.assertEqual(metrics['Demo target'],'2026-11-07T10:00')
 def test_repeated_complaint_detection(self):
  a=self.engine.analyze(self.case('grievance'));self.assertIn('POSSIBLE_DUPLICATE',{f['code'] for f in a['findings']})
 def test_urgent_grievance_pending_not_refunded(self):
  a=self.engine.analyze(self.case('grievance',3));codes={f['code'] for f in a['findings']}
  self.assertIn('HUMAN_ESCALATION',codes);self.assertIn('PAYMENT_PENDING',codes);self.assertIn('DEMO_TARGET_OVERDUE',codes)
  self.assertIn('do not state that a refund was completed',a['draft'])
 def test_str_cycle_and_amounts(self):
  a=self.engine.analyze(self.case('str'));codes={f['code'] for f in a['findings']}
  self.assertIn('CIRCULAR_PATH',codes);self.assertIn('PASS_THROUGH',codes)
  self.assertEqual(a['metrics'][1]['value'],'INR 1650000.00');self.assertEqual(len(a['graph']),3)
 def test_low_signal_str_no_automatic_disposition(self):
  a=self.engine.analyze(self.case('str',3));self.assertEqual(a['findings'],[]);self.assertIn('NOT FILED',a['draft']);self.assertIn('independent compliance review',a['draft'])
 def test_finding_evidence_references_resolve(self):
  for c in self.store.cases(list(MODULES)):
   a=self.engine.analyze(c);allowed=set(a['evidence_ids'])|{r['id'] for r in self.store.cases(['grievance'])}
   for f in a['findings']:
    self.assertTrue(set(f['evidence']).issubset(allowed),(c['id'],f))
 def test_report_hash_and_payload_history(self):
  self.act('property','prepare');report=self.engine.report('operator','PROPERTY-DEMO-001');digest=report.pop('content_sha256')
  self.assertEqual(hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest(),digest)
  self.assertEqual(len(report['payload_versions']),2)


class WorkflowTests(WorkFixture):
 def test_full_onboarding_handoff_local_only(self):
  self.pending();c=self.act('onboarding','approve','reviewer')
  self.assertEqual(c['state'],'READY_FOR_CBS_INTEGRATION');self.assertEqual(c['version'],4)
  self.assertIn('NOT_CONNECTED',self.engine.detail('reviewer',c['id'])['connector']['status'])
 def test_onboarding_blockers_prevent_preparation(self):
  with self.assertRaises(ConflictError):self.act('onboarding','prepare',index=2)
 def test_correction_preserves_prior_evidence_snapshot(self):
  self.act('onboarding','correct_fixture',index=2)
  versions=self.store.versions('ONBOARDING-DEMO-002')
  self.assertEqual(versions[0]['payload']['documents'][1]['fields']['applicant_alias'],'DEMO_CUSTOMER_B')
  self.assertEqual(versions[1]['payload']['documents'][1]['fields']['applicant_alias'],'DEMO_CUSTOMER_A')
 def test_property_findings_review_does_not_clear_title(self):
  self.pending('property',2);c=self.act('property','approve','reviewer',2)
  self.assertEqual(c['state'],'FINDINGS_REVIEWED');self.assertGreater(self.engine.analyze(c)['blockers'],0)
  self.assertIn('not title certification',self.engine.analyze(c)['draft'])
 def test_lead_handoff_independent_rm(self):
  self.pending('leads');self.assertEqual(self.act('leads','approve','relationship')['state'],'HANDOFF_ACCEPTED')
 def test_lead_consent_cannot_bypass(self):
  with self.assertRaises(ConflictError):self.act('leads','prepare',index=2)
 def test_withdrawal_invalidates_pending_handoff(self):
  c=self.pending('leads');old=self.draft(c,'approve','relationship');self.act('leads','withdraw_consent')
  with self.assertRaises(ConflictError):self.engine.commit('relationship',old)
  self.assertEqual(self.case('leads')['state'],'CONTACT_SUPPRESSED')
 def test_dormant_lead_cannot_automatically_handoff(self):
  self.act('leads','prepare',index=3)
  with self.assertRaises(ConflictError):self.act('leads','request_review',index=3)
 def test_grievance_internal_resolution_requires_confirmed_trace(self):
  self.pending('grievance');self.assertEqual(self.act('grievance','approve','reviewer')['state'],'INTERNAL_RESOLUTION_REVIEWED')
  self.pending('grievance',2)
  with self.assertRaises(ConflictError):self.act('grievance','approve','reviewer',2)
 def test_urgent_exception_must_not_be_cleared_by_fixture_replace(self):
  with self.assertRaises(ConflictError):self.act('grievance','correct_fixture',index=3)
  self.act('grievance','escalate',index=3)
  self.assertEqual(self.act('grievance','review_escalation','reviewer',3)['state'],'EXCEPTION_REVIEWED')
 def test_str_compliance_review_no_filing(self):
  self.pending('str');self.assertEqual(self.act('str','approve','compliance')['state'],'DRAFT_REVIEWED_NOT_FILED')
 def test_wrong_role_cannot_approve(self):
  c=self.pending()
  with self.assertRaises(ConflictError):self.draft(c,'approve','operator')
 def test_module_scope_not_found(self):
  with self.assertRaises(NotFoundError):self.engine.detail('relationship','STR-DEMO-001')
  with self.assertRaises(NotFoundError):self.engine.detail('compliance','ONBOARDING-DEMO-001')
 def test_stale_case_cannot_overwrite(self):
  c=self.case();draft=self.draft(c,'prepare');self.act('onboarding','add_note')
  with self.assertRaises(ConflictError):self.engine.commit('operator',draft)
 def test_arbitrary_evidence_rejected(self):
  c=self.case();body={'id':c['id'],'version':1,'action':'prepare','reason':'Reviewed synthetic evidence for this demonstration.','evidence':['INVENTED']}
  with self.assertRaises(ValidationError):self.engine.validate_action('operator',body)
 def test_note_requires_rationale_and_evidence(self):
  c=self.case()
  with self.assertRaises(ValidationError):self.draft(c,'add_note',reason='ok')
 def test_pii_rationale_rejected_without_mutation(self):
  c=self.case()
  with self.assertRaises(ValidationError):self.draft(c,'add_note',reason='Contact person@example.com to approve this case.')
  self.assertEqual(self.case()['version'],1)
 def test_versions_audit_atomic_and_pseudonymous(self):
  self.act('onboarding','prepare');events=self.store.events('ONBOARDING-DEMO-001')
  self.assertEqual([e['version'] for e in events],[1,2]);self.assertTrue(all(e['subject'].startswith('subject:') for e in events))
  with self.store.connect() as db:self.assertEqual(db.execute("SELECT count(*) FROM case_versions WHERE case_id='ONBOARDING-DEMO-001'").fetchone()[0],2)
 def test_return_for_correction_and_resubmit(self):
  self.pending();self.assertEqual(self.act('onboarding','return','reviewer')['state'],'RETURNED');self.pending();self.assertEqual(self.case()['state'],'PENDING_REVIEW')
 def test_cannot_confirm_approve_twice(self):
  self.pending();self.act('onboarding','approve','reviewer')
  with self.assertRaises(ConflictError):self.act('onboarding','approve','reviewer')
 def test_new_synthetic_cases_all_modules(self):
  for m in MODULES:
   draft=self.engine.validate_create('operator',{'module':m,'scenario':'standard','title':'Synthetic demonstration','reason':'Create a fictional case for workflow validation.'})
   ident=self.engine.create('operator',draft);self.assertEqual(self.store.case(ident,[m])['payload']['classification'],'SYNTHETIC_DEMO_ONLY')
 def test_bad_intake_and_nonmaker_create(self):
  with self.assertRaises(ValidationError):self.engine.validate_create('operator',{'module':'str','scenario':'unknown','title':'Test','reason':'Test case created for investigation.'})
  with self.assertRaises(ConflictError):self.engine.validate_create('compliance',{'module':'str','scenario':'standard','title':'Test','reason':'Test case created for investigation.'})
 def test_read_analysis_does_not_mutate(self):
  first=self.case();self.engine.detail('operator',first['id']);self.engine.board('operator')
  self.assertEqual(first,self.case())


class HTTPWorkbenchTests(WorkFixture):
 def setUp(self):
  super().setUp();self.server=WorkServer(0,self.engine);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base_url=f'http://127.0.0.1:{self.server.server_port}';self.addCleanup(self.stop)
 def stop(self):self.server.shutdown();self.server.server_close();self.thread.join(2)
 def request(self,path,body=None,token=None,headers=None):
  hdr={}
  if body is not None:hdr.update({'Content-Type':'application/json','X-Workbench-Request':'1'})
  if token:hdr.update({'Cookie':token[0],'X-CSRF-Token':token[1]})
  hdr.update(headers or {})
  req=Request(self.base_url+path,json.dumps(body).encode() if body is not None else None,headers=hdr)
  try:
   with urlopen(req,timeout=5) as response:
    raw=response.read();data=json.loads(raw) if 'application/json' in response.headers.get('Content-Type','') else raw
    if isinstance(data,dict) and response.headers.get('Set-Cookie'):data['_cookie']=response.headers['Set-Cookie'].split(';',1)[0]
    return response.status,data
  except HTTPError as error:return error.code,json.loads(error.read())
 def login(self,uid='operator'):
  code,data=self.request('/api/login',{'persona':uid,'password':PERSONAS[uid]['password'],'privacy_ack':True});self.assertEqual(code,200);return data['_cookie'],data['csrf']
 def review_action(self,token,module='onboarding',action='prepare',version=1):
  return self.request('/api/review',{'kind':'action','id':module.upper()+'-DEMO-001','version':version,'action':action,'reason':'Reviewed the cited synthetic evidence and proposed this internal workflow action.','evidence':self.engine.evidence_ids(self.case(module)['payload'])[:1]},token)
 def test_requires_session_and_ack(self):
  self.assertEqual(self.request('/api/board')[0],401)
  self.assertEqual(self.request('/api/login',{'persona':'operator','password':'Operator-2026!','privacy_ack':False})[0],400)
 def test_board_role_scope(self):
  token=self.login('compliance');code,data=self.request('/api/board',token=token);self.assertEqual(code,200);self.assertEqual(set(data['modules']),{'str'});self.assertEqual(len(data['cases']),3)
 def test_case_and_report_scope(self):
  token=self.login('relationship')
  for path in ('/api/case?id=STR-DEMO-001','/api/report?id=STR-DEMO-001'):self.assertEqual(self.request(path,token=token)[0],404)
 def test_review_no_write_then_single_use_confirmation(self):
  token=self.login();code,r=self.review_action(token);self.assertEqual(code,200);self.assertEqual(self.case()['state'],'NEW')
  self.assertEqual(self.request('/api/confirm',{'review_id':r['review_id']},token)[0],200);self.assertEqual(self.case()['state'],'PREPARED')
  self.assertEqual(self.request('/api/confirm',{'review_id':r['review_id']},token)[0],409)
 def test_review_cross_session_rejected(self):
  token=self.login();_,r=self.review_action(token);other=self.login('reviewer')
  self.assertEqual(self.request('/api/confirm',{'review_id':r['review_id']},other)[0],409)
  self.assertEqual(self.request('/api/confirm',{'review_id':r['review_id']},token)[0],200)
 def test_expired_review(self):
  token=self.login();_,r=self.review_action(token);self.server.reviews[r['review_id']]['expires']=0
  self.assertEqual(self.request('/api/confirm',{'review_id':r['review_id']},token)[0],409)
 def test_stale_confirmation(self):
  token=self.login();_,r=self.review_action(token);self.act('onboarding','add_note')
  self.assertEqual(self.request('/api/confirm',{'review_id':r['review_id']},token)[0],409)
 def test_csrf_origin_host_guards(self):
  token=self.login()
  self.assertEqual(self.request('/api/review',{},(token[0],'bad'))[0],403)
  self.assertEqual(self.request('/api/board',token=token,headers={'Host':'evil.example'})[0],403)
  self.assertEqual(self.request('/api/review',{},token,{'Origin':'https://evil.example'})[0],403)
 def test_unknown_fields_rejected(self):
  token=self.login();self.assertEqual(self.request('/api/review',{'kind':'action','customer_id':'other'},token)[0],400)
 def test_create_review_workflow(self):
  token=self.login();code,r=self.request('/api/review',{'kind':'create','module':'property','scenario':'title_gap','title':'Demonstration property review','reason':'Create a fictional case to inspect title continuity.'},token)
  self.assertEqual(code,200);self.assertEqual(len(self.store.cases(['property'])),3)
  code,result=self.request('/api/confirm',{'review_id':r['review_id']},token);self.assertEqual(code,201);self.assertTrue(result['case_id'].startswith('PROPERTY-'));self.assertEqual(len(self.store.cases(['property'])),4)
 def test_report_has_evidence_history_and_hash(self):
  token=self.login();code,data=self.request('/api/report?id=STR-DEMO-001',token=token)
  self.assertEqual(code,200);self.assertIn('content_sha256',data);self.assertIn('payload_versions',data);self.assertEqual(data['classification'],'SYNTHETIC_DEMO_ONLY')
 def test_logout_and_idle_expiry(self):
  token=self.login();self.assertEqual(self.request('/api/logout',{},token)[0],200);self.assertEqual(self.request('/api/board',token=token)[0],401)
  token=self.login();sid=token[0].split('=',1)[1];self.server.sessions[sid]['last']-=601;self.assertEqual(self.request('/api/board',token=token)[0],401)
 def test_kill_switch(self):
  token=self.login();self.server.disabled.touch();self.assertEqual(self.request('/api/board',token=token)[0],503);self.assertEqual(self.review_action(token)[0],503)
 def test_pii_not_echoed(self):
  token=self.login();body={'kind':'action','id':'ONBOARDING-DEMO-001','version':1,'action':'add_note','reason':'Please email person@example.com about the case.','evidence':['KYC-ID-01']}
  code,data=self.request('/api/review',body,token);self.assertEqual(code,400);self.assertNotIn('person@example.com',json.dumps(data));self.assertEqual(self.case()['version'],1)
 def test_static_paths_and_no_filesystem_access(self):
  for path in ('/','/app.js','/style.css'):self.assertEqual(self.request(path)[0],200)
  self.assertNotEqual(self.request('/../data/workbench/policy.json')[0],200)
 def test_secure_cookie_flags(self):
  req=Request(self.base_url+'/api/login',json.dumps({'persona':'operator','password':'Operator-2026!','privacy_ack':True}).encode(),headers={'Content-Type':'application/json','X-Workbench-Request':'1'})
  with urlopen(req) as r:
   self.assertIn('HttpOnly',r.headers['Set-Cookie']);self.assertIn('SameSite=Strict',r.headers['Set-Cookie']);self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy']);self.assertIn('no-store',r.headers['Cache-Control'])

class ConnectorBoundaryTests(unittest.TestCase):
 def test_all_external_boundaries_disabled(self):
  from bankworkbench.connectors import BOUNDARIES,IntegrationUnavailable
  for name,boundary in BOUNDARIES.items():
   with self.subTest(connector=name):
    self.assertFalse(boundary.status()['execution_enabled'])
    with self.assertRaises(IntegrationUnavailable):boundary.execute({'case_id':'DEMO'})
 def test_workbench_cannot_be_mistaken_for_pfm_upgrade(self):
  from upgrade_from import upgrade
  with tempfile.TemporaryDirectory() as td:
   source=Path(td)/'operations.sqlite3';WorkStore(source)
   with self.assertRaises(ValueError):upgrade(source,Path(td)/'new'/'pfm.sqlite3')
