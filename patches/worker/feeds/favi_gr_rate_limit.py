"""Shared pacing for public GR storefront checks.

A persistent 429 pauses the whole checkpointed generation. Callers must not
interpret a throttled response as an invalid product URL.
"""
import threading
import time

import requests


class StorefrontRateLimited(RuntimeError):
    pass


class StorefrontLimiter:
    def __init__(self, min_interval=0.5, clock=None, sleep=None):
        self.min_interval = min_interval
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

    def get(self, url, **kwargs):
        # Requests from both direct and collection URL stages share this lock.
        # The thread pools remain bounded but never burst at the storefront.
        with self.lock:
            if self.clock() < self.blocked_until:
                raise StorefrontRateLimited("Greek storefront 429 cooldown")
            for attempt in range(2):
                delay = self.next_at - self.clock()
                if delay > 0:
                    self.sleep(delay)
                response = requests.get(url, **kwargs)
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
            self.blocked_until = self.clock() + 300.0
            raise StorefrontRateLimited("Greek storefront returned HTTP 429 twice")


storefront_limiter = StorefrontLimiter()
