import sys
import streamlit as st
import pandas as pd
import numpy as np

# Mock session state for testing
class MockSessionState(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value

st.session_state = MockSessionState()
st.session_state['active_ticker'] = 'QCOM'
st.session_state['notation_mode'] = 'Compacto (M/B)'

import sections.stock_analyzer as sa

def run_tests():
    print("Testing importing modules...")
    import forecast_synthesizer
    import conflict_detector
    import sec_api
    
    print("\nPreparing mock data...")
    res = {
        "verdict": {
            "verdict": "STRONG BUY",
            "color": "#10b981",
            "description": "Test description",
            "valuation": {"current_price": 150.0, "consensus_target": 200.0, "upside_pct": 33.3},
            "quality": {"percentage": 85, "category": "HIGH QUALITY"},
            "risk": "Low"
        },
        "info": {
            "exchange": "NMS", "longName": "Qualcomm Inc", "sector": "Technology", 
            "industry": "Semiconductors", "regularMarketChange": 2.5, "regularMarketChangePercent": 1.5,
            "marketState": "REGULAR"
        },
        "hist": pd.DataFrame({"Close": [140, 145, 150], "Volume": [1000, 1200, 1500]}),
        "forensic": {
            "fcf": {"latest_true_fcf_b": "10.0", "latest_sbc_inflation_pct": 10.0, "signal": "SAFE"},
            "inventory": {"health_score": "HEALTHY", "health_color": "#10b981", "total_b": 5.0},
            "debt": {"refinance_risk": "SAFE", "refinance_color": "#10b981", "net_debt_ebitda": 1.2},
            "allocation": {"waterfall_items": []}
        },
        "conflict": {
            "score": 3, "dominant_view": "Fundamentals Stronger",
            "fundamental_signals": [{"label": "FCF Yield", "value": "Strong"}],
            "technical_signals": [{"label": "RSI", "value": "Oversold"}]
        },
        "forecast": {
            "eps": {"historical": {2023: 5.0}, "forward": {2024: 6.0}},
            "price": {"target_mean": 200, "upside_pct": 33.3, "recommendation": "BUY"},
            "revenue": {"historical": {2023: 35.0}, "fy26_estimate": 40.0}
        },
        "pdf": {
            "swot": {"strengths": ["S1"], "weaknesses": ["W1"], "opportunities": ["O1"], "threats": ["T1"]}
        },
        "health": {
            "z_score": 5.0, "z_label": "SAFE", "f_score": 7, "sloan_ratio": -5.0, "sloan_label": "LIMPIO"
        },
        "income": pd.DataFrame({"Revenue": [100, 200]}),
        "balance": pd.DataFrame({"Assets": [500, 600]}),
        "cashflow": pd.DataFrame({"OCF": [50, 60]}),
        "whales": pd.DataFrame(),
        "sec": {}
    }
    
    print("\nRunning Tab 1: General")
    try:
        sa._render_general_tab(res)
        print("Tab 1 OK")
    except Exception as e:
        print(f"Tab 1 Failed: {e}")
        
    print("\nRunning Tab 2: Deep Fundamental")
    try:
        sa._render_deep_fundamental_tab(res)
        print("Tab 2 OK")
    except Exception as e:
        print(f"Tab 2 Failed: {e}")
        
    print("\nRunning Tab 3: Forecast")
    try:
        sa._render_forecast_tab(res)
        print("Tab 3 OK")
    except Exception as e:
        print(f"Tab 3 Failed: {e}")
        
    print("\nRunning Tab 4: AI Conflict")
    try:
        sa._render_ai_conflict_tab(res)
        print("Tab 4 OK")
    except Exception as e:
        print(f"Tab 4 Failed: {e}")

if __name__ == "__main__":
    run_tests()
