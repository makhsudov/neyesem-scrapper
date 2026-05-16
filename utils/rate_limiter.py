import time
import random
import logging
from config import REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, RETRY_BACKOFF_BASE

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, min_delay: float = REQUEST_DELAY_MIN,
                 max_delay: float = REQUEST_DELAY_MAX):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_request_time = 0.0

    def wait(self):
        now = time.monotonic()
        elapsed = now - self._last_request_time
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request_time = time.monotonic()

    def backoff(self, attempt: int):
        base_wait = RETRY_BACKOFF_BASE ** attempt
        jitter = random.uniform(0, base_wait * 0.3)
        wait_time = base_wait + jitter
        logger.warning(f"Rate limited. Waiting {wait_time:.1f}s (attempt {attempt})")
        time.sleep(wait_time)
