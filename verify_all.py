import sys
import os
try:
    import pandas
    import streamlit
    import plotly
    import yfinance
    import numpy
    print("Dependencies: OK")
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

try:
    import sec_api
    print("sec_api: OK")
    import valuation_v2
    print("valuation_v2: OK")
    # Simulation of a simple call
    # res = valuation_v2.compute_quality_score("AAPL")
    # print(f"Sample Quality Score: {res['percentage']}%")
except Exception as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

print("All systems GO.")
