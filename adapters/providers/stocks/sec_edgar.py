"""SEC EDGAR — sec-edgar-downloader + REST search (migrated from data_sources.py)"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import RestMixin
from adapters.registry import register


@register
class SecEdgarAdapter(RestMixin, BaseDataAdapter):
    config = ProviderConfig(
        provider_id="sec_edgar", category="stocks",
        credential_key="",
        base_url="https://efts.sec.gov/LATEST/search-index",
        rate_limit_rpm=10, ttl_seconds=3600, priority="medium",
    )

    def _fetch_raw(self, ticker: str = "AAPL", form_type: str = "10-K", limit: int = 5, **kwargs):
        resp = self._get(
            "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&forms={form_type}&hits.hits._source.period_of_report=true".format(
                ticker=ticker, form_type=form_type
            )
        )
        return resp.json().get("hits", {}).get("hits", [])[:limit]

    def _normalize(self, raw) -> DataResult:
        rows = []
        for hit in raw:
            src = hit.get("_source", {})
            rows.append({
                "form_type": src.get("form_type"),
                "filed_at":  src.get("file_date"),
                "company":   src.get("display_names"),
                "url":       "https://www.sec.gov/Archives/" + src.get("file_path", ""),
            })
        df = pd.DataFrame(rows)
        return DataResult(
            provider_id="sec_edgar", category="stocks",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
