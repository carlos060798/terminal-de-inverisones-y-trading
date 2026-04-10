import feedparser
import pandas as pd
import streamlit as st
from datetime import datetime

def get_recent_sec_filings(form_type="4", limit=10):
    """
    Fetches the most recent SEC filings for a specific form type globally.
    form_type="4" is for Insiders.
    form_type="8-K" is for material events.
    """
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type={form_type}&owner=include&output=atom"
    
    # Needs identification
    headers = {"User-Agent": "QuantumTerminal research@quantum.com"}
    
    try:
        import requests
        resp = requests.get(url, headers=headers, timeout=10)
        feed = feedparser.parse(resp.text)
        
        entries = []
        for entry in feed.entries[:limit]:
            # Parsing "AAPL - Apple Inc. (0000320193) (Issuer)"
            title = entry.title
            parts = title.split(" - ")
            ticker = parts[0] if len(parts) > 0 else "N/A"
            
            entries.append({
                "ticker": ticker,
                "title": title,
                "link": entry.link,
                "updated": entry.updated,
                "summary": entry.summary
            })
            
        return pd.DataFrame(entries)
    except Exception as e:
        print(f"Error fetching global SEC feed: {e}")
        return pd.DataFrame()

def get_recent_congress_trades(limit=5):
    """
    Mock/Placeholder for aggregator of recent congress trades.
    In production, this would scrape the latest from CapitolTrades.
    """
    return pd.DataFrame([
        {"date": "2026-04-09", "member": "Nancy Pelosi", "ticker": "NVDA", "type": "Purchase", "amount": "$500k - $1M"},
        {"date": "2026-04-08", "member": "Tommy Tuberville", "ticker": "TXN", "type": "Sale", "amount": "$15k - $50k"},
        {"date": "2026-04-07", "member": "Josh Gottheimer", "ticker": "MSFT", "type": "Purchase", "amount": "$1k - $15k"},
    ]).head(limit)
