import yfinance as yf
import pandas as pd
import mibian
from datetime import datetime
import streamlit as st

@st.cache_data(ttl=3600)
def get_options_flow(ticker: str):
    """
    Analyzes the options chain to detect unusual activity.
    Logic: Look for Volume > Open Interest and high IV spikes.
    """
    tk = yf.Ticker(ticker)
    
    # Get expiration dates
    expirations = tk.options
    if not expirations:
        return pd.DataFrame()
    
    # Analyze the closest expiration (usually most active for "unusual" flow)
    opt = tk.option_chain(expirations[0])
    calls = opt.calls
    puts = opt.puts
    
    # Identify unusual calls
    calls['Type'] = 'CALL'
    puts['Type'] = 'PUT'
    
    all_options = pd.concat([calls, puts])
    
    # Criteria: Volume > Open Interest (Position accumulation)
    all_options['Unusual_Score'] = all_options['volume'] / all_options['openInterest'].replace(0, 1)
    
    # Filter highly unusual ones
    unusual = all_options[all_options['Unusual_Score'] > 1.5].copy()
    unusual = unusual.sort_values('Unusual_Score', ascending=False)
    
    return unusual.head(15)

def calculate_greeks(ticker_price, strike, days_to_expiry, iv, risk_free_rate=0.05, option_type='call'):
    """
    Calculates Delta and Gamma using Mibian (Black-Scholes).
    """
    if option_type.lower() == 'call':
        c = mibian.BS([ticker_price, strike, risk_free_rate, days_to_expiry], volatility=iv*100)
        return {"delta": c.callDelta, "theta": c.callTheta, "vega": c.vega, "gamma": c.gamma}
    else:
        p = mibian.BS([ticker_price, strike, risk_free_rate, days_to_expiry], volatility=iv*100)
        return {"delta": p.putDelta, "theta": p.putTheta, "vega": p.vega, "gamma": p.gamma}
