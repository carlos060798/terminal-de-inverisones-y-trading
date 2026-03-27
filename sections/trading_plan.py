"""
sections/trading_plan.py - Trading Plan Institucional
7 secciones + Notas Semanales + Intérprete de Señales Wyckoff.
"""
import streamlit as st
import pandas as pd
from ui_shared import kpi, dark_layout, CHART_SM

# ── Datos estáticos del plan ──────────────────────────────────────────────────
RUTINA_HORARIOS = [
    {"Bloque": "DOMINGO", "Día/Hora": "Domingo 6:00 – 6:45 PM", "Actividad": "Macro & Contexto", "Detalle": "DXY sesgo macro 1W, Correlaciones, Fases Wyckoff", "Duración": "45 min"},
    {"Bloque": "DOMINGO", "Día/Hora": "Domingo 6:45 – 7:30 PM", "Actividad": "Análisis Top-Down", "Detalle": "1W → 1D → 4H, OB, FVG, POI entrada, SL", "Duración": "45 min"},
    {"Bloque": "DOMINGO", "Día/Hora": "Domingo 7:30 – 8:00 PM", "Actividad": "Planteamiento & Alertas", "Detalle": "Narrativa setup, Alertas en 4H, R:R ≥ 1:3", "Duración": "30 min"},
    {"Bloque": "MAÑANA", "Día/Hora": "Lun-Vie 7:00 – 7:30 AM", "Actividad": "Revisión matutina", "Detalle": "Alertas noche, Cierre Asia, Gap índices", "Duración": "30 min"},
    {"Bloque": "NY OPEN", "Día/Hora": "Lun-Vie 12:00 – 2:00 PM", "Actividad": "Ventana operativa principal", "Detalle": "CHoCH en 1H, Ejecutar entradas, Gestionar SL/TP", "Duración": "2 horas"},
    {"Bloque": "NOCHE", "Día/Hora": "Lun-Vie 6:30 – 7:00 PM", "Actividad": "Preparación Tokyo", "Detalle": "Gestionar posiciones, Alertas sesión asiática", "Duración": "30 min"},
]

ACTIVOS = [
    # Forex (6)
    {"Activo": "EUR/USD", "Tipo": "Forex",  "Sesgo": "Short",   "POI": "1.0850", "SL": "1.0870", "TP": "1.0750", "Sesion": "London/NY"},
    {"Activo": "USD/JPY", "Tipo": "Forex",  "Sesgo": "Long",    "POI": "149.50", "SL": "148.80", "TP": "151.00", "Sesion": "Tokyo"},
    {"Activo": "GBP/USD", "Tipo": "Forex",  "Sesgo": "Neutral", "POI": "1.2620", "SL": "1.2580", "TP": "1.2720", "Sesion": "London"},
    {"Activo": "AUD/USD", "Tipo": "Forex",  "Sesgo": "Short",   "POI": "0.6450", "SL": "0.6480", "TP": "0.6380", "Sesion": "Tokyo"},
    {"Activo": "USD/CAD", "Tipo": "Forex",  "Sesgo": "Long",    "POI": "1.3520", "SL": "1.3480", "TP": "1.3620", "Sesion": "NY"},
    {"Activo": "NZD/USD", "Tipo": "Forex",  "Sesgo": "Neutral", "POI": "0.5980", "SL": "0.5950", "TP": "0.6050", "Sesion": "Tokyo"},
    # Indices (3)
    {"Activo": "US30",    "Tipo": "Indice", "Sesgo": "Neutral", "POI": "39500",  "SL": "39200",  "TP": "40200",  "Sesion": "NY"},
    {"Activo": "SPX500",  "Tipo": "Indice", "Sesgo": "Long",    "POI": "5100",   "SL": "5080",   "TP": "5200",   "Sesion": "NY"},
    {"Activo": "NAS100",  "Tipo": "Indice", "Sesgo": "Long",    "POI": "18200",  "SL": "18000",  "TP": "18600",  "Sesion": "NY"},
    # Metales (2)
    {"Activo": "XAU/USD", "Tipo": "Metal",  "Sesgo": "Long",    "POI": "2125",   "SL": "2115",   "TP": "2160",   "Sesion": "London"},
    {"Activo": "XAG/USD", "Tipo": "Metal",  "Sesgo": "Long",    "POI": "24.80",  "SL": "24.20",  "TP": "26.00",  "Sesion": "London"},
    # Crypto (2)
    {"Activo": "BTC/USD", "Tipo": "Crypto", "Sesgo": "Long",    "POI": "62000",  "SL": "60000",  "TP": "68000",  "Sesion": "24/7"},
    {"Activo": "ETH/USD", "Tipo": "Crypto", "Sesgo": "Long",    "POI": "3100",   "SL": "2980",   "TP": "3400",   "Sesion": "24/7"},
    # Accion (1)
    {"Activo": "NVDA",    "Tipo": "Accion", "Sesgo": "Long",    "POI": "820",    "SL": "790",    "TP": "900",    "Sesion": "NY"},
]


