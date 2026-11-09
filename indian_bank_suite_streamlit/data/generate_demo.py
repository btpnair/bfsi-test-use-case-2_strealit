"""Regenerate fictional fixtures; all identities, amounts and references are invented."""
import json
from pathlib import Path

rows = []
def add(uid, mon, day, label, amount, kind='PAYMENT', original=None):
    ident = f'TX-{uid[-3:]}-{mon.replace("-", "")}-{len(rows)+1:03}'
    row = dict(id=ident, customer_id=uid, account_id='DEMO-'+uid,
               posted_on=f'{mon}-{day:02}', direction='DEBIT' if kind=='PAYMENT' else 'CREDIT',
               amount=amount, currency='INR', narration=label+' / synthetic record',
               merchant=label, kind=kind)
    if original: row['original_id'] = original
    rows.append(row)
    return ident

for mon in ('2026-08', '2026-09', '2026-10'):
    add('CUST001',mon,1,'DEMO EMPLOYER SALARY','80000.00','INCOME')
    for day,merchant,amount in [(2,'RENT','18000.00'),(3,'BIGBASKET','4200.00'),
        (5,'AIRTEL','799.00'),(6,'NETFLIX','499.00'),(7,'SWIGGY','650.00'),
        (9,'IRCTC','1200.00'),(12,'TNEB ELECTRICITY','1800.00'),
        (14,'PHARMACY','850.00'),(16,'SCHOOL','4500.00'),
        (18,'DMART','3100.00'),(23,'UNKNOWN VENDOR','375.00')]:
        add('CUST001',mon,day,merchant,amount)
    purchase = add('CUST001',mon,20,'AMAZON','2500.00')
    add('CUST001',mon,25,'AMAZON REFUND','500.00','REFUND',purchase)
    add('CUST001',mon,26,'OWN ACCOUNT TRANSFER','10000.00','TRANSFER')
    if mon=='2026-10':
        add('CUST001',mon,27,'ZOMATO','850.00')
        add('CUST001',mon,29,'SWIGGY','700.00')
    add('CUST002',mon,1,'DEMO EMPLOYER SALARY','50000.00','INCOME')
    add('CUST002',mon,3,'RENT','12000.00')
    add('CUST002',mon,8,'DMART','2800.00')
    add('CUST002',mon,15,'JIO','399.00')
    add('CUST002',mon,21,'CAFE','400.00')
add('CUST001','2026-11',1,'DEMO EMPLOYER SALARY','80000.00','INCOME')
add('CUST001','2026-11',2,'RENT','18000.00')
add('CUST001','2026-11',5,'AIRTEL','799.00')
add('CUST002','2026-11',1,'DEMO EMPLOYER SALARY','50000.00','INCOME')
add('CUST002','2026-11',3,'RENT','12000.00')
Path(__file__).with_name('synthetic_bancs_export.json').write_text(
    json.dumps({'schema_version':1, 'data_classification':'SYNTHETIC_DEMO_ONLY',
                'note':'Proposed normalized adapter format, not an official TCS BaNCS schema.',
                'transactions':rows}, indent=2)+'\n')
print(f'Generated {len(rows)} synthetic transactions.')
