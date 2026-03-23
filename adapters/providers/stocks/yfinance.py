"""Yahoo Finance — yfinance (migrated from data_sources.py)"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register


@register
class YfinanceAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "yfinance"
    config = ProviderConfig(
        provider_id="yfinance", category="stocks",
        credential_key="",
        rate_limit_rpm=60, ttl_seconds=300, priority="high",
    )

    def _fetch_raw(self, ticker: str = "AAPL", period: str = "1y",
                   interval: str = "1d", **kwargs):
        yf = self._import_lib()
        df = yf.download(ticker, period=period, interval=interval,
                         auto_adjust=True, progress=False)
        return df

    def _normalize(self, raw: pd.DataFrame) -> DataResult:
        df = raw.copy()
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)
        df.index.name = "date"
        df = df.reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"], utc=True)
        return DataResult(
            provider_id="yfinance", category="stocks",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
