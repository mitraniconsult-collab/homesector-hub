"""Incremental RO translation and landing URL verification on durable disk."""
import hashlib
import json
import os
import time
from pathlib import Path

from .favi_gr_urls import verify_market_urls
from .favi_gr_collection_urls import verify_collection_urls
from .shopify_translations import fetch_translations, fetch_variant_translations

VERSION = 1


def _save(path, state):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, separators=(",", ":"))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary, path)


def collect(journal, products, categories, store, token, deadline, should_stop):
    meta = json.loads(journal.manifest.read_text(encoding="utf-8"))
    selected = [(p["id"], p.get("handle"), categories[p["id"]])
                for p in products if p["id"] in categories]
    fingerprint = hashlib.sha256(json.dumps(
        [VERSION, meta["bytes"], meta["items"], selected],
        ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    path = Path(journal.root) / "favi-ro-finalize-checkpoint.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if not isinstance(state, dict) or state.get("fingerprint") != fingerprint:
        state = {"fingerprint": fingerprint, "stage": "translations", "next_index": 0,
                 "translated_map": {}, "verified_urls": {}, "collection_urls": {},
                 "collection_check": {"checked": 0, "verified": 0, "without_collection": 0},
                 "variant_map": {},
                 "url_check": {"checked": 0, "verified": 0,
                               "reasons": {}, "sample_handles": {}}}
        _save(path, state)
    candidates = [p for p in products if p["id"] in categories]
    ids = [p["id"] for p in candidates]

    def advance(stage):
        state.update(stage=stage, next_index=0)
        _save(path, state)

    while state["stage"] != "ready":
        if should_stop() or time.time() >= deadline:
            return {"status": "yielded", "stage": state["stage"]}
        stage, index = state["stage"], state["next_index"]
        if stage == "translations":
            if index >= len(ids):
                advance("urls")
                continue
            batch = ids[index:index + 50]
            state["translated_map"].update(fetch_translations(
                batch, store=store, token=token, market="RO"))
        elif stage == "urls":
            if index >= len(candidates):
                advance("collections")
                continue
            batch = candidates[index:index + 20]
            urls, check = verify_market_urls(
                batch, categories, translated_map=state["translated_map"], market="RO")
            if check["checked"] != len(batch):
                raise RuntimeError("Incomplete RO URL batch")
            state["verified_urls"].update(urls)
            aggregate = state["url_check"]
            aggregate["checked"] += check["checked"]
            aggregate["verified"] += check["verified"]
            for reason, count in check["reasons"].items():
                aggregate["reasons"][reason] = aggregate["reasons"].get(reason, 0) + count
            for reason, handles in check["sample_handles"].items():
                samples = aggregate["sample_handles"].setdefault(reason, [])
                samples.extend(handles[:max(0, 3 - len(samples))])
        elif stage == "collections":
            missing = [p for p in candidates if p["id"] not in state["verified_urls"]]
            if index >= len(missing):
                advance("variants")
                continue
            batch = missing[index:index + 20]
            urls, check = verify_collection_urls(
                batch, set(), store, token, market="RO")
            state["collection_urls"].update(urls)
            for key in ("checked", "verified", "without_collection"):
                state["collection_check"][key] += check.get(key, 0)
        elif stage == "variants":
            variant_ids = list(dict.fromkeys(
                v["id"] for p in candidates if p["id"] in
                (state["verified_urls"] | state["collection_urls"])
                for v in p["variants"]["nodes"] if v.get("selectedOptions")))
            if index >= len(variant_ids):
                advance("ready")
                continue
            batch = variant_ids[index:index + 50]
            state["variant_map"].update(fetch_variant_translations(
                batch, "RO", store=store, token=token))
        else:
            raise RuntimeError("Invalid RO finalize stage")
        state["next_index"] += len(batch)
        _save(path, state)
        print(f"[favi-ro-finalize] stage={stage} checked={state['next_index']}", flush=True)
    missing = len(ids) - len(state["verified_urls"])
    if (set(state["translated_map"]) != set(ids)
            or state["url_check"]["checked"] != len(ids)
            or state["collection_check"]["checked"] +
               state["collection_check"]["without_collection"] != missing):
        raise RuntimeError("Incomplete RO finalize checkpoint")
    return {**state, "status": "ready"}
