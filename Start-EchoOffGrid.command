#!/bin/bash
set -eu
cd "$(dirname "$0")"
# Release packages already include the archive. Source checkouts cache it once.
python3 prepare-starter-wiki.py dist/reference
exec python3 dashboard.py "$@"
