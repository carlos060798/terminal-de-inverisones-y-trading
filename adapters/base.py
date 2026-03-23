"""
adapters/base.py
Core abstractions for the v7 Data Fabric Engine.

Every data adapter inherits from BaseDataAdapter and implements only:
  - config: ProviderConfig  (class-level)
  - _fetch_raw(**kwargs)    (provider-specific fetch)
  - _normalize(raw)         (map raw → DataResult)

All shared concerns (timing, error capture, credential lookup, circuit breaker
notification) are handled here — this is the "80% reuse" foundation.
"""
from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class ProviderConfig:
    """Static configuration for a single data provider."""
    provider_id: str
    category: str           # macro | stocks | crypto | forex | commodities | news | volatility | alternative
    credential_key: str     # key name in st.secrets / os.environ; "" = no auth needed
    base_url: str = ""
    rate_limit_rpm: int = 60
    daily_quota: int = 0    # 0 = unlimited
    ttl_seconds: int = 300
    priority: str = "medium"  # realtime | high | medium | low | batch
    enabled: bool = True


@dataclass
class DataResult:
    """Normalized envelope returned by every adapter.fetch() call."""
    provider_id: str
    category: str
    fetched_at: str         # UTC ISO-8601
    latency_ms: int
    success: bool
    data: Any               # DataFrame | dict | list | None
    error: str = ""
    ttl_seconds: int = 300

    def is_stale(self) -> bool:
        """True if TTL has elapsed since fetched_at."""
        try:
            fetched = datetime.fromisoformat(self.fetched_at)
            age = (datetime.now(timezone.utc) - fetched).total_seconds()
            return age > self.ttl_seconds
        except Exception:
            return True


# ---------------------------------------------------------------------------
# Abstract base adapter
# ---------------------------------------------------------------------------

class BaseDataAdapter(ABC):
    """
    Abstract base for all 49 data adapters.

    Subclasses define:
      config: ProviderConfig          — class-level attribute
      _fetch_raw(**kwargs) -> Any     — raw provider response
      _normalize(raw) -> DataResult  — map raw to DataResult.data schema

    This class handles everything else automatically.
    """

    # Subclasses MUST define this at class level
    config: ProviderConfig

    # Optional: reference to circuit breaker (set by ExecutionEngine after init)
    _circuit_breaker: Optional[Any] = None

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def fetch(self, **kwargs) -> DataResult:
        """
        Execute fetch with automatic timing, error capture, and circuit
        breaker notification. Called by ExecutionEngine worker threads.
        """
        if not self.config.enabled:
            return self._empty_result("provider disabled")

        t0 = time.perf_counter()
        try:
            raw = self._fetch_raw(**kwargs)
            result = self._normalize(raw)
            result.latency_ms = int((time.perf_counter() - t0) * 1000)
            result.fetched_at = self._now_utc()
            result.success = True
            result.ttl_seconds = self.config.ttl_seconds

            if self._circuit_breaker:
                self._circuit_breaker.record_success(self.config.provider_id)

            logger.debug("[%s] fetch OK in %dms", self.config.provider_id, result.latency_ms)
            return result

        except Exception as exc:
            latency = int((time.perf_counter() - t0) * 1000)
            logger.warning("[%s] fetch FAILED in %dms: %s", self.config.provider_id, latency, exc)

            if self._circuit_breaker:
                self._circuit_breaker.record_failure(self.config.provider_id)

            return DataResult(
                provider_id=self.config.provider_id,
                category=self.config.category,
                fetched_at=self._now_utc(),
                latency_ms=latency,
                success=False,
                data=None,
                error=str(exc),
                ttl_seconds=self.config.ttl_seconds,
            )

    # -----------------------------------------------------------------------
    # Abstract methods — subclasses implement ONLY these two
    # -----------------------------------------------------------------------

    @abstractmethod
    def _fetch_raw(self, **kwargs) -> Any:
        """Provider-specific data retrieval. Must raise on error."""

    @abstractmethod
    def _normalize(self, raw: Any) -> DataResult:
        """
        Map provider-specific raw response to DataResult.
        success, latency_ms, fetched_at, ttl_seconds are filled by fetch().
        """

    # -----------------------------------------------------------------------
    # Shared helpers available to all subclasses
    # -----------------------------------------------------------------------

    def _get_credential(self) -> str:
        """
        Read API key from st.secrets or os.environ.
        Same pattern as balancer.py — st.secrets first, then os.environ fallback.
        """
        key = self.config.credential_key
        if not key:
            return ""
        try:
            import streamlit as st
            val = st.secrets.get(key)
            if val:
                return str(val)
        except Exception:
            pass
        return os.environ.get(key, "")

    def is_configured(self) -> bool:
        """True if no credential needed OR credential is present in environment."""
        if not self.config.credential_key:
            return True
        return bool(self._get_credential())

    def _now_utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _empty_result(self, error: str) -> DataResult:
        return DataResult(
            provider_id=self.config.provider_id,
            category=self.config.category,
            fetched_at=self._now_utc(),
            latency_ms=0,
            success=False,
            data=None,
            error=error,
            ttl_seconds=self.config.ttl_seconds,
        )
