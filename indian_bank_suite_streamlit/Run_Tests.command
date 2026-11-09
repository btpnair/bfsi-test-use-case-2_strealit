#!/bin/zsh
set -eu
cd -- "${0:A:h}"
python3 -m compileall -q pfm bankworkbench tests data upgrade_from.py
python3 -m unittest discover -s tests -v
print '\nTests complete.'
