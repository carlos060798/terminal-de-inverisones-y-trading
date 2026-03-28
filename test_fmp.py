import toml
import os
import sys

# Load secrets to environment
secrets = toml.load(".streamlit/secrets.toml")
os.environ["FMP_API_KEY"] = secrets.get("FMP_API_KEY", "")

# Add current dir to path
sys.path.append(os.getcwd())

from adapters.execution_engine import ExecutionEngine

def test_fmp():
    print("--- Probando Diagnóstico FMP (Stable & v4) ---")
    import requests
    api_key = os.getenv("FMP_API_KEY")
    
    urls = [
        f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={api_key}",
        f"https://financialmodelingprep.com/api/v4/key-metrics-ttm?symbol=AAPL&apikey={api_key}",
        f"https://financialmodelingprep.com/v3/stable/key-metrics?symbol=AAPL&apikey={api_key}"
    ]
    
    for url in urls:
        print(f"\nTrying: {url.split('?')[0]}")
        resp = requests.get(url)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text[:200]}...")

if __name__ == "__main__":
    test_fmp()
