"""
finterm/charts/sentiment.py
Sentiment visualization: News timelines and distribution.
"""
import plotly.graph_objects as go
from .base import COLORS, apply_theme

def create_sentiment_timeline(df_news, df_price=None):
    """
    Creates a timeline of news sentiment.
    If df_price is provided, it can overlay sentiment on top of price.
    """
    if df_news.empty:
        return None
        
    fig = go.Figure()
    
    # Sort by date
    df_news = df_news.sort_values('date')
    
    colors = [COLORS["bull"] if s > 0 else (COLORS["bear"] if s < 0 else COLORS["neutral"]) 
              for s in df_news['sentiment_score']]
              
    fig.add_trace(go.Bar(
        x=df_news['date'],
        y=df_news['sentiment_score'],
        marker_color=colors,
        text=df_news['title'],
        hovertemplate="<b>%{x}</b><br>Score: %{y:.2f}<br>%{text}<extra></extra>",
        name="Sentimiento Noticias"
    ))
    
    fig.update_layout(
        title="Impacto de Sentimiento en el Tiempo",
        yaxis_title="Score (-1 a +1)",
        height=350,
        yaxis=dict(range=[-1.1, 1.1])
    )
    
    return apply_theme(fig)

def create_sentiment_donut(pos, neu, neg):
    """Creates a donut chart for sentiment distribution."""
    fig = go.Figure(go.Pie(
        labels=['Positivo', 'Neutral', 'Negativo'],
        values=[pos, neu, neg],
        hole=.6,
        marker=dict(colors=[COLORS["bull"], COLORS["neutral"], COLORS["bear"]]),
        textinfo='percent',
        textfont=dict(size=12, color="white")
    ))
    
    # Add central indicator
    avg_score = (pos - neg) / (pos + neu + neg) if (pos + neu + neg) > 0 else 0
    label = "BULLISH" if avg_score > 0.2 else ("BEARISH" if avg_score < -0.2 else "NEUTRAL")
    
    fig.update_layout(
        title="Distribución de Sentimiento",
        annotations=[dict(text=label, x=0.5, y=0.5, font_size=18, showarrow=False, font_color="white")],
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5),
        height=350,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    
    return apply_theme(fig)

def create_sentiment_gauge(score):
    """Simple gauge for average sentiment score (-1 to 1)."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Sentimiento IA (FinBERT)", 'font': {'size': 16}},
        gauge={
            'axis': {'range': [-1, 1], 'tickwidth': 1},
            'bar': {'color': COLORS["accent"]},
            'bgcolor': "rgba(0,0,0,0)",
            'steps': [
                {'range': [-1, -0.3], 'color': "rgba(255, 77, 109, 0.2)"},
                {'range': [-0.3, 0.3], 'color': "rgba(251, 191, 36, 0.1)"},
                {'range': [0.3, 1], 'color': "rgba(0, 212, 170, 0.2)"}
            ],
            'threshold': {'line': {'color': "white", 'width': 2}, 'value': score}
        }
    ))
    
    fig.update_layout(height=250, margin=dict(t=50, b=20))
    return apply_theme(fig)
