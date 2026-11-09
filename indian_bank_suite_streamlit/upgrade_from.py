"""Copy a previous synthetic demo database into a clean v2 package without modifying the source."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from urllib.parse import quote


def upgrade(source, destination):
    source, destination = Path(source).expanduser().resolve(), Path(destination).resolve()
    if source.is_dir():
        if (source/'pfm.sqlite3').is_file(): source=source/'pfm.sqlite3'
        else: source=source/'runtime'/'pfm.sqlite3'
    if not source.is_file():
        raise ValueError('Previous pfm.sqlite3 was not found. Choose the old project folder or its runtime folder.')
    if destination.exists():
        raise ValueError('The destination already contains a database. Nothing was overwritten. Use a fresh v2 folder before first launch.')
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=destination.with_suffix('.upgrade-tmp')
    key_destination=destination.with_suffix('.audit-key')
    if temporary.exists() or key_destination.exists():
        raise ValueError('Destination contains previous upgrade files. Use a fresh v2 folder.')
    # SQLite backup gives a consistent copy. Stop the old server first to avoid missing later edits.
    try:
        with closing(sqlite3.connect('file:'+quote(str(source))+'?mode=ro',uri=True)) as old:
            tables={r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'cases' in tables and 'staff' in tables:
                raise ValueError('Choose the previous PFM database, not the operations workbench database.')
            if not {'goals','transactions','users'}.issubset(tables):
                raise ValueError('This is not a supported PFM demo database.')
            with closing(sqlite3.connect(temporary)) as new:
                old.backup(new)
        temporary.chmod(0o600)
        source_key=source.with_suffix('.audit-key')
        if source_key.exists():
            shutil.copyfile(source_key,key_destination)
            key_destination.chmod(0o600)
        from pfm.storage import Store
        # Promote only after the full backup succeeds. The original file is never changed.
        os.replace(temporary,destination)
        Store(destination)  # schema migration preserves IDs, amounts and goals
    except Exception:
        if temporary.exists(): temporary.unlink()
        raise
    return destination


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',help='Old project folder, runtime folder or pfm.sqlite3 path; synthetic demo data only.')
    args=parser.parse_args()
    try:
        result=upgrade(args.source,Path(__file__).resolve().parent/'runtime'/'pfm.sqlite3')
        print('Previous demo copied and migrated. Original files were unchanged.')
        print('Run: python3 -m pfm demo --open')
    except (ValueError,OSError,sqlite3.Error) as error:
        parser.exit(1,f'Upgrade stopped: {error}\n')


if __name__=='__main__': main()
