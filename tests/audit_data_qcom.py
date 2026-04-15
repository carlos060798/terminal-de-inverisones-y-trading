
import sys
import json
import os
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock

# 1. Mock Streamlit to avoid issues running as standalone script
mock_st = MagicMock()
mock_st.cache_data = lambda **kwargs: (lambda f: f)
sys.modules["streamlit"] = mock_st

# 2. Import the services to audit
# We add the root directory to sys.path to ensure imports work
sys.path.append(os.getcwd())

import sec_api
import cache_utils

def safe_json_dump(data, filename):
    """Saves data to JSON, handling non-serializable objects like DataFrames/Timestamps."""
    def df_to_dict(obj):
        if isinstance(obj, pd.DataFrame):
            # Stringify columns and index to avoid Timestamp keys
            obj_clean = obj.copy()
            obj_clean.columns = [str(c) for c in obj_clean.columns]
            obj_clean.index = [str(i) for i in obj_clean.index]
            return obj_clean.to_dict(orient='index')
        if isinstance(obj, pd.Series):
            obj_clean = obj.copy()
            obj_clean.index = [str(i) for i in obj_clean.index]
            return obj_clean.to_dict()
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(filename, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4, default=df_to_dict)

def audit_qcom():
    ticker = "QCOM"
    print(f"--- Iniciando Auditoría de Datos para {ticker} ---", flush=True)
    
    output_dir = "artifacts/data_audit_qcom"
    os.makedirs(output_dir, exist_ok=True)
    
    audit_results = {
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "sec": {},
        "yfinance": {}
    }

    # === SEC DATA AUDIT ===
    print("Capturando datos de la SEC Submissions...", flush=True)
    try:
        cik = sec_api.ticker_to_cik(ticker)
        audit_results["sec"]["cik"] = cik
        
        # Submissions
        subs = sec_api.get_company_submissions(ticker)
        audit_results["sec"]["submissions_summary"] = {
            "name": subs.get("name") if subs else None,
            "filings_count": len(subs.get("recent_filings", [])) if subs else 0
        }
        if subs:
            print(f"Guardando raw submissions para {ticker}...", flush=True)
            safe_json_dump(subs, f"{output_dir}/sec_submissions_raw.json")
            
        # Company Facts
        print("Capturando datos de la SEC Company Facts (puede tardar unos segundos)...", flush=True)
        facts = sec_api.get_company_facts(ticker)
        if facts:
            print(f"Guardando {len(facts.get('facts', {}).get('us-gaap', {}))} conceptos GAAP para {ticker}...", flush=True)
            safe_json_dump(facts, f"{output_dir}/sec_facts_raw.json")
            
        # Specific Concept: Net Income
        print("Capturando serie temporal de NetIncomeLoss de la SEC...", flush=True)
        ni_series = sec_api.get_concept_timeseries(ticker, "NetIncomeLoss")
        if ni_series is not None:
            audit_results["sec"]["net_income_series_head"] = ni_series.head(5).to_dict(orient='records')
            safe_json_dump(ni_series, f"{output_dir}/sec_net_income_series.json")
            
        # High Level Financials
        print("Procesando estados financieros consolidados desde SEC...", flush=True)
        sec_financials = sec_api.get_financials_from_sec(ticker)
        audit_results["sec"]["processed_financials"] = sec_financials
        safe_json_dump(sec_financials, f"{output_dir}/sec_processed_financials.json")

    except Exception as e:
        print(f"Error en auditoría SEC: {e}", flush=True)
        audit_results["sec"]["error"] = str(e)

    # === YFINANCE DATA AUDIT ===
    print("Capturando datos de yfinance Info...", flush=True)
    try:
        # Info
        info = cache_utils.get_ticker_info(ticker)
        audit_results["yfinance"]["info_keys"] = list(info.keys()) if info else []
        safe_json_dump(info, f"{output_dir}/yf_info_raw.json")
        
        # Financials
        print("Capturando estados financieros de yfinance...", flush=True)
        yf_financials = cache_utils.get_financials(ticker)
        audit_results["yfinance"]["financials_status"] = {
            "income": not yf_financials['income'].empty,
            "balance": not yf_financials['balance'].empty,
            "cashflow": not yf_financials['cashflow'].empty
        }
        safe_json_dump(yf_financials, f"{output_dir}/yf_financials_raw.json")
        
        # History
        print("Capturando historial de precios (1mo) de yfinance...", flush=True)
        hist = cache_utils.get_history(ticker, period="1mo")
        audit_results["yfinance"]["history_summary"] = {
            "rows": len(hist),
            "last_close": float(hist['Close'].iloc[-1]) if not hist.empty else None
        }
        safe_json_dump(hist, f"{output_dir}/yf_history_raw.json")

    except Exception as e:
        print(f"Error en auditoría yfinance: {e}", flush=True)
        audit_results["yfinance"]["error"] = str(e)

    # Save summary report
    safe_json_dump(audit_results, f"{output_dir}/audit_summary.json")
    print(f"--- Auditoría completada. Reporte guardado en {output_dir}/audit_summary.json ---", flush=True)

if __name__ == "__main__":
    audit_qcom()
