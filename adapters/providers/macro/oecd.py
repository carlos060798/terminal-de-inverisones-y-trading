"""OECD — via sdmx1 / pandasdmx"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register


@register
class OecdAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "sdmx"
    config = ProviderConfig(
        provider_id="oecd", category="macro",
        credential_key="",
        rate_limit_rpm=10, ttl_seconds=86400, priority="low",
    )

    def _fetch_raw(self, dataset: str = "QNA", key: str = "", **kwargs):
        sdmx = self._import_lib()
        oecd = sdmx.Request("OECD")
        params = {"key": key} if key else {}
        resp = oecd.data(dataset, **params)
        return sdmx.to_pandas(resp)

    def _normalize(self, raw) -> DataResult:
        df = raw.reset_index() if hasattr(raw, "reset_index") else pd.DataFrame({"value": raw})
        df.columns = [str(c).lower() for c in df.columns]
        return DataResult(
            provider_id="oecd", category="macro",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
