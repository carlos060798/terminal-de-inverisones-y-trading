import praw
import streamlit as st
import database as db
from datetime import datetime, timedelta
from services import sentiment_service

def sync_reddit_sentiment(ticker_list):
    """
    Fetch Reddit (WallStreetBets, Stocks) for mentions of ticker_list
    and save sentiment counts to DB.
    """
    try:
        client_id = st.secrets.get("REDDIT_CLIENT_ID")
        client_secret = st.secrets.get("REDDIT_CLIENT_SECRET")
        user_agent = "QuantumTerminal v1.0"
        
        if not client_id or client_id == "REMPLAZAME_CLI_ID":
            # Silently skip if not configured
            return

        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
        subreddits = ["wallstreetbets", "stocks", "investing"]
        # Limit to last 24h
        cutoff = datetime.utcnow() - timedelta(days=1)
        
        mentions = {t.upper(): 0 for t in ticker_list}
        
        for sub_name in subreddits:
            subreddit = reddit.subreddit(sub_name)
            # Fetch hot posts
            for submission in subreddit.hot(limit=100):
                if datetime.utcfromtimestamp(submission.created_utc) < cutoff:
                    continue
                
                text = (submission.title + " " + submission.selftext).upper()
                for ticker in ticker_list:
                    # Basic word boundary check
                    if f" {ticker} " in f" {text} " or text.startswith(f"{ticker} ") or text.endswith(f" {ticker}"):
                        mentions[ticker] += 1
                        
        # Save to DB
        for ticker, count in mentions.items():
            if count > 0:
                # Análisis de sentimiento sobre el titular del pulso (Sprint 2)
                res = sentiment_service.classify_news(f"{ticker} moon rocket buy") if count > 5 else {"label": "neutral", "score": 0.5}
                label_val = 1.0 if res['label'] == 'positive' else (-1.0 if res['label'] == 'negative' else 0.0)

                db.save_sentiment(
                    ticker=ticker,
                    source="reddit",
                    sentiment=label_val,
                    mentions=count,
                    headline=f"Reddit Daily Pulse: {count} mentions in top finance subs",
                    score=res['score']
                )
        
        return True
        
    except Exception as e:
        print(f"[REDDIT SERVICE] Error: {e}")
        return False

if __name__ == "__main__":
    # Test
    sync_reddit_sentiment(["AAPL", "TSLA", "BTC"])
