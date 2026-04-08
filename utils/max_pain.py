"""
Max Pain Calculator.
For a given ticker and expiration date, calculates the strike price where
the maximum number of options contracts (calls + puts) expire worthless —
the price Market Makers are incentivized to pin near at expiry.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st


@st.cache_data(ttl=1800, show_spinner=False)
def get_max_pain(ticker: str, expiration: str) -> dict:
    """
    Compute Max Pain for a ticker on a given expiration date.

    Returns:
        dict with max_pain_price, strikes, call_oi, put_oi, total_pain_per_strike
    """
    try:
        tk = yf.Ticker(ticker)
        chain = tk.option_chain(expiration)
    except Exception as e:
        return {"error": f"Error al obtener cadena de opciones: {e}"}

    calls = chain.calls[["strike", "openInterest"]].copy()
    puts  = chain.puts[["strike", "openInterest"]].copy()

    calls.columns = ["strike", "call_oi"]
    puts.columns  = ["strike", "put_oi"]

    calls["call_oi"] = pd.to_numeric(calls["call_oi"], errors="coerce").fillna(0).astype(int)
    puts["put_oi"]   = pd.to_numeric(puts["put_oi"],  errors="coerce").fillna(0).astype(int)

    # Merge on strike
    df = pd.merge(calls, puts, on="strike", how="outer").fillna(0)
    df = df.sort_values("strike").reset_index(drop=True)

    strikes = df["strike"].values

    if len(strikes) == 0:
        return {"error": "No hay strikes disponibles para esta expiración."}

    # For each potential expiry price S, calculate total pain:
    # Pain = sum over all strikes K: call_OI(K) * max(S-K, 0) + put_OI(K) * max(K-S, 0)
    pain = np.zeros(len(strikes))
    for i, s in enumerate(strikes):
        call_pain = (df["call_oi"] * np.maximum(s - strikes, 0)).sum()
        put_pain  = (df["put_oi"]  * np.maximum(strikes - s, 0)).sum()
        pain[i]   = call_pain + put_pain

    df["total_pain"] = pain
    max_pain_idx   = np.argmin(pain)
    max_pain_price = float(strikes[max_pain_idx])

    # Get current price
    try:
        current_price = tk.fast_info["last_price"]
    except Exception:
        current_price = None

    return {
        "ticker": ticker,
        "expiration": expiration,
        "max_pain_price": max_pain_price,
        "current_price": current_price,
        "distance_pct": round((current_price - max_pain_price) / max_pain_price * 100, 2)
                        if current_price else None,
        "strikes": strikes.tolist(),
        "call_oi": df["call_oi"].tolist(),
        "put_oi": df["put_oi"].tolist(),
        "total_pain": pain.tolist(),
        "df": df,
    }


def get_expirations(ticker: str) -> list:
    """Return available option expiration dates for a ticker."""
    try:
        return list(yf.Ticker(ticker).options)
    except Exception:
        return []
