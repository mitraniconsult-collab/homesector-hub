#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Easyrea → Shopify availability and arrival dates in one supplier snapshot.
Warehouse quantities and product publication status are NEVER changed.
Default mode: dry run. Unknown suppliers/statuses are left for review.
"""

import os
import csv
import sys
import time
import json
import datetime
import requests

import runtime
from stock_rules import decide, product_date

# ============================================================
#  НАСТРОЙКИ
# ============================================================

# ---- Режим: идва от приложението (DRY_RUN / --dry-run / --real-run).
#      По подразбиране ТЕСТ. Виж runtime.py. ----
DRY_RUN = runtime.dry_run(default=True)

# Stop real runs when matched, tracked supplier records use unexpected statuses.
# Missing/blank SKUs are skipped individually and cannot change Shopify.
MAX_UNKNOWN_STATUS_PCT = 25.0
STOPPED_STATUS_IDS = {x.strip() for x in os.environ.get("EASYREA_STOPPED_STATUS_IDS", "").split(",") if x.strip()}

# ---- EasyRea ----
EASYREA_BASE      = "https://api-prod.easyrea.com/private/api/easyrea"
EASYREA_LOGIN = os.environ.get("EASYREA_LOGIN", "")
EASYREA_PASSWORD = os.environ.get("EASYREA_PASSWORD", "")
CODE_MAGASIN      = "26284"
SUFFIXE_MAGASIN   = "1"
PAGE_SIZE         = 200          # колко продукта на страница (вдигнато за по-малко заявки)

# ---- Shopify ----
# Токенът се взима АВТОМАТИЧНО от Client ID + Secret (client credentials grant).
# Не пишеш токен ръчно — скриптът си го взима свеж при всяко пускане.
SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
SHOPIFY_API_VER   = "2026-04"


# Metafield за датата на пристигане ("на път" продукти)
META_NAMESPACE    = "custom"
META_KEY          = "expected_arrival"

# ВАЖНО: само продукти с тези vendor-и се пипат. Всичко друго (други
# доставчици) се ПРОПУСКА напълно — нито наличност, нито DRAFT.
# Сравнението е без значение за главни/малки букви и интервали.
EASYREA_VENDORS = {
    "atmosphera",
    "hesperide",
    "5five",
    "secret de gourmet",
    "feeric",
}

REPORT_FILE = "sync_report_{}.csv".format(
    datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
)
REPORT_FILE = os.path.join(os.environ.get("HUB_REPORT_DIR", "."), REPORT_FILE)

# ============================================================
#  EASYREA
# ============================================================

class EasyRea:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/148.0.0.0 Safari/537.36",
            "Origin": "https://easyrea.com",
            "Referer": "https://easyrea.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,bg;q=0.8",
            "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        })
        self.xsrf = None

    def login(self):
        # Стъпка 0: посети easyrea.com, за да вземеш Incapsula cookies
        # (без това login-ът връща 403). Това е същото, което правеше diag.py.
        try:
            self.s.get("https://easyrea.com/", timeout=30)
        except Exception:
            pass

        url = f"{EASYREA_BASE}/user/login"
        r = self.s.post(
            url,
            data={"login": EASYREA_LOGIN, "password": EASYREA_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"[easyrea] Логин неуспешен. HTTP {r.status_code}")
            print(f"[easyrea] Content-Type: {r.headers.get('Content-Type')}")
            print(f"[easyrea] Отговор (първи 400 символа):\n{r.text[:400]}")
            r.raise_for_status()
        # xsrf токенът идва като cookie 'xsrf-token' (= x-csrf-token header).
        self.xsrf = self.s.cookies.get("xsrf-token")
        if not self.xsrf:
            # резервен вариант: разкодирай го от JWT 'token' cookie
            tok = self.s.cookies.get("token")
            if tok:
                import base64
                payload = tok.split(".")[1]
                payload += "=" * (-len(payload) % 4)
                data = json.loads(base64.urlsafe_b64decode(payload))
                self.xsrf = data.get("xsrfToken")
        if not self.xsrf:
            raise RuntimeError("Логинът успя, но xsrf токенът не е намерен.")
        print("[easyrea] Логин успешен.")

    def fetch_all_products(self):
        """Връща dict: code(str) -> {idTypeDispo, qteDispo, dateArrivage, libelle}"""
        url = f"{EASYREA_BASE}/magasins/{CODE_MAGASIN}/{SUFFIXE_MAGASIN}/produits"
        out = {}
        page = 1
        total = None
        received = 0
        empty_attempts = 0
        previous_page = None
        while True:
            body = {
                "idsSegmentation": [], "idsTheme": [], "codesGroupes": [],
                "idsFavori": [], "idsPictogrammes": [], "idsPicto": [],
                "idsUsine": [], "codesMarque": [], "codesStyle": [],
                "inPanier": [], "typesMassif": [], "idsFonctionAffiner": [],
                "tradepalDestockagePourcentRemise": [], "idProgrammeEtp": None,
                "idCleContainer": None, "idsCleContainer": [], "idsTypeDispo": [],
                "checkIsStateCentrale2": False, "incoterm": [],
                "nombreAffichage": PAGE_SIZE, "page": page, "texte": "",
                "tousProduits": True, "ordreAffichage": "ORDER_CATEGORIE_ASC",
                "isRayon": False, "isAllRayon": False,
                "codeMagasin": CODE_MAGASIN, "suffixeMagasin": SUFFIXE_MAGASIN,
                "modeMultiMag": False, "typePanier": "STD",
            }
            r = self.s.post(
                url, json=body, timeout=60,
                headers={
                    "Content-Type": "application/json;charset=UTF-8",
                    "x-csrf-token": self.xsrf,
                    "lang": "en",
                    "Referer": "https://easyrea.com/produits/tous",
                },
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("results")
            if total is None:
                total = data.get("totalResults", 0)
                print(f"[easyrea] Общо продукти: {total}")
            if not isinstance(results, list):
                raise RuntimeError("Невалиден Easyrea отговор")
            if not results:
                # A premature empty response can be transient. Retry this exact
                # page twice before treating it as the end of the supplier feed.
                if total and received < total and empty_attempts < 2:
                    empty_attempts += 1
                    print(f"[easyrea] празна страница {page}: повторна проверка {empty_attempts}/2", flush=True)
                    time.sleep(2)
                    continue
                if total and received < total:
                    deficit = total - received
                    # totalResults counts supplier rows, not unique SKUs. A small
                    # mismatch must never imply that unseen SKUs are stopped.
                    # Cap drift at BOTH 0.1% and 20 rows; larger gaps still fail.
                    tolerated = deficit <= min(20, total * 0.001)
                    message = f"Непълен Easyrea каталог: обявени {total}, получени {received}, уникални {len(out)}, празна страница {page}"
                    if not DRY_RUN and not tolerated:
                        raise RuntimeError(message + " — реалната синхронизация е спряна")
                    print(f"[WARNING] {message}. " + (
                        "Малка разлика в брояча след 3 празни отговора; обработват се само получените SKU. Липсващите остават БЕЗ ПРОМЯНА."
                        if tolerated else "Само диагностичен тест; REAL RUN остава блокиран."
                    ), flush=True)
                break
            empty_attempts = 0
            # Reject repeated pages even if their raw row count reaches total.
            signature = json.dumps(results, sort_keys=True, ensure_ascii=False)
            if signature == previous_page:
                raise RuntimeError(f"Easyrea повтори страница {page} — синхронизацията е спряна")
            previous_page = signature
            received += len(results)
            for p in results:
                code = str(p.get("codeArticle", "")).strip()
                if not code:
                    continue
                # ако код се повтаря (масификация), пазим "най-добрия" статус
                rec = {
                    "idTypeDispo": p.get("idTypeDispo"),
                    "qteDispo": p.get("qteDispo"),
                    "dateArrivage": p.get("dateArrivageADateJour"),
                    "libelle": p.get("libelle", ""),
                    **{k: p.get(k) for k in ("availabilityLabel", "libelleTypeDispo", "labelTypeDispo", "typeDispo")},
                }
                if code not in out or rec["idTypeDispo"] == 1:
                    out[code] = rec
            print(f"[easyrea] страница {page}: +{len(results)} (общо уникални: {len(out)})")
            page += 1
            time.sleep(0.3)  # учтиво към сървъра / Incapsula
        if not out:
            raise RuntimeError("Easyrea върна празен каталог — без промени")
        print(f"[easyrea] Готово. Уникални кодове: {len(out)}")
        return out


# ============================================================
#  SHOPIFY
# ============================================================

class Shopify:
    def __init__(self):
        self.base = f"https://{SHOPIFY_STORE}/admin/api/{SHOPIFY_API_VER}"
        token = self._get_token()
        self.headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
        }

    def _get_token(self):
        """Взима свеж Admin API токен чрез client credentials grant."""
        if not SHOPIFY_CLIENT_ID or not SHOPIFY_CLIENT_SECRET:
            raise RuntimeError("Задай SHOPIFY_CLIENT_ID и SHOPIFY_CLIENT_SECRET.")
        r = requests.post(
            f"https://{SHOPIFY_STORE}/admin/oauth/access_token",
            json={
                "grant_type": "client_credentials",
                "client_id": SHOPIFY_CLIENT_ID,
                "client_secret": SHOPIFY_CLIENT_SECRET,
            },
            timeout=30,
        )
        r.raise_for_status()
        token = r.json().get("access_token")
        if not token:
            raise RuntimeError(f"Токенът не е получен: {r.text[:200]}")
        print("[shopify] Токен получен.")
        return token

    def gql(self, query, variables=None):
        r = requests.post(
            f"{self.base}/graphql.json",
            headers=self.headers,
            json={"query": query, "variables": variables or {}},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise RuntimeError(f"Shopify GraphQL error: {data['errors']}")
        # throttle handling
        cost = data.get("extensions", {}).get("cost", {})
        avail = cost.get("throttleStatus", {}).get("currentlyAvailable", 1000)
        if avail < 200:
            time.sleep(2)
        return data["data"]

    def fetch_all_variants(self):
        out = []
        cursor = None
        q = """
        query($cursor: String) {
          productVariants(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              sku id inventoryPolicy inventoryQuantity
              inventoryItem { tracked }
              metafield(namespace: "custom", key: "expected_arrival") { value }
              product {
                id status vendor templateSuffix variantsCount { count }
                metafield(namespace: "custom", key: "expected_arrival") { value }
              }
            }
          }
        }"""
        while True:
            conn = self.gql(q, {"cursor": cursor})["productVariants"]
            for n in conn["nodes"]:
                prod = n["product"]
                out.append({
                    "sku": (n.get("sku") or "").strip(),
                    "variant_id": n["id"], "product_id": prod["id"],
                    "quantity": n.get("inventoryQuantity"),
                    "tracked": (n.get("inventoryItem") or {}).get("tracked", False),
                    "status": prod["status"], "vendor": prod.get("vendor", "").strip(),
                    "inventory_policy": n["inventoryPolicy"],
                    "template_suffix": prod.get("templateSuffix") or "",
                    "variant_date": (n.get("metafield") or {}).get("value"),
                    "product_date": (prod.get("metafield") or {}).get("value"),
                    "variant_count": (prod.get("variantsCount") or {}).get("count"),
                })
            if not conn["pageInfo"]["hasNextPage"]:
                break
            next_cursor = conn["pageInfo"]["endCursor"]
            if not next_cursor or next_cursor == cursor:
                raise RuntimeError("Невалидна Shopify пагинация")
            cursor = next_cursor
            print(f"[shopify] заредени варианти: {len(out)}")
        return out

    def mutation(self, query, variables, field):
        result = self.gql(query, variables).get(field)
        if result is None:
            raise RuntimeError(f"Липсва резултат от {field}")
        if result.get("userErrors"):
            raise RuntimeError(f"{field}: {result['userErrors']}")

    def set_metafield_date(self, owner_id, value):
        if value is None:
            q = """mutation($m: [MetafieldIdentifierInput!]!) {
              metafieldsDelete(metafields: $m) { userErrors { field message } }
            }"""
            self.mutation(q, {"m": [{"ownerId": owner_id, "namespace": META_NAMESPACE, "key": META_KEY}]}, "metafieldsDelete")
        else:
            q = """mutation($m: [MetafieldsSetInput!]!) {
              metafieldsSet(metafields: $m) { userErrors { field message } }
            }"""
            self.mutation(q, {"m": [{"ownerId": owner_id, "namespace": META_NAMESPACE, "key": META_KEY, "type": "date", "value": value}]}, "metafieldsSet")

    def set_variant_policy(self, product_id, variant_id, policy):
        q = """mutation($product: ID!, $variants: [ProductVariantsBulkInput!]!) {
          productVariantsBulkUpdate(productId: $product, variants: $variants) {
            userErrors { field message }
          }
        }"""
        self.mutation(q, {"product": product_id, "variants": [{"id": variant_id, "inventoryPolicy": policy}]}, "productVariantsBulkUpdate")

# ============================================================
#  ЛОГИКА ЗА СИНХРОНИЗАЦИЯ
# ============================================================

def build_plan(variants, easyrea):
    from collections import defaultdict
    groups = defaultdict(list)
    for v in variants:
        if v["vendor"].lower() not in EASYREA_VENDORS:
            continue
        rec = easyrea.get(v["sku"])
        d = decide(rec, v["quantity"] if v["tracked"] else None, STOPPED_STATUS_IDS)
        groups[v["product_id"]].append((v, rec, d))
    return groups


def validate_plan(entries, dry_run):
    """Guard supplier status changes without treating skipped SKUs as mutations."""
    from collections import Counter
    counts = Counter()
    for v, rec, d in entries:
        if not v["sku"]:
            counts["blank_sku"] += 1
        elif rec is None:
            counts["missing_supplier"] += 1
        elif not v["tracked"] or not isinstance(v["quantity"], int) or isinstance(v["quantity"], bool):
            counts["unknown_inventory"] += 1
        elif d.policy is None:
            counts["unknown_status"] += 1
        else:
            counts["confirmed"] += 1
    matched = counts["confirmed"] + counts["unknown_status"]
    unknown_pct = 100 * counts["unknown_status"] / max(matched, 1)
    print(f"[план] {len(entries)} варианта | потвърдени: {counts['confirmed']} | "
          f"без SKU: {counts['blank_sku']} | липсващи в Easyrea: {counts['missing_supplier']} | "
          f"непрочетена/непроследявана наличност: {counts['unknown_inventory']} | "
          f"непознат статус: {counts['unknown_status']} ({unknown_pct:.1f}% от съпоставените с прочетена наличност)", flush=True)
    if sum(counts[k] for k in ("blank_sku", "missing_supplier", "unknown_inventory", "unknown_status")):
        print("[WARNING] Пропуснатите варианти остават БЕЗ ПРОМЯНА; продуктовите дати при непълни групи също се запазват.", flush=True)
    if not dry_run:
        if not counts["confirmed"]:
            raise RuntimeError("Няма потвърдени варианти за синхронизация — без промени")
        if unknown_pct > MAX_UNKNOWN_STATUS_PCT and not runtime.force():
            raise RuntimeError("Над 25% непознати статуси сред съпоставените Easyrea варианти — без промени; пуснете диагностичен тест")
    return counts


def apply_variant(sh, v, d):
    if d.policy is None:
        return "review"
    # Disable overselling first. Enable it only after the correct date is saved.
    if d.policy == "DENY" and v["inventory_policy"] != "DENY":
        sh.set_variant_policy(v["product_id"], v["variant_id"], "DENY")
    if v["variant_date"] != d.arrival:
        sh.set_metafield_date(v["variant_id"], d.arrival)
    if d.policy == "CONTINUE" and v["inventory_policy"] != "CONTINUE":
        sh.set_variant_policy(v["product_id"], v["variant_id"], "CONTINUE")
    return "applied"


def main():
    runtime.require_env("EASYREA_LOGIN", "EASYREA_PASSWORD", "SHOPIFY_STORE", "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET")
    runtime.print_mode_banner("Easyrea → Shopify · наличности и дати", DRY_RUN)
    er = EasyRea()
    er.login()
    easyrea = er.fetch_all_products()
    sh = Shopify()
    groups = build_plan(sh.fetch_all_variants(), easyrea)
    all_entries = [entry for group in groups.values() for entry in group]
    from collections import Counter
    print("[диагностика] Easyrea статуси: " + json.dumps(dict(Counter(str(r.get("idTypeDispo")) for r in easyrea.values())), ensure_ascii=False))
    review_entries = [(v, rec, d) for v, rec, d in all_entries if d.policy is None]
    for v, rec, d in review_entries[:20]:
        labels = {k: rec.get(k) for k in ("availabilityLabel", "libelleTypeDispo", "labelTypeDispo", "typeDispo") if rec and rec.get(k) is not None}
        print(f"[за проверка] SKU {v['sku']}: {d.reason}; етикети={json.dumps(labels, ensure_ascii=False)}")
    if not all_entries:
        raise RuntimeError("Не са намерени варианти от Easyrea брандовете")
    validate_plan(all_entries, DRY_RUN)
    rows = []
    errors = 0
    progress = 0
    for product_id, entries in groups.items():
        first = entries[0][0]
        complete = len(entries) == first["variant_count"]
        decisions = [d for _, _, d in entries]
        change_product, target_date, note = product_date(decisions, complete)
        product_error = ""
        # Save compatibility date before any CONTINUE mutation.
        if not DRY_RUN and change_product:
            try:
                if first["product_date"] != target_date:
                    sh.set_metafield_date(product_id, target_date)
            except Exception as e:
                product_error = str(e)
                errors += 1
        for v, rec, d in entries:
            progress += 1
            applied = "dry-run"
            if not DRY_RUN:
                try:
                    if product_error:
                        raise RuntimeError(product_error)
                    applied = apply_variant(sh, v, d)
                except Exception as e:
                    applied = f"ERROR: {e}"
                    errors += 1
            rows.append({
                "sku": v["sku"], "variant_id": v["variant_id"], "product_id": product_id,
                "supplier_status": rec.get("idTypeDispo") if rec else "MISSING",
                "action": d.action, "quantity_preserved": v["quantity"],
                "current_policy": v["inventory_policy"], "target_policy": d.policy or "UNCHANGED",
                "current_variant_date": v["variant_date"] or "", "target_variant_date": d.arrival or "",
                "current_product_date": first["product_date"] or "",
                "target_product_date": (target_date or "") if change_product else "UNCHANGED",
                "reason": d.reason, "review_note": note, "applied": applied,
            })
            if progress % 100 == 0 or progress == len(all_entries):
                print(f"PROGRESS {progress}/{len(all_entries)}", flush=True)
    with open(REPORT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    from collections import Counter
    print("\n=== ОБОБЩЕНИЕ ===")
    for action, count in Counter(r["action"] for r in rows).items():
        print(f"  {action}: {count}")
    print(f"Отчет записан: {REPORT_FILE}")
    print("ТЕСТ: няма промени в Shopify" if DRY_RUN else f"РЕАЛЕН режим | грешки: {errors}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
