# Version 2 verification

Run from the project root with Python 3.10+:

```sh
python3 -m compileall -q pfm tests data upgrade_from.py
python3 -m unittest discover -s tests -v
```

The result log identifies the tested runtime/platform. HTTP tests need loopback socket permission, use ephemeral 127.0.0.1 ports and temporary databases, and contact no bank/AI service.

Coverage: arithmetic/import/refund/categories; goal editing, archive/restore, ownership, versions, normalized duplicates, field/count/amount/date limits; review/confirm and replay/expiry/session checks; CSRF/cookie flags, session revocation/expiry, privacy acknowledgement, PII input/output minimisation, login throttling, mass assignment and legacy migration.

Browser walkthrough:

1. Sign in after the notice, inspect Customer 01 October totals.
2. Create Emergency fund, target 60000, saved 10000, deadline 2027-06-30. Review, confirm, check estimate 6250.00 using demo date 6 November 2026.
3. Edit progress/date; review, confirm and check the card.
4. Try saved exceeding target; verify inline error and unchanged stored goal.
5. Archive after review, then restore through Archived goals. Check progress retained.
6. Use only a fictional test PAN-like token ABCDE1234F to check rejection; never enter real identifiers. Rejected input must not be echoed into chat.
7. Ask Food spending then and last month?, inspect expandable evidence.
8. Hide/show amounts, including goal amount fields and chat.
9. Sign out; verify protected page data cleared. Customer 02 must not see Customer 01 goals.
10. Upgrade a disposable v1 synthetic DB into a fresh extraction and verify preserved goals.

UI screenshots show temporary synthetic verification records, not preloaded customer goals. Tests do not constitute production load acceptance, penetration testing, exhaustive validation or compliance certification.
