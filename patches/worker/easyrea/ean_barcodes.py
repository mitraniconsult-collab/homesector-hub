#!/usr/bin/env python3
"""Shopify EAN migration, uses existing Hub Shopify client credentials.
Safe default is dry-run. Re-running a real job skips all already-correct EANs.
"""
from __future__ import annotations

import concurrent.futures
import csv
import datetime as dt
import os
import pathlib
import sys
import threading
from collections import defaultdict

import import_products
from import_products import Shopify

# Multi-barcode types are available in Shopify Admin API 2026-10.
import_products.API_VERSION = '2026-10'

QUERY = """query EanScan($after:String) {
  productVariants(first:50,after:$after) {
    nodes { id sku product { id title }
      barcodes(first:20) { nodes { value type } pageInfo { hasNextPage } } }
    pageInfo { endCursor hasNextPage }
  }
}"""
WRITE = """mutation EanWrite($productId:ID!,$variants:[ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId:$productId,variants:$variants) {
    productVariants { id barcodes(first:20) { nodes { value type } } }
    userErrors { field message }
  }
}"""
READ = """query EanVerify($ids:[ID!]!) {
  nodes(ids:$ids) { ... on ProductVariant { id
    barcodes(first:20) { nodes { value type } pageInfo { hasNextPage } } } }
}"""

def ean(value):
    if not isinstance(value,str) or not value.isascii() or not value.isdecimal() or len(value) not in (8,13):
        return False
    numbers=[int(x) for x in value]
    check=numbers.pop()
    total=sum(n*(3 if i%2==0 else 1) for i,n in enumerate(numbers[::-1]))
    return (10-total%10)%10==check

def classification(variant):
    b=variant['barcodes']
    items=b['nodes']
    if not items: return 'NO_BARCODE'
    if b['pageInfo']['hasNextPage']: return 'REVIEW_TRUNCATED'
    if not all(ean(x['value']) for x in items): return 'REVIEW_NON_EAN'
    if all(x['type']=='EAN' for x in items): return 'ALREADY_EAN'
    return 'UPDATE'

def main():
    real='--real-run' in sys.argv
    if '--dry-run' in sys.argv: real=False
    config={k:os.environ.get(k,'') for k in ('SHOPIFY_STORE','SHOPIFY_CLIENT_ID','SHOPIFY_CLIENT_SECRET')}
    if not all(config.values()):
        raise RuntimeError('Липсва SHOPIFY_STORE или Shopify Client ID/Secret във Worker')
    shop=Shopify(config)
    # Separate clients per worker avoid shared requests.Session use.
    thread=threading.local()
    def client():
        if not hasattr(thread,'shop'):thread.shop=Shopify(config)
        return thread.shop
    report_dir=pathlib.Path(os.environ.get('HUB_REPORT_DIR','.'))
    report_dir.mkdir(parents=True,exist_ok=True)
    filename=report_dir/('ean_migration_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S')+'.csv')
    counts=defaultdict(int)
    cursor=None
    visited=set()
    page_number=0
    with filename.open('w',newline='',encoding='utf-8-sig') as fp:
        writer=csv.writer(fp)
        writer.writerow(['variant_id','sku','product','barcodes','status','note'])
        while True:
            connection=shop.call(QUERY,{'after':cursor})['productVariants']
            rows=connection['nodes']
            if not rows and connection['pageInfo']['hasNextPage']:raise RuntimeError('Празна Shopify страница с още резултати')
            groups=defaultdict(list)
            info={}
            for v in rows:
                status=classification(v)
                counts['scanned']+=1
                info[v['id']]=v
                if status=='UPDATE':
                    groups[v['product']['id']].append({
                        'id':v['id'],
                        'barcodes':[{'value':b['value'],'type':'EAN'} for b in v['barcodes']['nodes']]
                    })
                else:
                    counts[status]+=1
                    writer.writerow([v['id'],v.get('sku',''),v['product']['title'],
                        '|'.join(b['value'] for b in v['barcodes']['nodes']),status,''])
            if groups and real:
                def run_one(entry):
                    product_id,variants=entry
                    client_sh=client()
                    try:
                        response=client_sh.call(WRITE,{'productId':product_id,'variants':variants})['productVariantsBulkUpdate']
                        if response['userErrors']:raise RuntimeError(str(response['userErrors']))
                        actual={v['id']:v for v in response['productVariants']}
                        # Verify every returned variant's values and type.
                        for variant in variants:
                            remote=actual.get(variant['id'])
                            if not remote or remote['barcodes']['nodes']!=variant['barcodes']:
                                raise RuntimeError('Неуспешна проверка на EAN след запис '+variant['id'])
                        return variants, None
                    except Exception as exc:
                        # An ambiguous mutation is not blindly retried.
                        return variants, str(exc)
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    futures=[pool.submit(run_one,entry) for entry in groups.items()]
                    for future in concurrent.futures.as_completed(futures):
                        batch,error=future.result()
                        for v in batch:
                            vv=info[v['id']]
                            status='REVIEW_FAILED' if error else 'UPDATED'
                            counts[status]+=1
                            writer.writerow([v['id'],vv.get('sku',''),vv['product']['title'],
                                '|'.join(x['value'] for x in v['barcodes']),status,error or ''])
            else:
                for group in groups.values():
                    for v in group:
                        vv=info[v['id']]
                        counts['WOULD_UPDATE']+=1
                        writer.writerow([v['id'],vv.get('sku',''),vv['product']['title'],
                            '|'.join(x['value'] for x in v['barcodes']),'WOULD_UPDATE','dry-run'])
            fp.flush()
            page_number+=1
            print(f"[EAN] page={page_number} scanned={counts['scanned']} updated={counts['UPDATED']} would_update={counts['WOULD_UPDATE']} failed={counts['REVIEW_FAILED']} blank={counts['NO_BARCODE']} invalid={counts['REVIEW_NON_EAN']}",flush=True)
            if not connection['pageInfo']['hasNextPage']:break
            new_cursor=connection['pageInfo']['endCursor']
            if not new_cursor or new_cursor==cursor or new_cursor in visited:
                raise RuntimeError('Shopify pagination stalled')
            visited.add(new_cursor)
            cursor=new_cursor
    print(f"[EAN] FINAL mode={'real' if real else 'dry'} counts={dict(counts)} report={filename}",flush=True)
    if counts['REVIEW_FAILED']:
        raise RuntimeError(f"{counts['REVIEW_FAILED']} записа не са потвърдени. Проверете CSV отчета.")

if __name__=='__main__':
    main()
