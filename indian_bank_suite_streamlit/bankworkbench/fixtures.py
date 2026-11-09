"""Every alias, transaction, document and source in this module is fictional."""
from copy import deepcopy

MODULES={
 'onboarding':{'name':'Customer onboarding','section':'5.2','subtitle':'CASA intake, document reconciliation and controlled CBS handoff','icon':'◎'},
 'property':{'name':'Property due diligence','section':'5.3','subtitle':'Title reconstruction, valuation and evidence-backed findings','icon':'▦'},
 'leads':{'name':'Lead nurturing','section':'5.4','subtitle':'Explainable prioritisation, consent and relationship-manager handoff','icon':'↗'},
 'grievance':{'name':'Grievance redressal','section':'5.5','subtitle':'Complaint triage, investigation and reviewed resolution','icon':'◌'},
 'str':{'name':'Suspicious transaction review','section':'5.6','subtitle':'Transaction tracing, evidence and human-reviewed draft narratives','icon':'◇'}
}
PERSONAS={
 'operator':{'name':'Operations analyst','password':'Operator-2026!','role':'maker','modules':list(MODULES)},
 'reviewer':{'name':'Operations / legal reviewer','password':'Reviewer-2026!','role':'checker','modules':['onboarding','property','grievance']},
 'relationship':{'name':'Relationship manager','password':'Manager-2026!','role':'rm','modules':['leads']},
 'compliance':{'name':'Compliance reviewer','password':'Compliance-2026!','role':'compliance','modules':['str']}
}


def doc(ref,kind,fields,status='SIMULATED_VERIFIED'):
 return {'id':ref,'type':kind,'source':'Synthetic evidence fixture — no external verification', 'status':status,'fields':fields}


