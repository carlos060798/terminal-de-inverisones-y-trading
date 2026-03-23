"""VIX current level via yfinance"""
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register

@register
class CboeVixAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "yfinance"
    config = ProviderConfig(
        provider_id="cboe_vix", category="volatility",
        credential_key="", rate_limit_rpm=60, ttl_seconds=300, priority="realtime"
    )

    def _fetch_raw(self, **kwargs):
        yf = self._import_lib()
        tk = yf.Ticker("^VIX")
        return tk.fast_info.last_price

    def _normalize(self, raw) -> DataResult:
        price = round(raw, 2) if raw else None
        return DataResult(provider_id="cboe_vix", category="volatility",
                          fetched_at="", latency_ms=0, success=bool(price), data=price)
