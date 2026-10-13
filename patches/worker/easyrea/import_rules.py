"""Pure import identity, media and copy rules; no external calls."""
from collections import defaultdict
import hashlib
import html
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

PENDING='hub-easyrea-pending'
READY='hub-easyrea-ready'
IMPORTED='hub-easyrea'
VENDORS={'ATMOSPHERA':'atmosphera','FIVE':'5five','5FIVE':'5five','HESPERIDE':'Hesperide','SECRET DE GOURMET':'Secret De Gourmet','FEERIC':'Feeric','NEKA':'Neka'}

def sku(value):
    return str(value or '').strip().upper()

def ean(value):
    # Preserve leading zeroes and never equate identifiers by integer conversion.
    return str(value or '').strip().replace(' ', '')

def handle(code):
    return 'easyrea-'+hashlib.sha256(sku(code).encode()).hexdigest()[:24]

def title_handle(title):
    import unicodedata
    letters={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sht','ъ':'a','ь':'y','ю':'yu','я':'ya'}
    value=''.join(letters.get(c,c) for c in title.lower())
    value=unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode()
    value=re.sub('[^a-z0-9]+','-',value).strip('-')[:200].rstrip('-')
    if not value:raise ValueError('Невалидно заглавие за URL')
    return value

def finished_tags(tags):
    return [t for t in tags if t!=IMPORTED and not t.startswith('hub-easyrea-')]+[IMPORTED]

def media_set_tag(urls,title):
    return "hub-easyrea-images-"+hashlib.sha256((title+"\n"+"\n".join(urls)).encode()).hexdigest()[:24]

def source_tag(code):
    return 'hub-easyrea-sku-'+sku(code)

class Index:
    def __init__(self, variants):
        self.skus=defaultdict(list);self.eans=defaultdict(list);self.staging=defaultdict(list)
        for v in variants:
            if sku(v.get('sku')): self.skus[sku(v['sku'])].append(v)
            if ean(v.get('barcode')): self.eans[ean(v['barcode'])].append(v)
            for tag in v['product'].get('tags',[]):
                if tag.startswith('hub-easyrea-sku-') and PENDING in v['product'].get('tags',[]):
                    self.staging[tag.removeprefix('hub-easyrea-sku-')].append(v)
    def decide(self, code, barcode):
        a=self.skus.get(sku(code),[]);b=self.eans.get(ean(barcode),[]) if ean(barcode) else []
        stage=self.staging.get(sku(code),[])
        if len(a)>1 or len(b)>1 or len(stage)>1: return 'REVIEW_DUPLICATE_IDENTIFIERS',None
        if a and b and a[0]['id']!=b[0]['id']: return 'REVIEW_SKU_EAN_CONFLICT',None
        if a and barcode and a[0].get('barcode') and ean(a[0]['barcode'])!=ean(barcode): return 'REVIEW_SKU_EAN_CONFLICT',None
        existing=(a or b or stage)
        if stage:
            if any(v['product']['id']!=stage[0]['product']['id'] for v in a+b): return 'REVIEW_SKU_EAN_CONFLICT',None
            return 'RESUME',stage[0]['product']['id']
        if existing: return ('EXISTS_SKU' if a else 'EXISTS_EAN'),existing[0]['product']['id']
        if not sku(code): return 'REVIEW_NO_SKU',None
        if not ean(barcode): return 'REVIEW_NO_EAN',None
        return 'NEW',None

def image_urls(listing, fiche):
    out=[];seen=set()
    def add(value):
        if not isinstance(value,str) or not value.strip(): return
        value=value.strip()
        if value.startswith('//'):value='https:'+value
        elif value.startswith('/'):value=urljoin('https://easyrea.com',value)
        p=urlsplit(value)
        if p.scheme not in ('https','http') or not p.netloc: return
        if re.search(r'\.(pdf|mp4|webm|svg)(?:$|\?)',value,re.I):return
        if any(x in p.path.lower() for x in ('/logo','/icon','/pictogram')):return
        # Only remove resizing parameters, keep signatures and asset identifiers.
        identity=urlunsplit((p.scheme,p.netloc,p.path,urlencode([(k,v) for k,v in parse_qsl(p.query) if k.lower() not in ('width','height','w','h','quality')]),''))
        if identity not in seen:seen.add(identity);out.append(value)
    def walk(value, context=False):
        if isinstance(value,dict):
            for key,val in value.items():
                key=key.lower()
                media=context or any(word in key for word in ('photo','image','visuel','picture'))
                if media and isinstance(val,str):add(val)
                elif isinstance(val,str):
                    # Easyrea sometimes places JJA asset links under generic keys
                    # such as url or src, outside a photo/image container.
                    candidate=val.strip()
                    if candidate.startswith('//'):candidate='https:'+candidate
                    if urlsplit(candidate).hostname=='media.jja-sa.com':add(candidate)
                elif isinstance(val,(dict,list)):walk(val,media)
        elif isinstance(value,list):
            for val in value:
                if context and isinstance(val,str):add(val)
                else:walk(val,context)
    # Primary first; combine all sources instead of fallback-only extraction.
    for key in ('photoPrincipale','photoAmbiance'):add(listing.get(key))
    walk(fiche or {});walk(listing)
    return out

class SafeHtml(HTMLParser):
    allowed={'p','ul','ol','li','strong','em','br','h2','h3','table','tbody','tr','th','td'}
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.blocked=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','iframe','object'):self.blocked+=1
        elif not self.blocked and tag in self.allowed:self.parts.append('<'+tag+'>')
    def handle_endtag(self,tag):
        if tag in ('script','style','iframe','object'):self.blocked=max(0,self.blocked-1)
        elif not self.blocked and tag in self.allowed and tag!='br':self.parts.append('</'+tag+'>')
    def handle_data(self,data):
        if not self.blocked:self.parts.append(html.escape(data))

def validate_copy(data, vendor):
    if not isinstance(data,dict):raise ValueError('Невалиден AI отговор')
    title=data.get('title');description=data.get('description')
    if not isinstance(title,str) or not isinstance(description,str):raise ValueError('Липсва AI заглавие или описание')
    title=' '.join(title.split())
    if not (10<=len(title)<=180) or not re.search('[А-Яа-я]',title) or vendor.casefold() not in title.casefold():raise ValueError('Заглавието не следва българския образец и бранда')
    if '<' in title or '>' in title:raise ValueError('HTML в заглавие')
    parser=SafeHtml();parser.feed(description);description=''.join(parser.parts)
    text=re.sub('<[^>]+>','',description)
    if len(text)<100 or not re.search('[А-Яа-я]',text):raise ValueError('Непълно българско описание')
    return title,description
