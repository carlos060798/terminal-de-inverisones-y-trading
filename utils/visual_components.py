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

def render_financial_statement_table(df):
    """
    Renderiza una tabla de estados de resultados premium estilo InvestingPro.
    Incluye: Nombre métrica, Mini-Trend, y 5 años de historial.
    """
    import pandas as pd
    from ui_shared import fmt
    import base64
    from io import BytesIO

    if df is None or df.empty:
        st.warning("No hay datos históricos para generar el estado financiero.")
        return

    # Preparar métricas a mostrar
    metrics = [
        ("Ingresos", "Revenue", "$"),
        ("Cr. ingresos (YoY %)", "RevGrowth", "%"),
        ("Coste de los ingresos", "COGS", "$"),
        ("Utilidad bruta", "Gross Profit", "$"),
        ("Margen bruto (%)", "GrossMarginPct", "%"),
        ("Ingresos de explotación", "Operating Income", "$"),
        ("Beneficio neto", "Net Income", "$"),
        ("Margen neto (%)", "NetMarginPct", "%"),
    ]

    # Cálculo de métricas adicionales para la tabla
    df = df.copy()
    if "Revenue" in df.columns:
        # Calcular crecimiento YoY (asumiendo que viene ordenado por año desc en sec_api, pero reversed(years) lo usará asc)
        df = df.sort_values("Year")
        df["RevGrowth"] = df["Revenue"].pct_change() * 100
        df["GrossMarginPct"] = (df["Gross Profit"] / df["Revenue"]) * 100 if "Gross Profit" in df.columns else None
        df["NetMarginPct"] = (df["Net Income"] / df["Revenue"]) * 100 if "Net Income" in df.columns else None

    # Años disponibles (columnas)
    years = sorted([c for c in df["Year"].unique()], reverse=True)[:5]
    
    # CSS para la tabla premium
    st.markdown("""
    <style>
    .fin-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Inter', sans-serif;
        color: #f1f5f9;
        margin-bottom: 30px;
    }
    .fin-table th {
        text-align: right;
        padding: 12px 8px;
        border-bottom: 2px solid #1e293b;
        color: #94a3b8;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .fin-table th:first-child { text-align: left; }
    .fin-table td {
        padding: 12px 8px;
        border-bottom: 1px solid #0f172a;
        font-size: 14px;
        text-align: right;
    }
    .fin-table td:first-child {
        text-align: left;
        font-weight: 500;
        color: #cbd5e1;
    }
    .fin-table tr:hover { background: rgba(255,255,255,0.02); }
    .metric-name { display: flex; align-items: center; gap: 8px; }
    .spark-col { width: 50px; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

    header_html = "<tr><th>Métrica</th><th class='spark-col'></th>"
    for yr in years:
        header_html += f"<th>{yr}</th>"
    header_html += "</tr>"

    rows_html = ""
    for label, col, pref in metrics:
        if col not in df.columns: continue
        
        # Obtener valores históricos para esta métrica
        vals = []
        for yr in reversed(years): # De viejo a nuevo para el sparkline
            v = df[df["Year"] == yr][col].values
            vals.append(v[0] if len(v) > 0 else 0)
        
        # Generar Sparkline base64
        spark_img = ""
        fig_spark = render_sparkline(vals, height=20, width=60, color='#3b82f6')
        if fig_spark:
            buf = BytesIO()
            fig_spark.write_image(buf, format="png", scale=2)
            spark_img = f'<img src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}" width="50">'
        
        row = f"<tr><td><div class='metric-name'>{label}</div></td><td class='spark-col'>{spark_img}</td>"
        for yr in years:
            v = df[df["Year"] == yr][col].values
            val = v[0] if len(v) > 0 else None
            row += f"<td>{fmt(val, pref)}</td>"
        row += "</tr>"
        rows_html += row

    st.markdown(f"<table class='fin-table'>{header_html}{rows_html}</table>", unsafe_allow_html=True)

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
