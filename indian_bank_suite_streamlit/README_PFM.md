# MoneyWise v2

A local personal-finance application for the Indian Bank RFP's first described use case, section 5.1 Conversational Personal Finance Management. This version adds reviewed goal editing, archive/restore, stronger validation, privacy screening and a redesigned banking-style interface.

**Use synthetic data only.** This is a development prototype, not an official Indian Bank or ICICI service. It has no live TCS BaNCS connection and uses rules rather than a trained AI model. No payments, deposits, account changes or investments can be executed. Customer deployment needs the Bank's approved infrastructure and review.

## Start on your Mac

Use Python **3.10 or later**. No pip packages or API keys are needed.

1. Extract the complete ZIP into a new writable folder.
2. Open Terminal in the extracted `indian_bank_pfm` folder (the one containing this README and `pfm`).
3. Start the application:

```sh
python3 -m pfm demo --open
```

Or double-click `Start_Demo.command`. Version 2 defaults to **port 8767**, keeping it separate from your earlier 8765/8766 demo. If the requested port is busy, a free loopback port is selected automatically and printed in Terminal. Use that exact URL.

Sign in as **Customer 01 / demo-1234** or **Customer 02 / demo-5678**. Acknowledge the synthetic-data/privacy notice. The IDs behind these profiles remain CUST001 and CUST002 for local CLI reports. Keep Terminal open. Press **Control+C** to stop.

A browser refresh requires signing in again. The session ends after 10 minutes without an API request or 30 minutes overall. A fresh sign-in revokes the previous session for the same demo customer.

## Keep your previous goals

Stop the old demo and the new demo first. Before launching the freshly extracted v2 folder, run this from its project root:

```sh
python3 upgrade_from.py "/full/path/to/your/old/indian_bank_pfm"
python3 -m pfm demo --open
```

You can drag the old project folder from Finder into Terminal to enter its path. The upgrade reads the old SQLite database, makes a consistent local copy, preserves goal IDs/progress and migrates the schema. It does not modify the old database and refuses to overwrite a destination database. If you already launched v2, use another fresh extraction for the upgrade. Only migrate your synthetic demo data.

See `docs/UPGRADE.md` for more detail. The ZIP excludes runtime databases, sessions, audit keys and test customers' saved goals.

## What changed

- Separate Overview, Savings goals, Transactions, Finance assistant and Privacy centre views; responsive desktop/mobile layout, accessible labels and confirmation dialogs.
- Create and **edit** a goal's name, target, already-saved amount and date. Review the complete draft, then confirm. Cancel leaves the record unchanged.
- **Archive and restore** goals without deleting their history or progress. No permanent delete operation is exposed.
- Server-side ownership, version checks, active-name uniqueness, 20-active-goal cap, exact money calculations, date limits, field-specific errors, and common PII/secret-pattern rejection.
- Chat never saves a goal directly. An explicit `create goal NAME | TARGET | SAVED | YYYY-MM-DD` produces a draft for the reviewed form.
- HttpOnly/SameSite session cookies, CSRF tokens, origin/Host checks, session expiry, request limits, duplicate JSON-key rejection and restrictive response headers.
- Minimal outbound data: account/customer identifiers and raw narrations are omitted from transaction responses; profile identifiers are masked.
- Privacy acknowledgement, local privacy centre, screen amount masking and pseudonymous audit subjects. No external AI calls, trackers, fonts or CDNs.

## Try it

Choose **October 2026**. Customer 01's synthetic income is INR 80,000, net spending INR 39,523 and cash-flow surplus INR 40,477. Surplus is not an account balance. Only imported posted activity is counted; statement completeness is not established. November is a partial sample.

Open Savings goals, enter **Emergency fund**, target **60000**, already saved **10000**, target date **2027-06-30**, then click **Review goal** and **Confirm and create**. With the fixed demo business date **6 November 2026**, the estimate is INR 6,250 per month. Click **Edit goal** to change the saved amount or date, review, and confirm again.

The estimator divides the remaining target over the calendar months touched, including the current and deadline month, and rounds up to a paise. It assumes no interest or returns and does not schedule actual payments. The last contribution must occur by the chosen deadline. Overdue goals can retain their original deadline when recording progress; choose a new future date to revise the plan. Completed status uses the self-reported saved amount, not a bank balance.

