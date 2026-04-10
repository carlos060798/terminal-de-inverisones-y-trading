"""
finterm/charts/macro.py
Macroeconomic data visualization: FRED, Interest rates, Yield curves.
"""
import plotly.graph_objects as go
from .base import COLORS, apply_theme

def create_macro_multi_chart(data, title="Indicadores Macroeconómicos"):
    """
    Plots multiple FRED indicators. Handles samples as dict or DataFrame.
    """
    import pandas as pd
    
    df_fred = None
    if isinstance(data, pd.DataFrame):
        df_fred = data
    elif isinstance(data, dict):
        if data:
            try:
                # Align series by date index
                df_fred = pd.concat(data, axis=1).sort_index()
                # If column names are numbers (from list/dict), they will be the keys
            except Exception as e:
                print(f"[create_macro_multi_chart] Concat error: {e}")
                df_fred = None
    
    if df_fred is None or (isinstance(df_fred, pd.DataFrame) and df_fred.empty):
        return None
        
    fig = go.Figure()
    
    palette = [COLORS["accent"], COLORS["bull"], COLORS["purple"], COLORS["neutral"]]
    
    for i, col in enumerate(df_fred.columns):
        fig.add_trace(go.Scatter(
            x=df_fred.index,
            y=df_fred[col],
            name=col,
            line=dict(color=palette[i % len(palette)], width=2)
        ))
        
    fig.update_layout(
        title=dict(text=title),
        hovermode="x unified",
        height=500,
        legend=dict(orientation="h", x=0.5, y=-0.15, xanchor="center")
    )
    
    return apply_theme(fig)

def create_yield_curve_chart(tenors, yields=None, date_label="Current"):
    """
    Plots the treasury yield curve.
    
    Args:
        tenors: List of strings ['3M', '2Y', '10Y', etc.] OR a dict {tenor: yield}
        yields: List of floats (optional if tenors is a dict)
    """
    if isinstance(tenors, dict) and yields is None:
        data_dict = tenors
        tenors = list(data_dict.keys())
        yields = list(data_dict.values())
    
    if not yields:
        return None
    # Simple line chart for yield curve
    fig = go.Figure()
    
    # Check for inversion (10Y vs 2Y)
    is_inverted = False
    if '2Y' in tenors and '10Y' in tenors:
        idx2 = tenors.index('2Y')
        idx10 = tenors.index('10Y')
        if yields[idx2] > yields[idx10]:
            is_inverted = True

    line_color = COLORS["bear"] if is_inverted else COLORS["bull"]
    
    fig.add_trace(go.Scatter(
        x=tenors,
        y=yields,
        mode='lines+markers',
        name=date_label,
        line=dict(color=line_color, width=3),
        marker=dict(size=10, line=dict(width=2, color="white"))
    ))
    
    fig.update_layout(
        title=f"Curva de Tipos (Treasury Yield Curve) - {date_label}",
        yaxis_title="Rendimiento (%)",
        xaxis_title="Vencimiento",
        height=400
    )
    
    if is_inverted:
        fig.add_annotation(
            text="⚠️ CURVA INVERTIDA",
            xref="paper", yref="paper",
            font=dict(size=14, color=COLORS["bear"]),
            bgcolor="rgba(255, 77, 109, 0.1)",
            bordercolor=COLORS["bear"],
            borderwidth=1, padding=10
        )
        
    return apply_theme(fig)

def create_historical_chart(series, title="Historical Data", color=None):
    """
    Plots a simple historical line chart for any pandas Series.
    """
    if series is None or series.empty:
        return None
        
    fig = go.Figure()
    line_color = color if color else COLORS["accent"]
    
    fig.add_trace(go.Scatter(
        x=series.index,
        y=series.values,
        mode='lines',
        name=title,
        line=dict(color=line_color, width=2),
        fill='tozeroy',
        fillcolor=f"rgba({int(line_color[1:3],16) if line_color.startswith('#') else 59}, {int(line_color[3:5],16) if line_color.startswith('#') else 130}, {int(line_color[5:7],16) if line_color.startswith('#') else 246}, 0.1)"
    ))
    
    fig.update_layout(
        title=dict(text=title),
        hovermode="x unified",
        height=350,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    
    return apply_theme(fig)
