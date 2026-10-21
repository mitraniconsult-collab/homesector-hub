import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'easyrea'))
import image_sources as sources
from image_diagnostics import ImageReview

URL='https://www.decorationbrands.com/chair.html'
PAGE='''<div class="product-page-top"><div class="product-gallery-slick"><img src="https://media.decorationbrands.com/media/catalog/product/3/5/3560231743154_1.jpeg"></div><div id="gallery-modal"></div><h1>Chair</h1><div>186886</div><h2>Related Products</h2><div>186887</div>'''

class SourceTests(unittest.TestCase):
    def test_js_search_uses_published_readonly_config_and_filters_external_urls(self):
        page='window.algoliaConfig = {"applicationId":"ABCDEFGHIJ","indexName":"store","apiKey":"public-test-key"};'
        response=Mock(status_code=200)
        response.json.return_value={'nbHits':2,'hits':[{'url':URL},{'url':'https://example.com/wrong'}]}
        with patch.object(sources.requests,'post',return_value=response) as post:
            self.assertEqual(sources.search_urls(page,'123'),[URL])
        self.assertFalse(post.call_args.kwargs['json']['typoTolerance'])
        self.assertEqual(post.call_args.kwargs['json']['query'],'123')
    def test_js_search_failure_is_not_reported_as_product_missing(self):
        page='window.algoliaConfig = {"applicationId":"ABCDEFGHIJ","indexName":"store","apiKey":"public-test-key"};'
        with patch.object(sources.requests,'post',return_value=Mock(status_code=503)):
            with self.assertRaises(ImageReview) as error:sources.search_urls(page,'123')
        self.assertEqual(error.exception.code,'SOURCE_SEARCH_UNAVAILABLE')
    def search(self,links=True):
        r=Mock(status_code=200)
        r.text=f'<a class="product-item-link" href="{URL}">Chair</a>' if links else ''
        return r
    def test_ean_only_matches_exact_gallery_and_accepts_jpeg(self):
        self.assertIsNotNone(sources.parse_product(PAGE,'','3560231743154'))
        self.assertIsNone(sources.parse_product(PAGE,'','3560231743155'))
        self.assertIsNone(sources.parse_product(PAGE,'',''))
        self.assertIsNone(sources.parse_product(PAGE,'186887','3560231743154'))
    def test_search_falls_back_from_sku_to_ean(self):
        with patch.object(sources.requests,'get',side_effect=[self.search(False),self.search()]) as get,patch.object(sources,'fetch',return_value=PAGE):
            result=sources.discover('186886','3560231743154')
        self.assertEqual(result['url'],URL)
        self.assertEqual(result['source_query'],'186886; 3560231743154')
        self.assertEqual(get.call_args.kwargs['params']['q'],'3560231743154')
    def test_not_found_and_ean_mismatch_have_different_reasons(self):
        with patch.object(sources.requests,'get',return_value=self.search(False)):
            with self.assertRaises(ImageReview) as error:sources.discover('123')
        self.assertEqual(error.exception.code,'SOURCE_NOT_FOUND')
        with patch.object(sources.requests,'get',return_value=self.search()),patch.object(sources,'fetch',return_value=PAGE):
            with self.assertRaises(ImageReview) as error:sources.discover('186886','3560231743155')
        self.assertEqual(error.exception.code,'EAN_MISMATCH')
        self.assertEqual(error.exception.details['source_candidates'],1)
    def test_ambiguous_exact_matches_are_never_chosen_arbitrarily(self):
        r=self.search();r.text+=f'<a class="product-item-link" href="{URL}?duplicate=1">Duplicate</a>'
        with patch.object(sources.requests,'get',return_value=r),patch.object(sources,'fetch',return_value=PAGE):
            with self.assertRaises(ImageReview) as error:sources.discover('186886')
        self.assertEqual(error.exception.code,'SOURCE_AMBIGUOUS')
    def test_missing_gallery_is_reported(self):
        with patch.object(sources.requests,'get',return_value=self.search()),patch.object(sources,'fetch',return_value='<div class="product-page-top">186886</div>'):
            with self.assertRaises(ImageReview) as error:sources.discover('186886')
        self.assertEqual(error.exception.code,'SOURCE_NO_GALLERY')
