import requests
import pandas as pd
import streamlit as st
from datetime import datetime
import io

def get_finra_daily_short_volume(date=None):
    """
    Downloads and parses FINRA Daily Short Sale Volume files.
    Format: Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    
    # FINRA consolidated URL
    url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date}.txt"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            df = pd.read_csv(io.StringIO(resp.text), sep="|")
            return df
        else:
            # Try previous day
            return pd.DataFrame()
    except Exception as e:
        print(f"Error fetching FINRA data: {e}")
        return pd.DataFrame()

def get_ticker_short_stats(ticker: str):
    """
    Combines Daily Short Volume with context.
    Daily Short % = ShortVolume / TotalVolume
    """
    # Fetch recent date (usually yesterday)
    today = datetime.now().strftime("%Y%m%d")
    df = get_finra_daily_short_volume(today)
    
    if df.empty:
        return None
    
    row = df[df['Symbol'] == ticker.upper()]
    if row.empty:
        return None
    
    res = row.iloc[0].to_dict()
    res['ShortPercentage'] = (res['ShortVolume'] / res['TotalVolume']) * 100 if res['TotalVolume'] > 0 else 0
    return res
