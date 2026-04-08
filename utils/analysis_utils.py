import pandas as pd
import numpy as np

def detect_fvg(df):
    """
    Detects Fair Value Gaps (FVG) in a OHLC DataFrame.
    Returns a list of dicts with 'type', 'top', 'bottom', and 'index'.
    """
    fvgs = []
    if len(df) < 3:
        return fvgs
        
    for i in range(2, len(df)):
        # Bullish FVG: Low of candle i > High of candle i-2
        if df['Low'].iloc[i] > df['High'].iloc[i-2]:
            fvgs.append({
                'type': 'Bullish',
                'bottom': df['High'].iloc[i-2],
                'top': df['Low'].iloc[i],
                'index': df.index[i-1]
            })
        # Bearish FVG: High of candle i < Low of candle i-2
        elif df['High'].iloc[i] < df['Low'].iloc[i-2]:
            fvgs.append({
                'type': 'Bearish',
                'bottom': df['High'].iloc[i],
                'top': df['Low'].iloc[i-2],
                'index': df.index[i-1]
            })
    return fvgs

def detect_ob(df, lookback=20):
    """
    Detects potential Order Blocks (OB).
    Simplification: Last candle before a significant displacement.
    """
    obs = []
    if len(df) < lookback:
        return obs
        
    # Logic: Look for candles with high body-to-wick ratio (displacement)
    for i in range(len(df) - 5, len(df)):
        body = abs(df['Close'].iloc[i] - df['Open'].iloc[i])
        avg_body = df['Close'].diff().abs().rolling(10).mean().iloc[i]
        
        if body > 1.5 * avg_body: # Significant move
            # Bullish OB: Last bearish candle before the move
            if df['Close'].iloc[i] > df['Open'].iloc[i]:
                # Look back for the last red candle
                for j in range(i-1, i-5, -1):
                    if df['Close'].iloc[j] < df['Open'].iloc[j]:
                        obs.append({
                            'type': 'Bullish OB',
                            'top': df['High'].iloc[j],
                            'bottom': df['Low'].iloc[j],
                            'price': df['Close'].iloc[j]
                        })
                        break
            # Bearish OB: Last bullish candle before the move
            else:
                for j in range(i-1, i-5, -1):
                    if df['Close'].iloc[j] > df['Open'].iloc[j]:
                        obs.append({
                            'type': 'Bearish OB',
                            'top': df['High'].iloc[j],
                            'bottom': df['Low'].iloc[j],
                            'price': df['Close'].iloc[j]
                        })
                        break
    return obs

def calculate_setup_score(confluences, smc_data=None):
    """
    Calculates a qualitative setup score (0-100).
    confluences: dict with boolean values
    smc_data: results from detection
    """
    score = 0
    weights = {
        'sesgo_aligned': 25,
        'in_poi': 20,
        'fvg_detected': 15,
        'ob_detected': 15,
        'session_active': 10,
        'risk_reward_ok': 15
    }
    
    if confluences.get('sesgo_aligned'): score += weights['sesgo_aligned']
    if confluences.get('in_poi'): score += weights['in_poi']
    if smc_data and smc_data.get('fvgs'): score += weights['fvg_detected']
    if smc_data and smc_data.get('obs'): score += weights['ob_detected']
    if confluences.get('session_active'): score += weights['session_active']
    if confluences.get('rr'): score += weights['risk_reward_ok']
    
    return score
