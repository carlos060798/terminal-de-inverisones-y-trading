"""
Short Squeeze Radar.
Identifies stocks in the watchlist with high short interest ratios,
making them candidates for violent short-squeeze moves on volume spikes.
"""
import pandas as pd
import yfinance as yf
import streamlit as st


@st.cache_data(ttl=3600, show_spinner=False)
def get_short_data(ticker: str) -> dict:
    """
    Extract short interest data for a ticker from yfinance.
    Key metrics: shortPercentOfFloat, shortRatio (days to cover), sharesShort.
    """
    try:
        info = yf.Ticker(ticker).fast_info
        full_info = yf.Ticker(ticker).info
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

    short_pct   = full_info.get("shortPercentOfFloat", None)
    short_ratio = full_info.get("shortRatio", None)
    shares_short = full_info.get("sharesShort", None)
    float_shares = full_info.get("floatShares", None)
    price        = full_info.get("currentPrice") or full_info.get("regularMarketPrice")

    # Squeeze Score (0-100): weighted composite
    score = 0
    if short_pct is not None:
        score += min(short_pct / 0.30 * 40, 40)      # max 40 pts at 30%+ short float
    if short_ratio is not None:
        score += min(short_ratio / 10   * 30, 30)     # max 30 pts at 10+ days to cover
    if price:
        # Bonus for lower liquidity (smaller floats more squeezable)
        if float_shares and float_shares < 50_000_000:
            score += 20
        elif float_shares and float_shares < 200_000_000:
            score += 10
    score = round(min(score, 100), 1)

    if score >= 75:
        risk_label = "🔥 Alto Riesgo de Squeeze"
    elif score >= 50:
        risk_label = "⚠️ Moderado"
    elif score >= 25:
        risk_label = "🟡 Bajo"
    else:
        risk_label = "⚪ Mínimo"

    return {
        "ticker": ticker,
        "price": price,
        "short_pct_float": round(short_pct * 100, 1) if short_pct else None,
        "short_ratio": round(short_ratio, 1) if short_ratio else None,
        "shares_short": shares_short,
        "float_shares": float_shares,
        "squeeze_score": score,
        "risk_label": risk_label,
    }


def scan_short_squeeze(tickers: list) -> pd.DataFrame:
    """
    Scan all tickers and return a sorted DataFrame of short squeeze candidates.
    """
    results = []
    for t in tickers:
        d = get_short_data(t)
        if "error" not in d:
            results.append(d)

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values("squeeze_score", ascending=False).reset_index(drop=True)
    return df
