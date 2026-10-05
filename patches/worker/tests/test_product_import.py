import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch
import os,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'easyrea'))
from import_rules import Index, image_urls, validate_copy, PENDING, source_tag,handle,media_set_tag,title_handle,finished_tags
from import_products import Shopify,UncertainCreate,plan,main
from product_ai import generate, AIConfigurationError, classify, category_family

def variant(code='123',barcode='0012345678905',pid='1',pending=False):
    return {'id':'v'+pid,'sku':code,'barcode':barcode,'product':{'id':pid,'tags':[PENDING,source_tag(code)] if pending else [],'status':'DRAFT','handle':handle(code)}}

def product(pending=True,media=None,code='123',barcode='0012345678905'):
    return {'id':'1','title':'Маса atmosphera','descriptionHtml':'<p>Описание</p>','status':'DRAFT','handle':handle(code),'tags':[PENDING,source_tag(code),media_set_tag(['https://cdn/a.jpg'],'Маса atmosphera')] if pending else [],
            'variants':{'nodes':[{'id':'v1','sku':code,'barcode':barcode,'price':'15.00'}],'pageInfo':{'hasNextPage':False}},
            'media':{'nodes':media or [],'pageInfo':{'hasNextPage':False}}}

class ImportRules(unittest.TestCase):
    def test_provider_credit_failure_stops_without_retry_or_secret(self):
        import requests
        response=Mock(status_code=400)
        response.json.return_value={'error':{'type':'invalid_request_error','message':'Credit too low secret-key'}}
        response.raise_for_status.side_effect=requests.HTTPError(response=response)
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'secret-key'}),patch('product_ai.requests.post',return_value=response) as post,patch('product_ai.time.sleep') as sleep:
            with self.assertRaises(AIConfigurationError) as error:generate({}, {}, 'Neka','claude')
        self.assertNotIn('secret-key',str(error.exception));self.assertIn('Credit too low',str(error.exception))
        self.assertEqual(post.call_count,1);sleep.assert_not_called()
    def test_transliterated_title_and_single_finished_tag(self):
        self.assertEqual(title_handle('Анти-пяна за спа Neka 1 литър'),'anti-pyana-za-spa-neka-1-litar')
        self.assertEqual(finished_tags(['seasonal','hub-easyrea-ready','hub-easyrea-sku-X','hub-easyrea-images-Y']),['seasonal','hub-easyrea'])
    def test_category_walk_uses_only_valid_shop_ids(self):
        root={'id':'root','parentId':None,'isRoot':True,'isLeaf':False,'fullName':'Home'}
        leaf={'id':'leaf','parentId':'root','isRoot':False,'isLeaf':True,'fullName':'Home > Cushions'}
        def choose(system,prompt,schema,requested,validator):
            path='Home > Cushions' if 'Home > Cushions' in schema['properties']['category_name']['enum'] else 'Home'
            return validator({'category_name':path}),'openai'
        with patch('product_ai.request_json',side_effect=choose):
            self.assertEqual(classify('Възглавница','Описание',[root,leaf])['id'],'leaf')
    def test_unknown_category_is_rejected(self):
        root={'id':'root','parentId':None,'isRoot':True,'isLeaf':True,'fullName':'Home'}
        with patch('product_ai.request_json') as request:
            request.side_effect=lambda system,prompt,schema,requested,validator: (validator({'category_name':'invented'}),'openai')
            with self.assertRaises(ValueError):classify('Възглавница','Описание',[root])
    def test_product_family_guards_supply_and_accessory_categories(self):
        self.assertTrue(category_family('Гранули хлор Neka 3 кг').endswith('Pool Cleaners & Chemicals'))
        self.assertIsNone(category_family('Генератор за хлор Neka'))
        self.assertTrue(category_family('Декоративна възглавница Hesperide').endswith('Throw Pillows'))
        self.assertTrue(category_family('Основа за парасол Hesperide').endswith('Outdoor Umbrella Bases'))
        self.assertIsNone(category_family('Калъф за чадър Hesperide'))
    def test_ean_only_existing_and_conflicts(self):
        self.assertEqual(Index([variant(code='')]).decide('123','0012345678905')[0],'EXISTS_EAN')
        self.assertTrue(Index([variant(),variant(pid='2',code='456',barcode='999')]).decide('123','999')[0].startswith('REVIEW'))
        self.assertTrue(Index([variant(),variant(pid='2')]).decide('123','0012345678905')[0].startswith('REVIEW'))
    def test_pending_resumes_even_when_sku_was_not_written(self):
        v=variant(pending=True);v['sku']='';v['barcode']=''
        self.assertEqual(Index([v]).decide('123','0012345678905'),('RESUME','1'))
    def test_supplier_collisions_are_never_new(self):
        cat={'123':{'gencode':'01','marque':'ATMOSPHERA'},'456':{'gencode':'01','marque':'FIVE'}}
        rows,candidates=plan(cat,Index([]),set());self.assertEqual(candidates,[])
        self.assertTrue(all(r['action']=='REVIEW_SUPPLIER_EAN_CONFLICT' for r in rows))
    def test_all_media_sources_nested_strings_and_dedup(self):
        urls=image_urls({'photoPrincipale':'https://cdn/a.jpg','photoAmbiance':'https://cdn/b.jpg'}, {'listePhotos':[{'urlPhoto':'https://cdn/c.jpg'},'https://cdn/d.jpg'], 'images':{'large':'https://cdn/a.jpg?width=500'},'manuel':'https://cdn/instructions.pdf'})
        self.assertEqual(urls,['https://cdn/a.jpg','https://cdn/b.jpg','https://cdn/c.jpg','https://cdn/d.jpg'])
    def test_ai_english_missing_brand_and_html_are_checked(self):
        good={'title':'Маса atmosphera Bella, Бял','description':'<p>'+'Българско описание за масата. '*8+'</p><script>bad()</script>'}
        title,desc=validate_copy(good,'atmosphera');self.assertNotIn('bad()',desc)
        for title in ['English table atmosphera','Маса без марка','<b>Маса atmosphera</b>']:
            with self.assertRaises(ValueError):validate_copy({**good,'title':title},'atmosphera')

