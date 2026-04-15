import pandas as pd
import numpy as np
import yfinance as yf
from services.fred_service import FREDUltraService
import database as db

class MacroStressEngine:
    def __init__(self):
        self.fred = FREDUltraService()

    def get_ticker_macro_correlation(self, ticker: str, series_id: str, days=365):
        """Calcula la correlación histórica (Pearson) entre un Ticker y una serie FRED."""
        if not ticker or not isinstance(ticker, str) or ticker.strip() == "":
            return 0
        # 1. Obtener precio del Ticker
        try:
            tk_hist = yf.Ticker(ticker).history(period=f"{days}d")["Close"]
        except Exception:
            return 0
        
        # 2. Obtener serie FRED
        fred_hist = self.fred.get_series_ultra(series_id, days=days)
        if fred_hist.empty: return 0
        
        # 3. Alineación de datos
        fred_hist.set_index("date", inplace=True)
        fred_hist.index = pd.to_datetime(fred_hist.index).tz_localize(None)
        tk_hist.index = tk_hist.index.tz_localize(None)
        
        combined = pd.concat([tk_hist, fred_hist["value"]], axis=1).dropna()
        combined.columns = ["ticker", "macro"]
        
        if combined.empty: return 0
        
        correlation = combined["ticker"].corr(combined["macro"])
        return correlation

    def run_portfolio_stress_test(self, portfolio_df: pd.DataFrame):
        """
        Analiza el riesgo de la cartera ante shocks macro.
        portfolio_df debe tener columnas ['ticker', 'shares', 'avg_cost']
        """
        results = {
            "scenarios": {},
            "top_sensitivities": []
        }
        
        # Series clave para el Stress Test
        macro_shocks = {
            "DGS10": {"name": "Salto en Tasas (10Y)", "description": "Si el Tesoro 10Y sube +100bps"},
            "CPIAUCSL": {"name": "Shock de Inflación", "description": "Si el CPI sube por encima del target"},
            "UNRATE": {"name": "Recesión (Sahm Rule)", "description": "Si el desempleo activa la señal de recesión"},
            "M2SL": {"name": "Ajuste de Liquidez", "description": "Si la Fed retira liquidez M2"}
        }
        
        for _, stock in portfolio_df.iterrows():
            ticker = stock['ticker']
            sensitivities = {}
            for series_id, info in macro_shocks.items():
                corr = self.get_ticker_macro_correlation(ticker, series_id)
                sensitivities[info['name']] = corr
            
            results["top_sensitivities"].append({
                "ticker": ticker,
                "data": sensitivities
            })

        # Simulación agregada de impacto
        # (Lógica simplificada: Correlación * Peso en Cartera)
        total_value = (portfolio_df['shares'] * portfolio_df['avg_cost']).sum() # Simplificación
        
        for series_id, info in macro_shocks.items():
            impact_score = 0
            for stock in results["top_sensitivities"]:
                corr = stock["data"][info['name']]
                # Aquí ponderamos (esto es una aproximación visual)
                impact_score += corr * 10 # Multiplicador de estrés
            
            results["scenarios"][info['name']] = {
                "impact_label": "CRÍTICO" if abs(impact_score) > 7 else "RELEVANTE" if abs(impact_score) > 3 else "BAJO",
                "color": "#ef4444" if impact_score < -3 else "#10b981" if impact_score > 3 else "#94a3b8"
            }
            
        return results
