import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

class OptionsEngine:
    @staticmethod
    def get_options_data(ticker: str):
        """Obtiene la cadena de opciones completa."""
        tk = yf.Ticker(ticker)
        try:
            expirations = tk.options
            if not expirations:
                return None
            # Tomamos la expiración más cercana por ahora (mayor volumen/gamma)
            near_term = expirations[0]
            chain = tk.option_chain(near_term)
            return {
                "expiration": near_term,
                "calls": chain.calls,
                "puts": chain.puts
            }
        except:
            return None

    @staticmethod
    def calculate_gamma_exposure(calls: pd.DataFrame, puts: pd.DataFrame):
        """Simulación simplificada de exposición Gamma (GEX) e identificación de Muros."""
        # En una terminal real usaríamos Black-Scholes para la Gamma exacta.
        # Aquí usaremos Open Interest (OI) como proxy de 'Muro' de liquidez.
        
        call_walls = calls.sort_values("openInterest", ascending=False).head(5)
        put_walls = puts.sort_values("openInterest", ascending=False).head(5)
        
        total_call_oi = calls["openInterest"].sum()
        total_put_oi = puts["openInterest"].sum()
        pc_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 0
        
        return {
            "call_walls": call_walls[["strike", "openInterest", "lastPrice"]].to_dict("records"),
            "put_walls": put_walls[["strike", "openInterest", "lastPrice"]].to_dict("records"),
            "pc_ratio": pc_ratio,
            "sentiment": "Bullish" if pc_ratio < 0.7 else "Bearish" if pc_ratio > 1.1 else "Neutral"
        }

    @staticmethod
    def calculate_max_pain(calls: pd.DataFrame, puts: pd.DataFrame):
        """Calcula el precio de 'Max Pain' (donde más opciones expiran sin valor)."""
        strikes = sorted(set(calls["strike"]) | set(puts["strike"]))
        losses = []
        for s in strikes:
            # Loss for call writers
            call_loss = calls[calls["strike"] < s]
            c_loss = ((s - call_loss["strike"]) * call_loss["openInterest"]).sum()
            
            # Loss for put writers
            put_loss = puts[puts["strike"] > s]
            p_loss = ((put_loss["strike"] - s) * put_loss["openInterest"]).sum()
            
            losses.append(c_loss + p_loss)
            
        max_pain = strikes[np.argmin(losses)]
        return max_pain

    @staticmethod
    def plot_gamma_walls(ticker: str, calls: pd.DataFrame, puts: pd.DataFrame):
        """Gráfico institucional de Muros de Liquidez (Gamma Walls)."""
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=calls["strike"], y=calls["openInterest"],
            name="Calls OI", marker_color="#10b981", opacity=0.7
        ))
        
        fig.add_trace(go.Bar(
            x=puts["strike"], y=-puts["openInterest"],
            name="Puts OI", marker_color="#ef4444", opacity=0.7
        ))
        
        fig.update_layout(
            title=f"Cadena de Opciones: Muros de Liquidez para {ticker}",
            xaxis_title="Strike Price ($)",
            yaxis_title="Open Interest (Contratos)",
            barmode='relative',
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        return fig
