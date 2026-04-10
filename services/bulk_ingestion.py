"""Bulk Ingestion Service — Coordinates multiple data sources with parallel execution."""
import concurrent.futures
import time
from services.data_ingestion import tiingo_service, reddit_service, crypto_service, finnhub_service

def run_bulk_sync(tickers: list[str], include_reddit=True, include_crypto=True):
    """
    Run ingestion for a list of tickers across all active services in parallel.
    """
    start_time = time.time()
    results = {"tiingo": 0, "reddit": 0, "crypto": False, "errors": []}
    
    # We use ThreadPoolExecutor for I/O bound tasks (API calls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # 1. Tiingo News (Parallel per ticker)
        future_to_ticker = {executor.submit(tiingo_service.sync_tiingo_news, t): t for t in tickers}
        
        # 2. Reddit Pulse (Single call for all tickers usually preferred by PRAW)
        if include_reddit:
            reddit_future = executor.submit(reddit_service.sync_reddit_sentiment, tickers)
        
        # 3. Crypto Global (Single call)
        if include_crypto:
            crypto_future = executor.submit(crypto_service.sync_crypto_metrics)

        # Wait for Tiingo results
        for future in concurrent.futures.as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                if future.result():
                    results["tiingo"] += 1
            except Exception as e:
                results["errors"].append(f"Tiingo {ticker}: {str(e)}")

        # Wait for others
        if include_reddit:
            try:
                if reddit_future.result():
                    results["reddit"] = len(tickers)
            except Exception as e:
                results["errors"].append(f"Reddit: {str(e)}")

        if include_crypto:
            try:
                results["crypto"] = crypto_future.result()
            except Exception as e:
                results["errors"].append(f"Crypto: {str(e)}")

    results["duration"] = round(time.time() - start_time, 2)
    return results

if __name__ == "__main__":
    # Test run
    test_tickers = ["AAPL", "TSLA", "BTC", "NVDA"]
    print(f"Starting bulk sync for {test_tickers}...")
    summary = run_bulk_sync(test_tickers)
    print(f"Sync complete: {summary}")