CHECKLIST_MORNING = [
    "Revisar si alguna alerta se activó durante la noche/Asia",
    "Verificar impacto de fundamentales (Investing / FF)",
    "Revisar DXY y contexto general", "Chequear precio cerca de POI validado"]
CHECKLIST_LUNCH = [
    "Identificar setups activos o entrando a POI",
    "Confirmar CHoCH / BOS en 1H antes de entrar",
    "Calcular tamaño de posición y R:R",
    "Gestionar posiciones activas (TP1, Break Even)"]
CHECKLIST_EVENING = [
    "Actualizar journal con operaciones del día",
    "Verificar posiciones sin SL/TP activo",
    "Fijar alertas para sesión Tokyo",
    "Cerrar gráficas — descanso mental"]

ALERTAS = [
    {"Activo": "EUR/USD", "Tipo": "Entrada",      "Nivel": "1.0850", "Protocolo": "Short en 15m si llega"},
    {"Activo": "XAU/USD", "Tipo": "Invalidación", "Nivel": "2115",   "Protocolo": "Cerrar idea larga"},
    {"Activo": "SPX500",  "Tipo": "Entrada",       "Nivel": "5100",   "Protocolo": "CHoCH alcista NY Open"},
]

JOURNAL_COLUMNS = ["Fecha", "Activo", "Tipo", "Entrada", "Salida", "Pips/Pts", "Resultado", "Notas"]

# ── Wyckoff: System prompt del intérprete ────────────────────────────────────
_WYCKOFF_SYSTEM = """Eres el intérprete oficial del indicador Wyckoff Structure Detector v6 (Pine Script).
El usuario te da las lecturas actuales del indicador. Responde SIEMPRE en español con Markdown técnico y estas secciones obligatorias:
1. **CONTEXTO ESTRUCTURAL**: Explica lo que significa esa combinación Estructura + Fase
2. **MOMENTO DEL CICLO**: En qué punto exacto del ciclo Wyckoff está el precio ahora
3. **SEÑALES CONFIRMADAS**: Qué eventos (PS/SC/AR/ST/Spring/SOS/BU) ya ocurrieron y cuáles faltan
4. **ZONA OPERATIVA**: ¿Hay zona de entrada válida? (Agresiva=Fase C, Principal=Fase D). Si no, indica claramente "SIN ZONA VÁLIDA"
5. **PLAN DE TRADING**: Entrada sugerida, Stop Loss estructural, TP1 (próxima liquidez), TP2 (OB opuesto), R:R estimado
6. **ESCENARIO ALTERNATIVO**: Qué pasaría si el precio invalida la tesis
7. **NIVEL DE INVALIDACIÓN**: Precio exacto donde la tesis queda nula

Sé conciso, específico y accionable. Evita repetir las lecturas del usuario."""


