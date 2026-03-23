"""CEPAL/ECLAC — REST API (CEPALSTAT)"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import RestMixin
from adapters.registry import register


@register
class CepalAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="cepal", category="macro",
        credential_key="",
        base_url="https://api.cepal.org/v1",
        rate_limit_rpm=10, ttl_seconds=604800, priority="batch",
    )

    def _fetch_raw(self, indicator_id: int = 3, country_id: str = "ARG",
                   start_year: int = 2000, end_year: int = 2024, **kwargs):
        resp = self._get(
            f"/indicator/{indicator_id}/country/{country_id}",
            params={"startYear": start_year, "endYear": end_year, "format": "json"},
        )
        return resp.json()

    def _normalize(self, raw) -> DataResult:
        data = raw if isinstance(raw, list) else raw.get("data", [raw])
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame({"raw": [str(raw)]})
        df.columns = [str(c).lower() for c in df.columns]
        return DataResult(
            provider_id="cepal", category="macro",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
