"""
utils/technical_analysis.py - Robust Technical Analysis Indicators
Includes ATR (Average True Range) for volatility-based alerting and stop-loss positioning.
"""
import pandas as pd
import numpy as np

def calculate_atr(df, period=14):
    """
    Calculates Average True Range (ATR).
    df: DataFrame with 'High', 'Low', 'Close'
    """
    if df is None or df.empty or len(df) <= period:
        return 0.0
    
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    # TR = max(H-L, |H-Cp|, |L-Cp|)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # ATR as SMA of TR
    atr = tr.rolling(window=period).mean()
    
    return atr.iloc[-1]

def get_volatility_adjusted_price(ticker_df, current_price, multiplier=2.0, direction="up"):
    """
    Calculates price levels based on ATR from current price.
    useful for stops and threshold alerts.
    """
    atr = calculate_atr(ticker_df)
    if atr == 0:
        return current_price
    
    offset = atr * multiplier
    if direction == "up":
        return current_price + offset
    else:
        return current_price - offset