def template(module,scenario='standard'):
 if module=='onboarding':
  data={'applicant':'DEMO_CUSTOMER_A','product':'SAVINGS','age':32,'branch':'DEMO_CHENNAI',
   'consent':True,'screening':'SIMULATED_CLEAR','documents':[
    doc('KYC-ID-01','IDENTITY',{'applicant_alias':'DEMO_CUSTOMER_A','birth_year':'1994','token':'ID_TOKEN_A'}),
    doc('KYC-ADDR-01','ADDRESS',{'applicant_alias':'DEMO_CUSTOMER_A','locality':'DEMO_LOCALITY','token':'ADDRESS_TOKEN_A'}),
    doc('KYC-FORM-01','APPLICATION',{'applicant_alias':'DEMO_CUSTOMER_A','product':'SAVINGS'})]}
  if scenario=='name_mismatch':data['documents'][1]['fields']['applicant_alias']='DEMO_CUSTOMER_B'
  if scenario=='missing_document':data['documents']=data['documents'][:1]
 elif module=='property':
  data={'property':'DEMO_PLOT_A','declared_value':'8500000.00','owner':'OWNER_C','registry_status':'SIMULATED_CLEAR','litigation_status':'SIMULATED_CLEAR',
   'title_chain':[{'id':'TITLE-01','date':'2004-06-12','from':'OWNER_A','to':'OWNER_B'}, {'id':'TITLE-02','date':'2015-04-16','from':'OWNER_B','to':'OWNER_C'}],
   'comparables':[{'id':'VAL-01','value':'8000000.00'},{'id':'VAL-02','value':'8200000.00'},{'id':'VAL-03','value':'8400000.00'}],
   'documents':[doc('DEED-01','TITLE_DEED',{'property':'DEMO_PLOT_A','owner':'OWNER_C'}),doc('EC-01','ENCUMBRANCE_SNAPSHOT',{'status':'SIMULATED_CLEAR'}),doc('PLAN-01','BUILDING_PLAN',{'status':'SIMULATED_PRESENT'})]}
  if scenario=='title_gap':data['title_chain'][1]['from']='OWNER_X'
  if scenario=='valuation_exception':data['declared_value']='12000000.00';data['litigation_status']='SIMULATED_PENDING'
 elif module=='leads':
  data={'prospect':'DEMO_PROSPECT_A','product':'DEPOSIT','channel':'EMAIL','consent':True,'consent_source':'CONSENT-DEMO-01','consent_expires':'2027-12-31','dnc':False,
   'requested_callback':True,'engagements_7d':3,'need_confirmed':True,'days_since_contact':2,
   'history':[{'id':'ENG-01','date':'2026-11-02','event':'Prospect asked for deposit product information'},{'id':'ENG-02','date':'2026-11-04','event':'Callback preference recorded'}],
   'documents':[doc('CONSENT-DEMO-01','CONSENT',{'channel':'EMAIL','purpose':'DEMO_PRODUCT_INFORMATION'})]}
  if scenario=='no_consent':data['consent']=False;data['dnc']=True
  if scenario=='dormant':data.update(requested_callback=False,engagements_7d=0,need_confirmed=False,days_since_contact=75)
 elif module=='grievance':
  data={'customer':'DEMO_CUSTOMER_A','channel':'MOBILE','description':'UPI payment debited but beneficiary not credited. Please investigate.','amount':'2500.00',
   'reported_at':'2026-11-04T10:00:00','vulnerable_support':False,'regulatory_exception':False,
   'transaction_status':'SIMULATED_REVERSAL_CONFIRMED','related_case':None,
   'documents':[doc('PAY-01','PAYMENT_TRACE',{'status':'SIMULATED_REVERSAL_CONFIRMED','amount':'2500.00'}),doc('ACK-01','COMPLAINT_ACK',{'received':'2026-11-04T10:00:00'})]}
  if scenario=='duplicate':data['related_case']='DEMO_RELATED_COMPLAINT';data['transaction_status']='SIMULATED_PENDING';data['documents'][0]['fields']['status']='SIMULATED_PENDING'
  if scenario=='urgent':data.update(description='Repeated ATM debit dispute, urgent assistance requested.',transaction_status='SIMULATED_PENDING',vulnerable_support=True,regulatory_exception=True)
 elif module=='str':
  data={'alert':'DEMO_ALERT_A','subject':'ENTITY_A','rail':'DEMO_UPI','transactions':[
    {'id':'AML-T01','from':'ENTITY_A','to':'ENTITY_B','amount':'600000.00','at':'2026-11-03T09:00:00'},
    {'id':'AML-T02','from':'ENTITY_B','to':'ENTITY_C','amount':'550000.00','at':'2026-11-03T09:30:00'},
    {'id':'AML-T03','from':'ENTITY_C','to':'ENTITY_A','amount':'500000.00','at':'2026-11-03T10:00:00'}],
   'documents':[doc('AML-SOURCE-01','TRANSACTION_EXPORT',{'coverage':'Synthetic fixture only'}),doc('AML-KYC-01','CUSTOMER_CONTEXT',{'subject':'ENTITY_A','source':'Synthetic KYC context'})]}
  if scenario=='pass_through':data['transactions']=data['transactions'][:2]
  if scenario=='low_signal':data['transactions']=[{'id':'AML-T04','from':'ENTITY_A','to':'ENTITY_D','amount':'5000.00','at':'2026-11-03T12:00:00'}]
 else:raise ValueError('Unknown use case.')
 data['classification']='SYNTHETIC_DEMO_ONLY'
 return deepcopy(data)

SCENARIOS={
 'onboarding':{'standard':'Consistent synthetic application','name_mismatch':'Cross-document alias mismatch','missing_document':'Missing address/application evidence'},
 'property':{'standard':'Complete synthetic title chain','title_gap':'Broken title continuity','valuation_exception':'Valuation variance and pending search'},
 'leads':{'standard':'Consented engaged prospect','no_consent':'Suppressed / no communication consent','dormant':'Dormant prospect'},
 'grievance':{'standard':'Payment reversal evidence available','duplicate':'Possible repeated complaint','urgent':'Urgent exception needing human review'},
 'str':{'standard':'Circular transaction chain','pass_through':'Rapid pass-through chain','low_signal':'Low-signal alert'}
}
