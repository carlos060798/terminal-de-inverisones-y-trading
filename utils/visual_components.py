import streamlit as st
import plotly.graph_objects as go

def inject_custom_css():
    """Vaciado: Los estilos se cargan ahora desde assets/styles.css para mayor performance."""
    pass

def render_health_bar(score, title="Salud de la empresa"):
    """Dibuja una barra de salud segmentada de 1 a 5."""
    segments = ""
    for i in range(1, 6):
        active_class = f"health-active-{score}" if i <= score else ""
        segments += f'<div class="health-segment {active_class}"></div>'
    
    st.markdown(f"""
    <div style="margin-top:20px;">
        <div class="kpi-label">{title}</div>
        <div class="health-bar-container">
            {segments}
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:5px; font-size:10px; color:#5a6f8a;">
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
        <div class="kpi-label">{label}</div>
        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
            <span style="color:#5a6f8a; font-size:12px;">{min_val:,.2f}</span>
            <span style="color:#ffffff; font-size:12px; font-weight:700;">{current:,.2f}</span>
            <span style="color:#5a6f8a; font-size:12px;">{max_val:,.2f}</span>
        </div>
        <div style="height:4px; background:rgba(255,255,255,0.05); border-radius:2px; position:relative;">
            <div style="position:absolute; left:{pct}%; top:-3px; width:10px; height:10px; background:#3b82f6; border-radius:50%; border:2px solid #0f172a;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_metric_card(title, value, subtitle="", delta=None):
    """Dibuja una tarjeta de métrica estilo dashboard institucional."""
    delta_html = ""
    if delta is not None:
        color = "#10b981" if delta > 0 else "#ef4444"
        icon = "↑" if delta > 0 else "↓"
        delta_html = f'<span style="color:{color}; font-size:12px; margin-left:8px; font-weight:600;">{icon} {abs(delta):.1f}%</span>'
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="mc-label">{title}</div>
        <div class="mc-value">{value}{delta_html}</div>
        <div class="mc-bench" style="color:#5a6f8a;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def render_signal_badge(level, label=None):
    """
    Dibuja un badge de señal técnica (Compra/Venta/Mantener).
    level: float/int de -5 (Extrema Venta) a 5 (Extrema Compra).
    """
    if label is None:
        if level > 2: label = "Compra Fuerte"
        elif level > 0.5: label = "Compra"
        elif level < -2: label = "Venta Fuerte"
        elif level < -0.5: label = "Venta"
        else: label = "Mantener"
    
    css_class = "signal-hold"
    if level > 0.5: css_class = "signal-buy"
    elif level < -0.5: css_class = "signal-sell"
    
    st.markdown(f'<div class="signal-badge {css_class}">{label}</div>', unsafe_allow_html=True)

def render_insight_box(text, type="info"):
    """Dibuja una caja de insight/nota contextual."""
    if type == "info":
        st.info(text)
    elif type == "success":
        st.success(text)
    elif type == "warning":
        st.warning(text)
    else:
        st.error(text)

def render_chart_container(fig, height=300):
    """Envuelve un gráfico Plotly en un contenedor con el estilo corporativo."""
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="#f1f5f9", family="Inter"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=height
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def render_sparkline(data, height=30, width=100, color='#3b82f6'):
    """Genera un sparkline (mini gráfico) usando Plotly."""
    if not data or len(data) < 2:
        return None
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=data,
        mode='lines',
        line=dict(color=color, width=2),
        fill='tozeroy',
        fillcolor=f'rgba{tuple(list(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.1])}'
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
        xaxis=dict(showgrid=False, color='#5a6f8a', tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#5a6f8a', tickfont=dict(size=10), side="right"),
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
