"""BIS — Bank for International Settlements (REST API)"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import RestMixin
from adapters.registry import register


@register
class BisAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="bis", category="macro",
        credential_key="",
        base_url="https://stats.bis.org/api/v1",
        rate_limit_rpm=20, ttl_seconds=86400, priority="low",
    )

    def _fetch_raw(self, dataset: str = "WS_LONG_CPI", key: str = "M.US.N.N.IX.XDC.H", **kwargs):
        import io
        resp = self._get(f"/data/{dataset}/{key}", params={"format": "csv"})
        return pd.read_csv(io.StringIO(resp.text))

    def _normalize(self, raw: pd.DataFrame) -> DataResult:
        df = raw.copy()
        df.columns = [str(c).lower().strip() for c in df.columns]
        return DataResult(
            provider_id="bis", category="macro",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
