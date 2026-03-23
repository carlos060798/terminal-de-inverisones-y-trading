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

def autodiscover_providers() -> int:
    """
    Import all modules under adapters/providers/ so their @register decorators
    execute. Returns count of newly registered adapters.
    Call once at app startup (e.g. in execution_engine.py __init__).
    """
    import adapters.providers as _pkg
    before = len(_REGISTRY)

    for finder, modname, ispkg in pkgutil.walk_packages(
        path=_pkg.__path__,
        prefix=_pkg.__name__ + ".",
        onerror=lambda name: logger.warning("Cannot import provider module: %s", name),
    ):
        try:
            importlib.import_module(modname)
        except Exception as exc:
            logger.warning("Failed to import %s: %s", modname, exc)

    added = len(_REGISTRY) - before
    logger.info("autodiscover_providers: loaded %d adapters (%d total)", added, len(_REGISTRY))
    return added
