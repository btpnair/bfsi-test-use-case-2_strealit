# Version 2 local API

Default URL http://127.0.0.1:8767. If busy, use the free port printed at startup. This replaces the v1 bearer-token API.

Every POST requires application/json and X-PFM-Request: 1. Login sends customer_id, password and privacy_ack: true; response sets an HttpOnly SameSite=Strict pfm_session cookie and returns a separate csrf value. Authenticated POSTs must send the cookie and X-CSRF-Token. GETs need the cookie. Host/Origin checks, body limits and field allowlists apply. Bearer authentication is not enabled.

| Route | Contract |
|---|---|
| POST /api/login | customer_id, password, privacy_ack. Returns masked customer_label, csrf, policy and durations; sets cookie. |
| GET /api/dashboard?month=2026-10 | Summary, previous bucket, safe transaction fields, active/archived goals, recurring candidates and available months. |
| POST /api/chat | message and month. Returns safe_message, answer, evidence_ids, method; optionally goal_draft, never a direct mutation. |
| POST /api/goals/review | action=create/edit/archive/restore. Create/edit: name,target,saved,due_on. Edit/archive/restore: id,integer version. Archive/restore disallow monetary/name fields. Returns normalized draft and review_id without saving. |
| POST /api/goals/confirm | review_id only. Uses server-held reviewed action once; returns goal_id and action. |
| POST /api/logout | Empty object. Revokes session, expires cookie and clears its reviews. |

Review expiry is five minutes, bound to one session. Versions and validation repeat on commit. There is no direct-write goal endpoint, permanent deletion, transfer or bank workflow endpoint. Outbound transactions omit source account/customer fields and raw narration.

Errors: 400 input validation with fields where applicable; 401 login/session; 403 request/CSRF/Host/Origin; 404 unavailable route or unknown/non-owned goal; 409 stale/replayed/expired review; 429 rate limit; 503 local kill switch; 500 unexpected failure. Internal errors do not echo arbitrary input. Unauthenticated unknown API routes return 401.

CLI imports/reports use operating-system file privileges, not these customer sessions. They are developer functions for synthetic data only.
