# Five application walkthroughs

Start `python3 -m bankworkbench --open`, sign in as operator / Operator-2026!, and acknowledge synthetic-data use. Every action needs an operational rationale (20–1200 screened characters), 1–20 valid source references, review and confirmation. All states are local case states, not external Bank-system statuses. To change role, sign out and choose the designated persona; passwords are in the main README.

## Customer onboarding

Open ONBOARDING-DEMO-001. Inspect Findings, Evidence and Draft report. Choose Prepare CBS handoff package, then Submit for independent review, confirming each action. Re-login as reviewer. Review handoff readiness and confirm. Result READY_FOR_CBS_INTEGRATION means an internal reviewed package only; no account/CPV/activation call exists.

ONBOARDING-DEMO-002 shows cross-document alias mismatch, and 003 lacks address/application evidence. Preparation is blocked. An analyst can load a corrected synthetic fixture and cite the previous evidence; prior payload versions remain in the downloaded report. This is a demo evidence revision, not a real KYC correction or verification. Missing consent cannot be bypassed through this operation.

## Property due diligence

Inspect PROPERTY-DEMO-001 for title chronology and synthetic comparable median. Case 002 has a transferor/transferee continuity gap. Case 003 has declared-value variance plus pending litigation search status. Prepare findings report and submit for independent review as operator. A reviewer can sign off that findings were reviewed or return the case with rationale.

FINDINGS_REVIEWED does not clear the title, validate a market price or approve a loan. Unresolved source gaps stay in the report. The variance rule is a demo threshold, not a property valuation standard. No registry/court/valuation service is queried.

## Lead nurturing

LEADS-DEMO-001 has consented product interest, recent engagement and callback preference. Inspect score factors, source history and channel permission. Prepare the draft, submit for independent review, then sign in as relationship / Manager-2026! and accept RM handoff. The text is a draft; no message is sent, no CRM record is updated and no product is sold.

Case 002 is suppressed for missing consent/do-not-contact. Preparing engagement or handing off is blocked. Case 003 is dormant and below the demo qualification score, so automatic handoff is blocked. Recording consent withdrawal on an active/pending case stops further contact preparation and invalidates a stale pending handoff. The score is not trained conversion propensity and uses no protected demographic attributes.

## Grievance redressal

GRIEVANCE-DEMO-001 has a synthetic confirmed reversal trace, with a possible related complaint. Prepare the investigation/resolution draft, submit for review, then have reviewer approve internal resolution. No real refund, customer notification or CRM closure is executed.

Case 002 has pending payment evidence. Resolution sign-off is blocked; investigate, add notes, return for correction or escalate. Duplicate detection suggests linkage and never silently rejects/closes complaints. Case 003 is urgent with a human-exception flag: use Escalate for exception review, then reviewer records exception review. It cannot be cleared by swapping to a corrected fixture. EXCEPTION_REVIEWED records human review, not completed redressal.

Demo target hours are configurable assumptions against 6 November 2026 12:00 IST, not regulatory deadlines. No live timer, regulator escalation or statutory notice is sent.

## Suspicious transaction review

STR-DEMO-001 has a time-ordered circular chain; 002 has pass-through movement; 003 has low configured signal. Inspect findings, transaction edges, entity graph and source references. Clicking graph edges shows the transaction reference. Gross edge volume may count the same funds repeatedly.

As operator, prepare investigation narrative and submit for independent review. Sign in as compliance / Compliance-2026!, review sources and narrative, then record internal draft review or return. DRAFT_REVIEWED_NOT_FILED never means an STR was filed. No FIU upload, regulator-specific schema validation, live AML alert disposition or conclusion of wrongdoing is performed. Human authorized Bank officials retain those decisions.

## Evidence, reports and updates

The Activity tab shows action, role, screened rationale, evidence and case version. Download internal report includes current findings, document fields, full retained payload revisions, event trail and a SHA-256 content checksum. Keep source case ID and version together when citing references; document IDs can recur across separate fictional cases.

New synthetic cases can be created from a module's intake button. Pick a controlled scenario and provide a fictional title/rationale. Real document upload and customer-data input are intentionally unavailable. Analysis is recalculated on read; it does not mutate the case or contact external systems.
