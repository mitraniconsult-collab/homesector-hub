import copy
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import image_jobs as jobs
from image_sources import parse_product, safe_url

class State:
    def __init__(self,state=None): self.state=state; self.version=0
    def read(self): return copy.deepcopy(self.state),str(self.version)
    def write(self,state,version):
        if version!=str(self.version): raise jobs.Conflict()
        self.state=copy.deepcopy(state);self.version+=1

class ImagesTests(unittest.TestCase):
    def item(self): return {'id':'gid://shopify/Product/1','sku':'123','barcode':'','title':'Маса','vendor':'Hesperide','urls':['https://media.decorationbrands.com/media/catalog/product/3/5/a.jpg'],'attempted':True,'attempted_at':time.time()}
    def product(self): return {'title':'Маса','vendor':'Hesperide','status':'ACTIVE','media':{'nodes':[]},'variants':{'nodes':[{'sku':'123','barcode':''}],'pageInfo':{'hasNextPage':False}}}
    def test_resume_does_not_repeat_ambiguous_mutation(self):
        item=self.item();item['attempted_at']=0
        runner=jobs.ImageJobs(State());shop=Mock();shop.product.return_value=self.product()
        result=runner.process(shop,{'mode':'real'},item,0)
        self.assertEqual(result,'REVIEW_UNCERTAIN');shop.call.assert_not_called()
    def test_processing_and_ready_media_are_reconciled(self):
        item=self.item();p=self.product();p['media']['nodes']=[{'alt':jobs.image_alt('123',item['urls'][0]),'status':'PROCESSING','image':None}]
        self.assertEqual(jobs.reconcile(p,item),'WAITING_MEDIA')
        p['media']['nodes'][0].update(status='READY',image={'url':'https://cdn.shopify.com/test.jpg'})
        self.assertEqual(jobs.reconcile(p,item),'ADDED')
    def test_wait_for_eventual_media_visibility(self): self.assertEqual(jobs.reconcile(self.product(),self.item()),'WAITING_MEDIA')
    def test_different_owner_cannot_mutate_checkpoint(self):
        store=State({'owner':'other','status':'running','lease_until':time.time()+300})
        with self.assertRaises(jobs.Stopped): jobs.ImageJobs(store).update(lambda s:s.update(cursor=20))
        self.assertNotIn('cursor',store.state)
    def test_stale_lease_can_be_recovered_and_fences_previous_owner(self):
        store=State({'owner':'old','status':'running','lease_until':0})
        new=jobs.ImageJobs(store);new.claim()
        old=jobs.ImageJobs(store);old.owner='old'
        with self.assertRaises(jobs.Stopped):old.update(lambda s:None)
        self.assertEqual(store.state['owner'],new.owner)
    def test_pause_is_persisted(self):
        store=State({'version':1,'id':'run','owner':'old','lease_until':time.time()+300,'status':'running','items':[]})
        manager=jobs.ImageJobs(store)
        with patch.object(manager,'wake'):manager.control('pause')
        self.assertEqual(store.state['status'],'paused')
        old=jobs.ImageJobs(store);old.owner='old'
        with self.assertRaises(jobs.Stopped):old.update(lambda s:None)
    def test_checkpoint_conflict_does_not_overwrite(self):
        store=State({'a':1});_,version=store.read();store.write({'a':2},version)
        with self.assertRaises(jobs.Conflict):store.write({'a':3},version)
        self.assertEqual(store.state,{'a':2})
    def test_existing_image_skips_ai_and_write(self):
        shop=Mock();shop.product.return_value=self.product();shop.product.return_value['media']['nodes']=[{'id':'image'}]
        item=self.item();item.pop('attempted')
        with patch.object(jobs,'verify') as ai:
            self.assertEqual(jobs.ImageJobs(State()).process(shop,{'mode':'real'},item,0),'SKIPPED');ai.assert_not_called();shop.call.assert_not_called()
    def test_dry_mode_never_calls_ai_or_shopify_mutation(self):
        shop=Mock();shop.product.return_value=self.product();item=self.item();item.pop('attempted');item.pop('urls')
        with patch.object(jobs,'discover',return_value={'url':'source','images':['image']}),patch.object(jobs,'verify') as ai:
            self.assertEqual(jobs.ImageJobs(State()).process(shop,{'mode':'dry'},item,0),'PLANNED');ai.assert_not_called();shop.call.assert_not_called()
    def test_checkpoint_uses_storage_version_not_http_compression_etag(self):
        response=Mock();response.status_code=200
        response.headers={'etag':'W/"http-transformed"','x-hub-state-version':'"storage-version"'}
        response.json.return_value={'id':'run'}
        with patch.object(jobs.requests,'get',return_value=response),patch.dict('os.environ',{'HUB_WORKER_TOKEN':'test'}):
            value,version=jobs.RemoteState().read()
        self.assertEqual(version,'"storage-version"')
    def test_full_run_recovers_lost_mutation_response_without_duplicate(self):
        item=self.item();item.pop('attempted');item.pop('urls')
        state={'version':1,'id':'run','status':'running','phase':'process','mode':'real','items':[item],'cursor':0,'owner':'','lease_until':0,'ai_calls':0}
        store=State(state);manager=jobs.ImageJobs(store);manager.claim()
        shop=Mock();product=self.product();shop.product.side_effect=lambda **kw:copy.deepcopy(product)
        url='https://media.decorationbrands.com/media/catalog/product/3/5/a.jpg'
        def upload(*args,**kwargs):
            product['media']['nodes']=[{'alt':jobs.image_alt('123',url),'status':'READY','image':{'url':'https://cdn.shopify.com/test.jpg'}}]
            raise jobs.UncertainCreate('response lost')
        shop.call.side_effect=upload
        with patch.object(jobs,'Shopify',return_value=shop),patch.object(jobs,'discover',return_value={'url':'https://www.decorationbrands.com/a.html','images':[url]}),patch.object(jobs,'verify',return_value={'matches':True,'reason':'exact match'}),patch.dict('os.environ',{'OPENAI_API_KEY':'test'}):
            manager.execute(store.read()[0])
        self.assertEqual(store.state['status'],'success')
        self.assertEqual(store.state['items'][0]['result'],'ADDED')
        self.assertEqual(store.state['ai_calls'],1)
        self.assertEqual(shop.call.call_count,1)
    def test_original_gallery_exact_identifiers(self):
        text='''<div class="product-page-top"><div class="product-gallery-slick"><img src="https://media.decorationbrands.com/media/catalog/product/3/5/3560231743154_1.jpg?width=30"></div><div id="gallery-modal"></div><h1>Table cover</h1><div>186886</div><h2>Related Products</h2><div>186887</div>'''
        self.assertIsNotNone(parse_product(text,'186886','3560231743154'))
        self.assertIsNone(parse_product(text,'186887'))
        self.assertIsNone(parse_product(text,'186886','3560231743155'))
    def test_only_supplier_https_hosts(self):
        for url in ('http://www.decorationbrands.com/x','https://www.decorationbrands.com.evil.com/x','https://user@www.decorationbrands.com/x','https://127.0.0.1/x'):
            self.assertFalse(safe_url(url))
    def test_api_failure_blocks_instead_of_spending_in_a_loop(self):
        with patch.object(jobs,'request_json',side_effect=RuntimeError('failed')):
            with self.assertRaises(jobs.AIConfigurationError): jobs.verify(self.product(),{'sku':'123','barcode':'','title':'t','facts':'f','images':[]})

if __name__=='__main__': unittest.main()
