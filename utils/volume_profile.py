"""
Volume Profile Engine.
Calculates volume distribution across price levels from OHLCV data,
identifying POC (Point of Control), HVN (High Volume Nodes) and LVN (Low Volume Nodes).
"""
import pandas as pd
import numpy as np
import yfinance as yf


def compute_volume_profile(ticker: str, interval: str = "1h",
                           period: str = "1mo", n_bins: int = 50) -> dict:
    """
    Compute Volume Profile for a ticker.

    Args:
        ticker: Stock/FX ticker
        interval: '1h', '4h', '1d' — candle interval
        period: '5d', '1mo', '3mo' — lookback
        n_bins: Number of price levels to bucket

    Returns dict with:
        - profile: DataFrame with columns [price_level, volume, pct, is_poc, node_type]
        - poc_price: float
        - value_area_high: float (70% of volume above POC)
        - value_area_low: float
        - stats: summary
    """
    # yfinance interval mapping (4h not directly supported, we resample)
    yf_interval = interval
    if interval == "4h":
        yf_interval = "1h"  # download 1h and resample

    try:
        data = yf.download(ticker, period=period, interval=yf_interval, progress=False)
    except Exception as e:
        return {"error": f"Error descargando datos: {e}"}

    if data.empty or len(data) < 10:
        return {"error": "Datos insuficientes para el perfil de volumen"}

    # Handle multi-index columns
    if hasattr(data.columns, 'levels'):
        data.columns = data.columns.get_level_values(0)

    # Resample to 4H if requested
    if interval == "4h":
        data = data.resample("4h").agg({
            "Open": "first", "High": "max", "Low": "min",
            "Close": "last", "Volume": "sum"
        }).dropna()

    if data.empty:
        return {"error": "Sin datos después del resampleo"}

    # Use typical price weighted by volume
    # For each candle, distribute volume across the high-low range
    all_prices = []
    all_volumes = []

    for _, row in data.iterrows():
        high = row["High"]
        low = row["Low"]
        vol = row["Volume"]

        if pd.isna(high) or pd.isna(low) or pd.isna(vol) or vol == 0:
            continue
        if high == low:
            all_prices.append(high)
            all_volumes.append(vol)
        else:
            # Distribute volume uniformly across 5 price points in the range
            price_points = np.linspace(low, high, 5)
            vol_per_point = vol / 5
            all_prices.extend(price_points)
            all_volumes.extend([vol_per_point] * 5)

    if not all_prices:
        return {"error": "Sin datos de precio/volumen válidos"}

    prices_arr = np.array(all_prices)
    volumes_arr = np.array(all_volumes)

    # Create bins
    price_min = prices_arr.min()
    price_max = prices_arr.max()
    bins = np.linspace(price_min, price_max, n_bins + 1)
    bin_centers = (bins[:-1] + bins[1:]) / 2

    # Digitize and sum volumes per bin
    bin_indices = np.digitize(prices_arr, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    vol_per_bin = np.zeros(n_bins)
    for i, vol in zip(bin_indices, volumes_arr):
        vol_per_bin[i] += vol

    total_vol = vol_per_bin.sum()

    # POC = bin with max volume
    poc_idx = np.argmax(vol_per_bin)
    poc_price = float(bin_centers[poc_idx])

    # Value Area (70% of total volume centered on POC)
    va_target = total_vol * 0.70
    va_vol = vol_per_bin[poc_idx]
    low_idx = poc_idx
    high_idx = poc_idx

    while va_vol < va_target:
        expand_low = vol_per_bin[low_idx - 1] if low_idx > 0 else 0
        expand_high = vol_per_bin[high_idx + 1] if high_idx < n_bins - 1 else 0

        if expand_low >= expand_high and low_idx > 0:
            low_idx -= 1
            va_vol += vol_per_bin[low_idx]
        elif high_idx < n_bins - 1:
            high_idx += 1
            va_vol += vol_per_bin[high_idx]
        else:
            break

    va_low = float(bin_centers[low_idx])
    va_high = float(bin_centers[high_idx])

    # Classify nodes: HVN (>= 75th percentile), LVN (<= 25th percentile)
    vol_nonzero = vol_per_bin[vol_per_bin > 0]
    if len(vol_nonzero) > 0:
        hvn_threshold = np.percentile(vol_nonzero, 75)
        lvn_threshold = np.percentile(vol_nonzero, 25)
    else:
        hvn_threshold = lvn_threshold = 0

    node_types = []
    for v in vol_per_bin:
        if v == vol_per_bin[poc_idx]:
            node_types.append("POC")
        elif v >= hvn_threshold:
            node_types.append("HVN")
        elif v > 0 and v <= lvn_threshold:
            node_types.append("LVN")
        else:
            node_types.append("Normal")

    profile_df = pd.DataFrame({
        "price_level": bin_centers,
        "volume": vol_per_bin,
        "pct": (vol_per_bin / total_vol * 100) if total_vol > 0 else 0,
        "is_poc": [i == poc_idx for i in range(n_bins)],
        "node_type": node_types
    })

    return {
        "profile": profile_df,
        "poc_price": poc_price,
        "value_area_high": va_high,
        "value_area_low": va_low,
        "stats": {
            "ticker": ticker,
            "interval": interval,
            "period": period,
            "total_volume": float(total_vol),
            "n_candles": len(data),
            "price_range": f"${price_min:.2f} — ${price_max:.2f}",
        }
    }