Ask the assistant `Food spending`, `and last month?`, `Show my goals`, or `Recurring payments`. Supporting transaction IDs are expandable. Pattern-based recurring candidates are suggestions, not confirmed mandates. The assistant is English-language and deterministic.

## Goal validation rules

| Field/control | Rule |
|---|---|
| Name | 1–60 normalized characters, at least one letter, whitespace collapsed; no HTML, hidden/control characters, or recognized sensitive patterns |
| Target | More than zero, up to INR 1 crore, at most two decimal places; no signs, exponent, NaN or infinity |
| Saved | Zero or more, no more than target; same money format |
| Date | Valid ISO date, normally today/future using the displayed demo date, up to the end of the calendar year ten years ahead |
| Existing overdue date | May remain unchanged to record progress; a changed date must be current/future |
| Active names | Case-insensitive normalized uniqueness per customer |
| Count | Up to 20 active goals per customer; archived goals do not count |
| Changes | Review expires after 5 minutes and can be confirmed once; goal version must still match |
| Scope | Customer identity comes from the server session; body fields cannot override it |

The UI accepts correctly grouped Indian or western comma amounts and converts them to plain decimal strings. The API accepts ungrouped decimal strings. Server validation is authoritative and runs again at confirmation.

## Privacy and security limits

**The database is not encrypted by this application.** Owner-only file permissions and pseudonymous audit subjects do not replace encryption. The development HTTP server is loopback-only, not a production web server. Cookies are HttpOnly/SameSite but do not carry Secure on local HTTP; real hosting needs HTTPS, Secure cookies, enterprise identity, MFA/step-up, encrypted storage, managed keys, account entitlements and monitoring.

PII screening uses finite patterns for PAN-like tokens, long numeric identifiers, common Indian mobile formats, email, common UPI suffixes and labelled secrets. It can miss names, addresses, unfamiliar formats and deliberately obfuscated data, and it can reject some harmless strings. It is not comprehensive DLP or an assertion of legal compliance. Only clearly marked synthetic exports with DEMO-prefixed account references are accepted, but labels themselves are not proof of synthetic provenance.

Goals, archives, synthetic records, demo user hashes, last-topic context and privacy acknowledgements remain locally until an operator resets the database. Full chat text stays only in page memory (last 20 exchanges) and is cleared at sign-out/expiry. Audit records omit raw chat, goal names, monetary values and source narrations; subjects are keyed pseudonyms, not anonymized data. Audit entries older than 90 days are pruned at startup. Local administrators can access files and CLI reports.

The Hide amounts control masks displayed financial values and goal amount fields; review actions require showing amounts. It is a screen convenience. Data already loaded is still in browser memory and accessible to the device owner. Signing out clears rendered protected data and local chat memory; it cannot revoke screenshots or previously copied information.

See `docs/SECURITY_PRIVACY.md` for implemented controls, known limitations and production dependencies.

## Tests and supporting files

```sh
python3 -m compileall -q pfm tests data upgrade_from.py
python3 -m unittest discover -s tests -v
```

Or run `Run_Tests.command`. HTTP tests require loopback socket permission and use temporary databases. Executed results are in `docs/TEST_RESULTS_V2.txt`.

The `pfm` modules separate normalization, validation/guardrails, storage, analytics/chat and HTTP. `web` contains all local website assets. `data` contains the 67-record synthetic JSON export, schema, rule configuration and fixture generator. `docs` includes integration notes, API, RFP traceability, security/privacy, design references, upgrade and test instructions. `MANIFEST.sha256` verifies packaged file content.

Local operator import/report remain available for synthetic normalized exports:

```sh
python3 -m pfm import-export --export data/synthetic_bancs_export.json --db runtime/import-test.sqlite3
python3 -m pfm report --customer CUST001 --month 2026-10 --db runtime/import-test.sqlite3
```

They are filesystem-privileged developer commands, not customer APIs. The normalized contract is proposed by this application, not an official TCS BaNCS schema. Actual bank interfaces and field/code mappings were not supplied.

Create `runtime/SERVICE_DISABLED` to block new data requests and sign-ins. Remove it to resume. In-flight requests and already-rendered values are not erased; this is not an enterprise kill switch.
