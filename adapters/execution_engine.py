"""
adapters/execution_engine.py
Multi-pool ThreadPoolExecutor — the core of the v7 Data Fabric Engine.

Dispatches fetch calls across 49 adapters with priority-aware parallelism.
Designed to work within Streamlit's single-threaded session model:
  - Engine is instantiated once via @st.cache_resource
  - Results are stored in a module-level cache dict (shared across reruns)
  - Fetch is called from section render() functions — non-blocking via Future

Priority pools (total max 21 threads, not 49):
  realtime  → 8T  (Binance, Kraken, OANDA, CBOE VIX)
  high      → 6T  (yfinance, Polygon, NewsAPI, Twitter, Alpha Vantage, IEX)
  medium    → 4T  (CoinGecko, FRED, StockTwits, ECB, Fixer, Reuters)
  low       → 2T  (World Bank, OECD, Google Trends, Messari, Simfin)
  batch     → 1T  (CFTC COT, USDA — once/day off-peak)
"""
from __future__ import annotations

import logging
import threading
import time
import os
import diskcache
from concurrent.futures import Future, ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from typing import Dict, List, Optional

from adapters.base import BaseDataAdapter, DataResult
from adapters.circuit_breaker import CircuitBreakerRegistry
from adapters.resource_budget import ResourceBudget

logger = logging.getLogger(__name__)

# Priority → thread count mapping
PRIORITY_THREADS: Dict[str, int] = {
    "realtime": 8,
    "high":     6,
    "medium":   4,
    "low":      2,
    "batch":    1,
}

# Persistent result cache (SQLite-backed) shareable across processes/reruns
_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache", "data_fabric")
_DISK_CACHE = diskcache.Cache(_CACHE_DIR)

def _cache_get(provider_id: str) -> Optional[DataResult]:
    """Retrieve result from persistent disk cache."""
    return _DISK_CACHE.get(provider_id)


def _cache_set(result: DataResult) -> None:
    """Store result in persistent disk cache with TTL."""
    _DISK_CACHE.set(result.provider_id, result, expire=result.ttl_seconds)


