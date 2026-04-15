import sys

path = r"d:\dasboard\sections\screener.py"
with open(path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1
for i, l in enumerate(lines):
    if "# [STOCK CARDS UI REDESIGN]" in l:
        start_idx = i
    if "if len(df_show) > top_n_cards:" in l and start_idx != -1:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    new_code = """        # [STOCK CARDS UI REDESIGN]
        st.markdown("<div class='sec-title'>📊 Oportunidades de Alta Convicción</div>", unsafe_allow_html=True)
        
        top_n_cards = 15
        df_cards = df_show.head(top_n_cards)

        # Sector Icons Mapping
        SECTOR_ICONS = {
            "Technology": "💻", "Healthcare": "🏥", "Financial Services": "🏦", "Energy": "⚡",
            "Consumer Cyclical": "🛍️", "Consumer Defensive": "🛡️", "Industrials": "🏗️",
            "Basic Materials": "💎", "Communication Services": "📡", "Real Estate": "🏢", 
            "Utilities": "💧"
        }

        cols_per_row = 3
        for i in range(0, len(df_cards), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(df_cards):
                    row = df_cards.iloc[i + j]
                    
                    t_tick = row["Ticker"]
                    t_name = row["Empresa"]
                    t_sector = row.get("Sector", "N/A")
                    icon = SECTOR_ICONS.get(t_sector, "📈")
                    
                    t_pe = row.get("P/E", "--")
                    t_pe_str = f"{t_pe:.1f}x" if pd.notna(t_pe) else "--"
                    
                    t_roe = row.get("ROE %", "--")
                    t_roe_str = f"{t_roe:.1f}%" if pd.notna(t_roe) else "--"
                    
                    t_quant = row.get("Quant", 50)
                    q_color = "#34d399" if pd.notna(t_quant) and t_quant > 70 else ("#fbbf24" if pd.notna(t_quant) and t_quant >= 40 else "#f87171")
                    
                    # Badges
                    badges = []
                    if pd.notna(row.get("Div %")) and row["Div %"] > 2.5: 
                        badges.append("<span style='background:rgba(16,185,129,0.1);color:#10b981;padding:2px 6px;border-radius:4px;font-size:9px;margin-right:4px;'>DIV %</span>")
                    if pd.notna(row.get("PEG")) and row["PEG"] > 0 and row["PEG"] < 1.0:
                        badges.append("<span style='background:rgba(96,165,250,0.1);color:#60a5fa;padding:2px 6px;border-radius:4px;font-size:9px;margin-right:4px;'>VALUE</span>")
                    
                    with col:
                        # Institutional Card
                        st.markdown(f\"\"\"
                        <div style='background: rgba(30, 41, 59, 0.4); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin-bottom: 20px;' class='high-conviction-card'>
                            <div style='display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:15px;'>
                                <div>
                                    <div style='display:flex; align-items:center; gap:8px;'>
                                        <span style='font-size:24px; font-weight:900; color:#60a5fa;'>{t_tick}</span>
                                        <span style='font-size:16px;'>{icon}</span>
                                    </div>
                                    <div style='font-size:11px; color:#94a3b8; margin-top:2px;'>{t_name}</div>
                                </div>
                                <div style='text-align:right;'>
                                    <div style='font-size:18px; font-weight:800; color:{q_color};'>{int(t_quant) if pd.notna(t_quant) else 50}%</div>
                                    <div style='font-size:8px; color:#64748b; text-transform:uppercase;'>Score de Calidad</div>
                                </div>
                            </div>
                            
                            <div style='display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom:15px;'>
                                <div>
                                    <div style='font-size:9px; color:#64748b; text-transform:uppercase;'>Precio</div>
                                    <div style='font-size:14px; font-weight:700;'>${row.get("Precio", 0):.2f}</div>
                                </div>
                                <div>
                                    <div style='font-size:9px; color:#64748b; text-transform:uppercase;'>P/E Ratio</div>
                                    <div style='font-size:14px; font-weight:700; color:#f0f6fc;'>{t_pe_str}</div>
                                </div>
                                <div>
                                    <div style='font-size:9px; color:#64748b; text-transform:uppercase;'>ROE</div>
                                    <div style='font-size:14px; font-weight:700; color:#10b981;'>{t_roe_str}</div>
                                </div>
                                <div>
                                    <div style='font-size:9px; color:#64748b; text-transform:uppercase;'>Sesgo Sector</div>
                                    <div style='font-size:10px; color:#94a3b8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{t_sector}</div>
                                </div>
                            </div>
                            
                            <div style='margin-bottom:15px;'>{"".join(badges)}</div>
                        </div>
                        \"\"\", unsafe_allow_html=True)
                        
                        # Sparkline Trend
                        s_data = row.get("Sparkline", [])
                        if s_data:
                            fig_spark = vc.render_sparkline(s_data)
                            if fig_spark:
                                st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})
                        
                        # Buttons
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("➕ Watch", key=f"add_{t_tick}", use_container_width=True):
                                db.add_ticker(t_tick, 0, row.get("Precio", 0), t_sector, "Screener Card")
                                st.success("OK")
                        with btn_col2:
                            if st.button("🔎 Analizar", key=f"analyze_{t_tick}", type="primary", use_container_width=True):
                                st.session_state["active_ticker"] = t_tick
                                st.toast(f"Analizando {t_tick}...")

"""
    lines[start_idx:end_idx] = [new_code]
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("PATCHED SCREENER")
else:
    print(f"NOT FOUND IN SCREENER, start:{start_idx}, end:{end_idx}")

# CSS PATCH
css_path = r"d:\dasboard\assets\styles.css"
bloom_css = """
/* ══════════════════════════════════════════════════════════════
   BLOOMBERG TERMINAL AESTHETIC (Quantum AI)
   ══════════════════════════════════════════════════════════════ */
.terminal-container {
    background-color: #000000 !important;
    border: 2px solid #333333 !important;
    border-radius: 8px !important;
    padding: 24px;
    font-family: 'Courier New', Courier, monospace !important;
    color: #00ff00 !important;
    box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.05), 0 10px 30px rgba(0, 0, 0, 0.5);
    margin-bottom: 24px;
}

.terminal-msg-user { 
    color: #ffffff !important; 
    border-left: 3px solid #60a5fa !important; 
    padding-left: 15px; 
    margin-bottom: 20px; 
    font-family: 'Inter', sans-serif !important;
}

.terminal-msg-ai { 
    color: #00ff00 !important; 
    border-left: 3px solid #00ff00 !important; 
    padding-left: 15px; 
    margin-bottom: 30px; 
    font-family: 'Courier New', Courier, monospace !important;
    text-shadow: 0 0 5px rgba(0, 255, 0, 0.2);
}

.terminal-model-tag { 
    font-size: 10px; 
    color: #444444; 
    text-transform: uppercase; 
    margin-top: 8px; 
    letter-spacing: 1px;
}

/* ══════════════════════════════════════════════════════════════
   CHART TOOLTIPS & HOVERS
   ══════════════════════════════════════════════════════════════ */
.js-plotly-plot .plotly .cursor-crosshair {
    cursor: crosshair !important;
}

/* ANIMATED GRADIENT BORDERS FOR HIGH CONVICTION */
@keyframes borderGlow {
    0% { border-color: rgba(59, 130, 246, 0.1); }
    50% { border-color: rgba(59, 130, 246, 0.8); }
    100% { border-color: rgba(59, 130, 246, 0.1); }
}

.high-conviction-card {
    animation: borderGlow 3s infinite ease-in-out;
}
"""
with open(css_path, "a", encoding="utf-8") as f:
    f.write(bloom_css)
print("PATCHED CSS")
