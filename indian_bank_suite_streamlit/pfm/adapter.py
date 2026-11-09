"""Read a proposed, normalized BaNCS export contract, never a live CBS API."""
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .security import has_sensitive

CATEGORIES = {'Food', 'Groceries', 'Shopping', 'Transport', 'Housing', 'Utilities',
              'Health', 'Education', 'Entertainment', 'Other', 'Income', 'Transfers'}


def paise(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError('Use a decimal string or integer for money, not a float.')
    if isinstance(value, str) and not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?', value):
        raise ValueError('Use a nonnegative decimal amount with at most two decimal places.')
    if isinstance(value, str) and len(value) > 20:
        raise ValueError('Amount is too long.')
    try:
        d = Decimal(value)
        if not d.is_finite() or d < 0 or d > Decimal('999999999.99'):
            raise ValueError('Amount outside supported range.')
        scaled = d * 100
        if scaled != scaled.to_integral_value():
            raise ValueError('INR amounts must have at most two decimal places.')
        return int(scaled)
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid monetary amount.') from None


def money(value):
    return f'{Decimal(value) / 100:.2f}'


@dataclass(frozen=True)
class Transaction:
    id: str
    customer_id: str
    account_id: str
    posted_on: str
    direction: str
    amount_paise: int
    narration: str
    merchant: str
    kind: str
    original_id: str | None


class BancsExportAdapter:
    """Contract version 1. Replace mapping only after Bank approves its CBS fields."""
    def read(self, path):
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(raw, dict) or type(raw.get('schema_version')) is not int or raw.get('schema_version') != 1:
            raise ValueError('Expected schema_version 1.')
        if raw.get('data_classification') != 'SYNTHETIC_DEMO_ONLY':
            raise ValueError('This local demo accepts only explicitly labelled synthetic exports.')
        rows = raw.get('transactions')
        if not isinstance(rows, list) or len(rows) > 100000:
            raise ValueError('transactions must be a list with at most 100000 rows.')
        result, seen = [], set()
        for row in rows:
            required = {'id', 'customer_id', 'account_id', 'posted_on', 'direction',
                        'amount', 'currency', 'narration', 'merchant', 'kind'}
            if not isinstance(row, dict) or not required.issubset(row):
                raise ValueError('A transaction is missing required fields.')
            for field in ('id', 'customer_id', 'account_id'):
                if not isinstance(row[field], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', row[field]):
                    raise ValueError(f'Invalid {field}.')
            if any(has_sensitive(row[field]) for field in ('id','customer_id','account_id')) or not row['account_id'].startswith('DEMO-'):
                raise ValueError('Export identifiers must be opaque synthetic references, not personal data.')
            if row['id'] in seen:
                raise ValueError('Duplicate transaction ID in export.')
            seen.add(row['id'])
            if row['currency'] != 'INR' or row['direction'] not in ('DEBIT', 'CREDIT'):
                raise ValueError('Only INR and DEBIT/CREDIT are supported.')
            if row['kind'] not in ('PAYMENT', 'INCOME', 'TRANSFER', 'REFUND'):
                raise ValueError('Invalid transaction kind.')
            if row['kind'] in ('INCOME', 'REFUND') and row['direction'] != 'CREDIT':
                raise ValueError('INCOME and REFUND must be credits.')
            if row['kind'] == 'PAYMENT' and row['direction'] != 'DEBIT':
                raise ValueError('PAYMENT must be a debit.')
            day = date.fromisoformat(row['posted_on'])
            if day.isoformat() != row['posted_on']:
                raise ValueError('Use YYYY-MM-DD dates.')
            for field in ('merchant', 'narration'):
                if not isinstance(row[field], str) or len(row[field]) > 500:
                    raise ValueError(f'Invalid {field}.')
                if has_sensitive(row[field]) or any(ord(c)<32 for c in row[field]):
                    raise ValueError('Personal or secret information is not allowed in demo transaction text.')
            original = row.get('original_id')
            if original is not None and (not isinstance(original, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', original)):
                raise ValueError('Invalid original_id.')
            if row['kind'] == 'REFUND' and (not isinstance(original, str) or not original):
                raise ValueError('A refund must reference its original payment.')
            result.append(Transaction(row['id'], row['customer_id'], row['account_id'],
                day.isoformat(), row['direction'], paise(row['amount']), row['narration'],
                row['merchant'], row['kind'], original))
        by_id = {t.id: t for t in result}
        totals = {}
        owners = {}
        for t in result:
            if t.account_id in owners and owners[t.account_id] != t.customer_id:
                raise ValueError('An account cannot belong to multiple customers.')
            owners[t.account_id] = t.customer_id
            if t.kind == 'REFUND':
                orig = by_id.get(t.original_id)
                if (not orig or orig.kind != 'PAYMENT' or orig.customer_id != t.customer_id
                    or orig.account_id != t.account_id or orig.posted_on > t.posted_on):
                    raise ValueError('Refund reference must be an earlier payment in the same customer account.')
                totals[orig.id] = totals.get(orig.id, 0) + t.amount_paise
                if totals[orig.id] > orig.amount_paise:
                    raise ValueError('Cumulative refunds exceed original payment.')
        return result
