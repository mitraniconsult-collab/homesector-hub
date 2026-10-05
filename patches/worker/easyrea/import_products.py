#!/usr/bin/env python3
"""Read-only planning, explicit AI preview and resumable Draft imports."""
import csv
from collections import Counter, defaultdict
import datetime
from decimal import Decimal
import os
from pathlib import Path
import sys
import time
import requests
import runtime
from import_rules import Index, VENDORS, PENDING, READY, sku, ean, handle, source_tag, image_urls, media_set_tag, title_handle, finished_tags, IMPORTED
from import_legacy import easyrea_login, easyrea_fiche, calculate_price, EASYREA_BASE, CODE_MAGASIN, SUFFIXE_MAGASIN
from product_ai import generate, provider_name, AIConfigurationError, classify

API_VERSION='2026-04'
VARIANTS='''query ImportVariants($cursor:String,$query:String){productVariants(first:250,after:$cursor,query:$query){pageInfo{hasNextPage endCursor} nodes{id sku barcode product{id tags status handle}}}}'''
PRODUCT_FIELDS='''id title descriptionHtml tags status handle category{id fullName} variants(first:2){nodes{id sku barcode price inventoryPolicy} pageInfo{hasNextPage}} media(first:250){nodes{id alt status mediaErrors{code message} ... on MediaImage{image{url}}} pageInfo{hasNextPage}}'''
BY_HANDLE='query ImportByHandle($handle:String!){productByIdentifier(identifier:{handle:$handle}){'+PRODUCT_FIELDS+'}}'
BY_ID='query ImportById($id:ID!){product(id:$id){'+PRODUCT_FIELDS+'}}'
CREATE='''mutation ImportCreate($product:ProductCreateInput!){productCreate(product:$product){product{id handle} userErrors{field message}}}'''
UPDATE_VARIANT='''mutation ImportVariant($productId:ID!,$variants:[ProductVariantsBulkInput!]!){productVariantsBulkUpdate(productId:$productId,variants:$variants){productVariants{id sku barcode} userErrors{field message}}}'''
UPDATE='''mutation ImportUpdate($product:ProductUpdateInput!,$media:[CreateMediaInput!]){productUpdate(product:$product,media:$media){product{id} userErrors{field message}}}'''

TAXONOMY='query ImportTaxonomy($cursor:String,$parent:ID){taxonomy{categories(first:250,after:$cursor,childrenOf:$parent){nodes{id name fullName parentId isRoot isLeaf} pageInfo{hasNextPage endCursor}}}}'
VERIFY_PUBLICATIONS='query ImportPublished($id:ID!){product(id:$id){resourcePublications(first:250){nodes{isPublished publication{id}} pageInfo{hasNextPage}}}}'
PUBLICATIONS='query ImportChannels($cursor:String){publications(first:250,after:$cursor,catalogType:APP){nodes{id} pageInfo{hasNextPage endCursor}} currentAppInstallation{accessScopes{handle}}}'
FILE_REMOVE='mutation ImportClearFailed($ids:[ID!]!){fileDelete(fileIds:$ids){deletedFileIds userErrors{field message}}}'
PUBLISH='mutation ImportPublish($id:ID!,$input:[PublicationInput!]!){publishablePublish(id:$id,input:$input){userErrors{field message}}}'

class UncertainCreate(RuntimeError):pass

