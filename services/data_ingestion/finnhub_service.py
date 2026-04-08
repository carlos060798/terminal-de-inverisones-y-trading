import finnhub
import streamlit as st
import database as db

def sync_finnhub_analysts(ticker):
    """
    Get analyst recommendations and price targets from Finnhub.
    """
    try:
        api_key = st.secrets.get("FINNHUB_API_KEY")
        if not api_key:
            return False
            
        finnhub_client = finnhub.Client(api_key=api_key)
        
        # Recommendations Trends (returns list of monthly snapshots)
        recs = finnhub_client.recommendation_trends(ticker)
        if recs:
            latest = recs[0]
            data = {
                'strong_buy': latest.get('strongBuy', 0),
                'buy': latest.get('buy', 0),
                'hold': latest.get('hold', 0),
                'sell': latest.get('sell', 0),
                'strong_sell': latest.get('strongSell', 0),
                'target_mean': None,
                'target_median': None
            }
            
            # Target Price
            targets = finnhub_client.price_target(ticker)
            if targets:
                data['target_mean'] = targets.get('targetMean')
                data['target_median'] = targets.get('targetMedian')
                
            db.save_analyst_recommendation(ticker, data)
            
        return True
    except Exception as e:
        print(f"[FINNHUB SERVICE] Error for {ticker}: {e}")
        return False

def sync_finnhub_earnings(ticker):
    """
    Get earnings surprises from Finnhub.
    """
    try:
        api_key = st.secrets.get("FINNHUB_API_KEY")
        if not api_key: return False
        
        finnhub_client = finnhub.Client(api_key=api_key)
        surprises = finnhub_client.company_earnings(ticker)
        if surprises:
            # We can save this to a separate table or update the analysis table
            pass
        return True
    except Exception:
        return False
