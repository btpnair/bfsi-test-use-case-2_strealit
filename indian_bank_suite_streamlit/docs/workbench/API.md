# Workbench local API

Default base URL http://127.0.0.1:8770. All POSTs require application/json and X-Workbench-Request: 1. Login sets an HttpOnly SameSite=Strict workbench_session cookie and returns a separate csrf value. Authenticated POSTs require X-CSRF-Token. Host/Origin restrictions and body field allowlists apply. No bearer-token or live integration API is available.

| Route | Contract |
|---|---|
| POST /api/login | persona,password,privacy_ack:true; returns csrf, profile and durations; sets cookie |
| GET /api/board | Role-scoped modules, queues, demo policy and available scenarios |
| GET /api/case?id=CASE | Module-authorized case, findings, facts, document register, drafts, allowed actions and events |
| GET /api/report?id=CASE | Same authorization, JSON internal report with payload versions, evidence, rationale and content hash; audit event |
| POST /api/review | kind:create with module,scenario,title,reason; or kind:action with id,version,action,reason,evidence array; no mutation |
| POST /api/confirm | review_id only; consumes a session-bound, five-minute draft, then re-validates/commits |
| POST /api/logout | Empty object; revokes session and reviews; expires cookie |

Actions depend on module/role/state: prepare, request_review, approve, return, add_note; selected modules also permit correct_fixture, withdraw_consent, escalate or review_escalation. A correction loads a synthetic fixture only. There are no direct case update/delete, raw upload, send-message, transfer, CBS account-create or regulator submission endpoints.

Errors: 400 validation with fields where applicable; 401 session/sign-in; 403 request guard; 404 route or non-owned module case; 409 stale/unavailable workflow/review; 429 rate/case limit; 503 local pause; 500 unexpected failure with no success asserted. Malformed inputs are not echoed. Unknown unauthenticated API paths return 401.

The report CLI is an OS-privileged local operator tool, not a customer API. App-owned case/connector fields are proposed internal contracts and must not be mistaken for TCS BaNCS or regulator schemas.
