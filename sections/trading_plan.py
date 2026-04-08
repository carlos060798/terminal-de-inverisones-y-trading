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
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Plan de Trading Profesional</h1>
        <p>Price Action · Wyckoff · Smart Money Concepts · Swing Trading</p>
      </div>
    </div>""", unsafe_allow_html=True)

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
        st.markdown("### 🏹 Filosofía y Reglas Fundamentales")
        
        c1, c2 = st.columns([2, 1])
        with c1:
            with st.expander("🛡️ Reglas de Comportamiento (No negociables)", expanded=True):
                st.markdown("""
                - ✅ Solo opero setups con sesgo claro en 1W y 1D
                - ✅ No persigo el precio. Si me faltó la entrada, busco el siguiente setup
                - ✅ No opero noticias de alto impacto (FOMC, NFP, CPI) salvo que esté protegido
                - ❌ Prohibido mover el SL en contra
                - ❌ Prohibido añadir posición a un trade perdedor
                """)
            
            with st.expander("📈 Reglas de Entrada y Confluencias"):
                st.markdown("""
                | Criterio | Requisito |
                |---|---|
                | **Sesgo 1W** | Definido (alcista / bajista / rango) |
                | **Contexto 1D** | En zona de interés institucional (OB, FVG, POI) |
                | **Estructura 4H** | BOS o ChoCH confirmado alineado con sesgo |
                | **Confluencias** | Al menos 2 (Weekly + OB + FVG + Wyckoff + Sesión) |
                """)

        with c2:
            st.info("💡 **Estilo:** Swing Trading (2 a 10 días)")
            st.info("🎯 **Edge:** Wyckoff + SMC en zonas institucionales")
            st.info("⚖️ **Gestión:** Riesgo 1% | R:R ≥ 1:2")

        st.markdown("---")
        st.markdown("### 🔵 Universo de Activos")
        
        universo_data = [
            {"Activo": "US30", "Tipo": "Índice USA", "Rol": "Sentimiento Riesgo", "Sesión": "NY"},
            {"Activo": "EURUSD", "Tipo": "Forex Major", "Rol": "Riesgo/Apetito EUR", "Sesión": "Londres/NY"},
            {"Activo": "GBPUSD", "Tipo": "Forex Major", "Rol": "Correlación EUR", "Sesión": "Londres/NY"},
            {"Activo": "DXY", "Tipo": "Índice Dólar", "Rol": "Inverso a Majors", "Sesión": "NY"},
            {"Activo": "US500", "Tipo": "Índice USA", "Rol": "Sentimiento Amplio", "Sesión": "NY"},
            {"Activo": "USDJPY", "Tipo": "Forex Yen", "Rol": "Carry Trade / Risk-off", "Sesión": "Tokio/NY"},
            {"Activo": "AUDUSD", "Tipo": "Forex Commodity", "Rol": "Riesgo Global / China", "Sesión": "Asia/Londres"},
        ]
        st.table(pd.DataFrame(universo_data))

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 2: PLAN DE SEGUIMIENTO
    # ──────────────────────────────────────────────────────────────────────────
    with tab_seg:
        st.markdown("### 🟢 Semáforo de Condición de Mercado")
        sem_col = st.radio("Estado Actual del Mercado", ["🟢 VERDE — Operar", "🟡 AMARILLO — Esperar", "🔴 ROJO — No operar"], horizontal=True)
        
        if "VERDE" in sem_col:
            st.success("Tendencia clara 1W + 1D | Setup en zona | R:R ≥ 1:2")
        elif "AMARILLO" in sem_col:
            st.warning("Estructura mixta | Precio en medio de rango | Sin gatillo definido")
        else:
            st.error("Semana de FOMC/NFP | Volatilidad extrema | Correlaciones contradictorias")

        st.markdown("---")
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("#### ⏰ Mapa de Sesiones (Colombia UTC-5)")
            st.markdown("""
            | Sesión | Horario | Importancia |
            |---|---|---|
            | **Londres** | 3:00am – 8:00am | EURUSD, GBPUSD, DE30 |
            | **Solape (L-NY)** | 8:00am – 12:00pm | **MÁXIMA LIQUIDEZ** |
            | **Nueva York** | 8:00am – 4:00pm | US30, US500, DXY |
            | **Tokio** | 8:00pm – 12:00am | USDJPY, AUDUSD, NIKKEI |
            """)
        
        with c2:
            st.markdown("#### 🌅 Rutina Diaria (8:15am – 8:45am)")
            st.markdown("""
            1. **Noticias:** ¿Hay alto impacto hoy? (Forex Factory)
            2. **Prioridades:** ¿Tocaron zonas del domingo?
            3. **Gatillo:** ¿Hay ChoCH/BOS en 4H/1H?
            4. **Alertas:** Actualizar si el precio se movió.
            """)

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
