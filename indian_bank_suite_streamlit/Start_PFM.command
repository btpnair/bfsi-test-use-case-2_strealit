#!/bin/zsh
set -eu
cd -- "${0:A:h}"
if ! command -v python3 >/dev/null 2>&1; then
  print 'Install Python 3.10 or later from https://www.python.org/downloads/macos/ and retry.'
  read 'reply?Press Return to close.'
  exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else "Python 3.10+ is required.")'
python3 -m pfm demo --open