class Shopify:
    def __init__(self,config):
        self.config=config;self.session=requests.Session();self.refresh()
    def refresh(self):
        r=requests.post(f"https://{self.config['SHOPIFY_STORE']}/admin/oauth/access_token",json={'grant_type':'client_credentials','client_id':self.config['SHOPIFY_CLIENT_ID'],'client_secret':self.config['SHOPIFY_CLIENT_SECRET']},timeout=30)
        if r.status_code!=200:raise RuntimeError(f'Shopify входът е неуспешен (HTTP {r.status_code})')
        self.session.headers['X-Shopify-Access-Token']=r.json()['access_token']
    def call(self,query,variables=None):
        mutation=query.lstrip().startswith('mutation')
        for attempt in range(5):
            try:
                r=self.session.post(f"https://{self.config['SHOPIFY_STORE']}/admin/api/{API_VERSION}/graphql.json",json={'query':query,'variables':variables or {}},timeout=90)
            except (requests.ConnectionError,requests.Timeout):
                if mutation:raise UncertainCreate('Неясен резултат от Shopify запис. Не повтарям записването; следващото изпълнение ще провери същия Draft.') from None
                if attempt==4:raise RuntimeError('Shopify не отговаря') from None
                time.sleep(2**attempt);continue
            if r.status_code==401 and attempt<4:
                self.refresh();continue # HTTP 401 never executes the mutation.
            if (r.status_code==429 or r.status_code>=500) and not mutation and attempt<4:
                time.sleep(2**attempt);continue
            if r.status_code!=200:
                if mutation and r.status_code>=500:raise UncertainCreate('Неясен резултат от Shopify запис; задачата е спряна без повторно създаване.')
                raise RuntimeError(f'Shopify HTTP {r.status_code}')
            try:payload=r.json()
            except ValueError:
                if mutation:raise UncertainCreate('Невалиден отговор след запис; не повтарям създаването.') from None
                raise RuntimeError('Невалиден Shopify отговор') from None
            errors=payload.get('errors') or []
            if errors:
                if all(e.get('extensions',{}).get('code')=='THROTTLED' for e in errors) and attempt<4:
                    time.sleep(2**attempt);continue # Rejected before execution.
                if mutation:raise UncertainCreate('Shopify върна GraphQL грешка след запис; нужна е повторна проверка.')
                raise RuntimeError('Shopify GraphQL: '+str([e.get('message','') for e in errors])[:500])
            if not payload.get('data'):
                if mutation:raise UncertainCreate('Липсват данни след Shopify запис; не повтарям създаването.')
                raise RuntimeError('Непълен Shopify отговор')
            return payload['data']
        raise RuntimeError('Shopify отказа заявката след 5 опита')
    def variants(self,query=None):
        out=[];cursor=None;seen=set()
        while True:
            conn=self.call(VARIANTS,{'cursor':cursor,'query':query})['productVariants']
            if not isinstance(conn.get('nodes'),list) or 'pageInfo' not in conn:raise RuntimeError('Непълна Shopify страница')
            out.extend(conn['nodes'])
            if query is None:print(f'[shopify] Заредени варианти: {len(out)}',flush=True)
            info=conn['pageInfo']
            if not info['hasNextPage']:return out
            cursor=info.get('endCursor')
            if not cursor or cursor in seen or not conn['nodes']:raise RuntimeError('Непълна Shopify пагинация — импортът е спрян')
            seen.add(cursor)
    def product(self,id=None,code=None):
        return self.call(BY_ID,{'id':id})['product'] if id else self.call(BY_HANDLE,{'handle':handle(code)})['productByIdentifier']
    def check(self,code,barcode):
        # Search is followed by exact normalization, never trust a fuzzy hit.
        import json
        q='sku:'+json.dumps(sku(code))
        if barcode:q+=' OR barcode:'+json.dumps(ean(barcode))
        return Index(self.variants(q)).decide(code,barcode)
    @staticmethod
    def checked(data,name):
        result=data.get(name)
        if not result or result.get('userErrors'):raise RuntimeError(name+' не успя: '+str((result or {}).get('userErrors',[]))[:500])
        if not result.get('product') and not result.get('productVariants'):raise RuntimeError(name+' не върна записани данни')
        return result
    def categories(self,parent=None):
        if not hasattr(self,'_categories'):self._categories={}
        if parent in self._categories:return self._categories[parent]
        out=[];cursor=None;seen=set()
        while True:
            conn=self.call(TAXONOMY,{'cursor':cursor,'parent':parent})['taxonomy']['categories'];out.extend(conn['nodes'])
            if not conn['pageInfo']['hasNextPage']:break
            cursor=conn['pageInfo']['endCursor']
            if not cursor or cursor in seen:raise RuntimeError('Непълна таксономия')
            seen.add(cursor)
        if not out and parent is None:raise RuntimeError('Липсва Shopify таксономия')
        self._categories[parent]=out;return out
    def channels(self, require_write=False):
        if hasattr(self,'_channels') and (not require_write or getattr(self,'_write_publications',False)):return self._channels
        out=[];cursor=None;seen=set()
        while True:
            data=self.call(PUBLICATIONS,{'cursor':cursor})
            scopes={s['handle'] for s in data['currentAppInstallation']['accessScopes']}
            if require_write and 'write_publications' not in scopes:raise AIConfigurationError('Shopify приложението няма write_publications. Разрешете публикации за Hub преди REAL RUN.')
            conn=data['publications'];out.extend(n['id'] for n in conn['nodes'])
            if not conn['pageInfo']['hasNextPage']:break
            cursor=conn['pageInfo']['endCursor']
            if not cursor or cursor in seen:raise RuntimeError('Непълен списък с канали')
            seen.add(cursor)
        if not out:raise RuntimeError('Не са открити sales channels')
        self._channels=out;self._write_publications='write_publications' in scopes;return out
    def category_for(self,title,description,requested='auto'):
        return classify(title,description,self.categories,requested)
    def finalize(self,p,category):
        pid=p['id'];self.current_product_id=pid
        if len(p['variants']['nodes'])!=1 or p['variants']['pageInfo']['hasNextPage']:raise RuntimeError('Импортът трябва да има точно един вариант')
        if not p['media']['nodes'] or p['media']['pageInfo']['hasNextPage'] or any(m['status']!='READY' or not (m.get('image') or {}).get('url') for m in p['media']['nodes']):raise RuntimeError('Продуктът има незавършени снимки; остава Draft за проверка')
        base=title_handle(p['title']);slug=base
        conflict=self.call(BY_HANDLE,{'handle':slug})['productByIdentifier']
        if conflict and conflict['id']!=pid:
            slug=base+'-'+sku(p['variants']['nodes'][0]['sku']).lower()
            conflict=self.call(BY_HANDLE,{'handle':slug})['productByIdentifier']
            if conflict and conflict['id']!=pid:raise RuntimeError('URL е зает от друг продукт; няма презаписване')
        self.checked(self.call(UPDATE_VARIANT,{'productId':pid,'variants':[{'id':p['variants']['nodes'][0]['id'],'inventoryPolicy':'CONTINUE'}]}),'productVariantsBulkUpdate')
        self.checked(self.call(UPDATE,{'product':{'id':pid,'handle':slug,'redirectNewHandle':True,'category':category['id'],'status':'DRAFT'},'media':None}),'productUpdate')
        saved=self.product(id=pid)
        if saved['status']!='DRAFT' or saved['handle']!=slug or (saved.get('category') or {}).get('id')!=category['id'] or saved['variants']['nodes'][0]['inventoryPolicy']!='CONTINUE':raise RuntimeError('Draft статусът, категорията или URL не са потвърдени; импортът остава незавършен')
        self.checked(self.call(UPDATE,{'product':{'id':pid,'tags':finished_tags(saved['tags'])},'media':None}),'productUpdate')
        return slug,0
    def save_draft(self,code,barcode,vendor,title,description,price,cost,urls,listing,fiche,existing_id=None,category=None,unavailable=None):
        p=self.product(id=existing_id) if existing_id else self.product(code=code)
        marker=source_tag(code)
        if p:
            if marker not in p['tags'] or PENDING not in p['tags'] or p['status'] not in ('DRAFT','ACTIVE'):raise RuntimeError('Съвпадение със съществуващ продукт извън незавършения импорт; няма промени')
            if media_set_tag(urls,p['title']) not in p['tags']:raise RuntimeError('Снимките или заглавието на незавършения Draft са променени; остава за проверка')
        else:
            tags=[PENDING,marker,media_set_tag(urls,title)]
            data=self.checked(self.call(CREATE,{'product':{'title':title,'descriptionHtml':description,'vendor':vendor,'status':'DRAFT','handle':handle(code),'tags':tags}}),'productCreate')
            pid=data['product']['id']
            if data['product']['handle']!=handle(code):raise UncertainCreate('Shopify промени идентификатора на Draft; прекратявам за проверка.')
            p=self.product(id=pid)
        if not p:raise RuntimeError('Shopify още не връща създадения Draft; проверете повторно без ново създаване')
        pid=p['id'];self.current_product_id=pid
        if not p or p['variants']['pageInfo']['hasNextPage'] or len(p['variants']['nodes'])!=1:raise RuntimeError('Draft няма точно един вариант; остава за проверка')
        variant=p['variants']['nodes'][0]
        if sku(variant.get('sku')) and sku(variant['sku'])!=sku(code):raise RuntimeError('Конфликт със SKU в незавършения Draft')
        if ean(variant.get('barcode')) and ean(variant['barcode'])!=ean(barcode):raise RuntimeError('Конфликт с EAN в незавършения Draft')
        item={'sku':code,'tracked':True,'cost':str(cost)}
        import re
        weight=str(((fiche or {}).get('informationsTechniques') or {}).get('poidsProduit') or '')
        match=re.search(r'([\d.,]+)\s*(kg|g)',weight.lower())
        if match:
            grams=float(match[1].replace(',','.'))*(1000 if match[2]=='kg' else 1)
            if grams>0:item['measurement']={'weight':{'value':grams,'unit':'GRAMS'}}
        self.checked(self.call(UPDATE_VARIANT,{'productId':pid,'variants':[{'id':variant['id'],'price':str(price),'barcode':barcode,'inventoryPolicy':'CONTINUE','inventoryItem':item}]}),'productVariantsBulkUpdate')
        if len(urls)>250 or p['media']['pageInfo']['hasNextPage']:raise RuntimeError('Над 250 снимки — продуктът остава за проверка')
        # Human-readable stable alts identify already accepted pictures on resume.
        unavailable=set(unavailable or [])
        all_alts=[f"{p['title']} — изображение {i+1}" for i in range(len(urls))]
        removed_alts={a for u,a in zip(urls,all_alts) if u in unavailable}
        failed=[m for m in p['media']['nodes'] if m['alt'] in removed_alts and m['status']=='FAILED']
        if failed:
            result=self.call(FILE_REMOVE,{'ids':[m['id'] for m in failed]})['fileDelete']
            if result.get('userErrors'):raise RuntimeError('Не може да се изчисти невалидната снимка: '+str(result['userErrors'])[:400])
            p=self.product(id=pid)
        actual={m['alt']:m for m in p['media']['nodes']}
        accepted=[(u,a) for u,a in zip(urls,all_alts) if u not in unavailable]
        expected=[a for u,a in accepted]
        if not expected:raise RuntimeError('Няма достъпни снимки')
        missing=[{'originalSource':url,'mediaContentType':'IMAGE','alt':alt} for url,alt in accepted if alt not in actual]
        if missing:self.checked(self.call(UPDATE,{'product':{'id':pid},'media':missing}),'productUpdate')
        for poll in range(30):
            p=self.product(id=pid)
            variants=p['variants']['nodes']
            if len(variants)!=1 or sku(variants[0].get('sku'))!=sku(code) or ean(variants[0].get('barcode'))!=ean(barcode) or Decimal(variants[0]['price'])!=Decimal(str(price)):raise RuntimeError('SKU, EAN или цена не са записани правилно')
            media={m['alt']:m for m in p['media']['nodes']}
            if any(media.get(a,{}).get('status')=='FAILED' for a in expected):raise RuntimeError('Shopify отказа снимка — Draft остава незавършен: '+str([{'alt':media[a].get('alt'),'errors':media[a].get('mediaErrors',[])} for a in expected if media.get(a,{}).get('status')=='FAILED'])[:400])
            if all(media.get(a,{}).get('status')=='READY' and (media[a].get('image') or {}).get('url') for a in expected):break
            if poll==29:raise RuntimeError('Снимките още не са готови — Draft остава за продължаване')
            time.sleep(2)
        if not category:raise RuntimeError('Липсва потвърдена Product category')
        self.finalize(p,category)
        return pid,len(expected)


