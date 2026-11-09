#!/bin/zsh
set -eu
cd -- "${0:A:h}"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else "Python 3.10+ is required.")'
python3 -m bankworkbench --open
