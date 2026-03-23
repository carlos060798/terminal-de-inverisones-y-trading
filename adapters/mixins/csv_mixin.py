"""
adapters/mixins/csv_mixin.py
CSV/ZIP download mixin for adapters that consume file-based data.
(CBOE VIX/SKEW, CFTC COT Reports, USDA ERS, CME Group)

Provides:
  _fetch_csv(url, compression, ...)  — download + parse to DataFrame
  _fetch_zip_csv(url, filename)      — download ZIP, extract specific CSV
"""
from __future__ import annotations

import io
import logging
import zipfile
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class CsvMixin:
    """
    Mixin for CSV/ZIP-based adapters.

    Usage:
        df = self._fetch_csv("https://cdn.cboe.com/.../VIX_History.csv")
        df = self._fetch_zip_csv("https://cftc.gov/.../fut_disagg_txt_2024.zip")
    """

    def _fetch_csv(
        self,
        url: str,
        compression: Optional[str] = None,
        sep: str = ",",
        skiprows: int = 0,
        encoding: str = "utf-8",
        timeout: float = 30.0,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Download a CSV (optionally compressed) and return as DataFrame.
        compression: None | "gzip" | "zip" | "bz2" — passed to pd.read_csv
        """
        import requests
        resp = requests.get(url, params=extra_params, timeout=timeout)
        resp.raise_for_status()

        raw_bytes = io.BytesIO(resp.content)

        if compression == "zip":
            # Let pandas handle zip internally
            df = pd.read_csv(raw_bytes, compression="zip", sep=sep,
                             skiprows=skiprows, encoding=encoding,
                             on_bad_lines="skip", low_memory=False)
        else:
            df = pd.read_csv(raw_bytes, compression=compression, sep=sep,
                             skiprows=skiprows, encoding=encoding,
                             on_bad_lines="skip", low_memory=False)

        logger.debug("CsvMixin: fetched %d rows from %s", len(df), url)
        return df

    def _fetch_zip_csv(
        self,
        url: str,
        filename_hint: str = "",
        sep: str = ",",
        encoding: str = "latin-1",
        timeout: float = 30.0,
    ) -> pd.DataFrame:
        """
        Download a ZIP archive and extract the first CSV (or the one matching filename_hint).
        Used for CFTC COT reports which ship as ZIP → TXT/CSV inside.
        """
        import requests
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            names = zf.namelist()
            # Pick file matching hint, or first file
            target = next(
                (n for n in names if filename_hint.lower() in n.lower()),
                names[0]
            )
            with zf.open(target) as f:
                df = pd.read_csv(
                    io.TextIOWrapper(f, encoding=encoding),
                    sep=sep,
                    on_bad_lines="skip",
                    low_memory=False,
                )

        logger.debug("CsvMixin: extracted '%s' from ZIP → %d rows", target, len(df))
        return df

    def _parse_date_col(self, df: pd.DataFrame, col: str, fmt: Optional[str] = None) -> pd.DataFrame:
        """Utility: parse a date column to datetime and set as index."""
        df[col] = pd.to_datetime(df[col], format=fmt, errors="coerce")
        df = df.dropna(subset=[col]).sort_values(col)
        return df
