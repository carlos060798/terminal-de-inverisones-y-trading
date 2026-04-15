"""
finterm/charts/indicators.py
Technical analysis indicators and synchronized panel charts.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from .base import COLORS, apply_theme

def create_technical_dashboard(df, ticker):
    """
    Creates a full technical dashboard with synchronous panels:
    - Price + MA + Bollinger
    - RSI
    - MACD
    """
    # Check for core columns
    required = ['Open', 'High', 'Low', 'Close']
    if not all(col in df.columns for col in required):
        return None
    
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.5, 0.15, 0.15, 0.2],
        subplot_titles=(f"{ticker} - Precio & Bandas", "RSI (14)", "MACD", "Presión de Volumen (Delta)")
    )


    # ── PANEL 1: PRECIO + MA + BOLLINGER ──
    # Price
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name="Precio", showlegend=False,
        increasing_line_color=COLORS["bull"], decreasing_line_color=COLORS["bear"]
    ), row=1, col=1)

    # MAs
    if 'MA20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="SMA 20", line=dict(color=COLORS["accent"], width=1)), row=1, col=1)
    if 'MA50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], name="SMA 50", line=dict(color=COLORS["neutral"], width=1)), row=1, col=1)

    # Bollinger Bands
    if 'BB_upper' in df.columns and 'BB_lower' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_upper'], name="BB Upper", line=dict(color="rgba(148, 163, 184, 0.3)", width=1, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_lower'], name="BB Lower", line=dict(color="rgba(148, 163, 184, 0.3)", width=1, dash='dot'), fill='tonexty', fillcolor='rgba(148, 163, 184, 0.05)'), row=1, col=1)

    # ── PANEL 2: RSI ──
    if 'RSI' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name="RSI", line=dict(color=COLORS["purple"], width=2)), row=2, col=1)
        # Thresholds
        fig.add_hline(y=70, line_dash="dash", line_color=COLORS["bear"], row=2, col=1, opacity=0.5)
        fig.add_hline(y=30, line_dash="dash", line_color=COLORS["bull"], row=2, col=1, opacity=0.5)
        fig.add_hrect(y0=30, y1=70, fillcolor="rgba(139, 92, 246, 0.05)", line_width=0, row=2, col=1)

    # ── PANEL 3: MACD ──
    if 'MACD' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], name="MACD", line=dict(color=COLORS["accent"], width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], name="Signal", line=dict(color=COLORS["bear"], width=1)), row=3, col=1)
        
        hist_colors = [COLORS["bull"] if h >= 0 else COLORS["bear"] for h in df['Hist'].fillna(0)]
        fig.add_trace(go.Bar(x=df.index, y=df['Hist'], name="Histograma", marker_color=hist_colors), row=3, col=1)

    # ── PANEL 4: VOLUME DELTA ──
    v_colors = [COLORS["bull"] if c >= o else COLORS["bear"] for c, o in zip(df['Close'], df['Open'])]
    v_delta = [v if c >= o else -v for c, o, v in zip(df['Close'], df['Open'], df['Volume'])]
    
    fig.add_trace(go.Bar(
        x=df.index, y=v_delta, 
        name="Delta Vol", 
        marker_color=v_colors,
        opacity=0.8
    ), row=4, col=1)


    # Layout tuning
    fig.update_layout(
        height=800,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    # Hide axis labels for upper charts to avoid clutter
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)
    fig.update_xaxes(showticklabels=False, row=3, col=1)
    
    return apply_theme(fig)


def create_volume_profile(df, n_bins=50):
    """Creates a horizontal volume profile chart (Price vs Volume)."""
    if df.empty:
        return None
        
    # Simplified volume profile logic
    price_min = df['Low'].min()
    price_max = df['High'].max()
    bins = pd.cut(df['Close'], bins=n_bins)
    vprof = df.groupby(bins)['Volume'].sum()
    
    fig = go.Figure(go.Bar(
        x=vprof.values,
        y=[b.mid for b in vprof.index],
        orientation='h',
        marker_color=COLORS["accent"],
        opacity=0.6
    ))
    
    fig.update_layout(
        title="Perfil de Volumen (POC)",
        xaxis_title="Volumen",
        yaxis_title="Precio"
    )
    
    return apply_theme(fig)
