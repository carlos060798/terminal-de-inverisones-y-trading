"""ECB — European Central Bank via sdmx1"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register


@register
class EcbAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "sdmx"
    config = ProviderConfig(
        provider_id="ecb_sdmx", category="macro",
        credential_key="",
        rate_limit_rpm=20, ttl_seconds=3600, priority="medium",
    )

    def _fetch_raw(self, dataset: str = "EXR", key: str = "M.USD.EUR.SP00.A", **kwargs):
        sdmx = self._import_lib()
        ecb = sdmx.Request("ECB")
        resp = ecb.data(dataset, key=key)
        return sdmx.to_pandas(resp)

    def _normalize(self, raw) -> DataResult:
        if hasattr(raw, "reset_index"):
            df = raw.reset_index()
        else:
            df = pd.DataFrame({"value": raw})
        df.columns = [str(c).lower() for c in df.columns]
        return DataResult(
            provider_id="ecb_sdmx", category="macro",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
