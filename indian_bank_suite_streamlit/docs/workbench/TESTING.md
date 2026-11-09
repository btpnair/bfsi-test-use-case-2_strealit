# Verification and acceptance boundary

Run `python3 -m unittest discover -s tests -v` from the package root. `Run_Tests.command` also compiles the PFM/workbench source. All dependencies are Python 3.10+ standard library; local HTTP tests need loopback socket permission. Temporary test databases are removed afterward. No bank/registry/messaging/regulator is contacted.

The suite includes previous PFM validation/security tests plus five-workspace analysis, title and ownership inconsistencies, missing onboarding evidence, lead consent/dormancy, grievance duplicates/pending/exception outcomes, circular/pass-through transaction traces, report integrity, role/module access, maker/checker state transitions, stale versions, correction history, consent withdrawal, escalation, evidence/rationale rules, single-use/cross-session/expired review gates, CSRF/Origin/Host, session expiry/logout, input PII rejection and disabled external connectors.

The executed result log is `TEST_RESULTS.txt` in this directory. Browser checks cover sign-in, queues, onboarding preparation/submission, analyst inability to sign off, independent reviewer sign-off, case history and STR graph rendering. Screenshots show temporary synthetic walkthrough records; the ZIP contains no runtime database.

Synthetic fixture results do not demonstrate model accuracy, OCR quality, legal correctness, transaction-monitoring detection quality, regulated advice suitability, statutory reporting compliance, real Bank integration, accessibility certification, performance/SLA or penetration-test acceptance. Real acceptance needs the Bank's BRDs, approved datasets and policies, signed interface contracts and independently reviewed controls.
