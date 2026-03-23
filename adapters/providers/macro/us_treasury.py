"""US Treasury — Fiscal Data REST API"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import RestMixin
from adapters.registry import register


@register
class UsTreasuryAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="us_treasury", category="macro",
        credential_key="",
        base_url="https://api.fiscaldata.treasury.gov/services/api/v1",
        rate_limit_rpm=60, ttl_seconds=3600, priority="medium",
    )

    def _fetch_raw(self, endpoint: str = "debt/search/",
                   fields: str = "record_date,tot_pub_debt_out_amt", **kwargs):
        resp = self._get(f"/{endpoint}", params={"fields": fields, "sort": "-record_date", "page[size]": "100"})
        return resp.json().get("data", [])

    def _normalize(self, raw) -> DataResult:
        df = pd.DataFrame(raw)
        if "record_date" in df.columns:
            df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce", utc=True)
        return DataResult(
            provider_id="us_treasury", category="macro",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
