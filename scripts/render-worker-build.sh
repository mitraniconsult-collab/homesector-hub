#!/usr/bin/env bash
# Render build: unpack the source snapshot, apply tracked worker overlays,
# install dependencies, and fail fast if Feed Manager isn't importable.
set -euo pipefail
cat source-bundle/part-*.txt > /tmp/homesector-source.b64
python -c "import base64;open('/tmp/homesector-source.tar.gz','wb').write(base64.b64decode(open('/tmp/homesector-source.b64','rb').read()))"
tar -xzf /tmp/homesector-source.tar.gz
test -f worker/app.py
test -d patches/worker
cp -r patches/worker/. worker/
python -m compileall -q worker
python -c "import sys;sys.path.insert(0,'worker');from feeds.api import router;assert router.prefix == '/feeds'"
python -m pip install --upgrade pip
python -m pip install -r worker/requirements.txt