def unavailable_images(urls):
    unavailable=[]
    for url in urls:
        # Missing assets are skipped; transient/network failures never masquerade as missing images.
        from urllib.parse import urlsplit
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname!='media.jja-sa.com':raise RuntimeError('Непознат източник на снимка — нужна е проверка')
        with requests.get(url,stream=True,timeout=30) as response:
            if response.status_code in (404,410):unavailable.append(url);continue
            response.raise_for_status()
            if not response.headers.get('Content-Type','').lower().startswith('image/'):raise RuntimeError('Източникът не връща изображение')
    return unavailable


def fetch_catalog(session,xsrf):
    out={};conflicts=set();page=1;received=0;total=None
    while True:
        body={'idsSegmentation':[],'idsTheme':[],'codesGroupes':[],'idsFavori':[],'idsPictogrammes':[],'idsPicto':[],'idsUsine':[],'codesMarque':[],'codesStyle':[],'inPanier':[],'typesMassif':[],'idsFonctionAffiner':[],'tradepalDestockagePourcentRemise':[],'idProgrammeEtp':None,'idCleContainer':None,'idsCleContainer':[],'idsTypeDispo':[],'checkIsStateCentrale2':False,'incoterm':[],'nombreAffichage':200,'page':page,'texte':'','tousProduits':True,'ordreAffichage':'ORDER_CATEGORIE_ASC','isRayon':False,'isAllRayon':False,'codeMagasin':CODE_MAGASIN,'suffixeMagasin':SUFFIXE_MAGASIN,'modeMultiMag':False,'typePanier':'STD'}
        r=session.post(f'{EASYREA_BASE}/magasins/{CODE_MAGASIN}/{SUFFIXE_MAGASIN}/produits',json=body,headers={'x-csrf-token':xsrf,'lang':'en'},timeout=60);r.raise_for_status();data=r.json()
        if total is None:total=data.get('totalResults');print(f'[easyrea] Обявени продукти: {total}',flush=True)
        records=data.get('results')
        if not isinstance(records,list):raise RuntimeError('Непълен Easyrea отговор')
        if not records:break
        received+=len(records)
        added=0
        for p in records:
            code=sku(p.get('codeArticle'))
            if not code:continue
            if code in out:
                if ean(p.get('gencode')) and ean(out[code].get('gencode')) and ean(p['gencode'])!=ean(out[code]['gencode']):conflicts.add(code)
            else:out[code]=p;added+=1
        if not added and page>1:raise RuntimeError('Easyrea повтори страница без нови кодове; импортът е спрян')
        print(f'[easyrea] Страница {page}: уникални SKU {len(out)}',flush=True);page+=1;time.sleep(.3)
    if not out:raise RuntimeError('Празен Easyrea каталог')
    warning=''
    if total and received!=total:
        warning=f'Easyrea обявява {total}, върна {received} реда; прочетени са всички страници до празната. Импортират се само потвърдените карти.'
        print('[WARNING] '+warning,flush=True)
    return out,conflicts,warning

