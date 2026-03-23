"""
adapters/resource_budget.py
CPU/RAM resource management + per-provider token-bucket rate limiting.

ResourceBudget:
  - Monitors system CPU and RAM via psutil
  - Pauses the "batch" thread pool when CPU > cpu_limit_pct
  - Pauses any pool when RAM > ram_limit_mb
  - Provides per-provider token buckets (rate_limit_rpm → tokens/second)

TokenBucket:
  - Refills at rate = rate_limit_rpm / 60 tokens/second
  - consume() returns True if a request is allowed, False if rate-limited
  - Thread-safe
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token Bucket — per-provider rate limiting
# ---------------------------------------------------------------------------

class TokenBucket:
    """
    Leaky-token-bucket for rate limiting one provider.

    capacity = rate_limit_rpm tokens per minute = rate_limit_rpm/60 per second.
    """

    def __init__(self, rate_limit_rpm: int, burst_factor: float = 1.5):
        self._rate = max(rate_limit_rpm, 1) / 60.0   # tokens per second
        self._capacity = self._rate * burst_factor * 60  # max burst
        self._tokens = float(self._capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume `tokens` from the bucket.
        Returns True if allowed, False if rate-limited (caller should back off).
        """
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def wait_and_consume(self, tokens: float = 1.0, timeout: float = 30.0) -> bool:
        """
        Block until tokens are available or timeout expires.
        Returns True if consumed, False if timed out.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.consume(tokens):
                return True
            time.sleep(0.1)
        return False

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        refill = elapsed * self._rate
        self._tokens = min(self._capacity, self._tokens + refill)
        self._last_refill = now

    @property
    def available_tokens(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens


# ---------------------------------------------------------------------------
# Resource Budget — CPU/RAM guard
# ---------------------------------------------------------------------------

class ResourceBudget:
    """
    Monitors system CPU and RAM. Provides signals to ExecutionEngine
    to pause or throttle pools when resources are constrained.
    """

    def __init__(
        self,
        cpu_limit_pct: float = 70.0,
        ram_limit_mb: float = 1500.0,
        check_interval_s: float = 2.0,
    ):
        self.cpu_limit_pct = cpu_limit_pct
        self.ram_limit_mb = ram_limit_mb
        self.check_interval_s = check_interval_s

        self._token_buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

        # Cached readings (updated by background thread)
        self._cpu_pct: float = 0.0
        self._ram_mb: float = 0.0
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def start_monitor(self) -> None:
        """Start background resource monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="resource_budget_monitor",
        )
        self._monitor_thread.start()
        logger.info("ResourceBudget monitor started (cpu_limit=%.0f%%, ram_limit=%.0fMB)",
                    self.cpu_limit_pct, self.ram_limit_mb)

    def stop_monitor(self) -> None:
        self._stop_event.set()

    def _monitor_loop(self) -> None:
        while not self._stop_event.wait(self.check_interval_s):
            try:
                import psutil
                self._cpu_pct = psutil.cpu_percent(interval=None)
                self._ram_mb  = psutil.virtual_memory().used / (1024 * 1024)
            except Exception as exc:
                logger.debug("psutil unavailable: %s", exc)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def is_cpu_overloaded(self) -> bool:
        return self._cpu_pct > self.cpu_limit_pct

    def is_ram_overloaded(self) -> bool:
        return self._ram_mb > self.ram_limit_mb

    def should_pause_batch(self) -> bool:
        """True when batch pool should be paused (non-critical loads only)."""
        return self.is_cpu_overloaded() or self.is_ram_overloaded()

    def should_pause_all(self) -> bool:
        """True only in critical RAM overload (>95% of limit)."""
        return self._ram_mb > self.ram_limit_mb * 1.35

    def get_bucket(self, provider_id: str, rate_limit_rpm: int) -> TokenBucket:
        """Get or create a token bucket for a provider."""
        with self._lock:
            if provider_id not in self._token_buckets:
                self._token_buckets[provider_id] = TokenBucket(rate_limit_rpm)
            return self._token_buckets[provider_id]

    def can_fetch(self, provider_id: str, rate_limit_rpm: int) -> bool:
        """
        Returns True if both system resources allow AND rate limit allows.
        Used by ExecutionEngine before dispatching a fetch task.
        """
        if self.should_pause_all():
            logger.warning("ResourceBudget: RAM critical — blocking fetch for %s", provider_id)
            return False
        bucket = self.get_bucket(provider_id, rate_limit_rpm)
        return bucket.consume()

    @property
    def cpu_pct(self) -> float:
        return self._cpu_pct

    @property
    def ram_mb(self) -> float:
        return self._ram_mb

    def stats(self) -> dict:
        return {
            "cpu_pct": round(self._cpu_pct, 1),
            "ram_mb": round(self._ram_mb, 1),
            "cpu_limit_pct": self.cpu_limit_pct,
            "ram_limit_mb": self.ram_limit_mb,
            "cpu_ok": not self.is_cpu_overloaded(),
            "ram_ok": not self.is_ram_overloaded(),
            "bucket_count": len(self._token_buckets),
        }
