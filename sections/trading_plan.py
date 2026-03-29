"""
sections/trading_plan.py - Plan de Trading Integral (v7.5)
Implementación TOTAL: 14 Pestañas, Metodología DSD, Motor Wyckoff v7.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from ui_shared import kpi

# ── 1. CONFIGURACIÓN Y CONSTANTES DSD ─────────────────────────────────────────

PERFIL_TRADER = [
    {"Elemento": "Horario Disponible", "Valor": "6:00 am - 12:00 pm (Hora Colombia)"},
    {"Elemento": "Sesiones Cubiertas", "Valor": "Cierre Europa + Apertura Nueva York"},
    {"Elemento": "Timeframes", "Valor": "Semanal (contexto), Diario (estructura), 4H/1H (gatillo)"},
    {"Elemento": "Metodología", "Valor": "Wyckoff 2.0 + Smart Money + Price Action"},
    {"Elemento": "Operaciones/Semana", "Valor": "Máximo 3-5 setups de alta probabilidad"},
    {"Elemento": "Capital en Riesgo", "Valor": "Máximo 2% por operación"},
    {"Elemento": "Filosofía", "Valor": "'No operar contra tendencia' (Lynch) / 'Pérdida limitada' (Darvas)"},
]

ACTIVOS_PRIORIZADOS = [
    {"Categoría": "Índices EEUU", "Activo": "S&P 500", "Símbolo": "ES / SPX500", "Prioridad": "⭐⭐⭐", "Volatilidad": "Alta", "Horario": "8:30-10:30 am"},
    {"Categoría": "Índices EEUU", "Activo": "Nasdaq 100", "Símbolo": "NQ / NAS100", "Prioridad": "⭐⭐⭐", "Volatilidad": "Muy Alta", "Horario": "8:30-10:30 am"},
    {"Categoría": "Índices EEUU", "Activo": "Dow Jones", "Símbolo": "YM / US30", "Prioridad": "⭐⭐", "Volatilidad": "Media", "Horario": "8:30-10:30 am"},
    {"Categoría": "Forex", "Activo": "EUR/USD", "Símbolo": "EURUSD", "Prioridad": "⭐⭐⭐", "Volatilidad": "Alta", "Horario": "6:00-10:00 am"},
    {"Categoría": "Forex", "Activo": "GBP/USD", "Símbolo": "GBPUSD", "Prioridad": "⭐⭐", "Volatilidad": "Media-Alta", "Horario": "6:00-9:00 am"},
    {"Categoría": "Forex", "Activo": "AUD/USD", "Símbolo": "AUDUSD", "Prioridad": "⭐", "Volatilidad": "Media", "Horario": "6:00-8:00 am"},
    {"Categoría": "Forex", "Activo": "USD/JPY", "Símbolo": "USDJPY", "Prioridad": "⭐⭐", "Volatilidad": "Media", "Horario": "8:30-11:00 am"},
    {"Categoría": "Commodities", "Activo": "Oro", "Símbolo": "XAUUSD", "Prioridad": "⭐⭐", "Volatilidad": "Alta", "Horario": "8:30-10:30 am"},
    {"Categoría": "Commodities", "Activo": "Petróleo WTI", "Símbolo": "USOIL", "Prioridad": "⭐⭐", "Volatilidad": "Alta", "Horario": "8:30-10:30 am"},
    {"Categoría": "Cripto", "Activo": "Bitcoin", "Símbolo": "BTCUSD", "Prioridad": "⭐⭐", "Volatilidad": "Muy Alta", "Horario": "9:00-11:00 am"},
    {"Categoría": "Cripto", "Activo": "Ethereum", "Símbolo": "ETHUSD", "Prioridad": "⭐", "Volatilidad": "Muy Alta", "Horario": "9:00-11:00 am"},
    {"Categoría": "Referencia", "Activo": "DXY", "Símbolo": "DXY", "Prioridad": "⭐⭐⭐", "Volatilidad": "Media", "Horario": "6:00-11:00 am"},
    {"Categoría": "Referencia", "Activo": "VIX", "Símbolo": "VIX", "Prioridad": "⭐⭐⭐", "Volatilidad": "Variable", "Horario": "6:00-11:00 am"},
]

CORRELACIONES = [
    {"Activo": "DXY", "Positiva": "USDJPY (+0.85)", "Negativa": "EURUSD (-0.92)", "Fuerza": "Muy Alta"},
    {"Activo": "DXY", "Positiva": "—", "Negativa": "GBPUSD (-0.88)", "Fuerza": "Muy Alta"},
    {"Activo": "DXY", "Positiva": "—", "Negativa": "AUDUSD (-0.85)", "Fuerza": "Muy Alta"},
    {"Activo": "DXY", "Positiva": "—", "Negativa": "XAUUSD (-0.75)", "Fuerza": "Alta"},
    {"Activo": "VIX", "Positiva": "—", "Negativa": "SPX500 (-0.80)", "Fuerza": "Alta"},
    {"Activo": "VIX", "Positiva": "—", "Negativa": "NAS100 (-0.78)", "Fuerza": "Alta"},
    {"Activo": "US10Y", "Positiva": "DXY (+0.65)", "Negativa": "SPX500 (-0.70)", "Fuerza": "Media-Alta"},
    {"Activo": "US10Y", "Positiva": "—", "Negativa": "NAS100 (-0.75)", "Fuerza": "Alta"},
    {"Activo": "BTC", "Positiva": "ETH (+0.90), NAS100 (+0.65)", "Negativa": "DXY (-0.60)", "Fuerza": "Media"},
    {"Activo": "WTI", "Positiva": "CAD/JPY (+0.75)", "Negativa": "USD/CAD (-0.70)", "Fuerza": "Media-Alta"},
]

RUTINA_DIARIA = [
    {"Hora": "6:00-6:15 am", "Actividad": "Checklist Macro Rápido", "Activos": "DXY, VIX, US10Y", "Duración": "15 min"},
    {"Hora": "6:15-7:30 am", "Actividad": "Análisis Forex (Europa)", "Activos": "EURUSD, GBPUSD", "Duración": "75 min"},
    {"Hora": "7:30-8:30 am", "Actividad": "Transición NY + Preparación", "Activos": "Todos", "Duración": "60 min"},
    {"Hora": "8:30-9:30 am", "Actividad": "GOLDEN HOUR Opening NY", "Activos": "ES, NQ, SPX500", "Duración": "60 min"},
    {"Hora": "9:30-10:30 am", "Actividad": "Confirmación + Ejecución", "Activos": "Todos", "Duración": "60 min"},
    {"Hora": "10:30-11:30 am", "Actividad": "Gestión Posiciones + Cripto", "Activos": "XAU, BTC, ETH", "Duración": "60 min"},
    {"Hora": "11:30-12:00 pm", "Actividad": "Cierre + Journal", "Activos": "Todos", "Duración": "30 min"},
]

CHECKLIST_DSD_23 = [
    "DXY: ¿Dirección alineada con el setup?",
    "VIX: ¿Nivel <15 (calma) o >20 (miedo)?",
    "Calendario: ¿Sin noticias ⭐⭐⭐ (CPI/FOMC) próximamente?",
    "Estructura 1W: ¿Fase Wyckoff alineada?",
    "Estructura 1D: ¿Confirmada dirección semanal?",
    "Fase 1H: ¿Estamos en Fase C o D?",
    "Evento: ¿Detectado Spring, UTAD o Test VPOC?",
    "Volumen: ¿Absorción o clímax detectado en el giro?",
    "SOT: ¿Hay agotamiento de empujes (Shortening of Thrust)?",
    "Weis Wave: ¿Confirmado volumen institucional?",
    "VWAP: ¿Precio en zona de valor o rechazando?",
    "Entrada: ¿Nivel exacto (POI) definido?",
    "Stop Loss: ¿Bajo el Spring o nivel invalidante?",
    "TP1/TP2: ¿Ratio R:R mínimo 1:2.5?",
    "Riesgo: ¿Máximo 2% del capital en esta operación?",
    "Riesgo Diario: ¿Menos del 4% acumulado hoy?",
    "Riesgo Semanal: ¿Menos del 8% acumulado esta semana?",
    "Límite Trades: ¿Es mi 1er o 2do trade del día?",
    "Psicología: ¿Operando por análisis, no por emoción?",
    "Descanso: ¿Dormí >6h y estoy enfocado?",
    "Revancha: ¿No estoy intentando recuperar pérdidas?",
    "Mentalidad: 'Entro, Defiendo, Salgo' activada",
    "Confirmación Final: ¿Todos los anteriores marcados?"
]

CHECKLIST_POST_17 = [
    "Monitorea posición cada 15 min",
    "Verifica que SL esté activo en broker",
    "No mover SL en contra bajo ninguna circunstancia",
    "Revisar correlaciones cada hora (DXY/VIX)",
    "Si alcanza TP1 → cerrar 50% + mover SL a BE",
    "Anotar estado emocional actual",
    "Verificar que VIX no esté disparándose (>2 unidades)",
    "Revisar noticias macro imprevistas",
    "Si sucede algo inesperado → evaluar cierre manual",
    "No agregar a posición perdedora (NUNCA)",
    "Solo agregar si el plan técnico lo contempla",
    "Revisar horario (¿falta < 1h para las 12pm?)",
    "Si hay 2 pérdidas hoy → PARAR inmediatamente",
    "Actualizar riesgo diario consumido",
    "Verificar que HTF (1D/4H) siga alineado",
    "Anotar lecciones de gestión parcial",
    "Preparar trail stop (1.5x ATR) si está en beneficio"
]

CHECKLIST_CIERRE_16 = [
    "Cerrar TODAS las posiciones abiertas (Regla 12pm)",
    "Cancelar todas las órdenes pendientes",
    "Verificar que no hay exposición residual",
    "Registrar CADA trade en el Journal",
    "Anotar P&L del día ($ y %)",
    "Calcular riesgo diario final",
    "Verificar riesgo semanal acumulado",
    "¿Se respetó el plan dominical? (Sí/No)",
    "¿Se siguió el checklist pre-entrada? (Sí/No)",
    "Anotar estado emocional al cerrar sesión",
    "Identificar mejor trade (¿respetó Wyckoff?)",
    "Identificar peor trade (¿error emocional?)",
    "Lección principal para mañana",
    "Identificar activos para vigilar mañana",
    "Desconectar terminal y plataforma de trading",
    "Descanso mental (mínimo 30 min sin pantallas)"
]

GLOSARIO_COMPLETO = {
    "Acumulación": "Fase donde Smart Money compra silenciosamente antes de tendencia alcista.",
    "Distribución": "Fase donde Smart Money vende silenciosamente antes de tendencia bajista.",
    "Spring": "Ruptura falsa hacia abajo que atrapa vendedores antes de giro alcista.",
    "Upthrust / UTAD": "Ruptura falsa hacia arriba que atrapa compradores antes de giro bajista.",
    "VPOC": "Point of Control — Precio con mayor volumen en el perfil.",
    "VAL / VAH": "Value Area Low/High — Límites del área de valor (70% volumen).",
    "HVN": "High Volume Node — Zona de alta aceptación de precio.",
    "LVN": "Low Volume Node — Zona de rechazo esperado de precio.",
    "Creek": "Resistencia clave en estructura de acumulación.",
    "ICE": "Soporte clave en estructura de distribución.",
    "ATR": "Average True Range — Medidor de volatilidad.",
    "BU": "BackUp — Retroceso tras una señal de fuerza (SOS).",
    "CHoCH": "Change of Character — Primer indicio de cambio de tendencia.",
    "Delta": "Volumen comprador menos volumen vendedor.",
    "FTI": "Fall Through Ice — Caída a través del soporte de distribución.",
    "JAC": "Jump Across Creek — Salto sobre la resistencia de acumulación.",
    "LPS / LPSY": "Último Punto de Soporte / Último Punto de Oferta.",
    "SC / BC": "Selling Climax / Buying Climax.",
    "SOS / SOW": "Sign of Strength / Sign of Weakness.",
    "SOT": "Shortening of Thrust — Agotamiento de la tendencia.",
    "ST": "Secondary Test — Test secundario de la parada.",
    "TST": "Test del Spring o Upthrust.",
    "HTF / MTF": "Higher Timeframe / Multi-Timeframe.",
    "R:R": "Relación Riesgo : Beneficio.",
    "VP": "Volume Profile (Perfil de Volumen).",
    "NFP / CPI / FOMC": "Eventos macroeconómicos clave (Nóminas, Inflación, Tasas)."
}

_WYCKOFF_SYSTEM_V7 = """Eres el Intérprete Oficial del Wyckoff Structure Detector v7.
Analiza estrictamente los datos técnicos y genera una tabla markdown de 17 FILAS exacta.

