"""Original supplier galleries only; identifier checks precede AI checks."""
import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
import requests
from image_diagnostics import ImageReview

BASE = 'https://www.decorationbrands.com'

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'product-item-link' in attrs.get('class', ''):
            self.urls.append(attrs.get('href', ''))

def safe_url(url, media=False):
    p = urlsplit(url)
    hosts = {'media.decorationbrands.com'} if media else {'www.decorationbrands.com'}
    return p.scheme == 'https' and p.hostname in hosts and not p.username and not p.password and p.port in (None, 443)

def fetch(url):
    if not safe_url(url): raise ValueError('Непознат доставчик')
    r = requests.get(url, timeout=45, allow_redirects=False)
    if r.status_code in (404, 410): return ''
    r.raise_for_status()
    if r.status_code != 200: raise RuntimeError('Доставчикът пренасочва заявката; нужна е проверка')
    if len(r.content) > 3_000_000: raise ValueError('Прекалено голяма продуктова страница')
    return r.text

def search_urls(page, term):
    links = Links(); links.feed(page)
    urls = list(dict.fromkeys(urljoin(BASE, u) for u in links.urls if safe_url(urljoin(BASE, u))))
    if urls: return urls
    # Some search pages contain only a JS results template. Reuse the site's
    # published read-only search configuration; never execute page JavaScript.
    marker = re.search(r'window\.algoliaConfig\s*=\s*', page)
    if not marker: return []
    try: config, _ = json.JSONDecoder().raw_decode(page[marker.end():])
    except ValueError:
        raise ImageReview('SOURCE_SEARCH_UNREADABLE','Не може да се прочете конфигурацията на търсачката в Decoration Brands.','Повтори след обновяване на каталога или провери страницата на доставчика.')
    app = config.get('applicationId', '')
    index = config.get('indexName', '')
    key = config.get('apiKey', '')
    if not isinstance(app,str) or not re.fullmatch(r'[A-Za-z0-9]{10}',app) or not isinstance(index,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,150}',index) or not isinstance(key,str) or not key:
        raise ImageReview('SOURCE_SEARCH_UNREADABLE','Липсва валидна публична конфигурация за търсене в Decoration Brands.','Провери дали търсачката на доставчика е достъпна.')
    r = requests.post(f'https://{app.lower()}-dsn.algolia.net/1/indexes/{index}_products/query', headers={'X-Algolia-Application-Id':app,'X-Algolia-API-Key':key}, json={'query':term,'hitsPerPage':13,'typoTolerance':False}, timeout=30, allow_redirects=False)
    if r.status_code != 200:
        raise ImageReview('SOURCE_SEARCH_UNAVAILABLE',f'Публичната търсачка на Decoration Brands върна HTTP {r.status_code}. Това не означава липсващ продукт.','Повтори по-късно или провери търсачката на доставчика.')
    data = r.json()
    if not isinstance(data.get('hits'),list) or not isinstance(data.get('nbHits'),int):
        raise ImageReview('SOURCE_SEARCH_UNREADABLE','Търсачката върна неразпознат отговор.','Провери търсачката на доставчика; не приемай този резултат за липсващ продукт.')
    if data['nbHits'] > 12:
        raise ImageReview('SEARCH_TOO_BROAD',f'Търсачката връща {data["nbHits"]} резултата за {term}; нужно е по-точно съвпадение.','Провери точните SKU и EAN.')
    urls = list(dict.fromkeys(hit['url'] for hit in data['hits'] if isinstance(hit.get('url'),str) and safe_url(hit['url'])))
    if data['nbHits'] and not urls:
        raise ImageReview('SOURCE_SEARCH_UNREADABLE','Има резултати в търсачката, но няма разпознати безопасни продуктови URL адреси.','Провери оригиналите в Decoration Brands.')
    return urls

