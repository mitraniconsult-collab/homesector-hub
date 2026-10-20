"""Optional remote archive for completed feed snapshots.

A long-running Render Free web service must NOT use local /tmp as permanent
storage. This module persists finished content to a configured HTTPS endpoint.
It does not create cloud resources, never embeds tokens in URLs or logs, and
fails closed when destination or credentials are missing.
"""
import hashlib
import json
import os
from urllib.parse import urlsplit
import requests

def archive_snapshot(xml_bytes, metadata, upload_url=None, bearer_token=None):
    upload_url = upload_url or os.getenv("FEED_ARCHIVE_UPLOAD_URL", "")
    bearer_token = bearer_token or os.getenv("FEED_ARCHIVE_BEARER_TOKEN", "")
    parsed = urlsplit(upload_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Persistent feed archive HTTPS upload URL is not configured")
    if not bearer_token:
        raise ValueError("Persistent feed archive authorization is not configured")
    if not isinstance(xml_bytes, bytes) or not xml_bytes.startswith(b"<?xml"):
        raise ValueError("Only completed XML exports can be archived")
    digest = hashlib.sha256(xml_bytes).hexdigest()
    response = requests.put(
        upload_url,
        data=xml_bytes,
        headers={
            "Authorization": "Bearer " + bearer_token,
            "Content-Type": "application/xml; charset=utf-8",
            "X-Content-SHA256": digest,
            "Cache-Control": "no-store",
        },
        timeout=120,
    )
    response.raise_for_status()
    # Return only non-sensitive verification details; calling code stores the
    # manifest in its own authorized status endpoint.
    return {
        "sha256": digest,
        "bytes": len(xml_bytes),
        "archive_status": "uploaded",
        "metadata": dict(metadata),
    }