def _render_wyckoff_interpreter():
    """Sub-sección: Intérprete de señales del indicador Wyckoff."""
    st.markdown("### 🎯 Intérprete de Señales — Wyckoff Structure Detector v6")
    st.caption("Ingresa las lecturas actuales de tu indicador en TradingView y la IA genera el análisis completo.")

    with st.form("wyckoff_interp_form"):
        c1, c2, c3 = st.columns(3)
        activo_w   = c1.text_input("Activo", placeholder="US30, EUR/USD, BTC...")
        timeframe_w= c2.selectbox("Timeframe", ["1H", "4H", "Daily", "Weekly"])
        precio_w   = c3.text_input("Precio actual", placeholder="5120.50")

        c4, c5 = st.columns(2)
        estructura = c4.selectbox("Estructura detectada", ["Acumulación", "Distribución", "Sin definir"])
        esquema    = c5.selectbox("Esquema", ["#1 (con Spring/UTAD)", "#2 (sin sacudida)", "Indefinido"])

        c6, c7, c8 = st.columns(3)
        fase       = c6.selectbox("Fase actual", ["A", "B", "C", "D", "E"])
        sesgo      = c7.selectbox("Sesgo", ["ALCISTA", "BAJISTA", "NEUTRAL"])
        creek_roto = c8.selectbox("Creek", ["✓ Roto (JAC)", "✗ No roto", "N/A"])

        c9, c10, c11 = st.columns(3)
        ice_nivel  = c9.text_input("Nivel ICE (soporte)", placeholder="0.0000")
        creek_nivel= c10.text_input("Nivel Creek (resistencia)", placeholder="0.0000")
        esfuerzo   = c11.selectbox("Esfuerzo vs Resultado", ["Armonía ✓", "Divergencia ⚠"])

        fortaleza  = st.slider("Fortaleza de estructura (%)", 0, 100, 70, 5)
        notas_extra= st.text_area("Contexto adicional (opcional)", placeholder="Ej: Spring #3 con vol bajo, DXY cayendo, noticias macro esta semana...")

        submitted = st.form_submit_button("🧠 Interpretar con IA", type="primary")

    if submitted and activo_w.strip():
        prompt = f"""Activo: {activo_w.upper()} | Timeframe: {timeframe_w} | Precio: {precio_w}

LECTURAS DEL INDICADOR:
- Estructura: {estructura} — Esquema: {esquema}
- Fase actual: {fase}
- Sesgo: {sesgo}
- Creek: {creek_roto} (nivel: {creek_nivel})
- ICE (soporte): {ice_nivel}
- Esfuerzo vs Resultado: {esfuerzo}
- Fortaleza de estructura: {fortaleza}%
- Contexto adicional: {notas_extra if notas_extra.strip() else 'Ninguno'}

Genera el análisis completo con plan de trading."""

        with st.spinner("Interpretando señales..."):
            try:
                from ai_engine import generate
                result = generate(prompt=prompt, system=_WYCKOFF_SYSTEM, max_tokens=1800)
                if result:
                    st.markdown(f"""<div style='background:linear-gradient(135deg,rgba(212,168,67,0.06),rgba(13,21,37,1));
                        border:1px solid rgba(212,168,67,0.25);border-radius:12px;padding:20px;margin-top:12px;'>
                        <div style='font-size:12px;color:#d4a843;font-weight:600;margin-bottom:12px;'>
                        🎯 INTERPRETACIÓN WYCKOFF — {activo_w.upper()} {timeframe_w}</div>
                    </div>""", unsafe_allow_html=True)
                    st.markdown(result)

                    # Guardar en historial de sesión
                    if "wyckoff_interp_history" not in st.session_state:
                        st.session_state.wyckoff_interp_history = []
                    st.session_state.wyckoff_interp_history.insert(0, {
                        "activo": activo_w.upper(), "tf": timeframe_w,
                        "estructura": estructura, "fase": fase,
                        "sesgo": sesgo, "result": result,
                        "time": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')
                    })
                    st.session_state.wyckoff_interp_history = st.session_state.wyckoff_interp_history[:10]
                else:
                    st.warning("La IA no devolvió respuesta. Verifica que DEEPSEEK_API_KEY o GEMINI_API_KEY estén configurados en `.streamlit/secrets.toml`.")
            except Exception as e:
                st.error(f"Error: {e}")
    elif submitted and not activo_w.strip():
        st.warning("Ingresa el nombre del activo.")

    # Historial de interpretaciones
    hist = st.session_state.get("wyckoff_interp_history", [])
    if hist:
        st.markdown("#### 📋 Interpretaciones recientes")
        for h in hist[:5]:
            with st.expander(f"🎯 {h['activo']} {h['tf']} | {h['estructura']} Fase {h['fase']} | {h['time']}", expanded=False):
                st.markdown(h["result"])


