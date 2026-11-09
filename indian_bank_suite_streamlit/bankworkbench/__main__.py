import argparse
import json
import os
from pathlib import Path
import threading
import webbrowser
from .engine import WorkEngine
from .fixtures import MODULES
from .storage import WorkStore

ROOT=Path(__file__).resolve().parent.parent


def main():
 os.umask(0o077)
 parser=argparse.ArgumentParser(description='Synthetic banking operations suite; no live Bank actions.')
 parser.add_argument('--db',type=Path,default=ROOT/'runtime'/'workbench.sqlite3')
 parser.add_argument('--port',type=int,default=8770)
 parser.add_argument('--open',action='store_true')
 parser.add_argument('--module',choices=list(MODULES))
 parser.add_argument('--report',help='Print an internal synthetic report by case ID; local operator command.')
 args=parser.parse_args()
 try:
  store=WorkStore(args.db);store.seed();engine=WorkEngine(store)
  if args.report:
   print(json.dumps(engine.report('operator',args.report),indent=2));return
  if not 0<=args.port<=65535:parser.error('Port must be between 0 and 65535.')
  from .server import WorkServer
  try:server=WorkServer(args.port,engine)
  except OSError as error:
   if error.errno not in (48,98,10048):raise
   server=WorkServer(0,engine);print('Requested port busy; using a free loopback port.')
  url=f'http://127.0.0.1:{server.server_port}/'+('?module='+args.module if args.module else '')
  print('SYNTHETIC BANKING WORKBENCH — no live CBS, registry, CRM, messaging, refund or FIU connection.\n'+url+'\nOperator: operator / Operator-2026!\nIndependent reviewer: reviewer / Reviewer-2026!\nRM: relationship / Manager-2026!\nCompliance: compliance / Compliance-2026!\nPress Control+C to stop.',flush=True)
  if args.open:threading.Timer(.5,lambda:webbrowser.open(url)).start()
  try:server.serve_forever()
  except KeyboardInterrupt:print('\nStopped.')
  finally:server.server_close()
 except (ValueError,OSError) as error:parser.exit(1,f'Error: {error}\n')


if __name__=='__main__':main()
