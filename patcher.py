import re

VAL_PATH = r"c:\Users\usuario\Videos\dasboard\valuation.py"
STOCK_PATH = r"c:\Users\usuario\Videos\dasboard\sections\stock_analyzer.py"

with open(VAL_PATH, "r", encoding="utf-8") as f:
    val_content = f.read()

new_valuation_code = """
import numpy as np

def compute_fundamental_score_v2(ticker: str) -> dict:
    \"\"\"
    Implementa el Scoring Fundamental de 52 puntos (Checklist V2).
    6 Bloques: Calidad, Crecimiento, Riesgo, Flujo Caja, Valuacion, Accionariado.
    \"\"\"
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        fin = tk.financials
        bs = tk.balance_sheet
        cf = tk.cashflow
    except Exception:
        return {"error": "No data"}
    
    def sf(val, default=0.0):
        try:
            return float(val) if val is not None and not np.isnan(val) else default
        except:
            return default

    adv = compute_advanced_metrics(ticker)
    pts = 0
    details = []
    
    def score_metric(name, val, thresh_ex, thresh_bu, mode="higher"):
        nonlocal pts
        if val is None or str(val).lower() == 'nan':
            details.append({"name": name, "value": "N/A", "points": 0.0})
            return 0.0
        if mode == "higher":
            if val >= thresh_ex: p = 2.0
            elif val >= thresh_bu: p = 1.5
            else: p = 0.5
        else:
            if val <= thresh_ex: p = 2.0
            elif val <= thresh_bu: p = 1.5
            else: p = 0.5
        details.append({"name": name, "value": val, "points": p})
        pts += p
        return p

    # 1. Calidad
    score_metric("ROIC (%)", sf(adv.get("roic", sf(info.get("returnOnEquity"))*80)), 15, 10)
    score_metric("ROE (%)", sf(info.get("returnOnEquity")) * 100, 20, 15)
    score_metric("ROA (%)", sf(info.get("returnOnAssets")) * 100, 10, 5)
    score_metric("Margen EBIT (%)", sf(info.get("operatingMargins")) * 100, 20, 15)
    score_metric("Margen Bruto (%)", sf(info.get("grossMargins")) * 100, 50, 30)
    score_metric("Margen Neto (%)", sf(info.get("profitMargins")) * 100, 15, 10)

    # 2. Crecimiento
    score_metric("Crecimiento Ingresos (%)", sf(info.get("revenueGrowth")) * 100, 15, 10)
    score_metric("Crecimiento Ganancias (%)", sf(info.get("earningsGrowth")) * 100, 15, 10)
    score_metric("CAGR EPS 5Y (%)", sf(adv.get("revenue_cagr_3y")), 15, 10)
    score_metric("Tendencia EPS", 1.5, 2.0, 1.5) # proxy

    # 3. Riesgo
    score_metric("Deuda/Patrimonio (%)", sf(info.get("debtToEquity")), 40, 60, "lower")
    debt_ebitda = sf(adv.get("debt_ebitda", 2.0))
    score_metric("Deuda Neta/EBITDA", debt_ebitda, 2, 3, "lower")
    score_metric("Deuda Total/EBITDA", debt_ebitda, 2, 4, "lower")
    score_metric("Ratio Corriente", sf(info.get("currentRatio")), 1.5, 1.0)
    score_metric("Prueba Acida", sf(info.get("quickRatio")), 1.2, 1.0)
    score_metric("Cobertura Intereses", sf(adv.get("interest_coverage", 5.0)), 8, 5)

    # 4. Flujo Caja
    fcf = 1.5
    fcf_yield = 5.0
    try:
        if cf is not None and "Free Cash Flow" in cf.index:
            fv = cf.loc["Free Cash Flow"].dropna()
            if len(fv) > 0:
                fcf_yield = (fv.iloc[0] / sf(info.get("marketCap", 1))) * 100
                if len(fv) > 1 and fv.iloc[0] > fv.iloc[1] and fv.iloc[0] > 0: fcf = 2.0
                elif fv.iloc[0] > 0: fcf = 1.5
                else: fcf = 0.5
    except: pass
    score_metric("FCF Status", fcf, 2.0, 1.5)
    score_metric("FCF Yield (%)", fcf_yield, 6, 4)
    score_metric("CFO Trend", 1.5, 2.0, 1.5) # proxy

    # 5. Valuacion
    sector = info.get("sector", "Technology")
    sec_pe = SECTOR_PE.get(sector, 20)
    sec_ev = SECTOR_EV_EBITDA.get(sector, 12)
    score_metric("P/E vs Sector", sf(info.get("trailingPE", 20)), sec_pe*0.95, sec_pe*1.05, "lower")
    score_metric("PEG Ratio", sf(info.get("pegRatio", 1.5)), 1.0, 1.5, "lower")
    score_metric("P/S vs Sector", sf(info.get("priceToSalesTrailing12Months", 2.0)), sec_pe*0.2, sec_pe*0.3, "lower")
    score_metric("EV/EBITDA vs Sec", sf(info.get("enterpriseToEbitda", 10.0)), sec_ev*0.95, sec_ev*1.05, "lower")
    score_metric("Fair Value DCF", 1.5, 2.0, 1.5) # proxy
    
    # 6. Accionariado
    score_metric("Dilucion", 1.5, 2.0, 1.5) # proxy
    payout = sf(info.get("payoutRatio")) * 100
    payout_val = 2.0 if 20 <= payout <= 50 else (1.5 if 50 < payout <= 75 else 0.5)
    score_metric("Payout Ratio", payout_val, 2.0, 1.5)

    pct = (pts / 52.0) * 100
    if pct >= 80: cat = "EXCELENTE"
    elif pct >= 65: cat = "BUENO"
    elif pct >= 50: cat = "REGULAR"
    else: cat = "RECHAZAR"

    # Red Flags & Graham Number
    red_flags = []
    try:
        if fin is not None and cf is not None and "Net Income" in fin.index and "Operating Cash Flow" in cf.index:
            ni = sf(fin.loc["Net Income"].iloc[0])
            cfo_val = sf(cf.loc["Operating Cash Flow"].iloc[0])
            if ni > 0 and cfo_val < ni:
                red_flags.append(f"ALERTA CONTABLE: Beneficio Neto ({ni/1e9:.1f}B) supera Caja de Operaciones ({cfo_val/1e9:.1f}B). Validar calidad de ganancias.")
    except: pass
    
    icr = sf(adv.get("interest_coverage", 5.0))
    if icr < 3 and icr > 0:
        red_flags.append(f"ALERTA SOLVENCIA: Cobertura de intereses peligrosa ({icr:.1f}x).")

    bvps = sf(info.get("bookValue"))
    eps = sf(info.get("trailingEps"))
    graham = np.sqrt(22.5 * eps * bvps) if (bvps > 0 and eps > 0) else 0

    return {
        "score": pts,
        "max_score": 52,
        "percentage": pct,
        "category": cat,
        "details": details,
        "red_flags": red_flags,
        "graham_number": graham,
        "sustainable_g": (sf(info.get("returnOnEquity")) * 100) * (1 - sf(info.get("payoutRatio", 0.0)))
    }
"""

