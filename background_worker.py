"""Background Worker — System service for unattended data harvesting."""
import time
import schedule
import database as db
from services import bulk_ingestion

def job_hourly_sync():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Hourly Sync Job...")
    try:
        # Get active tickers from watchlist to prioritize they
        wl = db.get_watchlist()
        tickers = wl["ticker"].tolist() if not wl.empty else ["AAPL", "TSLA", "MSFT", "NVDA", "BTC"]
        
        # Limit to top 10 tickers to avoid rate limits in background
        summary = bulk_ingestion.run_bulk_sync(tickers[:10])
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sync Complete. Results: {summary}")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sync Job Failed: {e}")

def main():
    print("🚀 Quantum Background Worker Started...")
    
    # Run once at start
    job_hourly_sync()
    
    # Schedule hourly
    schedule.every(1).hours.do(job_hourly_sync)
    
    # Run every 6 hours for Reddit (more expensive)
    # schedule.every(6).hours.do(...) 

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