FILAS OBLIGATORIAS:
1. Estructura: ▲ Acumulación / ▼ Distribución / Re-acumulación / Re-distribución
2. Esquema: #1 (con sacudida) / #2 (sin sacudida)
3. Fase: A, B, C, D o E
4. Último Evento: Spring, UTAD, SOS, SOW, BU, LPS, etc.
5. Sesgo: ▲ ALCISTA / ▼ BAJISTA / — NEUTRAL
6. Creek: Nivel de resistencia o status (✓ Roto)
7. ICE: Nivel de soporte o status (✓ Roto)
8. Weis Wave: Absorción ✓ / Normal
9. SOT: # empujes ⚠ / No detectado
10. HTF (Contexto superior): Alineación técnica con timeframe mayor
11. VP (Volume Profile): VPOC y Forma (P, b, D)
12. Delta: Lectura y Divergencias detectadas
13. Entrada: Agresiva / Principal / Conservadora / Esperar (incluir R:R)
14. Esfuerzo/Resultado: Armonía ✓ / Divergencia ⚠
15. Fortaleza: Barra visual y porcentaje (0-100%)
16. Alerta Crítica: Riesgo de manipulación o giro inminente
17. Nivel de Invalidez: Precio exacto de anulación de tesis

SCORING: Fase (30), Spring (15), Volumen (15), Weis (10), SOT (10), Armonía (10), MTF (10)."""

# ── 2. FUNCIONES DE RENDER──────────────────────────────────────────────────

def render_calculator():
    st.subheader("🛡️ Calculadora de Posición DSD")
    c1, c2 = st.columns(2)
    capital = c1.number_input("Capital Total ($)", value=10000.0, step=1000.0)
    risk_p = c2.slider("Riesgo (%)", 0.1, 5.0, 2.0)
    
    c3, c4 = st.columns(2)
    entry = c3.number_input("Precio Entrada", value=1.08500, format="%.5f")
    stop = c4.number_input("Precio Stop Loss", value=1.08200, format="%.5f")
    
    if entry != stop:
        risk_dist = abs(entry - stop)
        max_loss = capital * (risk_p / 100)
        # Suponiendo pip value en forex para demostración, o contratos directos
        position_size = max_loss / risk_dist
        
        st.success(f"**Pérdida Máxima:** ${max_loss:,.2f}")
        st.info(f"**Tamaño Sugerido:** {position_size:,.2f} unidades / contratos")
        st.caption(f"Distancia al SL: {risk_dist:,.5f} unidades")

def render_engine_v7():
    st.markdown("### 📊 Wyckoff v7 Indicator Intelligence")
    with st.form("engine_v7_form"):
        c1, c2, c3 = st.columns(3)
        symbol = c1.text_input("Activo", "EURUSD")
        tf = c2.selectbox("TF", ["15m", "1H", "4H", "1D"])
        price = c3.text_input("Precio", "1.1000")
        
        c4, c5, c6 = st.columns(3)
        struct = c4.selectbox("Estructura", ["Acumulación", "Distribución", "Cambiando"])
        phase = c5.selectbox("Fase", ["A", "B", "C", "D", "E"])
        event = c6.text_input("Evento", "Spring #3")
        
        c7, c8, c9 = st.columns(3)
        weis = c7.selectbox("Weis Wave", ["Absorción ✓", "Normal", "Débil"])
        sot = c8.selectbox("SOT", ["3+ empujes ⚠", "2 empujes", "Ninguno"])
        mtf = c9.selectbox("Alineación HTF", ["Alineado ✓", "Neutral", "Conflicto ⚠"])
        
        submitted = st.form_submit_button("🧠 ANALIZAR CON IA v7")
        
    if submitted:
        # Calcular score simplificado para feedback visual inmediato
        fase_pts = {"A":5, "B":10, "C":18, "D":25, "E":30}[phase]
        score = fase_pts + (15 if "Spring" in event else 5) + (10 if "Absorción" in weis else 0) + (10 if "3+" in sot else 0)
        
        prompt = f"Activo: {symbol} @ {tf} - Estructura: {struct}, Fase: {phase}, Evento: {event}, Weis: {weis}, SOT: {sot}, MTF: {mtf}. Fortaleza: {score}%"
        from ai_engine import generate
        res = generate(prompt, system=_WYCKOFF_SYSTEM_V7)
        if res:
            st.markdown(res)
            st.session_state["last_v7_analysis"] = {"phase": phase, "event": event, "fortaleza": score}

def render():
    st.markdown("<h2 style='text-align: center;'>📋 Plan de Trading Integral DSD v7</h2>", unsafe_allow_html=True)
    
    tabs = st.tabs([
        "👤 Perfil", "🎯 Activos", "🔗 Correlaciones", "🗓️ Rutina Dom", "📅 Rutina Diaria",
        "⚙️ Config", "📈 Criterios", "🛡️ Riesgo", "✅ Checklists", "📊 Engine v7",
        "🎯 Mercados", "📖 Ejemplos", "🗒️ Notas", "📚 Glosario"
    ])
    
    # 1. PERFIL
    with tabs[0]:
        st.subheader("1. Identidad Operativa")
        st.table(pd.DataFrame(PERFIL_TRADER))
    
    # 2. ACTIVOS
    with tabs[1]:
        st.subheader("2. Matriz de Activos (13)")
        st.dataframe(pd.DataFrame(ACTIVOS_PRIORIZADOS), use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("🎯 Enfoque Semanal (Máx 4)")
        st.multiselect("Selecciona tus 4 activos prioritarios:", [a["Símbolo"] for a in ACTIVOS_PRIORIZADOS], default=["ES / SPX500", "NQ / NAS100", "EURUSD", "XAUUSD"])

    # 3. CORRELACIONES
    with tabs[2]:
        st.subheader("3. Inter-dependencia de Mercados")
        st.dataframe(pd.DataFrame(CORRELACIONES), use_container_width=True, hide_index=True)
        st.info("**Reglas de Correlación:**\n1. DXY sube → Evitar LONGS en Forex/Oro.\n2. VIX > 20 → Reducir riesgo en Índices al 50%.\n3. US10Y Volátil → Precaución en NQ (Tecnológicas).\n4. BTC/NAS100 Divergencia → Esperar confirmación.")

    # 4. RUTINA DOMINICAL
    with tabs[3]:
        st.subheader("4. Análisis de Fin de Semana (2h)")
        c1, c2 = st.columns([1, 2])
        c1.markdown("**Horario:** 10:00 - 12:00 am (COL)")
        c1.table(pd.DataFrame([{"Fase": "1. Macro", "Mins": 30}, {"Fase": "2. Técnico", "Mins": 60}, {"Fase": "3. Plan", "Mins": 30}]))
        with c2:
            st.markdown("**Checklist Macro Semanal:**")
            st.checkbox("DXY Semanal: Tendencia y Nivel VAL/VAH")
            st.checkbox("VIX: Nivel (<15 Calma / >20 Miedo)")
            st.checkbox("US10Y: Cambio significativo (>0.20%)")
            st.checkbox("Calendario: Identificar CPI, FOMC, NFP")
        
        st.divider()
        st.markdown("#### Plan Semanal (Lunes - Viernes)")
        st.data_editor(pd.DataFrame([{"Día": d, "Activo": "", "Setup": "Pendiente"} for d in ["Lun", "Mar", "Mie", "Jue", "Vie"]]), use_container_width=True)

    # 5. RUTINA DIARIA
    with tabs[4]:
        st.subheader("5. Ciclo Operativo Diario")
        st.table(pd.DataFrame(RUTINA_DIARIA))
        st.info("**Golden Hour (8:30-9:30):** Foco máximo en apertura NY (ES/NQ).")

    # 6. CONFIGURACION
    with tabs[5]:
        st.subheader("6. Parámetros Técnicos v7")
        st.markdown("""
        | Parámetro | Swing | Intradía |
        |---|---|---|
        | Pivotes | 20 | 10 |
        | ATR | 20 | 14 |
        | Clímax | 2.5 | 2.0 |
        | VP Contexto | Weekly | Daily |
        """)
        st.divider()
        st.subheader("Interpretación del Dashboard")
        st.markdown("- **Estructura:** Define sesgo. ▲=Long / ▼=Short.\n- **Fase C/D:** Fases operativas. A/B=Espera.\n- **Weis Absorción:** Institucionales entrando ✓.\n- **Fortaleza >70%:** Alta probabilidad operativa.")

    # 7. CRITERIOS
    with tabs[6]:
        st.subheader("7. Patrones Wyckoff 2.0")
        with st.expander("PATRÓN 1: Spring (Acumulación Alcista)"):
            st.write("Cae bajo VAL con volumen < 80%. Entrada al recuperar rango.")
        with st.expander("PATRÓN 2: Upthrust (Distribución Bajista)"):
            st.write("Sube sobre VAH con volumen < 80%. Entrada al re-entrar al rango.")
        with st.expander("PATRÓN 3: Test VPOC (Continuación)"):
            st.write("Retroceso a zona de valor con volumen bajo. Gatillo en dirección tendencia.")

    # 8. RIESGO
    with tabs[7]:
        st.subheader("8. Gestión Institucional")
        c1, c2, c3 = st.columns(3)
        c1.markdown(kpi("Máx Trade", "2%", "Riesgo x capital", "blue"), unsafe_allow_html=True)
        c2.markdown(kpi("Máx Semanal", "8%", "Pausa obligatoria", "orange"), unsafe_allow_html=True)
        c3.markdown(kpi("Drawdown", "15%", "Hard Stop Cuenta", "red"), unsafe_allow_html=True)
        st.divider()
        render_calculator()

    # 9. CHECKLISTS
    with tabs[8]:
        st.subheader("9. Listas de Verificación (DSD)")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Pre-Entrada (23)**")
            for i in range(5): st.checkbox(CHECKLIST_DSD_23[i], key=f"pre_{i}")
            st.caption("... Ver todos en el manual")
        with c2:
            st.markdown("**Post-Entrada (17)**")
            for i in range(5): st.checkbox(CHECKLIST_POST_17[i], key=f"post_{i}")
        with c3:
            st.markdown("**Cierre (16)**")
            for i in range(5): st.checkbox(CHECKLIST_CIERRE_16[i], key=f"cie_{i}")

    # 10. ENGINE V7
    with tabs[9]:
        render_engine_v7()

    # 11. MERCADOS
    with tabs[10]:
        st.subheader("11. Contexto por Mercado")
        m = st.radio("Selecciona:", ["Forex", "Crypto", "Índices"], horizontal=True)
        if m == "Forex": st.write("Fases B largas. Sensible a noticias USD (DXY).")
        elif m == "Crypto": st.write("Volatilidad extrema. Springs agresivos. MTF es obligatorio.")
        else: st.write("Estructuras muy limpias. Sesión NY es la clave.")

    # 12. EJEMPLOS
    with tabs[11]:
        st.subheader("12. Simulaciones de Interpretación")
        st.info("Revisa la documentación v7 para 3 ejemplos detallados (EURUSD, BTC, SPX500).")

    # 13. NOTAS
    with tabs[12]:
        st.subheader("13. Bitácora Semanal")
        week_key = f"notes_{datetime.now().strftime('%Y_%W')}"
        notes = st.text_area("Notas / Análisis Personal", value=st.session_state.get(week_key, ""), height=300)
        if st.button("Guardar Notas"):
            st.session_state[week_key] = notes
            st.success("Notas guardadas para esta semana.")

    # 14. GLOSARIO
    with tabs[13]:
        st.subheader("14. Terminología Wyckoff")
        for k, v in GLOSARIO_COMPLETO.items():
            st.markdown(f"**{k}:** {v}")
