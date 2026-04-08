"""
Unusual Options Activity Scanner.
Scans option chains for anomalous volume relative to open interest,
indicating potential institutional positioning.
"""
import pandas as pd
import yfinance as yf
from datetime import datetime


def scan_unusual_options(tickers: list, max_tickers: int = 5,
                         vol_oi_threshold: float = 2.0,
                         max_expirations: int = 2) -> pd.DataFrame:
    """
    Scan option chains for unusual activity.

    Filters: Volume > (Open Interest * vol_oi_threshold)

    Args:
        tickers: List of ticker symbols
        max_tickers: Max tickers to scan (rate limit protection)
        vol_oi_threshold: Min ratio of Volume/OI to flag
        max_expirations: How many nearest expiration dates to check

    Returns DataFrame with anomalous contracts.
    """
    anomalies = []
    scan_tickers = tickers[:max_tickers]

    for ticker in scan_tickers:
        try:
            tk = yf.Ticker(ticker)
            expirations = tk.options

            if not expirations:
                continue

            # Only check nearest N expirations
            check_dates = expirations[:max_expirations]

            for exp_date in check_dates:
                try:
                    chain = tk.option_chain(exp_date)

                    # Process Calls
                    calls = chain.calls.copy()
                    if not calls.empty and "volume" in calls.columns and "openInterest" in calls.columns:
                        calls["volume"] = pd.to_numeric(calls["volume"], errors="coerce").fillna(0)
                        calls["openInterest"] = pd.to_numeric(calls["openInterest"], errors="coerce").fillna(0)
                        calls["vol_oi_ratio"] = calls.apply(
                            lambda r: r["volume"] / r["openInterest"] if r["openInterest"] > 0 else 0, axis=1
                        )
                        unusual_calls = calls[calls["vol_oi_ratio"] >= vol_oi_threshold]

                        for _, row in unusual_calls.iterrows():
                            anomalies.append({
                                "Ticker": ticker,
                                "Tipo": "CALL 📈",
                                "Strike": row.get("strike", 0),
                                "Expiración": exp_date,
                                "Volume": int(row.get("volume", 0)),
                                "Open Interest": int(row.get("openInterest", 0)),
                                "Vol/OI": round(row["vol_oi_ratio"], 1),
                                "IV": round(row.get("impliedVolatility", 0) * 100, 1),
                                "Last Price": round(row.get("lastPrice", 0), 2),
                                "Bid": round(row.get("bid", 0), 2),
                                "Ask": round(row.get("ask", 0), 2),
                            })

                    # Process Puts
                    puts = chain.puts.copy()
                    if not puts.empty and "volume" in puts.columns and "openInterest" in puts.columns:
                        puts["volume"] = pd.to_numeric(puts["volume"], errors="coerce").fillna(0)
                        puts["openInterest"] = pd.to_numeric(puts["openInterest"], errors="coerce").fillna(0)
                        puts["vol_oi_ratio"] = puts.apply(
                            lambda r: r["volume"] / r["openInterest"] if r["openInterest"] > 0 else 0, axis=1
                        )
                        unusual_puts = puts[puts["vol_oi_ratio"] >= vol_oi_threshold]

                        for _, row in unusual_puts.iterrows():
                            anomalies.append({
                                "Ticker": ticker,
                                "Tipo": "PUT 📉",
                                "Strike": row.get("strike", 0),
                                "Expiración": exp_date,
                                "Volume": int(row.get("volume", 0)),
                                "Open Interest": int(row.get("openInterest", 0)),
                                "Vol/OI": round(row["vol_oi_ratio"], 1),
                                "IV": round(row.get("impliedVolatility", 0) * 100, 1),
                                "Last Price": round(row.get("lastPrice", 0), 2),
                                "Bid": round(row.get("bid", 0), 2),
                                "Ask": round(row.get("ask", 0), 2),
                            })

                except Exception:
                    continue

        except Exception:
            continue

    if not anomalies:
        return pd.DataFrame()

    df = pd.DataFrame(anomalies)
    # Sort by urgency (highest Vol/OI ratio first)
    df = df.sort_values("Vol/OI", ascending=False).reset_index(drop=True)

    return df


def get_options_sentiment(df: pd.DataFrame) -> dict:
    """Calculate aggregate sentiment from anomalies."""
    if df.empty:
        return {"call_count": 0, "put_count": 0, "ratio": 0, "signal": "Neutral"}

    calls = df[df["Tipo"].str.contains("CALL")]
    puts = df[df["Tipo"].str.contains("PUT")]

    call_vol = calls["Volume"].sum()
    put_vol = puts["Volume"].sum()

    ratio = call_vol / put_vol if put_vol > 0 else float("inf")

    if ratio > 1.5:
        signal = "🟢 Bullish Flow"
    elif ratio < 0.67:
        signal = "🔴 Bearish Flow"
    else:
        signal = "⚪ Neutral"

    return {
        "call_count": len(calls),
        "put_count": len(puts),
        "call_volume": int(call_vol),
        "put_volume": int(put_vol),
        "ratio": round(ratio, 2),
        "signal": signal
    }