def parse_product(page, code, barcode='', diagnostics=None):
    def reject(reason):
        if diagnostics is not None: diagnostics['reason'] = reason
        return None
    start = page.find('product-page-top')
    if start < 0: return reject('PRODUCT_PAGE_UNREADABLE')
    # Exclude related-product recommendations from identifier matching.
    end = page.find('Related Products', start)
    section = page[start:end if end >= 0 else len(page)]
    text = html.unescape(re.sub(r'<[^>]+>', ' ', section))
    text = ' '.join(text.split())
    if code and not re.search(r'(?<![\w])' + re.escape(code) + r'(?![\w])', text, re.I): return reject('SKU_MISMATCH')
    if not code and not barcode: return reject('NO_IDENTIFIER')
    image_start = section.find('product-gallery-slick')
    if image_start < 0: return reject('SOURCE_NO_GALLERY')
    image_end = section.find('id="gallery-modal"', image_start)
    gallery = section[image_start:image_end if image_end >= 0 else image_start + 15000]
    images = list(dict.fromkeys(re.findall(r'https://media\.decorationbrands\.com/media/catalog/product/[^"?\s<>]+\.(?:jpe?g|png|webp)', html.unescape(gallery), re.I)))
    if not images or not all(safe_url(u, True) for u in images): return reject('SOURCE_NO_IMAGES')
    source_eans = set(re.findall(r'(?<!\d)\d{13}(?!\d)', gallery))
    source_eans.update(re.findall(r'\b(?:EAN|GTIN|Barcode|Code-barres)\s*[:#]?\s*(\d{8}|\d{12,14})\b', text, re.I))
    if diagnostics is not None: diagnostics['source_eans'] = sorted(source_eans)
    if barcode and barcode not in source_eans: return reject('EAN_MISMATCH' if source_eans else 'SOURCE_EAN_MISSING')
    title = re.search(r'<h1\b[^>]*>(.*?)</h1>', section, re.S)
    name = html.unescape(re.sub(r'<[^>]+>', '', title.group(1))) if title else ''
    return {'sku': code, 'barcode': next(iter(source_eans)) if len(source_eans) == 1 else '', 'title': name, 'facts': text[:10000], 'images': images[:20]}

def discover(code, barcode=''):
    code, barcode = str(code or '').strip(), str(barcode or '').strip()
    if not code and not barcode:
        raise ImageReview('NO_IDENTIFIER', 'Липсват и SKU, и EAN/баркод.', 'Добави поне един точен идентификатор в Shopify.')
    matches = []
    checked = set(); reasons = []; searches = []
    for term in dict.fromkeys(t for t in (code, barcode) if t):
        searches.append(term)
        r = requests.get(BASE + '/catalogsearch/result/', params={'q':term}, timeout=45, allow_redirects=False)
        r.raise_for_status()
        if r.status_code != 200:
            raise ImageReview('SOURCE_SEARCH_UNAVAILABLE', 'Decoration Brands не върна страница с резултати за ' + term + '.', 'Провери достъпа до каталога и повтори задачата.', source_query='; '.join(searches))
        urls = search_urls(r.text,term)
        # Do not accept the first result if the bounded search could hide another exact match.
        if len(urls) > 12:
            reasons.append('SEARCH_TOO_BROAD')
            continue
        for url in urls:
            if url in checked or not safe_url(url): continue
            checked.add(url); detail = {}
            parsed = parse_product(fetch(url), code, barcode, detail)
            if parsed: matches.append({**parsed, 'url':url})
            else: reasons.append(detail.get('reason', 'PRODUCT_PAGE_UNREADABLE'))
        if matches: break
    details = {'source_query':'; '.join(searches), 'source_candidates':len(checked), 'source_rejections':reasons}
    if len(matches) == 1: return {**matches[0], **details}
    if len(matches) > 1:
        raise ImageReview('SOURCE_AMBIGUOUS', f'Намерени са {len(matches)} страници със същите идентификатори; няма еднозначен оригинал.', 'Провери правилния модел в Decoration Brands.', **details)
    labels = {
        'SKU_MISMATCH':'SKU не е потвърден в намерените страници',
        'EAN_MISMATCH':'EAN от Shopify се различава от EAN на намерените оригинали',
        'SOURCE_EAN_MISSING':'доставчикът не показва EAN за потвърждение',
        'SOURCE_NO_IMAGES':'намерената продуктова страница няма достъпни оригинални снимки',
        'SOURCE_NO_GALLERY':'не е разпозната галерия на намерената страница',
        'PRODUCT_PAGE_UNREADABLE':'не е разпозната продуктова страница или тя е премахната',
        'SEARCH_TOO_BROAD':'търсенето връща над 12 страници и не е достатъчно точно',
    }
    reason = next((r for r in ('EAN_MISMATCH','SOURCE_EAN_MISSING','SOURCE_NO_IMAGES','SOURCE_NO_GALLERY','SKU_MISMATCH','SEARCH_TOO_BROAD','PRODUCT_PAGE_UNREADABLE') if r in reasons), 'SOURCE_NOT_FOUND')
    message = 'Decoration Brands: ' + labels.get(reason, 'няма резултати за посочените идентификатори') + '. Търсено: ' + '; '.join(searches) + f'. Проверени страници: {len(checked)}.'
    raise ImageReview(reason, message, 'Провери SKU/EAN и дали артикулът още има страница в Decoration Brands; не се качват снимки на сходен модел.', **details)
