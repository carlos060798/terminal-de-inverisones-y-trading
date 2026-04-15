import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import datetime
from ui_shared import DARK, dark_layout, fmt, kpi
from utils.trading_plan_utils import load_md, save_entry_to_db, get_recent_entries

# Path to markdown files provided by user
MD_PATH = Path("d:/usuario/descargas/")
MATRIZ_MD = MD_PATH / "01_MATRIZ_PLAN_TRADING.md"
SEGUIMIENTO_MD = MD_PATH / "02_PLANIFICACION_SEGUIMIENTO.md"
DOMINICAL_MD = MD_PATH / "03_INSTRUCTIVO_ANALISIS_DOMINICAL.md"

def render():
    # ── Premium CSS for Trading Plan ──
    st.markdown("""
    <style>
    .tp-card {
        background: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
    }
    .check-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        background: rgba(16, 185, 129, 0.05);
        border-radius: 10px;
        margin-bottom: 8px;
        border: 1px solid rgba(16, 185, 129, 0.1);
    }
    .check-icon { color: #10b981; font-weight: 800; }
    .check-text { font-size: 14px; color: #e2e8f0; }
    
    .matrix-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 15px;
    }
    .matrix-table th {
        text-align: left;
        padding: 12px;
        background: rgba(255, 255, 255, 0.03);
        color: #94a3b8;
        font-size: 11px;
        text-transform: uppercase;
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .matrix-table td {
        padding: 12px;
        color: #f1f5f9;
        font-size: 13px;
        border-bottom: 1px solid rgba(255,255,255,0.03);
    }
    .semaforo {
        display: flex;
        gap: 10px;
        margin-bottom: 20px;
    }
    .sem-opt {
        flex: 1;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        font-weight: 700;
        cursor: pointer;
        opacity: 0.3;
        transition: all 0.3s;
    }
    .sem-opt.active { opacity: 1; transform: scale(1.05); box-shadow: 0 0 15px rgba(0,0,0,0.5); }
    .sem-verde { background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }
    .sem-amarillo { background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; }
    .sem-rojo { background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid #ef4444; }
    </style>
    """, unsafe_allow_html=True)

    tab_est, tab_seg, tab_dom, tab_dia = st.tabs([
        "📊 Matriz de Estrategia", 
        "🗓️ Plan de Seguimiento", 
        "📋 Análisis Dominical", 
        "📝 Diario de Operaciones"
    ])

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 1: MATRIZ DE ESTRATEGIA
    # ──────────────────────────────────────────────────────────────────────────
    with tab_est:
        st.markdown("<div class='sec-title'>🏹 Filosofía y Reglas Fundamentales</div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("""
            <div class='tp-card'>
                <h4 style='margin-top:0; color:#ef4444;'>🛡️ Reglas de Comportamiento (No negociables)</h4>
                <div class='check-item'><span class='check-icon'>✓</span><span class='check-text'>Solo opero setups con sesgo claro en 1W y 1D</span></div>
                <div class='check-item'><span class='check-icon'>✓</span><span class='check-text'>No persigo el precio. Si me faltó la entrada, busco el siguiente setup</span></div>
                <div class='check-item'><span class='check-icon'>✓</span><span class='check-text'>No opero noticias de alto impacto (FOMC, NFP, CPI) salvo protección</span></div>
                <div class='check-item' style='background:rgba(239, 68, 68, 0.05); border-color:rgba(239,68,68,0.1);'><span class='check-icon' style='color:#ef4444;'>✕</span><span class='check-text'>Prohibido mover el SL en contra</span></div>
                <div class='check-item' style='background:rgba(239, 68, 68, 0.05); border-color:rgba(239,68,68,0.1);'><span class='check-icon' style='color:#ef4444;'>✕</span><span class='check-text'>Prohibido añadir posición a un trade perdedor</span></div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class='tp-card'>
                <h4 style='margin-top:0; color:#60a5fa;'>📈 Reglas de Entrada (Confluencias SMC)</h4>
                <table class='matrix-table'>
                    <thead>
                        <tr><th>Criterio</th><th>Requisito Dimensional</th></tr>
                    </thead>
                    <tbody>
                        <tr><td><b>Sesgo 1W</b></td><td>Definido (alcista / bajista / rango)</td></tr>
                        <tr><td><b>Contexto 1D</b></td><td>En zona de interés institucional (OB, FVG, POI)</td></tr>
                        <tr><td><b>Estructura 4H</b></td><td>BOS o ChoCH confirmado alineado con sesgo</td></tr>
                        <tr><td><b>Confluencias</b></td><td>Mínimo 2 (Weekly + OB + FVG + Wyckoff)</td></tr>
                    </tbody>
                </table>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            st.markdown(f"""
            <div class='tp-card' style='text-align:center;'>
                <div style='font-size:10px; color:#94a3b8; text-transform:uppercase;'>Estilo de Inversión</div>
                <div style='font-size:20px; font-weight:800; color:#60a5fa; margin:10px 0;'>Swing Trading</div>
                <div style='font-size:12px; color:#e2e8f0;'>Frecuencia: 2 a 10 días</div>
            </div>
            <div class='tp-card' style='text-align:center;'>
                <div style='font-size:10px; color:#94a3b8; text-transform:uppercase;'>Gestión de Riesgo</div>
                <div style='font-size:20px; font-weight:800; color:#34d399; margin:10px 0;'>Max 1%</div>
                <div style='font-size:12px; color:#e2e8f0;'>R:R Mínimo 1:2</div>
            </div>
            """, unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 2: PLAN DE SEGUIMIENTO (Semáforo Dinámico)
    # ──────────────────────────────────────────────────────────────────────────
    with tab_seg:
        st.markdown("<div class='sec-title'>🟢 Semáforo de Condición de Mercado</div>", unsafe_allow_html=True)
        
        sem_status = st.select_slider(
            "Selecciona el estado del mercado para hoy",
            options=["🔴 CRÍTICO", "🟡 NEUTRAL", "🟢 ÓPTIMO"],
            value="🟢 ÓPTIMO"
        )
        
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            active = "active" if "ÓPTIMO" in sem_status else ""
            st.markdown(f"<div class='sem-opt sem-verde {active}'>🟢 OPERAR<br><small>Zonas Claras</small></div>", unsafe_allow_html=True)
        with col_s2:
            active = "active" if "NEUTRAL" in sem_status else ""
            st.markdown(f"<div class='sem-opt sem-amarillo {active}'>🟡 ESPERAR<br><small>Rango/Incertidumbre</small></div>", unsafe_allow_html=True)
        with col_s3:
            active = "active" if "CRÍTICO" in sem_status else ""
            st.markdown(f"<div class='sem-opt sem-rojo {active}'>🔴 FUERA<br><small>Noticias/Caos</small></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("""
            <div class='tp-card'>
                <h4 style='margin-top:0;'>⏰ Ventana de Oro (UTC-5)</h4>
                <table class='matrix-table'>
                    <tr><td>Londres</td><td>3:00am – 8:00am</td></tr>
                    <tr style='background:rgba(96,165,250,0.1);'><td style='font-weight:700;'>Solape L-NY</td><td>8:00am – 12:00pm</td></tr>
                    <tr><td>Nueva York</td><td>8:00am – 4:00pm</td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)
        
        with c2:
            st.markdown("""
            <div class='tp-card'>
                <h4 style='margin-top:0;'>🌅 Rutina de Apertura</h4>
                <div class='check-item'><span class='check-icon'>1</span><span class='check-text'>Noticias: Forex Factory (Evitar 🔴)</span></div>
                <div class='check-item'><span class='check-icon'>2</span><span class='check-text'>Fronteras: ¿Precio en POI Dominical?</span></div>
                <div class='check-item'><span class='check-icon'>3</span><span class='check-text'>Gatillo: ChoCH/BOS en M15/H1</span></div>
            </div>
            """, unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 3: ANÁLISIS DOMINICAL
    # ──────────────────────────────────────────────────────────────────────────
    with tab_dom:
        st.markdown("### 📋 Protocolo de Análisis Dominical (Macro → Micro)")
        
        with st.container(border=True):
            st.markdown("#### FASE 0: Preparación")
            c1, c2, c3 = st.columns(3)
            c1.checkbox("Forex Factory (Noticias 🔴)")
            c2.checkbox("Investing.com (Calendario)")
            c3.checkbox("Diario de Trading listo")

        st.markdown("#### FASE 1: Análisis Macro")
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Sesgo DXY (1W)", placeholder="ALCISTA / BAJISTA / NEUTRAL")
            st.text_area("Radar de Noticias Clave", placeholder="Mie: FOMC, Vie: NFP...")
        with col2:
            st.selectbox("Sentimiento Riesgo", ["Risk-On (Bolsas ↑)", "Risk-Off (Refugio ↑)", "Neutral/Rango"])

        st.markdown("#### FASE 2: Protocolo por Activo (1W → 1D → 4H)")
        st.info("⏱️ Meta: 6 minutos por activo. Analizar DXY → US500 → US30 → EURUSD...")
        
        with st.expander("🔍 Pasos por Activo"):
            st.markdown("""
            1. **Marco 1W:** Identificar tendencia y zonas de oferta/demanda.
            2. **Marco 1D:** Marcar OB, FVG y POI. Buscar liquidez previa.
            3. **Marco 4H:** Confirmar BOS/ChoCH alineado al sesgo.
            4. **Clasificación:** 🟢 Activo | 🟡 Desarrollo | 🔴 Sin Setup.
            """)

        st.markdown("#### 🛒 Preparar Operación (Enviar al Diario)")
        with st.container(border=True):
            sc1, sc2, sc3 = st.columns([2, 1, 1])
            plan_tick = sc1.text_input("Ticker Planeado", placeholder="US30, EURUSD...")
            plan_dir = sc2.selectbox("Dirección Plan", ["LONG", "SHORT"])
            if st.button("🚀 Enviar al Diario", use_container_width=True):
                if plan_tick:
                    st.session_state["journal_prefill"] = {
                        "activo": plan_tick.upper(),
                        "direccion": plan_dir,
                        "fecha": datetime.date.today()
                    }
                    st.success(f"Configuración para {plan_tick.upper()} enviada a la pestaña Diario.")
                else:
                    st.warning("Escribe un ticker primero.")

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 4: DIARIO DE OPERACIONES
    # ──────────────────────────────────────────────────────────────────────────
    with tab_dia:
        # Check for pre-fill from Tab 3
        prefill = st.session_state.get("journal_prefill", {})

        st.markdown("### 🧮 Calculadora de Riesgo y Sizing")
        with st.expander("Abrir Calculadora de Lotes/Contratos", expanded=False):
            cc1, cc2, cc3, cc4 = st.columns(4)
            balance = cc1.number_input("Balance Cuenta ($)", value=10000.0, step=1000.0)
            risk_p = cc2.number_input("Riesgo (%)", value=1.0, step=0.1)
            sl_points = cc3.number_input("SL (Puntos/Pips)", value=50.0, step=1.0)
            point_val = cc4.number_input("Valor Punto ($)", value=1.0, step=0.1)
            
            risk_usd = balance * (risk_p / 100)
            if sl_points > 0 and point_val > 0:
                pos_size = risk_usd / (sl_points * point_val)
                st.markdown(f"""
                <div style='background:rgba(96,165,250,0.1);padding:10px;border-radius:10px;text-align:center;'>
                    <span style='color:#60a5fa;font-weight:700;'>Riesgo: ${risk_usd:,.2f}</span> | 
                    <span style='color:#34d399;font-weight:700;'>Posición Sugerida: {pos_size:.2f} Lotes/Contratos</span>
                </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📝 Nueva Entrada al Diario")
        
        with st.form("trading_journal_form", clear_on_submit=True):
            f1, f2, f3 = st.columns(3)
            fecha = f1.date_input("Fecha", value=prefill.get("fecha", datetime.date.today()))
            activo = f2.text_input("Activo (Ticker)", value=prefill.get("activo", ""), placeholder="AAPL, EURUSD...")
            direc = f3.selectbox("Dirección", ["LONG", "SHORT"], index=0 if prefill.get("direccion") == "LONG" else 1 if prefill.get("direccion") == "SHORT" else 0)

            confluencias = st.text_area("Confluencias (Weekly OB, FVG, Wyckoff, etc.)", placeholder="Describe tus confluencias aquí...")
            
            with st.expander("📝 Evaluación de Confluencias (SMC Score)", expanded=False):
                c1, c2, c3 = st.columns(3)
                c_sesgo = c1.checkbox("Sesgo 1W Alineado", value=False)
                c_poi = c2.checkbox("En Punto de Interés (POI)", value=False)
                c_fvg = c3.checkbox("FVG Detectado / Cerrado", value=False)
                
                c4, c5, c6 = st.columns(3)
                c_ob = c4.checkbox("Order Block Confirmado", value=False)
                c_sess = c5.checkbox("En Sesión Activa", value=False)
                c_rr = c6.checkbox("R:R ≥ 1:2", value=False)
                
                from utils.analysis_utils import calculate_setup_score
                conf_dict = {
                    'sesgo_aligned': c_sesgo,
                    'in_poi': c_poi,
                    'fvg_detected': c_fvg,
                    'ob_detected': c_ob,
                    'session_active': c_sess,
                    'rr': c_rr
                }
                current_score = calculate_setup_score(conf_dict)
                st.progress(current_score / 100)
                st.markdown(f"**Setup Score: {current_score}/100**")

            f7, f8, f9, f10 = st.columns(4)
            precio_in = f7.number_input("Entrada", format="%.5f")
            sl = f8.number_input("Stop Loss", format="%.5f")
            tp1 = f9.number_input("Take Profit 1", format="%.5f")
            tp2 = f10.number_input("Take Profit 2", format="%.5f")

            f11, f12, f13 = st.columns(3)
            rr_exp = f11.number_input("R:R Esperado", value=2.0)
            resultado = f12.selectbox("Resultado", ["PENDIENTE", "WIN", "LOSS", "BE"])
            r_obt = f13.number_input("R Obtenidos", value=0.0)

            leccion = st.text_area("Lección / Observación Final")

            submit = st.form_submit_button("💾 Guardar Entrada", use_container_width=True)
            
            if submit:
                if not activo:
                    st.error("El campo 'Activo' es obligatorio.")
                else:
                    new_entry = {
                        "fecha": str(fecha),
                        "activo": activo.upper(),
                        "direccion": direc,
                        "sesgo_1w": sesgo_1w,
                        "contexto_1d": contexto_1d,
                        "gatillo": gatillo,
                        "confluencias": confluencias,
                        "entry_price": precio_in,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "rr_expected": rr_exp,
                        "resultado": resultado,
                        "r_obtenido": r_obt,
                        "leccion": leccion
                    }
                    save_entry_to_db(new_entry)
                    st.session_state["journal_prefill"] = {} # Clear prefill after saving
                    st.success(f"Entrada guardada para {activo.upper()}")
                    st.rerun()

        st.markdown("---")
        st.markdown("### 📑 Historial Reciente")
        history_df = get_recent_entries(15)
        if not history_df.empty:
            st.dataframe(history_df, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay entradas en el diario.")
