import streamlit as st
import plotly.graph_objects as go

def inject_custom_css():
    """Inyecta el CSS base para el diseño de tarjetas oscuras y profesional."""
    st.markdown("""
    <style>
    /* Estilo de Tarjetas */
    .stCard {
        background-color: #121212;
        border: 1px solid #2d2d2d;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
        transition: transform 0.2s;
    }
    .stCard:hover {
        border-color: #3b82f6;
    }
    
    /* Títulos y Subtítulos */
    .card-title {
        font-size: 14px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 5px;
    }
    .card-value {
        font-size: 24px;
        font-weight: 700;
        color: white;
    }
    .card-subtitle {
        font-size: 12px;
        color: #64748b;
    }
    
    /* Barra de Salud (1-5) */
    .health-bar-container {
        display: flex;
        gap: 4px;
        margin-top: 10px;
    }
    .health-segment {
        flex: 1;
        height: 8px;
        border-radius: 2px;
        background-color: #1e293b;
    }
    .health-active-1 { background-color: #ef4444; } /* Rojo */
    .health-active-2 { background-color: #f59e0b; } /* Naranja */
    .health-active-3 { background-color: #eab308; } /* Amarillo */
    .health-active-4 { background-color: #84cc16; } /* Verde Lima */
    .health-active-5 { background-color: #10b981; } /* Verde */
    
    /* Grid Layout */
    .dashboard-grid {
        display: grid;
        grid-template-columns: 3fr 2fr;
        gap: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

def render_health_bar(score):
    """
    Dibuja una barra de salud segmentada de 1 a 5.
    Score: int de 1 a 5.
    """
    segments = ""
    for i in range(1, 6):
        active_class = f"health-active-{score}" if i <= score else ""
        segments += f'<div class="health-segment {active_class}"></div>'
    
    st.markdown(f"""
    <div style="margin-top:20px;">
        <div class="card-title">Salud de la empresa</div>
        <div class="health-bar-container">
            {segments}
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:5px; font-size:10px; color:#64748b;">
            <span>DÉBIL</span>
            <span>EXCELENTE</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_range_slider(current, min_val, max_val, label="Rango 52 semanas"):
    """Dibuja un slider de rango visual para precio actual vs histórico."""
    pct = (current - min_val) / (max_val - min_val) if max_val > min_val else 0
    pct = max(0, min(1, pct)) * 100
    
    st.markdown(f"""
    <div style="margin-bottom:15px;">
        <div class="card-title">{label}</div>
        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
            <span style="color:#64748b; font-size:12px;">{min_val:.2f}</span>
            <span style="color:white; font-size:12px; font-weight:700;">{current:.2f}</span>
            <span style="color:#64748b; font-size:12px;">{max_val:.2f}</span>
        </div>
        <div style="height:4px; background:#1e293b; border-radius:2px; position:relative;">
            <div style="position:absolute; left:{pct}%; top:-3px; width:10px; height:10px; background:#3b82f6; border-radius:50%; border:2px solid #121212;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_metric_card(title, value, subtitle="", delta=None):
    """Dibuja una tarjeta de métrica estilo dashboard."""
    delta_html = ""
    if delta:
        color = "#10b981" if delta > 0 else "#ef4444"
        icon = "↑" if delta > 0 else "↓"
        delta_html = f'<span style="color:{color}; font-size:12px; margin-left:5px;">{icon} {abs(delta):.1f}%</span>'
    
    st.markdown(f"""
    <div class="stCard">
        <div class="card-title">{title}</div>
        <div class="card-value">{value}{delta_html}</div>
        <div class="card-subtitle">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def render_sparkline(data, height=30, width=100):
    """Genera un sparkline (mini gráfico) usando Plotly."""
    if not data or len(data) < 2:
        return None
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=data,
        mode='lines',
        line=dict(color='#3b82f6', width=2),
        fill='tozeroy',
        fillcolor='rgba(59, 130, 246, 0.1)'
    ))
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        width=width,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False
    )
    return fig

def render_price_history(df):
    """Dibuja el gráfico de historial de precios principal."""
    if df is None or df.empty:
        st.warning("No hay datos históricos disponibles.")
        return
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['Close'],
        mode='lines',
        line=dict(color='#3b82f6', width=3),
        fill='tozeroy',
        fillcolor='rgba(59, 130, 246, 0.05)'
    ))
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=280,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, color='#3e5068', tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor='#1e293b', color='#3e5068', tickfont=dict(size=10), side="right"),
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

