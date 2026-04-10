"""
finterm/charts/price.py
Price and volume visualization modules.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from .base import COLORS, apply_theme

def create_candlestick_chart(df, ticker, title="Análisis de Precio"):
    """
    Creates a professional Candlestick chart with Volume panel.
    
    Args:
        df: DataFrame with OHLCV data.
        ticker: String ticker symbol.
        title: Chart title.
    """
    if df.empty:
        return None
        
    # Create subplots: Price (row 1), Volume (row 2)
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.05, 
        row_heights=[0.8, 0.2]
    )

    # 1. Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name=ticker,
        increasing_line_color=COLORS["bull"],
        decreasing_line_color=COLORS["bear"]
    ), row=1, col=1)

    # 2. Volume
    colors = [COLORS["bull"] if row['Close'] >= row['Open'] else COLORS["bear"] 
              for _, row in df.iterrows()]
    
    fig.add_trace(go.Bar(
        x=df.index, 
        y=df['Volume'],
        name="Volumen",
        marker_color=colors,
        opacity=0.8
    ), row=2, col=1)

    # Layout updates
    fig.update_layout(
        title=dict(
            text=f"<b>{ticker}</b> — {title}",
            font=dict(size=20, color="white")
        ),
        xaxis_rangeslider_visible=False,
        height=700,
        showlegend=False
    )
    
    # Range Selectors
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=3, label="3M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all", label="MAX")
            ]),
            bgcolor=COLORS["bg_panel"],
            activecolor=COLORS["accent"],
            font=dict(size=10, color=COLORS["text_sec"])
        ),
        row=2, col=1
    )

    return apply_theme(fig)

def create_area_chart(df, ticker, title="Evolución de Precio"):
    """Creates a sleek area chart with gradient-like fill."""
    if df.empty:
        return None
        
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['Close'],
        fill='tozeroy',
        mode='lines',
        line=dict(color=COLORS["bull"], width=2),
        fillcolor='rgba(0, 212, 170, 0.1)', # Bull color with transparency
        name=ticker
    ))
    
    fig.update_layout(
        title=dict(text=f"<b>{ticker}</b> — {title}"),
        height=400
    )
    
    return apply_theme(fig)

def create_comparison_chart(dfs, tickers, title="Comparación de Rendimiento (Base 100)"):
    """
    Creates a multi-line comparison chart normalized to base 100.
    
    Args:
        dfs: List of DataFrames with 'Close' column.
        tickers: List of ticker strings.
    """
    fig = go.Figure()
    
    palette = [COLORS["accent"], COLORS["bull"], COLORS["purple"], COLORS["neutral"], 
               COLORS["bear"], "#ec4899", "#06b6d4", "#f97316"]
    
    for i, (df, tk) in enumerate(zip(dfs, tickers)):
        if df.empty: continue
        
        # Normalize
        norm_series = (df['Close'] / df['Close'].iloc[0]) * 100
        
        fig.add_trace(go.Scatter(
            x=df.index,
            y=norm_series,
            name=tk,
            line=dict(color=palette[i % len(palette)], width=2.5)
        ))
        
    fig.update_layout(
        title=dict(text=title),
        yaxis_title="Rendimiento Relativo (Base 100)",
        hovermode="x unified",
        height=500
    )
    
    return apply_theme(fig)
def create_historical_chart(series, title="Evolución Histórica", color=None):
    """
    Generic line chart for a time series.
    """
    if series is None or series.empty:
        return None
        
    line_color = color if color else COLORS["accent"]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series.index,
        y=series.values,
        mode='lines',
        line=dict(color=line_color, width=2),
        name=title
    ))
    
    fig.update_layout(
        title=dict(text=title),
        height=400
    )
    
    return apply_theme(fig)