class ImportWrites(unittest.TestCase):
    def shop(self):
        s=Shopify.__new__(Shopify);s.config={'SHOPIFY_STORE':'test'};s.session=Mock();return s
    def test_finalize_keeps_draft_without_publication_access(self):
        s=self.shop();p=product(media=[{'id':'m','alt':'image','status':'READY','image':{'url':'https://cdn/a'}}]);category={'id':'category'}
        saved={**p,'status':'DRAFT','handle':'masa-atmosphera','category':category,'variants':{'nodes':[{**p['variants']['nodes'][0],'inventoryPolicy':'CONTINUE'}]}}
        s.channels=Mock(side_effect=AssertionError('Draft imports must not access publications'));s.product=Mock(return_value=saved)
        s.call=Mock(side_effect=[{'productByIdentifier':None},{'productVariantsBulkUpdate':{'productVariants':[{'id':'v1'}]}},{'productUpdate':{'product':{'id':'1'}}},{'productUpdate':{'product':{'id':'1'}}}])
        self.assertEqual(s.finalize(p,category),('masa-atmosphera',0))
        s.channels.assert_not_called()
        self.assertEqual(s.call.call_args_list[2].args[1]['product']['status'],'DRAFT')
        self.assertEqual(s.call.call_args.args[1]['product']['tags'],['hub-easyrea'])
        self.assertFalse(any('publishablePublish' in call.args[0] for call in s.call.call_args_list))
    def test_unconfirmed_draft_retains_recovery_tags(self):
        s=self.shop();p=product(media=[{'status':'READY','image':{'url':'https://cdn/a'}}]);s.product=Mock(return_value={**p,'status':'ACTIVE'})
        s.call=Mock(side_effect=[{'productByIdentifier':None},{'productVariantsBulkUpdate':{'productVariants':[{'id':'v1'}]}},{'productUpdate':{'product':{'id':'1'}}}])
        with self.assertRaises(RuntimeError):s.finalize(p,{'id':'category'})
        self.assertEqual(s.call.call_count,3)
    def test_create_timeout_is_not_retried(self):
        s=self.shop();s.session.post.side_effect=__import__('requests').Timeout()
        with self.assertRaises(UncertainCreate):s.call('mutation Test { test }')
        self.assertEqual(s.session.post.call_count,1)
    def test_graphql_user_errors_do_not_count_as_success(self):
        with self.assertRaises(RuntimeError):Shopify.checked({'productVariantsBulkUpdate':{'productVariants':[],'userErrors':[{'message':'failure'}]}},'productVariantsBulkUpdate')
    def test_variant_failure_leaves_pending_without_media_or_ready(self):
        s=self.shop();s.product=Mock(return_value=product());s.call=Mock(return_value={'productVariantsBulkUpdate':{'userErrors':[{'message':'failure'}]}})
        with self.assertRaises(RuntimeError):s.save_draft('123','0012345678905','atmosphera','title','desc',15,5,['https://cdn/a.jpg'],{}, {})
        self.assertEqual(s.call.call_count,1)
    def test_resume_existing_media_does_not_upload_it_again(self):
        ready={'id':'m1','alt':'Маса atmosphera — изображение 1','status':'READY','image':{'url':'https://shopify/a.jpg'}}
        s=self.shop();s.product=Mock(return_value=product(media=[ready]));s.call=Mock(side_effect=[{'productVariantsBulkUpdate':{'productVariants':[{'id':'v1'}],'userErrors':[]}}, {'productUpdate':{'product':{'id':'1'},'userErrors':[]}}])
        s.finalize=Mock()
        pid,n=s.save_draft('123','0012345678905','atmosphera','title','desc',15,5,['https://cdn/a.jpg'],{}, {},category={'id':'category'})
        self.assertEqual((pid,n),('1',1));self.assertEqual(s.call.call_count,1)
        s.finalize.assert_called_once()
    def test_image_failure_prevents_ready(self):
        bad={'id':'m1','alt':'Маса atmosphera — изображение 1','status':'FAILED','image':None}
        s=self.shop();s.product=Mock(return_value=product(media=[bad]));s.call=Mock(return_value={'productVariantsBulkUpdate':{'productVariants':[{'id':'v1'}],'userErrors':[]}})
        with self.assertRaises(RuntimeError):s.save_draft('123','0012345678905','atmosphera','title','desc',15,5,['https://cdn/a.jpg'],{}, {})
        self.assertEqual(s.call.call_count,1)
    def test_dry_plan_never_calls_ai_or_mutates_shopify(self):
        import tempfile,csv
        cat={'123':{'gencode':'0012345678905','marque':'ATMOSPHERA','prixAchat':500,'photoPrincipale':'https://cdn/a.jpg'}}
        s=Mock();s.variants.return_value=[];s.check.return_value=('NEW',None);s.product.return_value=None
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'HUB_REPORT_DIR':d,'IMPORT_AI_PREVIEW':'0'}),patch('import_products.runtime.require_env',return_value={'SHOPIFY_STORE':'test'}),patch('import_products.runtime.dry_run',return_value=True),patch('import_products.runtime.batch_size',return_value=5),patch('import_products.easyrea_login',return_value=(None,None)),patch('import_products.fetch_catalog',return_value=(cat,set(),'')),patch('import_products.Shopify',return_value=s),patch('import_products.easyrea_fiche',return_value={'informationsTechniques':{}}),patch('import_products.unavailable_images',return_value=[]),patch('import_products.generate') as ai:
            main();ai.assert_not_called();s.save_draft.assert_not_called()
            with next(Path(d).glob('*.csv')).open(encoding='utf-8-sig') as f:self.assertEqual(next(csv.DictReader(f))['action'],'DRY_PLAN')
    def test_openai_schema_and_output_parser(self):
        content={'title':'Маса atmosphera Bella, Бял','description':'<p>'+'Описание на български за продукта. '*8+'</p>'}
        r=Mock();r.json.return_value={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(content)}]}]}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch('product_ai.requests.post',return_value=r) as post:
            title,desc,p=generate({}, {},'atmosphera','openai')
            self.assertEqual(p,'openai');self.assertEqual(post.call_args.kwargs['json']['text']['format']['schema']['additionalProperties'],False)
            self.assertFalse(post.call_args.kwargs['json']['store'])

if __name__=='__main__':unittest.main()
