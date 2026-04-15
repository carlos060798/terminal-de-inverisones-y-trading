import os
import streamlit as st
import pandas as pd
from fredapi import Fred

def test_fred():
    key = "4797f6e0145c0ce16d92ed042511da4f"
    try:
        fred = Fred(api_key=key)
        print("FRED Client: OK")
        
        # Test basic series
        s = fred.get_series("GS10", observation_start="2024-01-01")
        if not s.empty:
            print(f"Fetch GS10: OK ({len(s)} points)")
            print(f"Sample data:\n{s.tail()}")
        else:
            print("Fetch GS10: EMPTY")
            
        # Test indicators
        indicators = ["FEDFUNDS", "CPIAUCSL", "UNRATE", "M2SL"]
        for s_id in indicators:
            s_ind = fred.get_series(s_id, observation_start="2024-01-01")
            print(f"Fetch {s_id}: {'OK' if not s_ind.empty else 'EMPTY'}")
            
    except Exception as e:
        print(f"FRED Test FAILED: {e}")

if __name__ == "__main__":
    test_fred()
