"""
services/finnhub_client.py — Cliente para la API Gratuita de Finnhub.io
========================================================================
Extrae datos alternativos que complementan a yfinance y SEC:
- Sorpresas de ganancias (Earnings Surprises)
- Sentimiento Social (Reddit y Twitter/X)
"""

import requests
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def _get_api_key():
    try:
        return st.secrets.get("FINNHUB_API_KEY", "")
    except Exception:
        return ""

def get_earnings_surprises(ticker: str, limit: int = 4) -> pd.DataFrame:
    """Extrae las sorpresas de beneficios (Estimado vs Real) del último año."""
    api_key = _get_api_key()
    if not api_key:
        return pd.DataFrame()
        
    url = f"https://finnhub.io/api/v1/stock/earnings?symbol={ticker.upper()}&token={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            df = pd.DataFrame(data).head(limit)
            df = df.rename(columns={
                "actual": "EPS Real",
                "estimate": "EPS Estimado",
                "surprise": "Sorpresa Absoluta",
                "surprisePercent": "Sorpresa %",
                "period": "Periodo Fiscal"
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        print(f"[FINNHUB] Error en Earnings Surprises [{ticker}]: {e}")
        return pd.DataFrame()

def get_social_sentiment(ticker: str) -> dict:
    """Extrae el sentimiento de Reddit y X (Twitter) sobre la acción."""
    api_key = _get_api_key()
    if not api_key:
        return {}

    url = f"https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker.upper()}&token={api_key}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        # Consolidar sentimiento general
        result = {"reddit_mentions": 0, "reddit_bullish": 0, "twitter_mentions": 0, "twitter_bullish": 0}
        
        # Sumamos datos de Reddit
        if "reddit" in data and len(data["reddit"]) > 0:
            for entry in data["reddit"]:
                result["reddit_mentions"] += entry.get("mention", 0)
                result["reddit_bullish"] += entry.get("positiveMention", 0)
                
        # Sumamos datos de Twitter
        if "twitter" in data and len(data["twitter"]) > 0:
            for entry in data["twitter"]:
                result["twitter_mentions"] += entry.get("mention", 0)
                result["twitter_bullish"] += entry.get("positiveMention", 0)
                
        return result
    except Exception as e:
        print(f"[FINNHUB] Error en Social Sentiment [{ticker}]: {e}")
        return {}
