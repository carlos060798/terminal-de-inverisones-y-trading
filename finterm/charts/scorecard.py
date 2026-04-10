"""
finterm/charts/scorecard.py
Unified scoring visualization: Gauges and Radar charts.
"""
import plotly.graph_objects as go
from .base import COLORS, apply_theme

def create_score_gauge(score, label="FINTERM SCORE", target=None):
    """
    Creates a semi-circular gauge for the total score.
    
    Args:
        score: Float 0-100.
        label: Text label for the center.
        target: Optional target score (e.g. consensus).
    """
    # Color logic for the bar
    if score >= 75: bar_color = COLORS["bull"]
    elif score >= 50: bar_color = COLORS["accent"]
    elif score >= 30: bar_color = COLORS["neutral"]
    else: bar_color = COLORS["bear"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta" if target else "gauge+number",
        value=score,
        title={'text': label, 'font': {'size': 20, 'color': "white"}},
        delta={'reference': target} if target else None,
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': COLORS["text_sec"]},
            'bar': {'color': bar_color, 'thickness': 0.25},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': COLORS["grid"],
            'steps': [
                {'range': [0, 30], 'color': 'rgba(255, 77, 109, 0.1)'},
                {'range': [30, 70], 'color': 'rgba(251, 191, 36, 0.05)'},
                {'range': [70, 100], 'color': 'rgba(0, 212, 170, 0.1)'}
            ],
            'threshold': {
                'line': {'color': COLORS["accent"], 'width': 4},
                'thickness': 0.8,
                'value': target if target else score
            }
        }
    ))

    fig.update_layout(
        height=350,
        margin=dict(l=30, r=30, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)"
    )
    
    return apply_theme(fig)

def create_component_radar(breakdown, ticker="Ticker"):
    """
    Creates a radar/spider chart for the score breakdown components.
    
    Args:
        breakdown: Dict with keys ['Fundamental', 'Technical', 'Sentiment', 'Risk', 'Institutional']
        ticker: String ticker symbol.
    """
    categories = list(breakdown.keys())
    values = list(breakdown.values())
    
    # Close the circle
    categories.append(categories[0])
    values.append(values[0])
    
    fig = go.Figure()

    # Benchmark (Central Neutral Zone)
    fig.add_trace(go.Scatterpolar(
        r=[50] * len(categories),
        theta=categories,
        fill=None,
        line=dict(color=COLORS["grid"], width=1, dash='dot'),
        name='Neutral (50)'
    ))

    # Ticker Profile
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name=ticker,
        fillcolor='rgba(59, 130, 246, 0.3)',
        line=dict(color=COLORS["accent"], width=2)
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor=COLORS["grid"],
                tickfont=dict(size=9, color=COLORS["text_sec"]),
                angle=90
            ),
            angularaxis=dict(
                gridcolor=COLORS["grid"],
                tickfont=dict(size=11, color="white")
            ),
            bgcolor=COLORS["bg_main"]
        ),
        showlegend=True,
        legend=dict(x=0.5, y=-0.2),
        margin=dict(l=50, r=50, t=50, b=50),
        height=400,
        paper_bgcolor="rgba(0,0,0,0)"
    )

    return apply_theme(fig)

def create_component_bars(breakdown):
    """Creates a horizontal bar chart for components."""
    categories = list(breakdown.keys())
    values = list(breakdown.values())
    
    colors = [COLORS["bull"] if v >= 70 else (COLORS["accent"] if v >= 40 else COLORS["bear"]) 
              for v in values]
              
    fig = go.Figure(go.Bar(
        x=values,
        y=categories,
        orientation='h',
        marker_color=colors,
        text=[f"{v:.0f}" for v in values],
        textposition='auto',
    ))
    
    fig.update_layout(
        xaxis=dict(range=[0, 100], title="Puntaje (0-100)"),
        height=300,
        margin=dict(l=10, r=10, t=30, b=30)
    )
    
    return apply_theme(fig)
