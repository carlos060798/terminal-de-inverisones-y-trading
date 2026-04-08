import requests
import streamlit as st
import database as db

def sync_tiingo_news(ticker):
    """
    Get latest news and headlines from Tiingo News Feed API.
    Tiingo is excellent for real-time news across multiple sources.
    """
    try:
        api_key = st.secrets.get("TIINGO_API_KEY")
        if not api_key:
            return False
            
        # Tiingo News Feed endpoint
        url = f"https://api.tiingo.com/tiingo/news?tickers={ticker.lower()}&limit=10&token={api_key}"
        headers = {'Content-Type': 'application/json'}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            news_items = response.json()
            for item in news_items:
                # Some items include 'crawlDate', 'source', 'title', 'url', 'description'
                db.save_sentiment(
                    ticker=ticker.upper(),
                    source="tiingo",
                    sentiment=0.0, # Tiingo doesn't always provide a native sentiment score in the basic feed
                    headline=item.get('title', ''),
                    url=item.get('url', ''),
                    score=0.0 # Placeholder
                )
            return True
        else:
            print(f"[TIINGO SERVICE] HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"[TIINGO SERVICE] Error for {ticker}: {e}")
        return False

def sync_top_news():
    """Sync news for the main market (SPY, QQQ, DIA)."""
    for t in ["SPY", "QQQ", "DIA"]:
        sync_tiingo_news(t)

if __name__ == "__main__":
    sync_tiingo_news("AAPL")
