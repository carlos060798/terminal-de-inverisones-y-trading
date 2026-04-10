import requests
import pandas as pd
import streamlit as st
from typing import List, Dict, Optional

HOUSE_URL = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
SENATE_URL = "https://senate-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"

@st.cache_data(ttl=86400)
def get_congressional_trades(ticker: str = None) -> pd.DataFrame:
    """
    Fetches US Congress trades from public community datasets.
    """
    try:
        # Fetch House trades
        resp_h = requests.get(HOUSE_URL, timeout=10)
        house_data = resp_h.json()
        df_h = pd.DataFrame(house_data)
        df_h['chamber'] = 'House'
        
        # We focus on House first as Senate JSON structure varies or might be bigger
        df = df_h
        
        if ticker:
            ticker = ticker.upper()
            df = df[df['ticker'] == ticker]
            
        return df
    except Exception as e:
        print(f"Error fetching congressional trades: {e}")
        return pd.DataFrame()

def get_recent_congress_activity(limit: int = 20) -> pd.DataFrame:
    df = get_congressional_trades()
    if df.empty: return df
    
    # Sort by filing date
    if 'filing_date' in df.columns:
        df = df.sort_values('filing_date', ascending=False)
        
    return df.head(limit)
