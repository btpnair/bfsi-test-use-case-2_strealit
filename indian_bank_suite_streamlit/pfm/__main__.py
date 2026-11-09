import argparse
import json
import os
import threading
import webbrowser
from datetime import date
from pathlib import Path
from .adapter import BancsExportAdapter
from .engine import Engine
from .storage import Store

ROOT = Path(__file__).resolve().parent.parent


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description='Local PFM prototype with synthetic data; no bank connectivity.')
    parser.add_argument('command', choices=['demo', 'import-export', 'report'])
    parser.add_argument('--db', type=Path, default=ROOT/'runtime'/'pfm.sqlite3')
    parser.add_argument('--export', type=Path, help='Normalized JSON export (not raw TCS BaNCS data).')
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--open', action='store_true', help='Open local dashboard in the default browser.')
    parser.add_argument('--customer', default='CUST001')
    parser.add_argument('--month', default='2026-10')
    parser.add_argument('--as-of', default='2026-11-06', help='Demo business date for goal projections.')
    args = parser.parse_args()
    try:
        store = Store(args.db)
        if args.command == 'import-export':
            if not args.export:
                parser.error('import-export requires --export PATH')
            rows = BancsExportAdapter().read(args.export)
            store.import_transactions(rows)
            store.audit('LOCAL_OPERATOR', 'export_import', {'record_count': len(rows)})
            print(f'Validated {len(rows)} records; imported new IDs atomically. Existing identical IDs are skipped.')
            return
        if args.command == 'demo':
            rows = BancsExportAdapter().read(ROOT/'data'/'synthetic_bancs_export.json')
            store.import_transactions(rows)
            store.seed_demo_users()
        engine = Engine(store, ROOT/'data'/'category_rules.json', date.fromisoformat(args.as_of))
        if args.command == 'report':
            print(json.dumps(engine.dashboard(args.customer, args.month), indent=2))
            return
        from .server import DemoServer
        if not 0 <= args.port <= 65535:
            parser.error('--port must be between 0 and 65535')
        try:
            server = DemoServer(args.port, engine, args.db.parent/'SERVICE_DISABLED')
        except OSError as error:
            if error.errno not in (48,98,10048):
                raise
            server = DemoServer(0, engine, args.db.parent/'SERVICE_DISABLED')
            print('Requested port is busy. A free local port has been selected automatically.')
        url = f'http://127.0.0.1:{server.server_port}'
        print(f'SYNTHETIC DATA DEMO — no connection to Indian Bank or TCS BaNCS\n{url}\nBusiness date: {engine.today}\nCUST001 / demo-1234 or CUST002 / demo-5678\nPress Ctrl+C to stop.', flush=True)
        if args.open:
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\nStopped.')
        finally:
            server.server_close()
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    main()
