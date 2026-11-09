"""Application guardrails for a local synthetic-data prototype, not a DLP product."""
import re
import unicodedata

POLICY_VERSION = 'privacy-v2-2026-11'
PII_PATTERNS = (
    re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', re.I),  # PAN-like token
    re.compile(r'(?<![\w-])(?:[0-9][ -]?){11,18}[0-9](?![\w-])'),  # long account/card/Aadhaar-like numbers
    re.compile(r'(?<!\w)(?:\+91[ -]?)?[6-9][0-9]{9}(?!\w)'),
    re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.I),
    re.compile(r'\b[\w.-]+@(?:upi|ybl|ok\w*|paytm|ibl|axl)\b', re.I),
    re.compile(r'\b(?:otp|pin|cvv|password|passcode)\s*(?:is\s*|[:=]\s*|\s+)[A-Za-z0-9!@#$%^&*_-]{3,}', re.I),
    re.compile(r'\b(?:account|a/c|aadhaar|aadhar|card|mobile|phone)\s*(?:number|no\.?)?\s*[:=]?\s*[0-9][0-9 -]{5,}', re.I),
)
PII_MESSAGE = 'Please remove personal or secret information. Do not enter PAN, Aadhaar, account/card numbers, mobile numbers, email, OTP, PIN or passwords.'


class ValidationError(ValueError):
    def __init__(self, fields):
        self.fields = fields
        super().__init__('Please check the highlighted fields.')


class ConflictError(ValueError):
    pass


class NotFoundError(ValueError):
    pass


def has_sensitive(text):
    return isinstance(text, str) and any(p.search(text) for p in PII_PATTERNS)


def redact(text):
    text = str(text)
    for pattern in PII_PATTERNS:
        text = pattern.sub('[REDACTED]', text)
    return ''.join(c for c in text if unicodedata.category(c) not in ('Cc', 'Cf'))[:500]


def check_text(value, field, maximum=80, name=False):
    if not isinstance(value, str):
        raise ValidationError({field: 'Enter text.'})
    if any(unicodedata.category(c) in ('Cc','Cf') for c in value):
        raise ValidationError({field: 'Control characters and hidden formatting are not allowed.'})
    value = unicodedata.normalize('NFKC', value)
    value = ' '.join(value.split())
    if not 1 <= len(value) <= maximum:
        raise ValidationError({field: f'Enter between 1 and {maximum} characters.'})
    if '<' in value or '>' in value:
        raise ValidationError({field: 'HTML and script markup are not allowed.'})
    if has_sensitive(value):
        raise ValidationError({field: PII_MESSAGE})
    if name and not any(unicodedata.category(c).startswith('L') for c in value):
        raise ValidationError({field: 'Use a descriptive goal name with at least one letter.'})
    return value


def masked(value):
    return '•••• ' + str(value)[-4:]


def strict_fields(data, allowed, required=()):
    if not isinstance(data, dict) or set(data) - set(allowed):
        raise ValidationError({'request': 'Unexpected request fields.'})
    missing = set(required) - set(data)
    if missing:
        raise ValidationError({key: 'This field is required.' for key in sorted(missing)})
