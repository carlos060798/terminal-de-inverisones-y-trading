"""Institutional Holders via yfinance"""
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register

@register
class InstHoldersAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "yfinance"
    config = ProviderConfig(
        provider_id="inst_holders", category="stocks",
        credential_key="", rate_limit_rpm=60, ttl_seconds=300, priority="high"
    )

    def _fetch_raw(self, ticker: str = "AAPL", **kwargs):
        yf = self._import_lib()
        t = yf.Ticker(ticker)
        inst = t.institutional_holders
        if inst is not None and not inst.empty:
            return inst.head(10)
        return None

    def _normalize(self, raw) -> DataResult:
        return DataResult(provider_id="inst_holders", category="stocks",
                          fetched_at="", latency_ms=0, success=raw is not None, data=raw)
