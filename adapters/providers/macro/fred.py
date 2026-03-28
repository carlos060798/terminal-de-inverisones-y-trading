"""FRED — Federal Reserve Economic Data (pandas_datareader)"""
import pandas as pd
import pandas_datareader.data as pdr
from datetime import datetime
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.registry import register

@register
class FredAdapter(BaseDataAdapter):
    config = ProviderConfig(
        provider_id="fred", category="macro",
        credential_key="FRED_API_KEY",
        rate_limit_rpm=120, ttl_seconds=3600, priority="high",
    )

    def _fetch_raw(self, series_id: str = "GS10", **kwargs):
        """Fetch macro data using pandas_datareader."""
        start = datetime(2010, 1, 1)
        end = datetime.now()
        
        # pandas_datareader uses the environment variable 'FRED_API_KEY' 
        # automatically if set, or we can pass it if needed.
        # Since BaseDataAdapter uses _get_credential(), we can set it in env.
        api_key = self._get_credential()
        if api_key:
            import os
            os.environ["FRED_API_KEY"] = api_key
            
        return pdr.DataReader(series_id, "fred", start, end)

    def _normalize(self, raw: pd.DataFrame) -> DataResult:
        df = raw.reset_index()
        # FRED data usually has Date as index and the series_id as column name
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df = df.dropna().sort_values("date")
        
        return DataResult(
            provider_id="fred", category="macro",
            fetched_at="", latency_ms=0, success=True, data=df,
        )
