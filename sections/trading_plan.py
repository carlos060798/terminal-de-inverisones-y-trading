"""
sections/trading_plan.py - Trading Plan Institutional Module
Implements the 7 sections from Plan_Trading_Institucional.html as Streamlit tabs.
"""
import streamlit as st
import pandas as pd
from ui_shared import kpi, dark_layout, CHART_SM

# ---- Static data extracted from the HTML plan ----
# 1. Rutina Semanal
RUTINA_HORARIOS = [
    {"Bloque": "Domingo", "Hora": "22:00 – 23:00", "Actividad": "Revisión semanal, planificación"},
    {"Bloque": "Mañana", "Hora": "08:00 – 09:00", "Actividad": "Revisión de mercados, setups"},
    {"Bloque": "Almuerzo", "Hora": "12:00 – 13:00", "Actividad": "Análisis de precios, ajustes"},
    {"Bloque": "Noche", "Hora": "20:00 – 21:00", "Actividad": "Revisión de operaciones, journal"},
]

# 2. Metodología Top‑Down (placeholder description)
METODOLOGIA_DESC = """Flujo 1W → 1D → 4H → 1H. Gestión de riesgo: 1‑3% riesgo por operación, R:R 1:3.
Conceptos SMC/Wyckoff: Order‑Block, Liquidity‑Grab, Fair‑Value‑Gap, Breaker, Imbalance.
"""

# 3. Activos & Sesgos (example table)
ACTIVOS = [
    {"Activo": "EUR/USD", "Tipo": "Forex", "Precio": 1.12, "Sesgo": "Long", "Metodología": "SMC", "POI": "1.1250", "SL": "1.1150", "TP": "1.1350", "Sesión": "London"},
    {"Activo": "USD/JPY", "Tipo": "Forex", "Precio": 110.5, "Sesgo": "Short", "Metodología": "Wyckoff", "POI": "109.8", "SL": "111.0", "TP": "108.5", "Sesión": "Asia"},
    # ... add remaining 12 assets as needed
]

# 4. Checklist Diario (placeholder items)
CHECKLIST_MORNING = ["Revisar noticias macro", "Verificar niveles clave", "Actualizar tabla de activos"]
CHECKLIST_LUNCH = ["Revisar setups del mediodía", "Ajustar stops", "Re‑evaluar riesgo"]
CHECKLIST_EVENING = ["Cerrar posiciones abiertas", "Actualizar journal", "Planificar día siguiente"]

# 5. Análisis Dominical (placeholder template)
ANALISIS_DOMINICAL = {
    "Objetivo": "Identificar tendencias semanales y zonas de soporte/resistencia.",
    "Acciones": ["Marcar swing highs/lows", "Definir zonas de entrada", "Establecer niveles de stop"],
}

# 6. Alertas & Niveles (placeholder)
ALERTAS = [
    {"Activo": "EUR/USD", "Tipo": "Entrada", "Nivel": 1.1250, "Protocolo": "Confirmar ruptura"},
    {"Activo": "USD/JPY", "Tipo": "Invalidación", "Nivel": 109.5, "Protocolo": "Salir si rompe"},
]

# 7. Journal (simple DataFrame placeholder)
JOURNAL_COLUMNS = ["Fecha", "Activo", "Tipo", "Entrada", "Salida", "Pips", "Resultado"]
JOURNAL_DF = pd.DataFrame(columns=JOURNAL_COLUMNS)


