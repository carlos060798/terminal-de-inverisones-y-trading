"""
Pairs Trading / Statistical Arbitrage Scanner.
Uses Engle-Granger cointegration test to find mean-reverting pairs
in the watchlist, then tracks the spread for trading signals.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
from itertools import combinations


@st.cache_data(ttl=3600, show_spinner=False)
def compute_pairs_analysis(tickers: list, period: str = "1y") -> dict:
    """
    Scan all pairs in tickers list for cointegration.

    Returns dict with:
        - pairs: DataFrame of all tested pairs sorted by p-value
        - cointegrated: list of (t1, t2) passing significance test
    """
    if len(tickers) < 2:
        return {"error": "Se necesitan al menos 2 tickers para el análisis de pares."}

    try:
        from statsmodels.tsa.stattools import coint
    except ImportError:
        return {"error": "statsmodels no está instalado. Ejecuta: pip install statsmodels"}

    try:
        prices = yf.download(
            tickers, period=period, interval="1d",
            progress=False, auto_adjust=True
        )["Close"].ffill().dropna()
    except Exception as e:
        return {"error": str(e)}

    if prices.empty or len(prices) < 60:
        return {"error": "Datos insuficientes para análisis de cointegración."}

    available = [t for t in tickers if t in prices.columns]
    if len(available) < 2:
        return {"error": "Datos disponibles insuficientes."}

    results = []
    for t1, t2 in combinations(available, 2):
        try:
            score, p_value, _ = coint(prices[t1], prices[t2])
            results.append({
                "Ticker 1": t1,
                "Ticker 2": t2,
                "P-Value": round(p_value, 4),
                "Cointegrado": "✅" if p_value < 0.05 else "❌",
                "Test Score": round(score, 3),
            })
        except Exception:
            continue

    if not results:
        return {"error": "No se pudo calcular cointegración para ningún par."}

    pairs_df = pd.DataFrame(results).sort_values("P-Value").reset_index(drop=True)
    cointegrated = [
        (r["Ticker 1"], r["Ticker 2"])
        for _, r in pairs_df.iterrows()
        if r["P-Value"] < 0.05
    ]

    return {
        "pairs": pairs_df,
        "cointegrated": cointegrated,
        "prices": prices,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def get_spread_analysis(ticker1: str, ticker2: str, period: str = "1y") -> dict:
    """
    Calculate the normalized spread between two cointegrated stocks
    and generate Z-score signals.
    """
    try:
        prices = yf.download(
            [ticker1, ticker2], period=period, interval="1d",
            progress=False, auto_adjust=True
        )["Close"].ffill().dropna()
    except Exception as e:
        return {"error": str(e)}

    if ticker1 not in prices.columns or ticker2 not in prices.columns:
        return {"error": "No se pudieron obtener precios para ambos tickers."}

    p1 = prices[ticker1]
    p2 = prices[ticker2]

    # Hedge ratio via OLS
    try:
        from statsmodels.regression.linear_model import OLS
        from statsmodels.tools import add_constant
        model = OLS(p1, add_constant(p2)).fit()
        hedge_ratio = model.params.iloc[1]
    except Exception:
        hedge_ratio = p1.mean() / p2.mean()

    spread = p1 - hedge_ratio * p2
    z_score = (spread - spread.rolling(20).mean()) / spread.rolling(20).std()

    current_z = float(z_score.iloc[-1])
    if current_z > 2:
        signal = f"🔴 Short {ticker1} / Long {ticker2} (Z={current_z:.2f})"
    elif current_z < -2:
        signal = f"🟢 Long {ticker1} / Short {ticker2} (Z={current_z:.2f})"
    elif abs(current_z) < 0.5:
        signal = f"⚪ Neutral — Spread en media (Z={current_z:.2f})"
    else:
        signal = f"🟡 Monitorear — Divergiendo (Z={current_z:.2f})"

    return {
        "ticker1": ticker1,
        "ticker2": ticker2,
        "hedge_ratio": round(hedge_ratio, 4),
        "spread": spread,
        "z_score": z_score,
        "current_z": current_z,
        "signal": signal,
        "prices": prices,
    }
