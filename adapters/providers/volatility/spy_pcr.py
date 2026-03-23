"""SPY Put/Call Ratio via yfinance"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register

@register
class SpyPcrAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "yfinance"
    config = ProviderConfig(
        provider_id="spy_pcr", category="volatility",
        credential_key="", rate_limit_rpm=60, ttl_seconds=300, priority="high"
    )

    def _fetch_raw(self, **kwargs):
        yf = self._import_lib()
        tk = yf.Ticker("SPY")
        dates = tk.options[:1]
        if not dates: return None
        chain = tk.option_chain(dates[0])
        calls_vol = chain.calls["volume"].sum() if "volume" in chain.calls else 0
        puts_vol = chain.puts["volume"].sum() if "volume" in chain.puts else 0
        ratio = puts_vol / max(calls_vol, 1)
        return {"ratio": round(ratio, 3), "calls_vol": int(calls_vol), "puts_vol": int(puts_vol), "expiry": dates[0]}

    def _normalize(self, raw) -> DataResult:
        return DataResult(provider_id="spy_pcr", category="volatility",
                          fetched_at="", latency_ms=0, success=bool(raw), data=raw)
