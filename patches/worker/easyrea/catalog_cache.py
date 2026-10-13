"""Durable Easyrea import snapshot in the Hub's private Blob store."""
import gzip
import json
import os
import time

import requests

URL = os.environ.get('HUB_CATALOG_CACHE_URL', 'https://hub.homesector.bg/api/catalog-cache')
MAX_AGE = 24 * 60 * 60
MAX_BYTES = 40_000_000


def load(force=False):
    if force:
        print('[кеш] Избрано е обновяване от Easyrea', flush=True)
        return None
    token = os.environ.get('HUB_WORKER_TOKEN')
    if not token:
        print('[кеш] Липсва токен; ще се прочете Easyrea', flush=True)
        return None
    try:
        response = requests.get(URL, headers={'Authorization': f'Bearer {token}'}, timeout=45)
        if response.status_code == 404:
            print('[кеш] Първо изпълнение; ще се прочете Easyrea', flush=True)
            return None
        response.raise_for_status()
        if len(response.content) > 4_000_000:
            raise ValueError('Твърде голям кеш')
        body = gzip.decompress(response.content)
        if len(body) > MAX_BYTES:
            raise ValueError('Твърде голям каталог')
        data = json.loads(body)
        age = time.time() - data['fetched_at']
        if data.get('version') != 1 or not isinstance(data.get('catalog'), dict) or not data['catalog'] or age < -300 or age > MAX_AGE:
            print('[кеш] Каталогът е стар или непълен; ще се обнови', flush=True)
            return None
        if not isinstance(data.get('fiches'), dict):
            data['fiches'] = {}
        print(f'[кеш] Заредени {len(data["catalog"])} артикула от предишен обход ({int(age // 60)} мин. давност)', flush=True)
        return data
    except (requests.RequestException, ValueError, KeyError, TypeError, OSError) as exc:
        print(f'[кеш] Четенето не успя ({type(exc).__name__}); ще се прочете Easyrea', flush=True)
        return None


def save(data):
    token = os.environ.get('HUB_WORKER_TOKEN')
    if not token:
        print('[кеш] Липсва токен; каталогът не е запазен', flush=True)
        return
    try:
        body = gzip.compress(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode(), compresslevel=6)
        if len(body) > 4_000_000:
            raise ValueError('Компресираният каталог надхвърля 4 MB')
        response = requests.put(URL, data=body, headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/gzip'}, timeout=90)
        response.raise_for_status()
        print(f'[кеш] Запазени {len(data["catalog"])} артикула за следващото изпълнение', flush=True)
    except (requests.RequestException, ValueError) as exc:
        print(f'[кеш] Записът не успя ({type(exc).__name__}); следващото изпълнение ще обходи Easyrea', flush=True)
