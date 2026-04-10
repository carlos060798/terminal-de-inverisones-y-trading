"""
finterm/charts/fundamental.py
Financial metric visualizations: Income Statement, Balance Sheet, Ratios.
"""
import plotly.graph_objects as go
from .base import COLORS, apply_theme

def create_revenue_earnings_chart(df_hist):
    """
    Creates a dual-bar chart for Revenue and Net Income over the years.
    
    Args:
        df_hist: DataFrame with columns ['Year', 'Revenue', 'Net Income']
    """
    if df_hist.empty:
        return None
        
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df_hist["Year"],
        y=df_hist["Revenue"],
        name="Ingresos (Revenue)",
        marker_color=COLORS["accent"],
        text=[f"${v/1e9:.1f}B" if v >= 1e9 else f"${v/1e6:.1f}M" for v in df_hist["Revenue"]],
        textposition='outside',
        textfont=dict(color=COLORS["text_sec"])
    ))
    
    fig.add_trace(go.Bar(
        x=df_hist["Year"],
        y=df_hist["Net Income"],
        name="Beneficio Neto (Net Income)",
        marker_color=COLORS["bull"],
        text=[f"${v/1e9:.1f}B" if v >= 1e9 else f"${v/1e6:.1f}M" for v in df_hist["Net Income"]],
        textposition='outside',
        textfont=dict(color=COLORS["text_sec"])
    ))
    
    fig.update_layout(
        title="Trayectoria Financiera (Anual)",
        barmode='group',
        height=450,
        yaxis_title="Dólares ($)",
        legend=dict(x=0.5, y=-0.15, xanchor="center", orientation="h")
    )
    
    return apply_theme(fig)

def create_ratio_heatmap(df_ratios):
    """
    Creates a heatmap comparison of financial ratios.
    
    Args:
        df_ratios: DataFrame where index is metrics and columns are tickers.
    """
    if df_ratios.empty:
        return None
        
    fig = go.Figure(data=go.Heatmap(
        z=df_ratios.values,
        x=df_ratios.columns,
        y=df_ratios.index,
        colorscale='Viridis',
        text=df_ratios.values,
        texttemplate="%{text:.2f}",
        showscale=False
    ))
    
    fig.update_layout(
        title="Mapa de Ratios Comparativos",
        height=min(800, 30 * len(df_ratios.index) + 150),
        xaxis_title="Tickers / Peers",
        yaxis_title="Métrica"
    )
    
    return apply_theme(fig)

def create_margin_evolution(df_margins):
    """
    Evolution of margins (Gross, Operating, Net) over time.
    """
    if df_margins.empty:
        return None
        
    fig = go.Figure()
    
    metrics = ["Gross Margin", "Operating Margin", "Net Margin"]
    colors = [COLORS["accent"], COLORS["purple"], COLORS["bull"]]
    
    for i, m in enumerate(metrics):
        if m in df_margins.columns:
            fig.add_trace(go.Scatter(
                x=df_margins.index,
                y=df_margins[m] * 100,
                name=m,
                line=dict(color=colors[i], width=2),
                mode='lines+markers'
            ))
            
    fig.update_layout(
        title="Evolución de Márgenes (%)",
        yaxis_title="Porcentaje (%)",
        height=400
    )
    
    return apply_theme(fig)
