import re

STOCK_PATH = r"c:\Users\usuario\Videos\dasboard\sections\stock_analyzer.py"

with open(STOCK_PATH, "r", encoding="utf-8") as f:
    content = f.read()

scatter_func = """
# ---------------------------------------------------------------------------
# Moat Radar Chart (Echarts)
# ---------------------------------------------------------------------------
def _render_moat_radar():
    options = {
        "tooltip": {},
        "radar": {
            "indicator": [
                {"name": "Activos Intangibles (Marca/Patentes)", "max": 5},
                {"name": "Costes de Cambio (Switching)", "max": 5},
                {"name": "Efecto Red", "max": 5},
                {"name": "Ventaja en Costes", "max": 5}
            ],
            "splitNumber": 5,
            "axisName": {"color": "#94a3b8", "fontSize": 12},
            "splitLine": {"lineStyle": {"color": "rgba(255, 255, 255, 0.1)"}},
            "splitArea": {"show": False},
        },
        "series": [{
            "type": "radar",
            "data": [{
                "value": [4, 3, 5, 2],  # Ejemplo placeholder
                "name": "Fosos Defensivos",
                "itemStyle": {"color": "#a78bfa"},
                "areaStyle": {"color": "rgba(167,139,250,0.4)"},
                "lineStyle": {"color": "#a78bfa", "width": 2}
            }]
        }],
        "backgroundColor": "transparent"
    }
    if HAS_ECHARTS:
        st_echarts(options=options, height="350px")
    else:
        st.info("Instala streamlit-echarts para ver el radar.")

# ---------------------------------------------------------------------------
# Interactive Scatter Plot (Risk/Reward)
# ---------------------------------------------------------------------------
def _render_scatter_plot(main_ticker: str):
    with st.spinner("Calculando cuadrante de oportunidades (Score vs Valuation)..."):
        # Get sector peers
        try:
            tk = yf.Ticker(main_ticker)
            sector = tk.info.get("sector", "")
            peers = SECTOR_PEERS.get(sector, [])
            if main_ticker not in peers:
                peers = [main_ticker.upper()] + peers[:4]
            else:
                peers = peers[:5]
        except:
            peers = [main_ticker.upper(), "AAPL", "MSFT"]
        
        data = []
        for p in set(peers):
            try:
                # Get Score
                qs = valuation.compute_fundamental_score_v2(p)
                score_pct = qs.get("percentage", 0)
                
                # Get FV upside (Margin of Safety)
                dcf = valuation.compute_dcf_scenarios(p)
                curr_price = dcf.get("current_price", 1)
                fv = dcf.get("base", {}).get("fair_value", 0)
                mos = ((fv - curr_price) / fv * 100) if fv > 0 and curr_price else 0
                
                if score_pct > 0:
                    data.append({
                        "Ticker": p,
                        "Score": score_pct,
                        "MOS": mos,
                        "Color": "#34d399" if p == main_ticker.upper() else "#60a5fa"
                    })
            except: pass
            
        if len(data) < 2:
            st.info("No hay suficientes datos comparativos para graficar.")
            return
            
        df = pd.DataFrame(data)
        
        fig = go.Figure()
        
        # Add quadrants
        fig.add_hline(y=50, line_dash="dash", line_color="rgba(255,255,255,0.2)")
        fig.add_vline(x=0, line_dash="dash", line_color="rgba(255,255,255,0.2)")
        
        # Quadrant labels
        fig.add_annotation(x=max(df['MOS'].max(), 20), y=max(df['Score'].max(), 80), text="<b>COMPRA IDEAL</b>", 
                          showarrow=False, font=dict(color="#34d399", size=14), opacity=0.3)
        fig.add_annotation(x=min(df['MOS'].min(), -20), y=max(df['Score'].max(), 80), text="<b>BUENA PERO CARA</b>", 
                          showarrow=False, font=dict(color="#fbbf24", size=14), opacity=0.3)
                          
        fig.add_trace(go.Scatter(
            x=df['MOS'], y=df['Score'],
            mode='markers+text',
            text=df['Ticker'],
            textposition="top center",
            textfont=dict(color="#f0f6ff", size=11),
            marker=dict(size=14, color=df['Color'], line=dict(width=2, color="#0a0a0a")),
            hovertemplate="<b>%{text}</b><br>Score: %{y:.1f}%<br>Margen de Seguridad: %{x:.1f}%<extra></extra>"
        ))
        
        fig.update_layout(
            height=450, margin=dict(l=40, r=40, t=50, b=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif"),
            title=dict(text="Mapa de Oportunidades: Score (Calidad) vs Margen de Seguridad", font=dict(color="#94a3b8", size=14)),
            xaxis=dict(title="Margen de Seguridad (%) →", gridcolor="rgba(255,255,255,0.05)", zeroline=False),
            yaxis=dict(title="Score Fundamental (0-100) ↑", gridcolor="rgba(255,255,255,0.05)", zeroline=False),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
"""

render_calls = """
                # ── SCATTER PLOT OPPORTUNITIES ──
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    with st.expander("📍 Mapa de Oportunidades: Calidad vs Riesgo"):
                        try:
                            _render_scatter_plot(ticker_name)
                        except Exception as e:
                            st.warning(f"Error calculando cuadrantes: {e}")

                # ── MOAT RADAR ──
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    with st.expander("🏰 Fosos Defensivos (Moat Radar)"):
                        _render_moat_radar()
"""

# Insert _render_scatter_plot and _render_moat_radar right before render()
content = content.replace("def render():\n", scatter_func + "\n\ndef render():\n")

# Insert the expander calls right below the quality score expander
pattern = r'(# ── BUFFETT/DORSEY CHECKLIST ──\s*if ticker_name.+?st\.warning\(f"Error calculando quality score: \{e\}"\))'
content = re.sub(pattern, r'\1\n' + render_calls, content, flags=re.DOTALL)


with open(STOCK_PATH, "w", encoding="utf-8") as f:
    f.write(content)
