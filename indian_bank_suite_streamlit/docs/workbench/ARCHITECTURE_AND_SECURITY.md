# Architecture, privacy and integration plan

```text
Local staff browser
  -> session/CSRF/role guard
  -> case/evidence workbench API
  -> deterministic module analysis and reviewed workflow transitions
  -> SQLite case + immutable-through-API payload versions + case events

External boundaries: not configured
  CBS/BaNCS | KYC/CPV | registry/court/valuation | CRM/channels | payment trace | AML/FIU
```

Bankworkbench is separate from PFM but reuses money conversion, privacy-screening helpers and owner-only storage foundations. `fixtures.py` generates bounded dossiers; `engine.py` implements findings and workflow rules; `storage.py` stores staff, cases, payload versions and events; `server.py` enforces browser/API controls; `connectors.py` explicitly rejects external execution. `workbench_web` provides all local assets, without a CDN or analytics.

## Action integrity

Every action review is a server-held snapshot bound to a random session secret with a five-minute expiry and single use. Confirmation re-validates role, module, state, rationale, evidence references and case version. The case read, business guard, update, payload snapshot and events commit under BEGIN IMMEDIATE in one SQLite transaction. A stale version fails. Review expiry cannot be bypassed by changing a client field. A role outside a module sees not found for its cases/reports. The preparer cannot independently review its own submitted case.

Property sign-off confirms review of findings, not legal clearance. Grievance closure-like states are internal resolution review only; pending traces and exceptions block resolution approval. Lead contact permission is a hard gate; withdrawal invalidates subsequent preparation/handoff. STR review never exposes a filing action. No arbitrary tool execution, SQL, shell or network-agent feature exists.

## Local controls

- PBKDF2-HMAC-SHA256 staff password hashes with per-user salts and 600,000 iterations; published demo personas are deliberately known.
- HttpOnly/SameSite=Strict session cookie, separate CSRF token, custom JSON header, Host/Origin checks, cross-site request rejection, field allowlists, duplicate JSON-key rejection and 16 KiB POST limit.
- Ten-minute API inactivity and thirty-minute absolute session expiry; new same-persona sign-in revokes the old session. Sessions/drafts stay in process memory, not localStorage or SQLite.
- Ten sign-in attempts per loopback service per minute, 120 authenticated requests per session per minute, at most twenty pending reviews per session, ten-second I/O timeout and two hundred cases per module.
- Restrictive local-only CSP, frame denial, no-referrer, no-store, nosniff and disabled camera/microphone/geolocation/payment permissions. Dynamic content uses text nodes, not inserted HTML.
- Input screening rejects common PAN-like tokens, long numbers, common mobile/email/UPI patterns and labelled secrets. Typed fields are synthetic aliases, never genuine identifiers. Title/rationale length, controls and markup are validated. Detection is incomplete and can have false positives.
- Owner-only database/key files. Staff scope comes from fixed demo role assignments, not request-supplied authority. No application-level encryption exists.

## Data inventory and retention

Dossiers, document fields, prior payload versions, case events, screened rationale and evidence references remain until operator reset. Retaining rationale is intentional for case accountability; users must not put personal/confidential data into it. Events identify actors through keyed pseudonyms plus role. Common audit metadata logs case reference/action/evidence count but not raw rationale, and rows older than ninety days are pruned at startup. Case history has a different retention scope and is not pruned automatically.

Downloaded JSON reports include case facts, evidence, retained revisions and event rationale. They are plaintext. The content checksum detects accidental changes only; it is not a digital signature. Pseudonymization is neither encryption nor anonymization; the audit key is local alongside the database. OS owners, browser extensions or malware can access local data/memory. Sign-out clears rendered details but cannot revoke exports/screenshots.

The staff privacy acknowledgement is a demonstration notice with a versioned record, not production customer consent or a legal-basis decision. Use synthetic content only. No real documents are uploaded, real outbound messages sent, regulator contacted or Bank service queried.

## Production work still required

Use Bank-approved SSO/MFA and step-up, least-privilege per-case/customer entitlements, independent officer assignments, consent/DLP, encrypted databases/backups and managed keys, immutable audit, retention/erasure rules, SIEM/monitoring, incident controls, tested recovery and a production web/gateway service. Local HTTP lacks TLS/HSTS/Secure-cookie protection; the Python development server is not for public/customer exposure. Geography follows the laptop; India residency/DR and cloud isolation are not enforced.

Actual connectors need official contracts, source authentication, data classification and lawful access, code/field mapping, timeouts, replay/idempotency controls, signed approvals, error/reconciliation queues and rollback/compensating workflow. Real OCR, local approved models, evaluations, languages, voice and channel integrations are not supplied. Regex and rule fixtures cannot establish production KYC, legal/title, suitability, AML or regulatory correctness.

These are implemented controls and known gaps, not compliance certification or an assertion that every possible validation is covered.
