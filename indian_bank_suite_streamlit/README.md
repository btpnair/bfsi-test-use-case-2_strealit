# Indian Bank RFP local banking application suite

## Streamlit version (added 9 November 2026)

Run `python3 -m pip install -r requirements.txt`, then `python3 -m streamlit run streamlit_app.py`. For Streamlit Community Cloud use `streamlit_app.py` at repository root, or `indian_bank_suite/streamlit_app.py` if uploaded within that folder. See `STREAMLIT_SETUP.txt` for upload instructions.

The native Streamlit interface covers all five banking workbench workflows. It uses temporary data isolated by browser session and published fictional personas. The separate MoneyWise PFM interface remains in its original local-server form. The original local-server instructions below still apply to that version.

This package contains the existing MoneyWise PFM v2 application plus five new operational workspaces covering RFP sections 5.2–5.6. The workbench supports synthetic intake, rule-based findings, source references, draft reports, role-specific actions, independent review, versioned case history and JSON report downloads.

**All records are fictional.** This is a workflow prototype, not an official Indian Bank/TCS/ICICI product or a complete enterprise AI deployment. No trained model, OCR, live document check, Bank/CBS, registry, CRM, messaging, refund or FIU connection is configured. No real account opening, title clearance, credit decision, customer contact, refund or regulatory filing can be executed.

## Start the five new applications

Python **3.10+** is required. No pip packages, API keys, internet or cloud account are needed.

1. Extract the complete ZIP into a fresh writable folder.
2. Open Terminal in the `indian_bank_suite` folder containing this README and the `bankworkbench` package.
3. Run:

```sh
python3 -m bankworkbench --open
```

Or double-click **Start_Workbench.command**. The default URL is http://127.0.0.1:8770. If that port is busy, the application picks a free loopback port and prints the exact URL. Keep Terminal open; Control+C stops the server.

Sign in as **Operations analyst** with **Operator-2026!** and acknowledge the fictional-data notice. The left menu opens each of the five applications. Fifteen example cases are seeded automatically, three per use case. New synthetic cases can be created from the per-module intake button.

To open a particular workspace directly after sign-in:

```sh
python3 -m bankworkbench --module onboarding --open
```

Other module values: `property`, `leads`, `grievance`, `str`. Run one workbench process and use its navigation to switch modules.

## Demo personas and responsibilities

| Login ID / dropdown persona | Password | Permitted workflow |
|---|---|---|
| operator / Operations analyst | Operator-2026! | All five synthetic modules; intake, analysis preparation, notes and review submission |
| reviewer / Operations and legal reviewer | Reviewer-2026! | Onboarding, property and grievance; independent review/return/escalation review |
| relationship / Relationship manager | Manager-2026! | Lead cases; accept qualified handoff, return and consent suppression |
| compliance / Compliance reviewer | Compliance-2026! | STR cases; independent internal draft review or return |

These are published synthetic personas, not real identity proof or legal authority. A reviewer cannot create intakes or act as the preparing analyst. Module scope is enforced server-side. Bank production roles and case/customer entitlements need approved SSO/MFA and staffing design.

## What each application does

| RFP | Application | Local implementation |
|---|---|---|
| 5.2 | Customer onboarding | Synthetic identity/address/application fields; consistency and missing-document checks; exception blockers; corrected fixture revisions; evidence-backed handoff preparation and independent readiness review |
| 5.3 | Property due diligence | Time-ordered title chain, continuity/owner checks, synthetic comparable median and variance, pending source flags, findings report and independent findings review |
| 5.4 | Lead nurturing | Explainable rule score, engagement history, channel consent/expiry/do-not-contact suppression, draft-only personalised text, qualification threshold and RM handoff review |
| 5.5 | Grievance redressal | Payment/ATM/service classification, repeated-complaint suggestions, urgency/exception flags, configurable demo clock, payment-outcome evidence, resolution draft and human escalation |
| 5.6 | Suspicious transaction review | Time-ordered transaction graph, bounded circular-path tracing, pass-through and amount signals, source-linked internal narrative, compliance review with no filing authority |

All analytics are deterministic. Thresholds and target durations in `data/workbench/policy.json` are **demonstration assumptions**, not Bank policy, legal rules, eligibility criteria or statutory deadlines. The RFP leaves detailed BRDs to implementation. See `docs/workbench/RFP_COVERAGE.md` for remaining requirements.

## Try the independent-review flow

