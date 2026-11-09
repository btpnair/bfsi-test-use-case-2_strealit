"""Explicitly unavailable integration boundaries; no vendor API contracts are asserted."""
from dataclasses import dataclass


class IntegrationUnavailable(RuntimeError):pass


@dataclass(frozen=True)
class InterfaceBoundary:
 name:str
 purpose:str

 def status(self):
  return {'name':self.name,'status':'NOT_CONFIGURED','execution_enabled':False,'purpose':self.purpose}

 def execute(self,*args,**kwargs):
  raise IntegrationUnavailable(self.name+': no Bank-approved contract, credentials, entitlement or live transport is configured.')


BOUNDARIES={
 'cbs':InterfaceBoundary('Core banking / BaNCS boundary','Approved customer/account read services and controlled account-opening handoff'),
 'kyc':InterfaceBoundary('Verification boundary','Approved KYC, screening, consent and CPV evidence'),
 'registry':InterfaceBoundary('Property source boundary','Approved registry, encumbrance, litigation and valuation sources'),
 'crm':InterfaceBoundary('CRM boundary','Lead ownership, consent, engagement history and complaint cases'),
 'channels':InterfaceBoundary('Customer channel boundary','Approved outbound communication and delivery policies'),
 'payments':InterfaceBoundary('Payment evidence boundary','Read-only investigation trace and controlled resolution workflow'),
 'aml':InterfaceBoundary('AML case boundary','Approved alert, entity and transaction investigation services'),
 'fiu':InterfaceBoundary('Regulatory-reporting boundary','Authorized human-led reporting outside this prototype')
}
