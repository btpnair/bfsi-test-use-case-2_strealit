# Proposed TCS BaNCS export integration boundary

No BaNCS API specification or customer data was supplied. The provided RFP does not establish actual CBS endpoints, table names, transaction codes or interface credentials. This project therefore defines an application-owned normalization contract, not a TCS interface. No proprietary integration has been implemented or verified.

Suggested flow after the Bank approves the design:

```text
Bank-approved BaNCS read service or statement export
  -> Bank integration infrastructure (actual contract and identity controls)
  -> explicit field/code mapping and source reconciliation
  -> normalized INR posted transactions
  -> BancsExportAdapter validation
  -> PFM storage, calculations and customer-scoped experience
```

The current adapter requires the SYNTHETIC_DEMO_ONLY envelope label and DEMO-prefixed account references, screens known personal-data patterns, and reads a local JSON file at the third-to-fourth step. It never calls a bank service and never writes to CBS. The export command is intended for synthetic or separately approved, de-identified development records only.

## Normalized fields

| Field | Meaning and validation |
|---|---|
| `schema_version` | Integer 1 at the envelope level |
| `transactions` | Array, at most 100,000 entries per file |
| `id` | Stable source reference, 1–64 ASCII alphanumeric, underscore or hyphen; globally unique in local DB |
| `customer_id` | Opaque customer scope identifier using the same identifier character rules |
| `account_id` | Opaque account identifier; a single customer owner only in this prototype |
| `posted_on` | Posting date, strict `YYYY-MM-DD`; Bank integration must choose and document timezone/cutoff |
| `direction` | DEBIT or CREDIT |
| `amount` | Nonnegative INR decimal string with at most two decimal places; integer rupees also accepted; JSON float rejected |
| `currency` | INR only |
| `merchant` | String up to 500 characters; may be empty |
| `narration` | String up to 500 characters; may be empty; treated strictly as data |
| `kind` | PAYMENT debit, INCOME credit, REFUND credit, or TRANSFER debit/credit |
| `original_id` | Required for REFUND; original PAYMENT in same customer/account, posted on or before refund |

See `data/normalized_export.schema.json` for the structural contract. Python validation adds cross-record ownership, duplicate, refund reference, date, amount and refund-total checks. The importer compares existing IDs atomically, verifies account ownership across imports and prevents cumulative refunds above the original payment. File validation requires all refund originals in the same file; this is not a delta-feed or streaming importer.

A proposed export header can contain additional metadata such as `data_classification`, but the current importer checks the synthetic classification label but does not authenticate provenance, source signatures or production consent. Do not use this prototype as a data-loss-prevention boundary.

## Decisions needed from Indian Bank and its CBS integration team

Obtain the actual approved read-only interface, schema, permissions and sample payloads. Map real customer/account references and posting/value dates. Map debit/credit indicators, transaction codes, salary credits, own-account transfers, reversals, refunds, fees and cash withdrawals through an approved code dictionary. All these mappings remain unverified.

Handle joint accounts and customer entitlements explicitly; this prototype supports one owner per account. Define inter-account matching so own-account movements are not counted twice. Define currency handling (the prototype rejects non-INR), partial refunds and cross-account reversals, corrections, late arrivals, duplicate references and reconciliation. Determine statement completeness and update watermarks before enabling comparisons or financial forecasts.

Production ingestion should use Bank-controlled authentication, encryption, least-privilege access, consent, lineage, reconciliation and monitoring. A customer session must derive its scope from Bank SSO and account entitlements, never an arbitrary request field. Replace demo identities and filesystem imports with these approved services. Do not add credentials to source files or distribute them in this ZIP.

## Sample record

```json
{
  "id": "EXAMPLE-001",
  "customer_id": "CUST001",
  "account_id": "DEMO-CUST001",
  "posted_on": "2026-10-03",
  "direction": "DEBIT",
  "amount": "4200.00",
  "currency": "INR",
  "narration": "BIGBASKET / synthetic record",
  "merchant": "BIGBASKET",
  "kind": "PAYMENT"
}
```
