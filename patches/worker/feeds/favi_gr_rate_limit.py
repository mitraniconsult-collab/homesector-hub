"""Shared pacing for public GR storefront checks.

A persistent 429 pauses the whole checkpointed generation. Callers must not
interpret a throttled response as an invalid product URL.
"""
import threading
import time
import os
from urllib.parse import urljoin, urlparse

import requests


class StorefrontRateLimited(RuntimeError):
    pass


class StorefrontLimiter:
    def __init__(self, min_interval=0.5, clock=None, sleep=None, cooldown=300.0):
        if not 0.5 <= min_interval <= 30 or not 300 <= cooldown <= 86400:
            raise ValueError("Invalid storefront pacing configuration")
        self.min_interval = min_interval
        self.cooldown = cooldown
        self.interval = min_interval
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.lock = threading.Lock()
        self.next_at = 0.0
        self.blocked_until = 0.0
        self.successes = 0

    @staticmethod
    def _retry_after(response):
        raw = str(response.headers.get("Retry-After", "")).strip()
        try:
            return min(60.0, max(0.0, float(raw)))
        except ValueError:
            return 0.0

    @staticmethod
    def _crawler_headers(url):
        # Shopify merchant crawler signatures are scoped to a single domain.
        market = {"homesector.gr": "GR", "homesector.ro": "RO",
                  "homesector.hu": "HU"}.get(urlparse(url).hostname)
        if not market:
            return None
        signature_input = os.getenv(f"FEED_CRAWLER_{market}_SIGNATURE_INPUT", "")
        signature = os.getenv(f"FEED_CRAWLER_{market}_SIGNATURE", "")
        if bool(signature_input) != bool(signature):
            raise ValueError(f"Incomplete {market} crawler signature configuration")
        if not signature:
            return None
        if "\n" in signature_input + signature or "\r" in signature_input + signature:
            raise ValueError(f"Invalid {market} crawler signature configuration")
        return {"Signature-Input": signature_input, "Signature": signature,
                "Signature-Agent": '"https://shopify.com"'}

    def _request(self, url, kwargs):
        crawler_headers = self._crawler_headers(url)
        if not crawler_headers:
            return requests.get(url, **kwargs)
        # requests forwards custom headers across redirects. Never send a
        # domain-scoped signature to another host, even on an HTTP redirect.
        options = dict(kwargs)
        options["headers"] = {**(kwargs.get("headers") or {}), **crawler_headers}
        options["allow_redirects"] = False
        original_host = urlparse(url).hostname
        for _ in range(5):
            response = requests.get(url, **options)
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            target = urljoin(url, response.headers.get("Location", ""))
            parsed = urlparse(target)
            if parsed.scheme != "https" or parsed.hostname != original_host:
                return response
            url = target
        return response

    def get(self, url, **kwargs):
        # Requests from both direct and collection URL stages share this lock.
        # The thread pools remain bounded but never burst at the storefront.
        with self.lock:
            if self.clock() < self.blocked_until:
                raise StorefrontRateLimited("FAVI storefront 429 cooldown")
            for attempt in range(2):
                delay = self.next_at - self.clock()
                if delay > 0:
                    self.sleep(delay)
                response = self._request(url, kwargs)
                self.next_at = self.clock() + self.interval
                if response.status_code != 429:
                    self.successes += 1
                    if self.successes >= 100:
                        self.interval = max(self.min_interval, self.interval * 0.75)
                        self.successes = 0
                    return response
                self.successes = 0
                self.interval = min(2.0, max(1.0, self.interval * 2))
                if attempt == 0:
                    self.next_at = self.clock() + max(2.0, self._retry_after(response))
            # The scheduler keeps the current generation and resumes the same
            # unfinished batch after its five-minute retry window.
            self.blocked_until = self.clock() + self.cooldown
            raise StorefrontRateLimited("FAVI storefront returned HTTP 429 twice")


storefront_limiter = StorefrontLimiter(
    min_interval=float(os.getenv("FEED_STOREFRONT_MIN_INTERVAL_SECONDS", "0.5")),
    cooldown=float(os.getenv("FEED_STOREFRONT_429_COOLDOWN_SECONDS", "300")))