def render():
    st.markdown("""<div class='top-header'><h1>Plan de Trading Institucional</h1><p>Herramientas y checklist para operar con disciplina.</p></div>""", unsafe_allow_html=True)

    # Main tabs for each section
    tabs = st.tabs([
        "Rutina Semanal",
        "Metodología Top‑Down",
        "Activos & Sesgos",
        "Checklist Diario",
        "Análisis Dominical",
        "Alertas & Niveles",
        "Journal",
    ])

    # ---- 1. Rutina Semanal ----
    with tabs[0]:
        st.subheader("Distribución Horaria (7h semanales)")
        df = pd.DataFrame(RUTINA_HORARIOS)
        st.table(df)
        st.info("Regla de oro: No operar fuera de los bloques horarios definidos.")

    # ---- 2. Metodología Top‑Down ----
    with tabs[1]:
        st.subheader("Flujo Top‑Down y Gestión de Riesgo")
        st.markdown(METODOLOGIA_DESC)
        st.metric(label="Riesgo por operación", value="1‑3% del capital")
        st.metric(label="Ratio R:R", value="1:3")

    # ---- 3. Activos & Sesgos ----
    with tabs[2]:
        st.subheader("Tabla de Activos y Sesgos")
        df = pd.DataFrame(ACTIVOS)
        st.dataframe(df)
        st.caption("Actualiza la tabla con los 14 activos del plan.")

    # ---- 4. Checklist Diario ----
    with tabs[3]:
        st.subheader("Checklist Diario")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Mañana**")
            for item in CHECKLIST_MORNING:
                st.checkbox(item, key=f"chk_morn_{item}")
        with col2:
            st.markdown("**Almuerzo**")
            for item in CHECKLIST_LUNCH:
                st.checkbox(item, key=f"chk_lunch_{item}")
        with col3:
            st.markdown("**Noche**")
            for item in CHECKLIST_EVENING:
                st.checkbox(item, key=f"chk_even_{item}")
        st.success("Marca los ítems completados para llevar registro de disciplina.")

    # ---- 5. Análisis Dominical ----
    with tabs[4]:
        st.subheader("Plantilla de Análisis Dominical")
        st.text_area("Objetivo semanal", ANALISIS_DOMINICAL["Objetivo"], key="obj_week")
        for i, act in enumerate(ANALISIS_DOMINICAL["Acciones"]):
            st.text_input(f"Acción {i+1}", act, key=f"accion_{i}")
        if st.button("Guardar Análisis"):
            st.success("Análisis guardado (placeholder).")

    # ---- 6. Alertas & Niveles ----
    with tabs[5]:
        st.subheader("Alertas de Entrada / Invalidación")
        df = pd.DataFrame(ALERTAS)
        st.dataframe(df)
        st.caption("Configura alertas en tu broker o plataforma de trading.")

    # ---- 7. Journal ----
    with tabs[6]:
        st.subheader("Journal de Operaciones")
        # Simple entry form
        with st.form(key="journal_form"):
            date = st.date_input("Fecha", value=pd.Timestamp.today())
            activo = st.selectbox("Activo", options=[a["Activo"] for a in ACTIVOS])
            tipo = st.selectbox("Tipo", ["Long", "Short"])
            entrada = st.number_input("Precio Entrada", format="%.5f")
            salida = st.number_input("Precio Salida", format="%.5f", value=0.0)
            pips = st.number_input("Pips", step=0.1)
            resultado = st.selectbox("Resultado", ["Ganancia", "Pérdida", "Break Even"])
            submitted = st.form_submit_button("Agregar")
            if submitted:
                new_row = {
                    "Fecha": date,
                    "Activo": activo,
                    "Tipo": tipo,
                    "Entrada": entrada,
                    "Salida": salida if salida != 0 else None,
                    "Pips": pips,
                    "Resultado": resultado,
                }
                global JOURNAL_DF
                JOURNAL_DF = JOURNAL_DF.append(new_row, ignore_index=True)
                st.success("Operación añadida al journal.")
        st.dataframe(JOURNAL_DF)
        # KPI summary
        if not JOURNAL_DF.empty:
            total_ops = len(JOURNAL_DF)
            ganancias = JOURNAL_DF[JOURNAL_DF["Resultado"] == "Ganancia"].shape[0]
            perdidas = JOURNAL_DF[JOURNAL_DF["Resultado"] == "Pérdida"].shape[0]
            win_rate = ganancias / total_ops * 100 if total_ops else 0
            st.markdown(kpi("Win Rate", f"{win_rate:.1f}%", f"{ganancias}W / {perdidas}L", "green"), unsafe_allow_html=True)

# End of render()
