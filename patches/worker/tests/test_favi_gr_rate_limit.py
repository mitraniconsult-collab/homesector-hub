"""Bounded storefront pacing and 429 recovery."""
import unittest
from unittest.mock import patch

from feeds.favi_gr_rate_limit import StorefrontLimiter, StorefrontRateLimited
from feeds import favi_gr_urls


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Response:
    def __init__(self, status, handle="chair", retry_after=""):
        self.status_code = status
        self.headers = {"Content-Type": "text/html", "Retry-After": retry_after}
        self.url = "https://homesector.gr/products/" + handle
        self.text = "<html>" + handle + "</html>"


class StorefrontRateLimitTests(unittest.TestCase):
    def test_429_retry_recovers_and_keeps_exact_url_check(self):
        clock = Clock()
        limiter = StorefrontLimiter(clock=clock.monotonic, sleep=clock.sleep)
        with patch.object(favi_gr_urls, "storefront_limiter", limiter), \
             patch("feeds.favi_gr_rate_limit.requests.get",
                   side_effect=[Response(429, retry_after="3"), Response(200)]) as get:
            urls, report = favi_gr_urls.verify_market_urls(
                [{"id": "p1", "handle": "chair"}],
                {"p1": {"verified": True}}, workers=1)
        self.assertEqual(urls, {"p1": "https://homesector.gr/products/chair"})
        self.assertEqual(report["reasons"], {"verified": 1})
        self.assertEqual(get.call_count, 2)
        self.assertGreaterEqual(clock.now, 3.0)

    def test_persistent_429_defers_without_more_requests_and_can_resume(self):
        clock = Clock()
        limiter = StorefrontLimiter(clock=clock.monotonic, sleep=clock.sleep)
        with patch("feeds.favi_gr_rate_limit.requests.get",
                   side_effect=[Response(429), Response(429), Response(200)]) as get:
            with self.assertRaises(StorefrontRateLimited):
                limiter.get("https://homesector.gr/products/chair", timeout=5)
            self.assertEqual(get.call_count, 2)
            with self.assertRaises(StorefrontRateLimited):
                limiter.get("https://homesector.gr/products/other", timeout=5)
            self.assertEqual(get.call_count, 2)
            clock.sleep(300)
            self.assertEqual(limiter.get(
                "https://homesector.gr/products/chair", timeout=5).status_code, 200)
            self.assertEqual(get.call_count, 3)

    def test_all_url_workers_defer_if_storefront_stays_throttled(self):
        clock = Clock()
        limiter = StorefrontLimiter(clock=clock.monotonic, sleep=clock.sleep)
        products = [{"id": "p" + str(i), "handle": "chair-" + str(i)}
                    for i in range(20)]
        with patch.object(favi_gr_urls, "storefront_limiter", limiter), \
             patch("feeds.favi_gr_rate_limit.requests.get",
                   return_value=Response(429)) as get:
            with self.assertRaises(StorefrontRateLimited):
                favi_gr_urls.verify_market_urls(
                    products, {p["id"]: {"verified": True} for p in products})
        # A whole checkpoint batch creates only two external requests.
        self.assertEqual(get.call_count, 2)

    def test_longer_cooldown_can_be_configured_for_persistent_429(self):
        clock = Clock()
        limiter = StorefrontLimiter(min_interval=2, cooldown=900,
                                    clock=clock.monotonic, sleep=clock.sleep)
        with patch("feeds.favi_gr_rate_limit.requests.get",
                   side_effect=[Response(429), Response(429), Response(200)]) as get:
            with self.assertRaises(StorefrontRateLimited):
                limiter.get("https://homesector.ro/products/chair", timeout=5)
            clock.sleep(300)
            with self.assertRaises(StorefrontRateLimited):
                limiter.get("https://homesector.ro/products/chair", timeout=5)
            self.assertEqual(get.call_count, 2)
            clock.sleep(600)
            self.assertEqual(limiter.get("https://homesector.ro/products/chair", timeout=5).status_code, 200)


if __name__ == "__main__":
    unittest.main()
