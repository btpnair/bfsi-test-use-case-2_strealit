import json
import math
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from .adapter import CATEGORIES, money, paise
from .security import ValidationError, ConflictError, check_text, redact


class Engine:
    def __init__(self, store, rules_path, today=None):
        self.store = store
        self.today = today or date.today()
        self.rules = json.loads(Path(rules_path).read_text())
        for rule in self.rules['rules']:
            if rule['category'] not in CATEGORIES or not rule['tokens']:
                raise ValueError('Invalid category rules.')

    def categorized(self, uid):
        rows = self.store.transactions(uid)
        by_id = {r['id']: r for r in rows}
        def classify(t):
            if t['kind'] == 'TRANSFER':
                return 'Transfers', 'explicit transfer flag', 1.0
            if t['kind'] == 'INCOME':
                return 'Income', 'explicit income flag', 1.0
            if t['kind'] == 'REFUND':
                orig = by_id.get(t['original_id'])
                if not orig:
                    return 'Other', 'missing original payment; review required', 0.0
                cat, _, confidence = classify(orig)
                return cat, 'refund of ' + orig['id'], confidence
            text = t['merchant'] + ' ' + t['narration']
            for rule in self.rules['rules']:
                for token in rule['tokens']:
                    if re.search(r'(?<!\w)' + re.escape(token) + r'(?!\w)', text, re.I):
                        return rule['category'], 'matched ' + token, 0.8
            return 'Other', 'no matching rule; review required', 0.0
        for t in rows:
            category, reason, confidence = classify(t)
            t.update(category=category, reason=reason, confidence=confidence,
                     amount=money(t['amount_paise']))
        return rows

    def summary(self, uid, month):
        if not re.fullmatch(r'\d{4}-\d{2}', month):
            raise ValueError('Use YYYY-MM month.')
        date.fromisoformat(month + '-01')
        rows = [t for t in self.categorized(uid) if t['posted_on'].startswith(month)]
        categories, income, refunds, gross = {}, 0, 0, 0
        for t in rows:
            amt = t['amount_paise']
            if t['kind'] == 'INCOME':
                income += amt
            elif t['kind'] == 'PAYMENT':
                gross += amt
                categories[t['category']] = categories.get(t['category'], 0) + amt
            elif t['kind'] == 'REFUND':
                refunds += amt
                categories[t['category']] = categories.get(t['category'], 0) - amt
        net = gross - refunds
        return {'month': month, 'income': money(income), 'gross_spend': money(gross),
                'refunds': money(refunds), 'net_spend': money(net),
                'surplus': money(income - net),
                'savings_rate_pct': round((income-net) / income * 100, 2) if income else None,
                'categories': {c: money(v) for c, v in sorted(categories.items())},
                'transaction_count': len(rows), 'evidence_ids': [t['id'] for t in rows],
                'coverage': 'Imported posted transactions only; full calendar month bucket, possibly incomplete. Transfers excluded. Surplus is cash flow, not account balance.'}

    def goal_views(self, uid, include_archived=False):
        result = []
        for g in self.store.goals(uid, include_archived):
            due = date.fromisoformat(g['due_on'])
            remaining = max(0, g['target_paise'] - g['saved_paise'])
            # Contributions at each month-end including the deadline month (demo convention).
            months = (due.year-self.today.year)*12 + due.month-self.today.month + 1
            overdue = due < self.today and remaining > 0
            monthly = None if overdue else (remaining + max(1, months) - 1) // max(1, months)
            result.append({**g, 'name': redact(g['name']), 'status': ('archived' if g['archived'] else 'completed' if remaining == 0 else 'overdue' if overdue else 'active'), 'target': money(g['target_paise']), 'saved': money(g['saved_paise']),
                           'monthly_needed': None if monthly is None else money(monthly),
                           'overdue': overdue, 'progress_pct': min(100, round(g['saved_paise']/g['target_paise']*100, 1))})
        return result

    def validate_goal(self, uid, name, target, saved, due, ident=None):
        errors = {}
        try:
            name = check_text(name, 'name', 60, name=True)
        except ValidationError as error:
            errors.update(error.fields)
        for field, value in [('target',target),('saved',saved)]:
            try:
                amount = paise(value)
                if amount > 1000000000 or (field == 'target' and amount == 0):
                    raise ValueError()
                if field == 'target':
                    target = amount
                else:
                    saved = amount
            except (ValueError, TypeError):
                errors[field] = 'Enter a valid INR amount up to 1,00,00,000 with at most two decimals.' + (' Target must be greater than zero.' if field == 'target' else '')
        if 'target' not in errors and 'saved' not in errors and saved > target:
            errors['saved'] = 'Already saved cannot exceed the target.'
        try:
            deadline = date.fromisoformat(due)
            if deadline.isoformat() != due:
                raise ValueError()
            if deadline < self.today:
                # Existing overdue goals may retain their unchanged deadline when updating saved progress.
                original = self.store.goal(uid,ident) if ident else None
                if not original or original['due_on'] != due:
                    errors['due_on'] = 'Choose today or a future deadline.'
            if deadline.year > self.today.year + 10:
                errors['due_on'] = 'Choose a deadline within the next 10 calendar years.'
        except (ValueError, TypeError):
            errors['due_on'] = 'Enter a valid date in YYYY-MM-DD format.'
        if 'name' not in errors:
            active = self.store.goals(uid)
            if any(g['id'] != ident and ' '.join(g['name'].split()).casefold() == name.casefold() for g in active):
                errors['name'] = 'You already have an active goal with this name.'
            if len([g for g in active if g['id'] != ident]) >= 20:
                errors['name'] = 'You can keep up to 20 active goals. Archive a goal first.'
        if errors:
            raise ValidationError(errors)
        return {'name':name,'target':money(target),'saved':money(saved),'due_on':deadline.isoformat()}

    def add_goal(self, uid, name, target, saved, due):
        valid = self.validate_goal(uid,name,target,saved,due)
        return self.store.save_goal(uid,valid['name'],paise(valid['target']),paise(valid['saved']),valid['due_on'])

    def edit_goal(self, uid, ident, version, name, target, saved, due):
        self.store.goal(uid, ident)  # ownership checked before parsing or changing any data
        if type(version) is not int or version < 1:
            raise ValidationError({'version':'Refresh the goal and try again.'})
        valid = self.validate_goal(uid,name,target,saved,due,ident)
        return self.store.save_goal(uid,valid['name'],paise(valid['target']),paise(valid['saved']),valid['due_on'],ident,version)

    def archive_goal(self, uid, ident, version, archived):
        if type(version) is not int or version < 1 or type(archived) is not bool:
            raise ValidationError({'request':'Invalid goal action.'})
        goal = self.store.goal(uid,ident)
        return self.store.save_goal(uid,goal['name'],goal['target_paise'],goal['saved_paise'],goal['due_on'],ident,version,int(archived))

    def recurring(self, uid):
        # Heuristic candidates: same merchant/category, >=3 months, amounts within 10%.
        groups = {}
        for t in self.categorized(uid):
            if t['kind'] == 'PAYMENT' and t['merchant'].strip():
                key = (t['merchant'].casefold().strip(), t['category'])
                groups.setdefault(key, []).append(t)
        found = []
        for (_, category), rows in groups.items():
            amounts = [r['amount_paise'] for r in rows]
            if len({r['posted_on'][:7] for r in rows}) >= 3 and max(amounts) <= min(amounts)*1.1:
                found.append({'merchant': rows[0]['merchant'], 'category': category,
                              'typical_amount': money(sum(amounts)//len(amounts)),
                              'evidence_ids': [r['id'] for r in rows],
                              'label': 'Possible recurring payment; heuristic, confirm manually.'})
        return found

    def dashboard(self, uid, month):
        summary = self.summary(uid, month)
        year, mon = map(int, month.split('-'))
        prev = f'{year-1}-12' if mon == 1 else f'{year}-{mon-1:02}'
        previous = self.summary(uid, prev)
        nudges = []
        if summary['transaction_count'] == 0:
            nudges.append('No imported transactions for this month. Import a complete statement before drawing conclusions.')
        else:
            surplus = int(Decimal(summary['surplus']) * 100)
            if surplus < 0:
                nudges.append('Recorded outflows exceed recorded income. Review flexible spending and statement coverage.')
            if 'Other' in summary['categories']:
                nudges.append('Some payments need category review. Check the Other category before relying on totals by category.')
            if self.goal_views(uid):
                nudges.append('Review your monthly goal contribution against available cash flow; no money will be moved.')
            else:
                nudges.append('Set a savings goal with an amount and deadline to estimate a monthly contribution.')
        return {'customer_id': uid, 'demo': True, 'as_of': self.today.isoformat(),
                'engine': 'Explainable rules and intent templates; no trained ML model or LLM.',
                'summary': summary, 'previous_month': previous, 'goals': self.goal_views(uid),
                'archived_goals': [g for g in self.goal_views(uid,True) if g['archived']],
                'available_months': sorted({r['posted_on'][:7] for r in self.store.transactions(uid)}, reverse=True),
                'recurring': self.recurring(uid), 'nudges': nudges,
                'transactions': [t for t in self.categorized(uid) if t['posted_on'].startswith(month)]}

    def chat(self, uid, text, month):
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000:
            raise ValueError('Enter 1–1000 characters.')
        # Structured goal commands are validated per field below; ordinary chat is screened in full.
        if not text.strip().lower().startswith('create goal '):
            text = check_text(text, 'message', 1000)
        q = text.strip().lower()
        if any(term in q for term in ('ignore previous', 'system prompt', 'bypass guard', 'other customer', 'cust002', 'cust001', 'show all accounts', 'run sql', 'drop table')):
            self.store.audit(uid,'guardrail_block',{'rule':'scope_or_instruction'})
            return {'answer':'I can help only with your own spending and savings goals. I cannot reveal other customers, internal instructions or run commands.', 'month':month, 'evidence_ids':[], 'method':'Scope guardrail', 'safe_message':text}
        # Explicit month wins; relative follow-ups use the selected dashboard month.
        explicit = re.search(r'\b(\d{4}-\d{2})\b', q)
        if explicit:
            month = explicit.group(1)
        elif 'last month' in q:
            y, m = map(int, month.split('-'))
            month = f'{y-1}-12' if m == 1 else f'{y}-{m-1:02}'
        s = self.summary(uid, month)
        evidence, topic = s['evidence_ids'], 'summary'
        categories = [c for c in sorted(CATEGORIES - {'Income', 'Transfers'}) if re.search(r'\b' + re.escape(c.lower()) + r'\b', q)]
        if q.startswith('create goal '):
            # Deliberately explicit command; no inferred financial mutation.
            parts = text[len('create goal '):].split('|')
            if len(parts) != 4:
                raise ValueError('Use: create goal Name | target INR | saved INR | YYYY-MM-DD')
            name, target, saved, due = [p.strip() for p in parts]
            draft = self.validate_goal(uid,name,target,saved,due)
            return {'answer':'Please review and confirm this goal in the goal form. Nothing has been saved yet.',
                    'month':month, 'evidence_ids':[], 'method':'Goal review required', 'safe_message':'Create a savings goal', 'goal_draft':draft}
        elif any(w in q for w in ('transfer money', 'pay bill', 'send money', 'buy stock', 'invest for me')):
            answer = 'This demonstration cannot initiate financial transactions. Use an authorised Bank channel.'
            evidence = []
        elif 'goal' in q:
            goals = self.goal_views(uid)
            answer = '\n'.join(f"{g['name']}: INR {g['saved']} of INR {g['target']}; " +
                ('overdue, revise the plan.' if g['overdue'] else f"estimated monthly contribution INR {g['monthly_needed']}.") for g in goals)
            if not answer:
                has_archived = any(g['archived'] for g in self.store.goals(uid,True))
                answer = 'You have no active goals. Your archived goals are available in Savings goals.' if has_archived else 'You have no saved goals.'
            topic, evidence = 'goals', []
        elif 'recurring' in q or 'subscription' in q:
            items = self.recurring(uid)
            answer = '\n'.join(f"Possible recurring payment: {r['merchant']}, about INR {r['typical_amount']}." for r in items) or 'Not enough repeated history to identify recurring candidates (at least three months required).'
            evidence = [i for r in items for i in r['evidence_ids']]
            topic = 'recurring'
        elif categories or (q in ('and last month?', 'last month?', 'and last month', 'last month') and self.store.topic(uid).startswith('category:')):
            cat = categories[0] if categories else self.store.topic(uid).split(':', 1)[1]
            amount = s['categories'].get(cat, '0.00')
            answer = f'{month}: net {cat} spending is INR {amount}, including posted linked refunds. Transfers and income are excluded.'
            evidence = [t['id'] for t in self.categorized(uid) if t['posted_on'].startswith(month) and t['category'] == cat and t['kind'] in ('PAYMENT', 'REFUND')]
            topic = 'category:' + cat
        elif any(w in q for w in ('spend', 'saving', 'summary', 'income', 'surplus', 'last month', 'balance')):
            answer = (f"{month}: recorded income INR {s['income']}; net spending INR {s['net_spend']}; "
                      f"cash-flow surplus INR {s['surplus']}. This is not an account balance. Transfers are excluded.")
        elif any(w in q for w in ('recommend', 'advice', 'wellness', 'product')):
            answer = ('Review recurring charges and build an emergency savings goal from your recorded cash flow. '
                      'Ask the Bank about a savings or recurring-deposit option only after checking eligibility, current terms, liquidity and suitability. '
                      'No approved product catalogue or rates were supplied, so no product ranking or return is asserted.')
            evidence, topic = [], 'guidance'
        else:
            answer = ('I can show spending, income, savings, a category, goals or recurring payments. '
                      'Try "Food spending", "and last month?", or "show my goals". '
                      'This is a deterministic English-language demonstration.')
            evidence, topic = [], self.store.topic(uid)
        if s['transaction_count'] == 0 and topic not in ('goals', 'guidance', 'recurring'):
            answer = f'No imported transaction data for {month}. Zero totals do not establish that no activity occurred.'
            evidence = []
        self.store.topic(uid, topic)
        self.store.audit(uid, 'chat', {'topic': topic, 'month': month, 'evidence_count': len(evidence)})
        return {'answer': answer, 'month': month, 'evidence_ids': evidence,
                'method': 'Deterministic intent routing with database evidence; no external AI call.', 'safe_message': redact(text)}
