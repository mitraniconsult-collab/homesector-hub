"""Original supplier galleries only; identifier checks precede AI checks."""
import html
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit
import requests

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

def parse_product(page, code, barcode=''):
    start = page.find('product-page-top')
    if start < 0: return None
    # Exclude related-product recommendations from identifier matching.
    end = page.find('Related Products', start)
    section = page[start:end if end >= 0 else len(page)]
    text = html.unescape(re.sub(r'<[^>]+>', ' ', section))
    text = ' '.join(text.split())
    if not re.search(r'(?<![\w])' + re.escape(code) + r'(?![\w])', text, re.I): return None
    image_start = section.find('product-gallery-slick')
    image_end = section.find('id="gallery-modal"', image_start)
    gallery = section[image_start:image_end if image_end >= 0 else image_start + 15000]
    images = list(dict.fromkeys(re.findall(r'https://media\.decorationbrands\.com/media/catalog/product/[^"?\s<>]+\.(?:jpg|png|webp)', gallery)))
    if not images or not all(safe_url(u, True) for u in images): return None
    source_eans = set(re.findall(r'(?<!\d)\d{13}(?!\d)', gallery))
    if barcode and barcode not in source_eans: return None
    title = re.search(r'<h1\b[^>]*>(.*?)</h1>', section, re.S)
    name = html.unescape(re.sub(r'<[^>]+>', '', title.group(1))) if title else ''
    return {'sku': code, 'barcode': next(iter(source_eans)) if len(source_eans) == 1 else '', 'title': name, 'facts': text[:10000], 'images': images[:20]}

def discover(code, barcode=''):
    r = requests.get(BASE + '/catalogsearch/result/', params={'q': code}, timeout=45, allow_redirects=False)
    r.raise_for_status()
    if r.status_code != 200: raise RuntimeError('Недостъпен каталог на доставчика')
    links = Links(); links.feed(r.text)
    matches = []
    for url in list(dict.fromkeys(links.urls))[:4]:
        if not safe_url(url): continue
        parsed = parse_product(fetch(url), code, barcode)
        if parsed: matches.append({**parsed, 'url': url})
    if len(matches) != 1: raise ValueError('Няма еднозначно съвпадение по SKU/EAN в Decoration Brands')
    return matches[0]