def render():
    st.markdown("""
        <div style='text-align:center; padding: 10px 0 20px 0;'>
            <h2>📋 Plan de Trading Institucional</h2>
            <p style='color:#a0a0a0;'>Ejecución, Sistematicidad y Disciplina</p>
        </div>
    """, unsafe_allow_html=True)

    # Persistencia del journal
    if "trading_journal_df" not in st.session_state:
        st.session_state.trading_journal_df = pd.DataFrame(columns=JOURNAL_COLUMNS)

    tabs = st.tabs([
        "📅 Rutina Semanal",
        "🧠 Metodología",
        "📊 Activos & Sesgos",
        "✅ Checklist",
        "📝 Análisis Dominical",
        "🔔 Alertas",
        "📖 Journal",
        "🗒️ Notas Semanales",
        "🎯 Intérprete Wyckoff",
    ])

    # ── 1. Rutina Semanal ────────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Distribución Semanal")
        st.caption("Estructura de tiempo para maximizar enfoque y minimizar ruido.")
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(kpi("Horas/Semana", "7h", "Máxima eficiencia", "blue"), unsafe_allow_html=True)
        c2.markdown(kpi("Activos", "14 Max", "Focus", "purple"), unsafe_allow_html=True)
        c3.markdown(kpi("Timeframes", "4 TF", "Top-Down", "green"), unsafe_allow_html=True)
        c4.markdown(kpi("R:R Mínimo", "1:3", "Gestión riesgo", "orange"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(RUTINA_HORARIOS), use_container_width=True, hide_index=True)
        st.warning("**REGLA DE ORO:** Si no está en el plan del domingo, NO se opera.")

    # ── 2. Metodología ──────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Flujo Top-Down y Conceptos Clave")
        st.markdown("""**Flujo:** 1W → 1D → 4H → 1H

| Regla | Valor |
|---|---|
| Stop Loss | Más allá del POI invalidante |
| Take Profit 1 | Siguiente zona de liquidez |
| Take Profit 2 | OB opuesto en 4H |
| R:R mínimo | **1:3** |
| Break Even | Al alcanzar TP1 |""")
        col1, col2 = st.columns(2)
        with col1:
            st.info("**BOS/CHoCH**: Break of Structure y Change of Character.")
            st.success("**OB (Order Block)**: Huella institucional, zona de mitigación.")
        with col2:
            st.warning("**FVG (Fair Value Gap)**: Ineficiencia que el precio suele llenar.")
            st.error("**Liquidity Sweep**: Barrida de stops antes de la dirección real.")

    # ── 3. Activos & Sesgos ─────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Watchlist Operativa")
        st.dataframe(pd.DataFrame(ACTIVOS), use_container_width=True, hide_index=True)

    # ── 4. Checklist ─────────────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Checklist Diario de Ejecución")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("### 🌅 Mañana (7:00 AM)")
            for i, item in enumerate(CHECKLIST_MORNING):
                st.checkbox(item, key=f"am_{i}")
        with col2:
            st.markdown("### 🏙️ NY Open (12:00 PM)")
            for i, item in enumerate(CHECKLIST_LUNCH):
                st.checkbox(item, key=f"ny_{i}")
        with col3:
            st.markdown("### 🌙 Tokyo / Cierre (6:30 PM)")
            for i, item in enumerate(CHECKLIST_EVENING):
                st.checkbox(item, key=f"tk_{i}")

    # ── 5. Análisis Dominical ────────────────────────────────────────────────
    with tabs[4]:
        st.subheader("Plantilla de Análisis Dominical")
        st.markdown("*(Completa los domingos por la noche antes de la semana)*")
        with st.form("form_dominical"):
            st.text_area("Contexto Macro (DXY / Fundamentales)", placeholder="DXY en resistencia semanal, sesgo...", key="dom_macro")
            st.text_area("Activos en Zona Premium", placeholder="XAU en OB diario, EUR acumulando...", key="dom_premium")
            st.text_area("Setups Prioritarios (máx 4)", placeholder="1. EUR/USD Short en 1.0850...", key="dom_setups")
            st.text_area("Niveles de Invalidación", placeholder="Si XAU rompe 2115 → cierra idea larga", key="dom_inv")
            if st.form_submit_button("💾 Guardar Análisis Semanal"):
                st.success("✅ Análisis guardado para la semana.")

    # ── 6. Alertas ───────────────────────────────────────────────────────────
    with tabs[5]:
        st.subheader("Alertas Activas")
        st.dataframe(pd.DataFrame(ALERTAS), use_container_width=True, hide_index=True)
        with st.expander("➕ Añadir Alerta"):
            with st.form("alert_form"):
                c1, c2 = st.columns(2)
                n_act  = c1.text_input("Activo")
                n_tipo = c2.selectbox("Tipo", ["Entrada", "Invalidación", "Referencia"])
                c3, c4 = st.columns(2)
                n_niv  = c3.text_input("Nivel")
                n_prot = c4.text_input("Protocolo")
                if st.form_submit_button("Añadir"):
                    st.info("Alerta registrada (requiere conexión a BD para persistir).")

    # ── 7. Journal ───────────────────────────────────────────────────────────
    with tabs[6]:
        st.subheader("Journal de Operaciones")
        with st.expander("📌 Registrar Nuevo Trade", expanded=False):
            with st.form("journal_form_v2"):
                c1, c2, c3 = st.columns(3)
                date    = c1.date_input("Fecha", value=pd.Timestamp.today())
                activo  = c2.selectbox("Activo", [a["Activo"] for a in ACTIVOS] + ["Otro"])
                tipo    = c3.selectbox("Tipo", ["Long", "Short"])
                c4, c5, c6 = st.columns(3)
                entrada = c4.number_input("Entrada", format="%.5f")
                salida  = c5.number_input("Salida", format="%.5f", value=0.0)
                pips    = c6.number_input("Pips/Pts", step=1.0)
                resultado = st.selectbox("Resultado", ["Ganancia", "Pérdida", "Break Even"])
                notas  = st.text_area("Notas / Aprendizajes")
                if st.form_submit_button("💾 Guardar"):
                    new_trade = pd.DataFrame([{
                        "Fecha": date, "Activo": activo, "Tipo": tipo,
                        "Entrada": entrada,
                        "Salida": salida if salida != 0 else pd.NA,
                        "Pips/Pts": pips, "Resultado": resultado, "Notas": notas,
                    }])
                    st.session_state.trading_journal_df = pd.concat(
                        [st.session_state.trading_journal_df, new_trade], ignore_index=True)
                    st.success("✅ Trade registrado.")

        st.dataframe(st.session_state.trading_journal_df, use_container_width=True, hide_index=True)
        df_j = st.session_state.trading_journal_df
        if not df_j.empty:
            ganadoras = len(df_j[df_j["Resultado"] == "Ganancia"])
            perdedoras = len(df_j[df_j["Resultado"] == "Pérdida"])
            be = len(df_j[df_j["Resultado"] == "Break Even"])
            total = len(df_j)
            wr = (ganadoras / (total - be)) * 100 if (total - be) > 0 else 0
            c1, c2, c3 = st.columns(3)
            c1.markdown(kpi("Win Rate", f"{wr:.1f}%", f"{ganadoras}W / {perdedoras}L", "green" if wr >= 50 else "red"), unsafe_allow_html=True)
            c2.markdown(kpi("Trades", str(total), f"{be} BE", "blue"), unsafe_allow_html=True)
            c3.markdown(kpi("Pips Netos", f"{df_j['Pips/Pts'].sum():.1f}", "Total", "orange"), unsafe_allow_html=True)

    # ── 8. Notas Semanales ───────────────────────────────────────────────────
    with tabs[7]:
        st.subheader("🗒️ Notas Semanales")
        st.caption("Espacio libre para contexto de mercado, aprendizajes o recordatorios de la semana.")

        semana_key = f"notas_{pd.Timestamp.now().strftime('%Y-W%U')}"
        notas_actuales = st.session_state.get(semana_key, "")

        notas_input = st.text_area(
            f"Semana {pd.Timestamp.now().strftime('%Y · Semana %U')}",
            value=notas_actuales,
            height=280,
            placeholder="Ej: DXY en zona crítica. EUR/USD acumulando en 1.0800. Evitar operar martes por CPI...",
            key="notas_semana_input"
        )
        col_btn1, col_btn2, _ = st.columns([1, 1, 4])
        if col_btn1.button("💾 Guardar Notas"):
            st.session_state[semana_key] = notas_input
            st.success("✅ Notas guardadas.")
        if col_btn2.button("🗑️ Limpiar"):
            st.session_state[semana_key] = ""
            st.rerun()

        # Notas de semanas anteriores
        semanas_guardadas = {k: v for k, v in st.session_state.items()
                             if k.startswith("notas_") and k != semana_key and v}
        if semanas_guardadas:
            st.markdown("#### Semanas anteriores")
            for k, v in sorted(semanas_guardadas.items(), reverse=True)[:4]:
                with st.expander(k.replace("notas_", "📅 "), expanded=False):
                    st.markdown(v)

    # ── 9. Intérprete Wyckoff ────────────────────────────────────────────────
    with tabs[8]:
        _render_wyckoff_interpreter()
