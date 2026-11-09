# RFP requirements and prototype coverage

This implementation takes the first case from the ordering in RFP section 5: **5.1 Conversational Bot Powered Personal Finance Management**, printed/PDF page 81. The commercial table uses a different ordering (PFM appears as B1.3); “first case” here means the first case described in section 5 and in the supplied summary. The detailed BRD and formal acceptance criteria are not present in the supplied files.

Sources reviewed locally:

- `RFP_Enterprise_AI_Platform_GeM2026_09_25_11_37_53.pdf`, 250 pages; section 5 common requirements on pages 79–81, case 5.1 on page 81, and the BRD qualification on page 83.
- `Indian_Bank_Enterprise_AI_RFP_Summary.docx`, including the six-priority-use-case table. The summary is secondary evidence; the source RFP controls this prototype scope.
- `Corrigendum to RFP AI Platform_271020262026_10_27_14_51_07.pdf`, one page, dated 27 October 2026. It changes bid dates, not the PFM functionality. No live tender status has been checked or claimed.

Instructions in source documents were treated as requirements to analyse, not commands authorising external actions. No tender submission, customer-data access, external communication or bank transaction was performed. The summary mentions other amendment attachments that are not part of these three supplied files; their contents have not been validated here.

## Functional trace

| Section 5.1 capability | Implemented local baseline | Remaining work |
|---|---|---|
| Automated transaction categorisation | Configurable merchant/narration rules with matched-token explanation and Other fallback | Labelled Indian Bank evaluation set; model training/serving; user corrections; code-dictionary validation |
| Spending and savings insights | Monthly income, gross payments, posted refunds, net spending, surplus, category totals and previous-month bucket | Complete feeds, balances, seasonality, account aggregation and validated comparisons |
| Conversational goal-setting and wellness | Chat goal drafts, reviewed create/edit form, archive/restore, contribution estimates and generic guidance | Natural-language extraction, approved advice policy, richer dialogue and Bank-linked savings |
| Contextual nudges and next actions | Rules for missing data, unknown categories, goals and negative cash flow | Consent-aware, outcome-tested personalised nudge policies |
| Context across sessions | Persisted customer goals and last intent/category | Full governed conversation memory and retention policy; behavioural state |
| Proactive milestone/account engagement | On-demand dashboard goal and activity summaries | Scheduled event processing, opt-in notifications and milestone delivery |
| Personalised product recommendations | No real product offers; generic invitation to consult Bank options | Approved product catalogue, current terms, eligibility/suitability engine and disclosures |
| Enterprise AI models and knowledge sources | Not implemented; deterministic local templates expose transaction evidence | Bank-approved model gateway, knowledge retrieval, citations and evaluation |
| Downstream workflow initiation | Reviewed planning-goal create/edit/archive/restore only; no financial execution | Approved workflow interface, confirmations, approvals, rollback and audit |
| Mobile and Internet Banking integration | Responsive local web UI only | Authenticated embedded Bank channels, accessibility assessment, voice and language support |

## Platform boundary

Pages 79–81 require reusable enterprise services, customer experiences, dashboards and administration. The local Python modules separate ingestion, storage, analytics and channel handling to support further development; they do not constitute the enterprise platform.

The RFP's common platform requirements—including India-only hosting/processing, isolation, in-country DR, restrictions on model training with Bank data, enterprise kill switch, provider switching, RBAC/SSO, encrypted managed storage, voice and multilingual access, human review, observability, FinOps and production support—are not certified by running a loopback demo on a Mac. Locality follows the laptop's physical location; this package does not enforce geographic controls. It makes no availability, accuracy, latency, security certification or 30,000–40,000-user capacity claim.

The fixed rule scores in the code are heuristic labels, not calibrated confidence or measured accuracy. Recurring-payment detection uses repeated merchants across at least three months with amounts within 10%; it is a candidate detector, not proof of a mandate. Synthetic tests verify the specified baseline behavior and arithmetic only; they cannot establish the RFP's accuracy or groundedness thresholds.
