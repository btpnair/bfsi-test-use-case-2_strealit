# Security and privacy implementation and boundaries

The threat model is a local Mac running synthetic-data demonstrations. Tested cases include browser request abuse, unauthorized customer access, stale/replayed goal changes, malformed inputs and recognizable personal information. This is not bank-readiness, penetration-test, legal-compliance or exhaustive-validation certification.

## Implemented controls

| Area | Behavior |
|---|---|
| Authorization | Identity derives from server session. Goal reads/writes use customer ID and goal ID. Other-customer and unknown IDs share the same not-found response. |
| Goal integrity | Server-held validated draft, session binding, five-minute expiry and single-use confirmation. Exact paise arithmetic, name normalization, uniqueness and count/amount/date bounds. Versions prevent stale overwrites. |
| Atomicity | Goal change and audit event commit in one SQLite transaction using BEGIN IMMEDIATE. Uniqueness/count are checked at write time. Imports are atomic. |
| Sessions | Random 256-bit secrets in HttpOnly SameSite=Strict cookies; separate CSRF token in page memory. Ten-minute API inactivity and thirty-minute absolute expiry. Re-login revokes that customer's old session. No session tokens in localStorage or database. |
| Requests | Host/Origin allowlists, cross-site Fetch Metadata rejection, custom header, CSRF check, JSON-only POST, 8192-byte body limit, duplicate JSON-key rejection, field allowlists and no CORS. |
| Responses | No-store, local-only CSP, frame denial, nosniff, no-referrer and disabled camera/microphone/location/payment permissions. Text rendering uses textContent, not user HTML. |
| Limits | Ten login attempts per loopback client per minute; 120 authenticated requests per session per minute; 20 pending reviews per session; ten-second connection I/O timeout. Local development controls, not distributed abuse protection. |
| Passwords | Per-user random salts; PBKDF2-HMAC-SHA256 with 600,000 iterations for new hashes. Legacy 200,000-iteration hashes upgrade after successful login. Demo credentials are intentionally published. |
| Input privacy | Known PAN-like, long-number, Indian mobile, email, common UPI, labelled-identifier and secret patterns are rejected. Control/hidden characters and HTML markup rejected in user text. Rejected inputs are not echoed or audited. |
| Output privacy | Transaction responses omit source customer/account IDs and raw narrations. Profile identifiers are masked. Known patterns in legacy goal names/recurring descriptions are redacted. |
| Audit | Keyed pseudonymous subjects. Goal reference/event/version, without goal names, amounts or raw chat. Goal event is atomic with mutation. Ninety-day pruning at startup. Mutable local table, not an immutable enterprise ledger. |
| Notice | Versioned demo privacy acknowledgement stored as pseudonymous subject, policy and timestamp. Not production consent or legal-basis determination. |
| Locality | No external AI, analytics, CDN or bank calls. Loopback-only. Physical laptop geography is not enforced by code. |
| Storage | Owner-only database/audit-key files and restrictive new runtime directory permissions. SQLite/backups are not encrypted by this application. |
| Ingestion | Explicit SYNTHETIC_DEMO_ONLY label and DEMO-prefixed accounts, INR validation, duplicate/refund/ownership checks. Labels are not authenticated proof that data is fictional. |
| Assistant | Deterministic intents and own-customer evidence only. No arbitrary tools, SQL, shell or financial execution. Goal commands draft only, requiring reviewed form confirmation. No product rankings or guaranteed returns. |
| Kill switch | SERVICE_DISABLED blocks new data/sign-in requests. Does not interrupt in-flight work or clear already-rendered data. |

## Data inventory and retention

Synthetic transactions, active/archived goals, demo user hashes, last-topic context and privacy acknowledgements persist until operator reset. Archive is reversible, not erasure. Full chat is only in page memory, capped at the last 20 exchanges and cleared on refresh/logout/expiry. It is never stored in the server database.

Audit retains timestamp, pseudonymous subject, event and minimal metadata, with ninety-day pruning at startup. Legacy subjects are pseudonymized; arbitrary old metadata cannot be certified safe. Sessions and review drafts are process-memory-only. Logical expiry prevents use immediately; physical cleanup occurs on subsequent access/login/review or process exit.

The audit key is stored beside the database with owner permissions. Device administrators can access both. Pseudonymization is neither anonymization nor encryption. Hide amounts is a screen convenience; values remain available in page/process memory to the local device owner. Logout clears rendered protected records but cannot revoke screenshots or copies.

## Gaps and production dependencies

Pattern screening is incomplete and can have false positives. Names, addresses, free-text health/financial details, unfamiliar handles and obfuscated identifiers can pass. Never enter real customer data. The application does not protect against a compromised device, malware, browser extensions or a local administrator.

Local HTTP intentionally has no TLS, HSTS or Secure-cookie flag. Real deployment requires Bank-controlled HTTPS, Secure cookies, SSO/MFA/step-up, account entitlements, formal consent, encrypted databases/backups, KMS/HSM, retention/erasure enforcement, immutable audit, SIEM/DLP, incident response and tested recovery. Fake OTPs are not used to imply MFA.

Python's standard-library HTTP server is for development. Distributed limits, bounded production resource management, external scans, penetration testing, load testing and business acceptance remain open. This package is not an enterprise AI platform or an assertion of RFP compliance.

BaNCS contracts, approved model services, Bank classifications/product rules and complete BRDs were not supplied. Synthetic arithmetic tests do not establish real-customer suitability or model-quality thresholds.

## Engineering references

Official OWASP material reviewed on 6 November 2026 informed selected controls; this is not OWASP certification:

- [Session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
