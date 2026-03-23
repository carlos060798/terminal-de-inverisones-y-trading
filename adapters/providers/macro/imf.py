"""IMF — imf-reader library"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register


@register
class ImfAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "imf_reader"
    config = ProviderConfig(
        provider_id="imf", category="macro",
        credential_key="",
        rate_limit_rpm=10, ttl_seconds=86400, priority="low",
    )

    def _fetch_raw(self, database: str = "IFS", frequency: str = "A",
                   country: str = "US", series: str = "NGDP_R_PC_PP_PT", **kwargs):
        imf = self._import_lib()
        return imf.data(database, frequency, country, series)

    def _normalize(self, raw) -> DataResult:
        if hasattr(raw, "reset_index"):
            df = raw.reset_index()
        else:
            df = pd.DataFrame(raw)
        df.columns = [str(c).lower() for c in df.columns]
        return DataResult(
            provider_id="imf", category="macro",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
