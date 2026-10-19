import io
import sys
import time
import copy
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'easyrea'))
import image_quality as quality
import image_jobs as jobs

SOURCE='https://media.decorationbrands.com/media/catalog/product/3/5/source.jpg'
OLD='https://cdn.shopify.com/files/old.jpg'
class Store:
    def __init__(self,state):self.state=state
    def read(self):return copy.deepcopy(self.state),'v'
    def write(self,state,tag):self.state=copy.deepcopy(state)

class QualityTests(unittest.TestCase):
    def product(self):
        return {'id':'p','title':'Стол Hesperide','vendor':'Hesperide','status':'ACTIVE','variants':{'nodes':[{'id':'v','sku':'123','barcode':'','image':None}],'pageInfo':{'hasNextPage':False}},'media':{'nodes':[{'id':'old','alt':'old','status':'READY','image':{'id':'old-image','url':OLD,'width':400,'height':400}}],'pageInfo':{'hasNextPage':False}}}
    def source(self):return {'sku':'123','barcode':'','title':'Chair','facts':'Chair Hesperide','images':[SOURCE]}
    def metrics(self,url):return {'width':400 if url==OLD else 1200,'height':400 if url==OLD else 1200,'short':400 if url==OLD else 1200,'sharpness':100,'hash':url,'bytes_hash':url}
    def decision(self):return {'matches':True,'reason':'Същият стол, по-добри снимки','add_indices':[],'replacements':[{'current_id':'old','source_index':0,'reason':'Пикселизирана стара снимка'}]}
    def test_low_resolution_is_replaced_only_with_a_better_original(self):
        with patch.object(quality,'inspect',side_effect=self.metrics),patch.object(quality,'request_json',return_value=(self.decision(),'openai')):
            result=quality.gallery_plan(self.product(),self.source())
        self.assertEqual(result['urls'],[SOURCE]);self.assertEqual(result['remove_ids'],['old']);self.assertTrue(result['originals'])
    def test_inferior_supplier_image_cannot_remove_good_original(self):
        p=self.product();p['media']['nodes'][0]['image'].update(width=1600,height=1600)
        def metric(url):return {**self.metrics(url),'short':1600 if url==OLD else 1200}
        with patch.object(quality,'inspect',side_effect=metric),patch.object(quality,'request_json',return_value=(self.decision(),'openai')):
            result=quality.gallery_plan(p,self.source())
        self.assertEqual(result['remove_ids'],[])
    def test_dry_run_checks_quality_without_ai_or_removals(self):
        with patch.object(quality,'inspect',side_effect=self.metrics),patch.object(quality,'request_json')as ai:
            result=quality.gallery_plan(self.product(),self.source(),real=False)
        ai.assert_not_called();self.assertEqual(result['remove_ids'],[])
    def test_source_must_be_decorationbrands(self):
        source=self.source();source['images']=['https://cdn.shopify.com/files/new.jpg']
        with patch.object(quality,'inspect',side_effect=self.metrics):
            with self.assertRaises(ValueError):quality.gallery_plan(self.product(),source)
    def test_unknown_ai_media_id_rejected(self):
        decision=self.decision();decision['replacements'][0]['current_id']='unrelated-file'
        with patch.object(quality,'inspect',side_effect=self.metrics),patch.object(quality,'request_json',return_value=(decision,'openai')):
            with self.assertRaises(jobs.AIConfigurationError):quality.gallery_plan(self.product(),self.source())
    def test_identical_good_gallery_does_not_call_ai_or_duplicate(self):
        def metric(url):return {**self.metrics(url),'short':1200,'hash':'same','sharpness':100}
        with patch.object(quality,'inspect',side_effect=metric),patch.object(quality,'request_json')as ai:
            result=quality.gallery_plan(self.product(),self.source())
        ai.assert_not_called();self.assertFalse(result['urls']);self.assertFalse(result['remove_ids'])
    def test_replacement_is_not_lost_when_low_res_pixels_hash_like_original(self):
        def metric(url):return {**self.metrics(url),'hash':'same'}
        with patch.object(quality,'inspect',side_effect=metric),patch.object(quality,'request_json',return_value=(self.decision(),'openai')):
            result=quality.gallery_plan(self.product(),self.source())
        self.assertEqual(result['remove_ids'],['old'])
    def test_blur_metric_detects_blurred_test_pattern(self):
        im=Image.new('RGB',(512,512),'white');draw=ImageDraw.Draw(im)
        for x in range(0,512,16):draw.rectangle((x,0,x+7,511),fill='black')
        def encode(im):
            stream=io.BytesIO();im.save(stream,format='PNG');return quality.pixels(stream.getvalue())
        self.assertGreater(encode(im)['sharpness'],encode(im.filter(ImageFilter.GaussianBlur(8)))['sharpness'])
    def manager(self,item):
        runner=jobs.ImageJobs();runner.store=Store({'owner':runner.owner,'lease_until':time.time()+100,'status':'running','items':[item]});return runner
    def test_no_detach_until_every_new_image_is_ready(self):
        p=self.product();item={'sku':'123','urls':[SOURCE],'remove_ids':['old']};runner=self.manager(item);shop=Mock()
        self.assertEqual(runner.finish_replacement(shop,p,item,0),'WAITING_MEDIA');shop.call.assert_not_called()
    def test_detach_only_approved_product_reference_and_keep_file(self):
        p=self.product();item={'id':'p','sku':'123','urls':[SOURCE],'remove_ids':['old'],'before_media':quality.fingerprint(p)}
        p['media']['nodes'].append({'id':'new','alt':jobs.image_alt('123',SOURCE),'status':'READY','image':{'id':'new-image','url':SOURCE}})
        runner=self.manager(item);shop=Mock();shop.call.return_value={'fileUpdate':{'userErrors':[]}}
        self.assertEqual(runner.finish_replacement(shop,p,item,0),'WAITING_MEDIA')
        query,variables=shop.call.call_args.args
        self.assertIn('fileUpdate',query);self.assertNotIn('fileDelete',query)
        self.assertEqual(variables,{'files':[{'id':'old','referencesToRemove':['p']}]})
        self.assertTrue(runner.store.state['items'][0]['detach_attempted'])
    def test_lost_detach_response_is_reconciled_without_repeating(self):
        p=self.product();item={'id':'p','sku':'123','urls':[SOURCE],'remove_ids':['old'],'detach_attempted':True,'detach_at':0,'before_media':quality.fingerprint(p)}
        p['media']['nodes'].append({'id':'new','alt':jobs.image_alt('123',SOURCE),'status':'READY','image':{'id':'new-image','url':SOURCE}})
        runner=self.manager(item);shop=Mock()
        self.assertEqual(runner.finish_replacement(shop,p,item,0),'REVIEW_CLEANUP');shop.call.assert_not_called()
        p['media']['nodes']=p['media']['nodes'][1:]
        self.assertEqual(runner.finish_replacement(shop,p,item,0),'IMPROVED');shop.call.assert_not_called()

if __name__=='__main__':unittest.main()
