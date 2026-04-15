"""
adapters/registry.py
Central registry of all 49 data providers.

Pattern mirrors balancer.py PROVIDERS dict, extended with ProviderConfig dataclasses.

Usage:
    from adapters.registry import register, get_adapter, get_all_configs

    @register
    class MyAdapter(BaseDataAdapter):
        config = ProviderConfig(provider_id="my_provider", ...)

    adapter = get_adapter("my_provider")
    result  = adapter.fetch(ticker="AAPL")
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Dict, List, Optional, Type

from adapters.base import BaseDataAdapter, ProviderConfig

logger = logging.getLogger(__name__)

# ── Internal registry dicts ──────────────────────────────────────────────────
_REGISTRY: Dict[str, Type[BaseDataAdapter]] = {}
_CONFIGS:  Dict[str, ProviderConfig] = {}


# ── Registration decorator ───────────────────────────────────────────────────

def register(adapter_cls: Type[BaseDataAdapter]) -> Type[BaseDataAdapter]:
    """
    Class decorator that registers an adapter by its config.provider_id.

    Example:
        @register
        class FredAdapter(LibraryMixin, BaseDataAdapter):
            config = ProviderConfig(provider_id="fred", ...)
    """
    pid = adapter_cls.config.provider_id
    if pid in _REGISTRY:
        logger.warning("Adapter '%s' already registered — overwriting.", pid)
    _REGISTRY[pid] = adapter_cls
    _CONFIGS[pid] = adapter_cls.config
    return adapter_cls


# ── Query functions ──────────────────────────────────────────────────────────

def get_adapter(provider_id: str) -> Optional[BaseDataAdapter]:
    """Instantiate and return an adapter by id, or None if not registered."""
    cls = _REGISTRY.get(provider_id)
    if cls is None:
        logger.warning("Adapter '%s' not found in registry.", provider_id)
        return None
    return cls()


def get_all_configs() -> List[ProviderConfig]:
    """Return config for every registered provider (used by HealthDashboard)."""
    return list(_CONFIGS.values())


def get_all_ids() -> List[str]:
    return list(_REGISTRY.keys())


def get_by_category(category: str) -> List[str]:
    """Return provider_ids for a given category (e.g. 'macro', 'crypto')."""
    return [pid for pid, cfg in _CONFIGS.items() if cfg.category == category]


def get_by_priority(priority: str) -> List[str]:
    """Return provider_ids for a given priority tier."""
    return [pid for pid, cfg in _CONFIGS.items() if cfg.priority == priority]


def get_configured_ids() -> List[str]:
    """Return only provider_ids where credentials are present (or not needed)."""
    result = []
    for pid, cls in _REGISTRY.items():
        try:
            adapter = cls()
            if adapter.is_configured():
                result.append(pid)
        except Exception:
            pass
    return result


# ── Auto-discovery ───────────────────────────────────────────────────────────

def autodiscover_providers(priority_filter: Optional[List[str]] = None) -> int:
    """
    Import modules under adapters/providers/ to execute decorators.
    If priority_filter is provided, only load modules whose provider_id
    matches a prioritized list (logic: check static mapping or suffix).
    
    Deferred Start (Sprint 4):
    To truly defer, we'd need a mapping or scan names. 
    Here we implement a two-pass load if called with filters.
    """
    import adapters.providers as _pkg
    before = len(_REGISTRY)
    
    # Core providers to load in first pass for speed
    CORE_HINTS = ["binance", "yfinance", "fred", "cboe", "market_pulse", "sentiment_finbert"]

    for finder, modname, ispkg in pkgutil.walk_packages(
        path=_pkg.__path__,
        prefix=_pkg.__name__ + ".",
        onerror=lambda name: logger.warning("Cannot import provider module: %s", name),
    ):
        # If filtering for quick start, skip non-core modules based on name hint
        if priority_filter == ["CORE"]:
            is_core = any(hint in modname.lower() for hint in CORE_HINTS)
            if not is_core:
                continue

        try:
            importlib.import_module(modname)
        except Exception as exc:
            logger.warning("Failed to import %s: %s", modname, exc)

    added = len(_REGISTRY) - before
    logger.info("autodiscover_providers: loaded %d adapters (Pass: %s)", added, priority_filter or "FULL")
    return added
