"""Keep storefront requests for products that can pass the locale gate."""
import json
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

REUSE_MAX_AGE_SECONDS = 12 * 3600


def has_localized_copy(translated_map, product_id, market):
    entries = (translated_map.get(product_id) or {}).get(market) or []
    values = {entry.get("key"): str(entry.get("value") or "").strip()
              for entry in entries if isinstance(entry, dict)}
    return bool(values.get("title") and values.get("body_html"))


def reusable_urls(journal, products, translated_map, market):
    """Reuse only recent positive URL proofs for the same ID and current handle."""
    root = Path(journal.root)
    paths = sorted(root.parent.parent.glob("*/favi-*-source/favi-*-finalize-checkpoint.json"),
                   key=lambda path: path.stat().st_mtime, reverse=True)
    direct, collections = {}, {}
    by_id = {p["id"]: p for p in products}
    domain = "homesector." + market.lower()
    for path in paths:
        if path.parent == root or path.name != f"favi-{market.lower()}-finalize-checkpoint.json":
            continue
        manifest = path.parent / "manifest.json"
        if (not manifest.exists() or time.time() - manifest.stat().st_mtime >
                REUSE_MAX_AGE_SECONDS):
            continue
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        direct_old = state.get("auto_urls" if market == "GR" else "verified_urls") or {}
        for target, old in ((direct, direct_old),
                            (collections, state.get("collection_urls") or {})):
            for pid, url in old.items():
                product = by_id.get(pid)
                if not product or pid in target or not isinstance(url, str):
                    continue
                parsed = urlparse(url)
                source = str(product.get("handle") or "")
                translated = [str(entry.get("value") or "").strip() for entry in
                              (translated_map.get(pid) or {}).get(market, [])
                              if entry.get("key") == "handle"]
                path_value = unquote(parsed.path).rstrip("/")
                handles = [source] + translated if target is direct else [source]
                if (parsed.scheme == "https" and parsed.hostname == domain
                        and not parsed.port and not parsed.username and not parsed.password
                        and not parsed.query and not parsed.fragment
                        and any(handle and (
                            path_value.endswith("/products/" + handle)
                            if target is collections else path_value == "/products/" + handle)
                            for handle in handles)
                        and (path_value.startswith("/collections/") if target is collections
                             else path_value.startswith("/products/"))):
                    target[pid] = url
    return direct, collections