1. Sign in as operator and open Customer onboarding → **Consistent synthetic application**.
2. Select **Prepare CBS handoff package**. Write a rationale of at least 20 characters and tick the actual supporting evidence. Click Review action, inspect the draft and confirm.
3. Select **Submit for independent review** with fresh rationale/evidence; review and confirm. Case becomes PENDING REVIEW.
4. Sign out. Sign in as reviewer using Reviewer-2026!.
5. Open the pending onboarding case. Review handoff readiness, cite evidence and confirm.
6. The local case becomes READY FOR CBS INTEGRATION. **No account is created.** The connector still says NOT CONNECTED.

The analyst cannot perform independent sign-off. Each review expires in five minutes and can be confirmed once. Version checks prevent a stale tab overwriting newer work. Reason and evidence are required; action validity is checked again inside the database transaction. See `docs/workbench/WALKTHROUGHS.md` for the other four flows and exception scenarios.

## Existing PFM application

The complete MoneyWise v2 code remains included:

```sh
python3 -m pfm demo --open
```

Or use **Start_PFM.command**. PFM defaults to port 8767 and has its separate customer logins and local database. `README_PFM.md` has its instructions and the prior-goal upgrade process. To preserve previous PFM goals, use `upgrade_from.py` in a fresh extraction before starting PFM. Do not pass a workbench database to the PFM upgrade script. The new workbench uses `runtime/workbench.sqlite3`; PFM uses `runtime/pfm.sqlite3`.

## Data, safety and operating limits

The workbench accepts no real documents or arbitrary transaction uploads. Intake generates bounded fictional scenarios. Corrected evidence means a replacement synthetic fixture, not an external re-verification; prior case payload versions remain retained. Consent/exception flags cannot be bypassed by replacing certain fixtures. Lead withdrawal stops further contact preparation/handoff. An unresolved payment cannot be signed off as a confirmed reversal. STRs stay internal drafts; findings-review does not certify title or approve lending.

Common PII/secret patterns are rejected in titles/rationale. Detection is incomplete and may have false positives: do not enter real identifiers, contact information, confidential narrative or customer data. Source fields are opaque aliases/tokens. New inputs are rendered as text, not HTML.

The local server uses HttpOnly/SameSite cookies, CSRF and origin/Host checks, field allowlists, body limits, rate limits, restrictive response headers and session expiry (ten-minute API inactivity, thirty-minute maximum). Re-login revokes the previous same-persona session. Page refresh requires sign-in again. Signing out clears displayed protected information.

**SQLite, local keys, case history and downloaded reports are not encrypted by the application.** Database file permissions are owner-only; that does not protect against a compromised device or local administrator. Reports contain synthetic rationale, evidence and payload versions and should still be handled deliberately. SHA-256 content hashes are integrity aids, not digital signatures or non-repudiation.

Case versions/events persist until local operator reset. They include screened rationale, evidence IDs, action, role and pseudonymous actor subject. Common audit metadata omits raw rationale; those audit rows are pruned after ninety days at startup. The case history is a local mutable store, not an immutable enterprise ledger.

Create `runtime/WORKBENCH_DISABLED` to pause new workbench API requests/sign-ins; remove it to resume. This does not interrupt in-flight requests or wipe values already displayed. PFM retains its separate SERVICE_DISABLED control.

This Python development server and these synthetic identities are not suitable for public or real customer deployment. Required production services and controls are documented in `docs/workbench/ARCHITECTURE_AND_SECURITY.md`.

## Tests and package contents

```sh
python3 -m compileall -q pfm bankworkbench tests data upgrade_from.py
python3 -m unittest discover -s tests -v
```

Or run **Run_Tests.command**. Tests use temporary databases and ephemeral loopback ports. The executed result log is `docs/workbench/TEST_RESULTS.txt`. Includes the PFM regression suite and all five workbench workflows.

| Folder/file | Purpose |
|---|---|
| bankworkbench/ | Scenarios, analytics/state machines, storage, integration boundaries, HTTP and launch CLI |
| workbench_web/ | Responsive operations website, evidence views, action reviews and transaction graph |
| pfm/, web/ | Complete existing MoneyWise PFM v2 application |
| data/workbench/ | Demo policy, all synthetic dossiers and report schema |
| docs/workbench/ | Walkthroughs, RFP trace, architecture/privacy, API and executed tests |
| docs/workbench/examples/ | Example internal JSON reports for each of the five modules |
| upgrade_from.py | Preserves prior synthetic PFM goals in a fresh extraction |
| MANIFEST.sha256 | Integrity checksums for all packaged files |

Local operator report command (filesystem privilege, not a customer API):

```sh
python3 -m bankworkbench --report STR-DEMO-001
```

The package intentionally excludes databases, audit keys, active sessions, real documents, credentials for external systems, the original RFP files and Python caches.
