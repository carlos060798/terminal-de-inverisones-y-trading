"""FRED — Federal Reserve Economic Data (fredapi library)"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register


@register
class FredAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "fredapi"
    config = ProviderConfig(
        provider_id="fred", category="macro",
        credential_key="FRED_API_KEY",
        rate_limit_rpm=120, ttl_seconds=3600, priority="high",
    )

    def _fetch_raw(self, series_id: str = "GS10", **kwargs):
        Fred = self._import_from("fredapi", "Fred")
        fr = Fred(api_key=self._get_credential())
        return fr.get_series(series_id)

    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index()
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df = df.dropna().sort_values("date")
        return DataResult(
            provider_id="fred", category="macro",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