class ExecutionEngine:
    """
    Singleton-style engine (use @st.cache_resource to instantiate once per process).

    Usage in Streamlit sections:
        import streamlit as st
        from adapters.execution_engine import ExecutionEngine

        @st.cache_resource
        def get_engine():
            return ExecutionEngine()

        def render():
            engine = get_engine()
            results = engine.fetch_many(["fred", "world_bank", "imf"], timeout=8.0)
    """

    def __init__(self):
        from adapters.registry import autodiscover_providers
        autodiscover_providers()

        self._pools: Dict[str, ThreadPoolExecutor] = {
            priority: ThreadPoolExecutor(
                max_workers=n,
                thread_name_prefix=f"qrt_{priority}",
            )
            for priority, n in PRIORITY_THREADS.items()
        }
        self.circuit_breakers = CircuitBreakerRegistry(
            failure_threshold=3, reset_timeout=60.0
        )
        self.resource_budget = ResourceBudget(
            cpu_limit_pct=70.0,
            ram_limit_mb=1500.0,
        )
        self.resource_budget.start_monitor()
        self._pending: Dict[str, Future] = {}
        self._pending_lock = threading.Lock()

        logger.info("ExecutionEngine ready — %d priority pools, %d total threads",
                    len(self._pools), sum(PRIORITY_THREADS.values()))

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def fetch_one(self, provider_id: str, use_cache: bool = True, **kwargs) -> Optional[DataResult]:
        """
        Fetch a single provider synchronously (blocks until done or circuit open).
        Returns cached result if fresh. Returns None if circuit is OPEN.
        """
        # 1. Check cache first
        if use_cache:
            cached = _cache_get(provider_id)
            if cached is not None:
                return cached

        # 2. Check circuit breaker
        if not self.circuit_breakers.is_available(provider_id):
            logger.debug("[%s] circuit OPEN — skipping fetch", provider_id)
            return DataResult(
                provider_id=provider_id, category="unknown",
                fetched_at="", latency_ms=0, success=False,
                data=None, error="circuit breaker OPEN",
            )

        # 3. Get adapter
        from adapters.registry import get_adapter, _CONFIGS
        adapter = get_adapter(provider_id)
        if adapter is None:
            return None

        cfg = _CONFIGS.get(provider_id)

        # 4. Check resource budget + rate limit
        if cfg and not self.resource_budget.can_fetch(provider_id, cfg.rate_limit_rpm):
            logger.debug("[%s] rate limited by ResourceBudget", provider_id)
            return _cache_get(provider_id)  # serve stale if available

        # 5. Wire circuit breaker into adapter
        adapter._circuit_breaker = self.circuit_breakers

        # 6. Execute in appropriate priority pool
        priority = cfg.priority if cfg else "medium"
        pool = self._pools.get(priority, self._pools["medium"])

        future = pool.submit(adapter.fetch, **kwargs)
        try:
            result = future.result(timeout=15.0)
            if result.success:
                _cache_set(result)
            return result
        except Exception as exc:
            logger.error("[%s] fetch_one exception: %s", provider_id, exc)
            return None

    def fetch_many(
        self,
        provider_ids: List[str],
        timeout: float = 10.0,
        use_cache: bool = True,
        **kwargs,
    ) -> Dict[str, DataResult]:
        """
        Fetch multiple providers in parallel. Returns dict of provider_id → DataResult.
        Results that are fresh in cache are returned immediately without a thread.
        """
        results: Dict[str, DataResult] = {}
        to_fetch: List[str] = []

        # Serve from cache first
        for pid in provider_ids:
            if use_cache:
                cached = _cache_get(pid)
                if cached is not None:
                    results[pid] = cached
                    continue
            to_fetch.append(pid)

        if not to_fetch:
            return results

        # Submit uncached providers to their priority pools
        futures: Dict[Future, str] = {}
        for pid in to_fetch:
            if not self.circuit_breakers.is_available(pid):
                results[pid] = DataResult(
                    provider_id=pid, category="unknown",
                    fetched_at="", latency_ms=0, success=False,
                    data=None, error="circuit breaker OPEN",
                )
                continue

            from adapters.registry import get_adapter, _CONFIGS
            adapter = get_adapter(pid)
            if adapter is None:
                continue

            cfg = _CONFIGS.get(pid)
            adapter._circuit_breaker = self.circuit_breakers

            # Skip if resource-limited (return stale if available)
            if cfg and not self.resource_budget.can_fetch(pid, cfg.rate_limit_rpm):
                stale = _cache_get(pid)
                if stale:
                    results[pid] = stale
                continue

            priority = cfg.priority if cfg else "medium"
            # Pause batch pool if CPU/RAM is high
            if priority == "batch" and self.resource_budget.should_pause_batch():
                logger.info("ResourceBudget: skipping batch fetch for %s (CPU/RAM high)", pid)
                continue

            pool = self._pools.get(priority, self._pools["medium"])
            fut = pool.submit(adapter.fetch, **kwargs)
            futures[fut] = pid

        # Collect results with timeout
        if futures:
            done, pending = wait(list(futures.keys()), timeout=timeout)
            for fut in done:
                pid = futures[fut]
                try:
                    result = fut.result()
                    results[pid] = result
                    if result.success:
                        _cache_set(result)
                except Exception as exc:
                    logger.error("[%s] future error: %s", pid, exc)
            # Cancel timed-out futures
            for fut in pending:
                fut.cancel()
                pid = futures[fut]
                logger.warning("[%s] fetch timed out after %.1fs", pid, timeout)

        return results

    def fetch_dashboard_snapshot(self, timeout: float = 12.0) -> Dict[str, DataResult]:
        """
        Fetch all configured providers in one shot — intended for cold start.
        Realtime/high priority providers get priority; batch providers are skipped.
        """
        from adapters.registry import get_configured_ids, _CONFIGS
        all_ids = [
            pid for pid in get_configured_ids()
            if _CONFIGS.get(pid) and _CONFIGS[pid].priority != "batch"
        ]
        return self.fetch_many(all_ids, timeout=timeout)

    # -----------------------------------------------------------------------
    # Health & observability
    # -----------------------------------------------------------------------

    def health_summary(self) -> List[dict]:
        """
        Returns list of dicts for the Health Dashboard panel.
        One entry per registered provider.
        """
        from adapters.registry import get_all_configs
        from adapters.base import DataResult

        summaries = []
        cb_data = {d["provider_id"]: d for d in self.circuit_breakers.summary()}
        res_stats = self.resource_budget.stats()

        for cfg in get_all_configs():
            pid = cfg.provider_id
            cached = _cache_get(pid)
            cb = cb_data.get(pid, {"state": "closed", "icon": "✅", "failures": 0, "successes": 0, "last_error": ""})

            entry = {
                "provider_id":  pid,
                "category":     cfg.category,
                "priority":     cfg.priority,
                "enabled":      cfg.enabled,
                "configured":   False,
                "state":        cb["state"],
                "icon":         cb["icon"],
                "latency_ms":   cached.latency_ms if cached else None,
                "last_fetch":   cached.fetched_at if cached else None,
                "success":      cached.success    if cached else None,
                "ttl_seconds":  cfg.ttl_seconds,
                "last_error":   cb["last_error"],
                "total_failures":  cb["failures"],
                "total_successes": cb["successes"],
            }
            # Check if credentials are available
            try:
                from adapters.registry import get_adapter
                adapter = get_adapter(pid)
                entry["configured"] = adapter.is_configured() if adapter else False
            except Exception:
                pass

            summaries.append(entry)

        return summaries

    def resource_stats(self) -> dict:
        return self.resource_budget.stats()

    def shutdown(self) -> None:
        """Graceful shutdown — waits for running tasks to complete."""
        self.resource_budget.stop_monitor()
        for priority, pool in self._pools.items():
            pool.shutdown(wait=True)
            logger.info("Pool '%s' shut down.", priority)
