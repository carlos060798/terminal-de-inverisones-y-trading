import pandas as pd
from datetime import datetime, timedelta
import os
import streamlit as st
from fredapi import Fred
import database as db

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────
FRED_SERIES_ULTRA = {
    "Interés": {
        "DGS1": "Treasury 1-Year",
        "DGS2": "Treasury 2-Year",
        "DGS5": "Treasury 5-Year",
        "DGS10": "Treasury 10-Year",
        "DGS30": "Treasury 30-Year",
        "DFF": "Federal Funds Effective Rate",
        "T10Y2Y": "10Y-2Y Treasury Yield Spread",
        "T10Y3M": "10Y-3M Treasury Yield Spread",
    },
    "Inflación": {
        "CPIAUCSL": "Consumer Price Index (CPI)",
        "CPILFESL": "Core CPI",
        "PCEPI": "PCE Price Index",
        "PCEPILFE": "Core PCE",
        "T10YIE": "10-Year Breakeven Inflation Rate",
    },
    "Empleo": {
        "UNRATE": "Unemployment Rate",
        "PAYEMS": "Nonfarm Payrolls",
        "CIVPART": "Labor Force Participation Rate",
        "ICSA": "Initial Claims",
        "CCSA": "Continued Claims",
    },
    "Crecimiento": {
        "GDP": "Gross Domestic Product",
        "GDPC1": "Real GDP",
        "A191RL1Q225SBEA": "Real GDP Growth Rate",
        "INDPRO": "Industrial Production Index",
    },
    "Liquidez": {
        "M1SL": "M1 Money Stock",
        "M2SL": "M2 Money Stock",
        "WALCL": "Fed Total Assets",
        "TOTRESNS": "Total Reserves of Depository Institutions",
    },
    "Riesgo/Crédito": {
        "BAMLH0A0HYM2": "ICE BofA US High Yield Index Option-Adjusted Spread",
        "BAA10Y": "Moody's Seasoned Baa Corporate Bond Yield Relative to 10Y Treasury",
        "VIXCLS": "CBOE Volatility Index (VIX)",
        "STLFSI4": "St. Louis Fed Financial Stress Index",
    },
    "Vivienda": {
        "HOUST": "Housing Starts",
        "PERMIT": "Building Permits",
        "CSUSHPISA": "S&P/Case-Shiller U.S. National Home Price Index",
    },
    "Sentimiento": {
        "UMCSENT": "University of Michigan: Consumer Sentiment",
        "CSCICP03USM665S": "OECD Consumer Confidence Index for USA",
    }
}

