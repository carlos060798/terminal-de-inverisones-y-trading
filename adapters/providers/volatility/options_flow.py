"""Options Flow via yfinance"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register

@register
class OptionsFlowAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "yfinance"
    config = ProviderConfig(
        provider_id="options_flow", category="volatility",
        credential_key="", rate_limit_rpm=60, ttl_seconds=300, priority="high"
    )

    def _fetch_raw(self, ticker: str = "AAPL", **kwargs):
        yf = self._import_lib()
        t = yf.Ticker(ticker)
        dates = t.options[:3]
        result = []
        for d in dates:
            chain = t.option_chain(d)
            calls_vol = chain.calls["volume"].sum() if "volume" in chain.calls else 0
            puts_vol = chain.puts["volume"].sum() if "volume" in chain.puts else 0
            result.append({
                "expiry": d,
                "calls_vol": int(calls_vol) if pd.notna(calls_vol) else 0,
                "puts_vol": int(puts_vol) if pd.notna(puts_vol) else 0,
                "put_call_ratio": round(puts_vol / max(calls_vol, 1), 3),
            })
        return result

    def _normalize(self, raw) -> DataResult:
        return DataResult(provider_id="options_flow", category="volatility",
                          fetched_at="", latency_ms=0, success=bool(raw), data=raw)
