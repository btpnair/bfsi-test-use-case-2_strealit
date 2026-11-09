# Upgrade from the previous local demo

Keep the old project folder as a fallback. Stop both servers with Control+C. Extract the complete v2 ZIP into a new folder. Before its first launch, run from the new project root:

```sh
python3 upgrade_from.py "/full/path/to/old/project"
python3 -m pfm demo --open
```

The source may be the old project folder, runtime folder or pfm.sqlite3 file. Quote spaces; dragging the folder from Finder supplies its path. Migrate synthetic demo data only.

The script opens the source read-only and takes a consistent SQLite backup into the new runtime folder. It preserves goals/progress and migrates their schema. If an audit key exists, it is copied with owner-only permissions. Legacy audit subjects are pseudonymized and old password hashes upgrade on successful login. The original source is never modified. The script refuses to overwrite a destination database. If v2 was already launched, use another fresh extraction.

If migration fails after the backup is promoted, the source is still safe. Use a fresh extraction to retry. Keep the original folder until you have verified the goals in v2.

V2 defaults to port 8767. If busy, an OS-selected free port is printed. Always open the exact URL printed by the new Terminal process; an old 8765/8766 tab can still show the previous application.