class FREDUltraService:
    def __init__(self):
        self.api_key = st.secrets.get("FRED_API_KEY") or os.environ.get("FRED_API_KEY", "")
        self.fred = Fred(api_key=self.api_key) if self.api_key else None

    def get_series_ultra(self, series_id, days=365):
        """Obtiene una serie de FRED, la cachea en BD y la retorna."""
        if not self.fred:
            return pd.DataFrame()

        # 1. Intentar cargar de la BD primero (si es de hoy)
        # Por ahora descargamos y guardamos siempre para asegurar frescura en esta fase
        try:
            start_date = datetime.now() - timedelta(days=days)
            s = self.fred.get_series(series_id, observation_start=start_date)
            if not s.empty:
                df = s.reset_index()
                df.columns = ["date", "value"]
                # Guardar en BD
                obs_list = [{"date": str(row["date"].date()), "value": float(row["value"])} 
                            for _, row in df.dropna().iterrows()]
                db.save_macro_history(series_id, obs_list)
                return df
        except Exception as e:
            print(f"[FRED ULTRA] Error en {series_id}: {e}")
        
        return pd.DataFrame()

    def get_dashboard_metrics(self):
        """Retorna el estado actual de los indicadores clave."""
        keys = ["DGS10", "UNRATE", "CPIAUCSL", "VIXCLS", "WALCL", "M2SL", "T10Y2Y"]
        results = {}
        for k in keys:
            df = self.get_series_ultra(k, days=60)
            if not df.empty:
                results[k] = {
                    "current": df.iloc[-1]["value"],
                    "previous": df.iloc[-2]["value"] if len(df) > 1 else df.iloc[-1]["value"]
                }
        return results

    def calculate_sahm_rule(self):
        """Calcula la Regla de Sahm (Recesión = Promedio 3m Desempleo - Mínimo 12m > 0.5%)."""
        df = self.get_series_ultra("UNRATE", days=730) # 2 años
        if df.empty: return None
        
        df["ma3"] = df["value"].rolling(window=3).mean()
        current_ma3 = df["ma3"].iloc[-1]
        min_ma3_12m = df["ma3"].tail(12).min()
        sahm_value = current_ma3 - min_ma3_12m
        
        return {
            "value": sahm_value,
            "is_recession": sahm_value >= 0.5,
            "current_unrate": df["value"].iloc[-1]
        }

    def calculate_buffett_indicator(self):
        """Ratio Wilshire 5000 / GDP with improved fallbacks."""
        # GDP is more stable (Quarterly)
        gdp_df = self.get_series_ultra("GDP", days=365)
        
        # Try different Wilshire 5000 variants
        mkt_df = pd.DataFrame()
        for sid in ["WILL5000PR", "WILL5000IN", "WILL5000PRFC"]:
            mkt_df = self.get_series_ultra(sid, days=30)
            if not mkt_df.empty: break
            
        if gdp_df.empty: 
            # Extreme fallback for GDP (approx 28T for US 2024/2025)
            gdp = 28000.0
        else:
            gdp = gdp_df.iloc[-1]["value"]

        if mkt_df.empty:
            # If still empty, use a hardcoded proxy or fetch S&P 500 from yfinance
            try:
                import yfinance as yf
                spy_cap = yf.Ticker("SPY").fast_info.market_cap
                # Wilshire 5000 is approximately US Market Cap. SPY is ~80% of it.
                mkt = (spy_cap / 1e9 * 1.25) if spy_cap else 45000.0
            except:
                mkt = 45000.0 # Generic placeholder for US Market Cap ($45T)
        else:
            mkt = mkt_df.iloc[-1]["value"]
        
        ratio = (mkt / gdp) * 100
        
        # Quantitative Interpretation
        if ratio > 190: status = "MIEDO — SOBREVALORACIÓN EXTREMA"
        elif ratio > 150: status = "SOBREVALORADO"
        elif ratio > 110: status = "VALORACIÓN JUSTA"
        elif ratio > 80: status = "INFRAVALORADO"
        else: status = "GANGAS — NIVEL DE COMPRA HISTÓRICO"
                
        return {
            "ratio": ratio,
            "interpretation": status,
            "mkt_cap": mkt,
            "gdp": gdp
        }

    def get_macro_ticker_correlation(self, ticker: str, series_id: str, days=365):
        """Calcula la correlación entre una serie de FRED y el precio de una acción."""
        import yfinance as yf
        
        # 1. Obtener Macro
        macro_df = self.get_series_ultra(series_id, days=days)
        if macro_df.empty: return None
        
        # 2. Obtener Stock
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{days}d")
        if hist.empty: return None
        
        # 3. Alinear Datos
        macro_df["date"] = pd.to_datetime(macro_df["date"])
        macro_df.set_index("date", inplace=True)
        
        combined = pd.concat([macro_df["value"], hist["Close"]], axis=1).dropna()
        combined.columns = ["macro", "stock"]
        
        if len(combined) < 10: return None
        
        correlation = combined.corr().iloc[0, 1]
        return {
            "correlation": correlation,
            "sample_size": len(combined),
            "interpretation": "Positiva Fuerte" if correlation > 0.7 else "Negativa Fuerte" if correlation < -0.7 else "Baja/Nula"
        }
