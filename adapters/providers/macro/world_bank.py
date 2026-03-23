"""World Bank — wbdata library"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register


@register
class WorldBankAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "wbdata"
    config = ProviderConfig(
        provider_id="world_bank", category="macro",
        credential_key="",
        rate_limit_rpm=30, ttl_seconds=86400, priority="low",
    )

    def _fetch_raw(self, indicator: str = "NY.GDP.MKTP.CD", country: str = "US", **kwargs):
        wbdata = self._import_lib()
        return wbdata.get_dataframe({indicator: "value"}, country=country)

    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index().rename(columns={"date": "date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
        df = df.dropna(subset=["value"]).sort_values("date")
        return DataResult(
            provider_id="world_bank", category="macro",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
