"""
finterm/charts/portfolio.py
Portfolio analysis: Efficient frontier, allocation, and performance.
"""
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import pandas as pd
from .base import COLORS, apply_theme

def create_efficient_frontier_chart(results, max_sharpe=None, min_vol=None, current=None):
    """
    Plots the efficient frontier based on Monte Carlo simulations.
    
    Args:
        results: Array with [Volatility, Return, Sharpe]
        max_sharpe: List/Tuple [Vol, Ret] for the max sharpe portfolio.
        min_vol: List/Tuple [Vol, Ret] for the min vol portfolio.
    """
    fig = go.Figure()
    
    # Random Portfolios
    fig.add_trace(go.Scatter(
        x=results[:, 0] * 100,
        y=results[:, 1] * 100,
        mode='markers',
        marker=dict(
            color=results[:, 2],
            colorscale='Viridis',
            size=4,
            opacity=0.5,
            showscale=True,
            colorbar=dict(title="Sharpe Ratio", title_font_color="white", tickfont_color="white")
        ),
        name="Portafolios Simulados",
        hovertemplate="Volatilidad: %{x:.2f}%<br>Retorno: %{y:.2f}%<extra></extra>"
    ))
    
    # Key Points
    if max_sharpe:
        fig.add_trace(go.Scatter(
            x=[max_sharpe[0] * 100], y=[max_sharpe[1] * 100],
            mode='markers', name='Max Sharpe',
            marker=dict(color=COLORS["bull"], size=15, symbol='star', line=dict(color='white', width=1))
        ))
    
    if min_vol:
        fig.add_trace(go.Scatter(
            x=[min_vol[0] * 100], y=[min_vol[1] * 100],
            mode='markers', name='Min Volatilidad',
            marker=dict(color=COLORS["accent"], size=15, symbol='diamond', line=dict(color='white', width=1))
        ))

    fig.update_layout(
        title="Frontera Eficiente (Markowitz)",
        xaxis_title="Volatilidad Anualizada (%)",
        yaxis_title="Retorno Esperado (%)",
        height=600,
        legend=dict(x=0, y=1, bgcolor="rgba(0,0,0,0.5)")
    )
    
    return apply_theme(fig)

def create_allocation_donut(weights_dict):
    """Donut chart for portfolio weights."""
    fig = go.Figure(go.Pie(
        labels=list(weights_dict.keys()),
        values=list(weights_dict.values()),
        hole=.5,
        textinfo='label+percent',
        marker=dict(colors=px.colors.qualitative.Pastel)
    ))
    
    fig.update_layout(
        title="Distribución de Activos",
        showlegend=False,
        height=400,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return apply_theme(fig)

def create_correlation_heatmap(corr_matrix):
    """Heatmap for asset correlations."""
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.index,
        colorscale='RdBu',
        zmin=-1, zmax=1,
        text=corr_matrix.values,
        texttemplate="%{text:.2f}",
        showscale=True
    ))
    
    fig.update_layout(
        title="Matriz de Correlación",
        height=500,
        xaxis_showgrid=False,
        yaxis_showgrid=False
    )
    
    return apply_theme(fig)

def create_drawdown_chart(df_returns):
    """Area chart for historical drawdowns."""
    # Logic to calculate drawdown
    cum_ret = (1 + df_returns).cumprod()
    running_max = cum_ret.cummax()
    drawdown = (cum_ret / running_max) - 1
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=drawdown.index,
        y=drawdown * 100,
        fill='tozeroy',
        mode='lines',
        line=dict(color=COLORS["bear"], width=1.5),
        fillcolor='rgba(255, 77, 109, 0.1)',
        name="Drawdown"
    ))
    
    fig.update_layout(
        title="Drawdown Histórico (%)",
        yaxis_title="Pérdida desde el Máximo (%)",
        height=350
    )
    
    return apply_theme(fig)
