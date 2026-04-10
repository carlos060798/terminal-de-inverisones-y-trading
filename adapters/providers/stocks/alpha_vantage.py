"""Alpha Vantage — alpha_vantage library"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register


@register
class AlphaVantageAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "alpha_vantage.timeseries"
    config = ProviderConfig(
        provider_id="alpha_vantage", category="stocks",
        credential_key="ALPHA_VANTAGE_API_KEY",
        rate_limit_rpm=5, daily_quota=500, ttl_seconds=300, priority="high",
    )

    def _fetch_raw(self, ticker: str = "MSFT", outputsize: str = "compact", **kwargs):
        TimeSeries = self._import_from("alpha_vantage.timeseries", "TimeSeries")
        ts = TimeSeries(key=self._get_credential(), output_format="pandas")
        data, _ = ts.get_daily(symbol=ticker, outputsize=outputsize)
        return data

    def _normalize(self, raw: pd.DataFrame) -> DataResult:
        df = raw.reset_index().rename(columns={
            "date": "date", "1. open": "open", "2. high": "high",
            "3. low": "low", "4. close": "close", "5. volume": "volume",
        })
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df.columns = [c.split(". ")[-1] if ". " in str(c) else str(c).lower() for c in df.columns]
        return DataResult(
            provider_id="alpha_vantage", category="stocks",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
