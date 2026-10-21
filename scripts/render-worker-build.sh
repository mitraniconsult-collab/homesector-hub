#!/usr/bin/env bash
# Rehydrate the versioned source snapshot and apply current worker changes.
set -euo pipefail
bundle=$(mktemp)
trap 'rm -f "$bundle"' EXIT
cat source-bundle/part-*.txt | base64 -d > "$bundle"
tar -xzf "$bundle"
test -f worker/app.py
cp -r patches/worker/. worker/
python -m compileall -q worker
python -m pip install -r worker/requirements.txt
PYTHONPATH=worker python -c 'from app import app; from image_jobs import IMAGE_JOBS; assert callable(IMAGE_JOBS.vendors)'
