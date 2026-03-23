"""
adapters/circuit_breaker.py
Per-provider circuit breaker with three states: CLOSED, OPEN, HALF_OPEN.

CLOSED    → normal operation; failures are counted
OPEN      → provider paused for `reset_timeout` seconds after `failure_threshold` failures
HALF_OPEN → one probe request allowed; success → CLOSED, failure → back to OPEN

Used by BaseDataAdapter.fetch() to avoid hammering failing providers
and by ExecutionEngine to skip OPEN providers entirely.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

logger = logging.getLogger(__name__)


class State(str, Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProviderBreaker:
    """State machine for one provider."""
    provider_id: str
    failure_threshold: int = 3      # consecutive failures → OPEN
    success_threshold: int = 1      # successes from HALF_OPEN → CLOSED
    reset_timeout: float   = 60.0   # seconds to stay OPEN before trying HALF_OPEN

    state: State = State.CLOSED
    failure_count: int = 0
    success_count: int = 0
    opened_at: float = 0.0          # time.monotonic() when circuit opened
    total_failures: int = 0
    total_successes: int = 0
    last_failure_msg: str = ""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def record_success(self) -> None:
        with self._lock:
            self.total_successes += 1
            if self.state == State.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._close()
            elif self.state == State.CLOSED:
                self.failure_count = 0   # reset consecutive counter on success

    def record_failure(self, error: str = "") -> None:
        with self._lock:
            self.total_failures += 1
            self.last_failure_msg = error
            if self.state == State.HALF_OPEN:
                self._open()
            elif self.state == State.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self._open()

    def is_available(self) -> bool:
        """
        Returns True if the circuit allows a request to pass through.
        Automatically transitions OPEN → HALF_OPEN once reset_timeout elapses.
        """
        with self._lock:
            if self.state == State.CLOSED:
                return True
            if self.state == State.OPEN:
                if time.monotonic() - self.opened_at >= self.reset_timeout:
                    self._half_open()
                    return True   # probe request allowed
                return False
            # HALF_OPEN: allow one probe
            return True

    # -- Internal transitions -------------------------------------------------

    def _open(self) -> None:
        self.state = State.OPEN
        self.opened_at = time.monotonic()
        self.success_count = 0
        logger.warning("[circuit_breaker] %s → OPEN after %d failures", self.provider_id, self.failure_count)

    def _half_open(self) -> None:
        self.state = State.HALF_OPEN
        self.success_count = 0
        logger.info("[circuit_breaker] %s → HALF_OPEN (probe allowed)", self.provider_id)

    def _close(self) -> None:
        self.state = State.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info("[circuit_breaker] %s → CLOSED (recovered)", self.provider_id)

    @property
    def status_icon(self) -> str:
        return {"closed": "✅", "open": "🔴", "half_open": "🟡"}[self.state]


class CircuitBreakerRegistry:
    """
    Singleton-style registry of ProviderBreaker instances for all 49 providers.
    Thread-safe. Accessed by both BaseDataAdapter and ExecutionEngine.
    """

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 60.0):
        self._breakers: Dict[str, ProviderBreaker] = {}
        self._lock = threading.Lock()
        self._default_failure_threshold = failure_threshold
        self._default_reset_timeout = reset_timeout

    def get(self, provider_id: str) -> ProviderBreaker:
        with self._lock:
            if provider_id not in self._breakers:
                self._breakers[provider_id] = ProviderBreaker(
                    provider_id=provider_id,
                    failure_threshold=self._default_failure_threshold,
                    reset_timeout=self._default_reset_timeout,
                )
            return self._breakers[provider_id]

    def record_success(self, provider_id: str) -> None:
        self.get(provider_id).record_success()

    def record_failure(self, provider_id: str, error: str = "") -> None:
        self.get(provider_id).record_failure(error)

    def is_available(self, provider_id: str) -> bool:
        return self.get(provider_id).is_available()

    def summary(self) -> list[dict]:
        """Return list of dicts for Health Dashboard rendering."""
        with self._lock:
            return [
                {
                    "provider_id": pid,
                    "state": b.state.value,
                    "icon": b.status_icon,
                    "failures": b.total_failures,
                    "successes": b.total_successes,
                    "last_error": b.last_failure_msg,
                }
                for pid, b in sorted(self._breakers.items())
            ]