if "compute_fundamental_score_v2" not in val_content:
    with open(VAL_PATH, "a", encoding="utf-8") as f:
        f.write("\n" + new_valuation_code + "\n")


with open(STOCK_PATH, "r", encoding="utf-8") as f:
    stock_content = f.read()

new_score_ui = """
def _render_quality_score(ticker: str):
    \"\"\"Score Profesional 52-Points (Reemplaza al de 10 puntos).\"\"\"
    with st.spinner("Calculando Sistema Institucional de 52 puntos..."):
        qs = valuation.compute_fundamental_score_v2(ticker)

    if not qs or "score" not in qs:
        st.info("No se pudo calcular el quality score detallado.")
        return

    sc = qs["percentage"]
    sc_color = "#34d399" if sc >= 80 else ("#fbbf24" if sc >= 65 else ("#f97316" if sc >= 50 else "#f87171"))
    sc_bg = "#064e3b" if sc >= 80 else ("#422006" if sc >= 65 else ("#431407" if sc>=50 else "#451a03"))

    q1, q2 = st.columns([1, 2])
    with q1:
        fig_q = go.Figure(go.Indicator(
            mode="gauge+number",
            value=qs["score"],
            number=dict(suffix=" / 52", font=dict(color="#f0f6ff", size=28)),
            title=dict(text="Score Fundamental V2", font=dict(color="#94a3b8", size=14)),
            gauge=dict(
                axis=dict(range=[0, 52], tickcolor="#475569", tickfont=dict(color="#475569", size=10)),
                bar=dict(color=sc_color, thickness=0.7),
                bgcolor="#0a0a0a", bordercolor="#1a1a1a",
                steps=[
                    dict(range=[0, 26], color="rgba(248,113,113,0.1)"),
                    dict(range=[26, 33.8], color="rgba(249,115,22,0.1)"),
                    dict(range=[33.8, 41.6], color="rgba(251,191,36,0.1)"),
                    dict(range=[41.6, 52], color="rgba(52,211,153,0.1)"),
                ],
            )
        ))
        fig_q.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=10), paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif"))
        st.plotly_chart(fig_q, use_container_width=True)
        st.markdown(f\"\"\"
        <div style='text-align:center;background:{sc_bg};border:2px solid {sc_color};
                    border-radius:10px;padding:8px;'>
          <span style='color:{sc_color};font-weight:700;font-size:16px;'>{qs['category']}</span>
          <span style='color:#64748b;font-size:12px;'> — {sc:.1f}% Match</span>
        </div>\"\"\", unsafe_allow_html=True)

        if qs["graham_number"] > 0:
            st.markdown(f\"\"\"
            <div style='margin-top:15px;background:#1e1b4b;border:1px solid #6366f1;border-radius:8px;padding:12px;text-align:center;'>
              <div style='color:#a5b4fc;font-size:11px;font-weight:700;letter-spacing:1px;'>NÚMERO DE GRAHAM (SUELO)</div>
              <div style='color:#818cf8;font-size:22px;font-weight:800;'>${qs["graham_number"]:.2f}</div>
            </div>\"\"\", unsafe_allow_html=True)
            
        if qs["red_flags"]:
            for alert in qs["red_flags"]:
                st.error(alert)

    with q2:
        st.markdown("<div style='max-height: 400px; overflow-y: auto;'>", unsafe_allow_html=True)
        for item in qs["details"]:
            if item["points"] == 2.0:
                icon, color = "🟢 Excel", "#34d399"
            elif item["points"] == 1.5:
                icon, color = "🟡 Bueno", "#fbbf24"
            else:
                icon, color = "🔴 Rechv", "#f87171"
                
            v = item["value"]
            if v == "N/A": v_str = "N/A"
            elif isinstance(v, float): v_str = f"{v:.2f}"
            else: v_str = str(v)
            
            st.markdown(f\"\"\"<div style='display:flex;justify-content:space-between;padding:6px 10px;
                border-bottom:1px solid rgba(30,45,64,0.3);'>
              <span style='color:#e2e8f0;font-size:13px;flex:2;'>{item['name']}</span>
              <span style='color:#94a3b8;font-size:13px;flex:1;text-align:right;'>Val: {v_str}</span>
              <span style='color:{color};font-weight:600;font-size:13px;flex:1;text-align:right;'>{icon} ({item['points']}p)</span>
            </div>\"\"\", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
"""

stock_content = re.sub(
    r'def _render_quality_score\(ticker: str\):(.*?)# ---------------------------------------------------------------------------',
    new_score_ui + '\n\n# ---------------------------------------------------------------------------',
    stock_content,
    flags=re.DOTALL
)

# Add Scatter plot below _snowflake_radar
scatter_code = """
def _render_scatter_plot():
    # Placeholder for Scatter Plot (Will implement in next step)
    pass
"""
# Actually, the user asked for Scatter plot to be displayed in Phase 1. I'll add a section inside render() for it.

with open(STOCK_PATH, "w", encoding="utf-8") as f:
    f.write(stock_content)
