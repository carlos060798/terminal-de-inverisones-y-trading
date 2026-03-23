"""
adapters/mixins/rest_mixin.py
Shared HTTP session with retry + timeout for all REST-based adapters.
(Polygon, Alpha Vantage, CoinGecko, EIA, BLS, NewsAPI, StockTwits, etc.)

Provides:
  _get(path, params, headers)    — GET request, raises on HTTP error
  _post(path, json, headers)     — POST request
  _session                       — shared requests.Session per class

Session is created once per adapter class (not per instance) to reuse
TCP connections efficiently across Streamlit reruns.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RestMixin:
    """
    Mixin for REST-based adapters.

    Subclass uses self.config.base_url as the URL prefix.

    Usage:
        data = self._get("/v2/aggs/ticker/AAPL/...", params={"apiKey": self._get_credential()})
        return data.json()["results"]
    """

    _session: Optional[Any] = None   # requests.Session, class-level

    def _get_session(self) -> Any:
        """Return (or create) a shared requests.Session with retry logic."""
        if self.__class__._session is None:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            session = requests.Session()
            retry = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"],
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self.__class__._session = session
            logger.debug("RestMixin: created session for %s", self.__class__.__name__)
        return self.__class__._session

    def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
        base_url: Optional[str] = None,
    ) -> Any:
        """
        Execute GET request.
        path can be a full URL (starts with http) or relative to config.base_url.
        Raises requests.HTTPError on 4xx/5xx.
        """
        import requests
        url = path if path.startswith("http") else (base_url or self.config.base_url) + path
        session = self._get_session()
        resp = session.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp

    def _post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
        base_url: Optional[str] = None,
    ) -> Any:
        """Execute POST request."""
        url = path if path.startswith("http") else (base_url or self.config.base_url) + path
        session = self._get_session()
        resp = session.post(url, json=json, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp

    def _auth_header(self, scheme: str = "Bearer") -> Dict[str, str]:
        """Build Authorization header from credential."""
        return {"Authorization": f"{scheme} {self._get_credential()}"}
