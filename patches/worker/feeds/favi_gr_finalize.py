"""Checkpointed GR translation and URL verification before XML serialization.

Every completed batch is fsynced to the same generation as its source journal.
Yielding never writes a partial XML or changes a public Blob pointer.
"""
import hashlib
import json
import os
import time
from pathlib import Path

from .favi_gr_collection_urls import verify_collection_urls
from .favi_gr_urls import verify_market_urls
from .favi_url_eligibility import has_localized_copy, reusable_urls
from .shopify_auth import get_admin_token
from .shopify_translations import fetch_translations, fetch_variant_translations

VERSION = 2
TRANSLATION_BATCH = 50
URL_BATCH = 20
VARIANT_BATCH = 50
STAGES = ("translations", "direct_urls", "collections", "variants", "ready")


def _save(path, state):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, separators=(",", ":"))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary, path)


def _fingerprint(journal, products, categories, manual_urls):
    meta = json.loads(journal.manifest.read_text(encoding="utf-8"))
    source = [meta["bytes"], meta["items"], meta["products"]]
    selected = [(p["id"], p.get("handle"), categories[p["id"]])
                for p in products if p["id"] in categories]
    encoded = json.dumps([VERSION, source, selected, sorted(manual_urls)], sort_keys=True,
                         ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _initial(fingerprint):
    return {
        "version": VERSION, "fingerprint": fingerprint,
        "stage": "translations", "next_index": 0,
        "translated_map": {}, "auto_urls": {}, "collection_urls": {},
        "translated_variant_map": {},
        "url_check": {"checked": 0, "verified": 0, "reasons": {}, "sample_handles": {}},
        "collection_check": {"checked": 0, "verified": 0, "without_collection": 0},
    }


def _advance(path, state, stage):
    state["stage"] = stage
    state["next_index"] = 0
    _save(path, state)


def _accumulate(check, batch, keys):
    for key in keys:
        check[key] += batch.get(key, 0)


def _variant_ids(products, verified_ids):
    return list(dict.fromkeys(
        v["id"] for product in products if product["id"] in verified_ids
        for v in (product.get("variants") or {}).get("nodes", [])
        if v.get("id") and v.get("selectedOptions")
    ))


def collect(journal, products, categories, manual_urls, store, token, deadline, should_stop):
    if not store:
        store = os.getenv("SHOPIFY_STORE", "")
    if not store.endswith(".myshopify.com") or "/" in store:
        raise ValueError("Invalid Shopify hostname")
    path = Path(journal.root) / "favi-gr-finalize-checkpoint.json"
    fingerprint = _fingerprint(journal, products, categories, manual_urls)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if (not isinstance(state, dict) or state.get("version") != VERSION
            or state.get("fingerprint") != fingerprint):
        state = _initial(fingerprint)
        _save(path, state)
    if (state.get("stage") not in STAGES or not isinstance(state.get("next_index"), int)
            or state["next_index"] < 0):
        raise RuntimeError("Invalid GR finalize checkpoint")
    candidates = [p for p in products if p["id"] in categories]
    ids = [p["id"] for p in candidates]
    reused_direct, reused_collection = reusable_urls(
        journal, candidates, state["translated_map"], "GR")
    def yielding():
        return should_stop() or time.time() >= deadline
    def paused():
        return {"status": "yielded", "stage": state["stage"]}

    while state["stage"] != "ready":
        if yielding():
            return paused()
        stage = state["stage"]
        index = state["next_index"]
        if stage == "translations":
            if index >= len(ids):
                _advance(path, state, "direct_urls")
                reused_direct, reused_collection = reusable_urls(
                    journal, candidates, state["translated_map"], "GR")
                continue
            batch = ids[index:index + TRANSLATION_BATCH]
            values = fetch_translations(batch, store=store, token=token, market="GR")
            if set(values) != set(batch):
                raise RuntimeError("Incomplete GR translation batch")
            state["translated_map"].update(values)
            state["next_index"] += len(batch)
        elif stage == "direct_urls":
            if index >= len(candidates):
                _advance(path, state, "collections")
                continue
            batch = candidates[index:index + URL_BATCH]
            eligible = [p for p in batch if has_localized_copy(
                state["translated_map"], p["id"], "GR")]
            cached = {p["id"]: reused_direct[p["id"]] for p in eligible
                      if p["id"] in reused_direct}
            remaining = [p for p in eligible if p["id"] not in cached]
            urls, check = verify_market_urls(
                remaining, categories, translated_map=state["translated_map"])
            if check["checked"] != len(remaining):
                raise RuntimeError("Incomplete GR direct URL batch")
            skipped = len(batch) - len(eligible)
            check["checked"] += skipped + len(cached)
            check["verified"] += len(cached)
            check["reasons"]["verified_reused"] = (
                check["reasons"].get("verified_reused", 0) + len(cached))
            check["reasons"]["skipped_unlocalized_copy"] = (
                check["reasons"].get("skipped_unlocalized_copy", 0) + skipped)
            state["auto_urls"].update(cached)
            state["auto_urls"].update(urls)
            aggregate = state["url_check"]
            _accumulate(aggregate, check, ("checked", "verified"))
            for reason, count in check["reasons"].items():
                aggregate["reasons"][reason] = aggregate["reasons"].get(reason, 0) + count
            for reason, handles in check.get("sample_handles", {}).items():
                sample = aggregate["sample_handles"].setdefault(reason, [])
                sample.extend(handles[:max(0, 3 - len(sample))])
            state["next_index"] += len(batch)
        elif stage == "collections":
            missing = [p for p in candidates if p["id"] not in state["auto_urls"]
                       and has_localized_copy(state["translated_map"], p["id"], "GR")]
            if index >= len(missing):
                _advance(path, state, "variants")
                continue
            batch = missing[index:index + URL_BATCH]
            cached = {p["id"]: reused_collection[p["id"]] for p in batch
                      if p["id"] in reused_collection}
            remaining = [p for p in batch if p["id"] not in cached]
            urls, check = verify_collection_urls(
                remaining, set(), store, token or get_admin_token(store))
            check["checked"] += len(cached)
            check["verified"] += len(cached)
            state["collection_urls"].update(cached)
            state["collection_urls"].update(urls)
            _accumulate(state["collection_check"], check,
                        ("checked", "verified", "without_collection"))
            state["next_index"] += len(batch)
        elif stage == "variants":
            verified = set(manual_urls) | set(state["auto_urls"]) | set(state["collection_urls"])
            variants = _variant_ids(candidates, verified)
            if index >= len(variants):
                _advance(path, state, "ready")
                continue
            batch = variants[index:index + VARIANT_BATCH]
            values = fetch_variant_translations(batch, "GR", store=store, token=token)
            if set(values) != set(batch):
                raise RuntimeError("Incomplete GR variant translation batch")
            state["translated_variant_map"].update(values)
            state["next_index"] += len(batch)
        _save(path, state)
        print("[favi-gr-finalize] stage=" + stage +
              " checked=" + str(state["next_index"]), flush=True)
    if yielding():
        return paused()
    missing = [p for p in candidates if p["id"] not in state["auto_urls"]
               and has_localized_copy(state["translated_map"], p["id"], "GR")]
    variants = _variant_ids(candidates, set(manual_urls) | set(state["auto_urls"]) |
                            set(state["collection_urls"]))
    if (set(state["translated_map"]) != set(ids)
            or state["url_check"]["checked"] != len(ids)
            or state["collection_check"]["checked"] +
               state["collection_check"]["without_collection"] != len(missing)
            or set(state["translated_variant_map"]) != set(variants)):
        raise RuntimeError("Incomplete GR finalize checkpoint")
    return {**state, "status": "ready"}