FIELDS=['sku','barcode','vendor','action','note','product_id','title','description','cost_eur','sell_price','image_count','images_ready','image_urls','ai_provider','category_id','category_name','handle','channels','status']
def write_report(rows,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore');w.writeheader();w.writerows(rows)

def plan(catalog,index,supplier_conflicts):
    collisions=defaultdict(set)
    for code,p in catalog.items():
        if ean(p.get('gencode')):collisions[ean(p['gencode'])].add(code)
    rows=[];candidates=[]
    for code in sorted(catalog):
        p=catalog[code];barcode=ean(p.get('gencode'));vendor=VENDORS.get(str(p.get('marque') or '').strip().upper())
        action,pid=index.decide(code,barcode)
        if code in supplier_conflicts:action='REVIEW_SUPPLIER_SKU_CONFLICT'
        elif barcode and len(collisions[barcode])>1 and action in ('NEW','RESUME'):action='REVIEW_SUPPLIER_EAN_CONFLICT'
        elif not vendor and action in ('NEW','RESUME'):action='REVIEW_UNKNOWN_BRAND'
        row={'sku':code,'barcode':barcode,'vendor':vendor or str(p.get('marque') or ''),'action':action,'product_id':pid or '', 'note':''}
        rows.append(row)
        if action in ('NEW','RESUME'):candidates.append((code,p,row))
    return rows,candidates

def main():
    dry=runtime.dry_run(default=True);limit=runtime.batch_size(default=50)
    preview=os.environ.get('IMPORT_AI_PREVIEW')=='1'
    requested=os.environ.get('IMPORT_AI_PROVIDER','auto')
    repair_ids=__import__('json').loads(os.environ.get('IMPORT_REPAIR_IDS','[]'))
    if repair_ids:return repair(repair_ids,dry,requested)
    config=runtime.require_env('EASYREA_LOGIN','EASYREA_PASSWORD','SHOPIFY_STORE','SHOPIFY_CLIENT_ID','SHOPIFY_CLIENT_SECRET')
    if not dry or preview:provider_name(requested)
    report=Path(os.environ.get('HUB_REPORT_DIR','.'))/f"import_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    rows=[];errors=0
    print(f'=== Импорт v4: {"AI пример (до 5)" if dry and preview else "ПЛАН без AI" if dry else "Импорт като Draft"} | следващи {limit} липсващи ===',flush=True)
    try:
        shop=Shopify(config)
        session,xsrf=easyrea_login();catalog,conflicts,warning=fetch_catalog(session,xsrf)
        index=Index(shop.variants())
        rows,candidates=plan(catalog,index,conflicts)
        counts=Counter(r['action'] for r in rows)
        print('[план] '+str(dict(counts)),flush=True)
        selected=candidates[:min(limit,5) if dry and preview else limit]
        for i,(code,listing,row) in enumerate(selected,1):
            print(f'PROGRESS {i}/{len(selected)} | {code}',flush=True)
            try:
                shop.current_product_id=None
                # Recheck both identities just before AI spending and any write.
                action,pid=shop.check(code,row['barcode'])
                reserved=shop.product(code=code)
                if reserved:
                    if source_tag(code) in reserved['tags'] and PENDING in reserved['tags'] and reserved['status'] in ('DRAFT','ACTIVE'):
                        if pid and pid!=reserved['id']:action='REVIEW_SKU_EAN_CONFLICT'
                        elif not action.startswith('REVIEW'):action,pid='RESUME',reserved['id']
                    elif row['action']=='RESUME':action='REVIEW_CHANGED_DRAFT'
                    elif action=='NEW':action='REVIEW_RESERVED_HANDLE'
                if action not in ('NEW','RESUME'):
                    row.update(action=action,product_id=pid or '');continue
                row['product_id']=pid or ''
                fiche=easyrea_fiche(session,xsrf,code)
                if not fiche:row.update(action='REVIEW_NO_PRODUCT_CARD');continue
                urls=image_urls(listing,fiche);unavailable=unavailable_images(urls);row.update(image_count=len(urls),image_urls=json_urls(urls))
                cost=Decimal(str(listing.get('prixAchat') or 0))/100
                price=calculate_price(float(cost))
                row.update(cost_eur=str(cost),sell_price=price)
                if not cost or not price:row['action']='REVIEW_NO_PRICE';continue
                if not urls or len(unavailable)==len(urls):row.update(action='REVIEW_NO_IMAGES',note='Липсват достъпни снимки');continue
                row['note']='Пропуснати липсващи снимки: '+str(len(unavailable)) if unavailable else ''
                if dry and not preview:
                    row.update(action='DRY_PLAN',note='Без AI заявки и без Shopify записи');continue
                if action=='RESUME':
                    existing=shop.product(id=pid);title=existing['title'];description=existing['descriptionHtml'];provider='saved'
                else:title,description,provider=generate(listing,fiche,row['vendor'],requested)
                category=shop.category_for(title,description,requested)
                row.update(title=title,description=description,ai_provider=provider,category_id=category['id'],category_name=category['fullName'],handle=title_handle(title))
                if dry:row.update(action='AI_PREVIEW',note='Само AI пример; без Shopify записи');continue
                # Catch products added while Claude was generating the copy.
                fresh,fresh_id=shop.check(code,row['barcode'])
                if fresh not in ('NEW','RESUME'):
                    row.update(action=fresh,product_id=fresh_id or '');continue
                pid,ready=shop.save_draft(code,row['barcode'],row['vendor'],title,description,price,cost,urls,listing,fiche,existing_id=pid,category=category,unavailable=unavailable)
                row.update(action='RESUMED' if action=='RESUME' else 'CREATED',product_id=pid,images_ready=ready,note='; '.join(filter(None,[warning,row['note']])),handle=shop.product(id=pid)['handle'],channels=0,status='DRAFT')
            except UncertainCreate as exc:
                row.update(action='UNCERTAIN_WRITE',note=str(exc),product_id=getattr(shop,'current_product_id',None) or row['product_id']);errors+=1;raise
            except AIConfigurationError as exc:
                row.update(action='AI_BLOCKED',note=str(exc),product_id=getattr(shop,'current_product_id',None) or row['product_id']);errors+=1;raise
            except Exception as exc:
                row.update(action='ERROR',note=f'{type(exc).__name__}: {exc}'[:500],product_id=getattr(shop,'current_product_id',None) or row['product_id']);errors+=1
                print(f'[ERROR] {code}: {row["note"]}',flush=True)
            finally:write_report(rows,report)
        print('[резултат] '+str(dict(Counter(r['action'] for r in rows))),flush=True)
    finally:
        if rows:write_report(rows,report);print(f'Отчет записан: {report}',flush=True)
    if errors:raise RuntimeError(f'{errors} продукта не са завършени; вижте отчета. Следващото изпълнение проверява същите Draft продукти.')

def repair(ids,dry,requested):
    config=runtime.require_env('SHOPIFY_STORE','SHOPIFY_CLIENT_ID','SHOPIFY_CLIENT_SECRET')
    shop=Shopify(config)
    provider_name(requested)
    report=Path(os.environ.get('HUB_REPORT_DIR','.'))/f"import_repair_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    rows=[];errors=0
    try:
        for i,pid in enumerate(ids,1):
            row={'product_id':pid};rows.append(row)
            try:
                p=shop.product(id=pid)
                if not p or not (READY in p['tags'] or IMPORTED in p['tags'] or PENDING in p['tags']):raise RuntimeError('Продуктът не е от завършен Hub импорт; няма промени')
                if len(p['variants']['nodes'])!=1:raise RuntimeError('Повече от един вариант')
                row.update(sku=p['variants']['nodes'][0]['sku'],barcode=p['variants']['nodes'][0]['barcode'],title=p['title'],image_count=len(p['media']['nodes']))
                print(f'PROGRESS {i}/{len(ids)} | {row["sku"]}',flush=True)
                category=shop.category_for(p['title'],p['descriptionHtml'],requested)
                row.update(category_id=category['id'],category_name=category['fullName'],handle=title_handle(p['title']))
                if dry:row.update(action='REPAIR_PREVIEW',note='Без Shopify записи');continue
                # Keep recovery tags until Draft verification succeeds.
                shop.checked(shop.call(UPDATE,{'product':{'id':pid,'tags':list(dict.fromkeys(p['tags']+[READY]))},'media':None}),'productUpdate')
                slug,channels=shop.finalize(p,category)
                row.update(action='UPDATED',handle=slug,channels=channels,status='DRAFT',images_ready=len(p['media']['nodes']))
            except AIConfigurationError:raise
            except Exception as exc:
                errors+=1;row.update(action='ERROR',note=str(exc)[:500]);print('[ERROR] '+row['note'],flush=True)
            finally:write_report(rows,report)
    finally:
        if rows:write_report(rows,report);print(f'Отчет записан: {report}',flush=True)
    print('[резултат] '+str(dict(Counter(r['action'] for r in rows))),flush=True)
    if errors:raise RuntimeError(f'{errors} продукта не са обновени; вижте отчета')


def json_urls(urls):
    import json
    return json.dumps(urls,ensure_ascii=False)

if __name__=='__main__':main()
