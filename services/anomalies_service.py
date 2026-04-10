import pandas as pd
import numpy as np
from pyod.models.iforest import IForest
from pyod.models.lof import LOF
import streamlit as st

def detect_price_anomalies(df: pd.DataFrame):
    """
    Uses Isolation Forest to detect price/volume outliers.
    Returns indices of anomalous days.
    """
    if df.empty or len(df) < 50:
        return []
    
    # Prepare features: Returns and Volatility
    data = df[['Close', 'Volume']].copy()
    data['Returns'] = data['Close'].pct_change()
    data['Vol_Change'] = data['Volume'].pct_change()
    data = data.dropna()
    
    X = data[['Returns', 'Vol_Change']].values
    
    # Isolation Forest
    clf = IForest(contamination=0.03) # 3% anomalies
    clf.fit(X)
    
    # Predict
    preds = clf.labels_
    anomalies = data.index[preds == 1]
    
    return list(anomalies)

def detect_volume_spikes(df: pd.DataFrame):
    """
    Detects abnormal volume relative to 20-day average.
    """
    avg_vol = df['Volume'].rolling(20).mean()
    std_vol = df['Volume'].rolling(20).std()
    
    spikes = df[df['Volume'] > (avg_vol + 3 * std_vol)]
    return spikes
