"""BLS — Bureau of Labor Statistics (bls-python library)"""
import pandas as pd
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.mixins import LibraryMixin
from adapters.registry import register
from datetime import datetime


@register
class BlsAdapter(LibraryMixin, BaseDataAdapter):
    _lib_name = "bls"
    config = ProviderConfig(
        provider_id="bls", category="macro",
        credential_key="BLS_API_KEY",
        rate_limit_rpm=30, ttl_seconds=86400, priority="low",
    )

    def _fetch_raw(self, series: list = None, start_year: int = None, end_year: int = None, **kwargs):
        bls = self._import_lib()
        series = series or ["CUUR0000SA0"]
        current_year = datetime.now().year
        start = start_year or current_year - 4
        end = end_year or current_year
        return bls.get_series(series, start, end, api_key=self._get_credential())

    def _normalize(self, raw) -> DataResult:
        if hasattr(raw, "reset_index"):
            df = raw.reset_index()
        else:
            df = pd.DataFrame(raw)
        df.columns = [str(c).lower() for c in df.columns]
        return DataResult(
            provider_id="bls", category="macro",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
