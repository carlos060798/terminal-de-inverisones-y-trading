"""sections/quantum_ai.py - Quantum Intelligence Assistant."""

import streamlit as st
import datetime
import database as db
import yfinance as yf
from ui_shared import DARK, kpi

# from services.text_service import answer_financial_question  # Move to lazy import to avoid circular dep
from services.news_engine import fetch_ticker_news
from sections.macro_context import _fred_yield_curve, _yf_yield_curve

# --- DISPATCHER & INTENT ENGINE ---

def _classify_intent(query: str) -> str:
    ql = query.lower()
    if any(k in ql for k in ["macro", "fed", "vix", "cpi", "yield", "economía", "tasas"]):
        return "macro"
    if any(k in ql for k in ["noticias", "news", "titular", "rumor"]):
        return "news"
    if any(k in ql for k in ["ratio", "p/e", "scanner", "fundamental", "balance", "eps"]):
        return "scanner"
    return "full"

def _build_context(intent: str, ticker: str = None, topic: str = None) -> str:
    ctx_parts = []
    
    # 1. Macro Data
    if intent in ["macro", "full"]:
        try:
            yc = _fred_yield_curve() or _yf_yield_curve()
            if yc:
                ctx_parts.append(f"YIELD CURVE (Spread 10y-2y): {yc['spread_10y_2y']:.2f}% ({yc['status']})")
        except: pass
        
    # 2. News Data
    if intent in ["news", "full"]:
        try:
            news = fetch_ticker_news(ticker or topic, hours_back=24)
            if news:
                headlines = [f"- {n.title} ({n.source})" for n in news[:5]]
                ctx_parts.append("LATEST NEWS (24h):\n" + "\n".join(headlines))
            else:
                ctx_parts.append("No recent news found.")
        except: pass
        
    # 3. Fundamental Ratios (yfinance)
    if intent in ["scanner", "full"] and ticker:
        try:
            tk_obj = yf.Ticker(ticker)
            info = tk_obj.info
            ratio_keys = ['trailingPE', 'forwardPE', 'pegRatio', 'priceToSalesTrailing12Months',
                          'priceToBook', 'returnOnEquity', 'returnOnAssets', 'debtToEquity',
                          'shortRatio', 'currentPrice', 'targetMeanPrice']
            scan_lines = []
            for k in ratio_keys:
                v = info.get(k)
                if v is not None:
                    scan_lines.append(f"- {k}: {v}")
            if scan_lines:
                ctx_parts.append(f"FUNDAMENTAL SCAN ({ticker}):\n" + "\n".join(scan_lines))
        except: pass

    return "\n\n".join(ctx_parts)

def _dispatch(query: str, ticker: str = None):
    with st.spinner("Quantum IA procesando..."):
        # Lazy import of answer_financial_question
        from services.text_service import answer_financial_question
        intent = _classify_intent(query)
        context = _build_context(intent, ticker=ticker, topic=query)
        ans, pid = answer_financial_question(query, context, ticker)
        return ans, pid

# --- UI SECTIONS ---

def _render_chat_section():
    st.markdown("""
        <style>
        .terminal-container {
            background-color: #000000;
            border: 2px solid #333333;
            border-radius: 4px;
            padding: 20px;
            font-family: 'Courier New', Courier, monospace;
            color: #00ff00;
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.1);
            margin-bottom: 20px;
            min-height: 400px;
        }
        .terminal-msg-user { color: #ffffff; border-left: 3px solid #60a5fa; padding-left: 10px; margin-bottom: 15px; }
        .terminal-msg-ai { color: #00ff00; border-left: 3px solid #00ff00; padding-left: 10px; margin-bottom: 25px; }
        .terminal-model-tag { font-size: 10px; color: #666666; text-transform: uppercase; margin-top: 5px; }
        .suggestion-btn {
            background: #111111 !important;
            border: 1px solid #333333 !important;
            color: #888888 !important;
            font-size: 12px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='sec-title'>> QUANTUM_TERMINAL_V1.0.4 // AI_CORE</div>", unsafe_allow_html=True)
    
    if "quantum_chat" not in st.session_state:
        st.session_state["quantum_chat"] = []

    # Terminal Logic for Chat History
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state["quantum_chat"]:
            role_cls = "terminal-msg-user" if msg["role"] == "user" else "terminal-msg-ai"
            prefix = "USER>" if msg["role"] == "user" else "AGENT>"
            
            st.markdown(f"""
            <div class='{role_cls}'>
                <div style='font-weight:bold; font-size:12px; margin-bottom:4px;'>{prefix}</div>
                <div style='font-size:14px; line-height:1.5;'>{msg["content"]}</div>
                {f"<div class='terminal-model-tag'>Engine: {msg['model']}</div>" if 'model' in msg else ""}
            </div>
            """, unsafe_allow_html=True)

    # Quick suggestions
    st.markdown("<div style='margin-bottom:10px; font-size:10px; color:#444;'>COMMAND_PRESETS:</div>", unsafe_allow_html=True)
    sg1, sg2, sg3 = st.columns(3)
    if sg1.button("EX_MACRO_DAILY", use_container_width=True):
        st.session_state.quantum_query = "¿Cuál es el resumen macroeconómico del día?"
    if sg2.button("SCAN_TECH_NEWS", use_container_width=True):
        st.session_state.quantum_query = "Dame las últimas noticias del sector tech"
    if sg3.button("DEEP_SCAN_AAPL", use_container_width=True):
        st.session_state.quantum_query = "Haz un escáner fundamental completo de AAPL"

    # Input Area
    input_col = st.container()
    query = st.chat_input("READY FOR INPUT...", key="q_chat")
    
    # Process Quick logic
    if st.session_state.get("quantum_query"):
        query = st.session_state.quantum_query
        st.session_state.quantum_query = None

    if query:
        st.session_state["quantum_chat"].append({"role": "user", "content": query})
        st.rerun()

    # Dispatch logic (if the last message is from user)
    if st.session_state["quantum_chat"] and st.session_state["quantum_chat"][-1]["role"] == "user":
        last_query = st.session_state["quantum_chat"][-1]["content"]
        
        # Local model override for Quantum Chat
        local_model = st.sidebar.selectbox("🤖 Engine Override", 
            ["Auto-Balanceador", "groq-llama", "deepseek-reasoner", "deepseek-chat", "openai-4o", "openai-4o-mini", "gemini-2.5-flash-preview-04-17", "or-qwen", "or-deepseek"],
            index=0)
            
        if local_model != "Auto-Balanceador":
            st.session_state["force_llm"] = local_model
            
        ans, pid = _dispatch(last_query)
        
        st.session_state["quantum_chat"].append({"role": "assistant", "content": ans, "model": pid})
        st.rerun()


def _render_quick_scan_section():
    st.markdown("<div class='sec-title'>Modo Experto: Quick Scan</div>", unsafe_allow_html=True)
    st.info("Obtén análisis estructurados extraídos directamente de las fuentes maestras.")

    col1, col2 = st.columns([1, 2])
    with col1:
        tk = st.text_input("Ticker objetivo", placeholder="ej. NVDA").upper()
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        q1, q2, q3, q4 = st.columns(4)
        do_ratios = q1.button("📊 Ratios FinViz", use_container_width=True)
        do_news = q2.button("📰 Noticias (48h)", use_container_width=True)
        do_macro = q3.button("🌍 Contexto Macro", use_container_width=True)
        do_full = q4.button("🤖 Análisis Total IA", type="primary", use_container_width=True)

    if not tk and (do_ratios or do_news or do_full):
        st.warning("Debes introducir un ticker para escaneo de empresa.")
        return

    if do_ratios:
        with st.spinner("Extrayendo ratios fundamentales..."):
            try:
                tk_obj = yf.Ticker(tk)
                info = tk_obj.info
                ratios = {
                    "P/E": info.get("trailingPE"),
                    "Forward P/E": info.get("forwardPE"),
                    "PEG": info.get("pegRatio"),
                    "P/S": info.get("priceToSalesTrailing12Months"),
                    "P/B": info.get("priceToBook"),
                    "EV/EBITDA": info.get("enterpriseToEbitda"),
                    "ROE": f"{(info.get('returnOnEquity') or 0)*100:.1f}%",
                    "ROA": f"{(info.get('returnOnAssets') or 0)*100:.1f}%",
                    "Debt/Eq": info.get("debtToEquity"),
                    "Current Ratio": info.get("currentRatio"),
                    "Profit Margin": f"{(info.get('profitMargins') or 0)*100:.1f}%",
                    "Revenue Growth": f"{(info.get('revenueGrowth') or 0)*100:.1f}%",
                    "Div Yield": f"{(info.get('dividendYield') or 0)*100:.2f}%",
                    "Short Ratio": info.get("shortRatio"),
                    "Target Price": f"${info.get('targetMeanPrice', 0):.2f}",
                    "RSI (14)": "—",
                    "Beta": info.get("beta"),
                }
                # Render as premium visual cards
                cards_html = "<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:15px;'>"
                for label, val in ratios.items():
                    if val is None:
                        val = "—"
                    val_str = f"{val:.2f}" if isinstance(val, float) else str(val)
                    cards_html += f"""
                    <div style='background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px;text-align:center;'>
                        <div style='color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:0.5px;'>{label}</div>
                        <div style='color:#f0f6fc;font-size:18px;font-weight:800;margin-top:4px;'>{val_str}</div>
                    </div>"""
                cards_html += "</div>"
                st.markdown(cards_html, unsafe_allow_html=True)
                st.caption(f"📡 Fuente: Yahoo Finance (yfinance) · {tk}")
            except Exception as e:
                st.error(f"No se pudo obtener datos del ticker: {e}")

    if do_news:
        with st.spinner("Escaneando feeds RSS..."):
            news = fetch_ticker_news(tk)
            for n in news[:8]:
                st.markdown(f"- **{n.source}**: [{n.title}]({n.link})")

    if do_macro:
        with st.spinner("Consolidando contexto macro..."):
            ctx = _build_context("macro")
            st.code(ctx, language="text")

    if do_full:
        ans, pid = _dispatch(f"Hazme un resumen ejecutivo de {tk}", ticker=tk)
        st.success(f"Análisis Completado (Modelo: {pid})")
        st.markdown(ans)

# --- MAIN RENDER ---

def render():
    st.markdown("<h1 style='text-align: center; color: #60a5fa;'>🧠 Quantum Intelligence Assistant</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8; margin-bottom: 30px;'>Orquestación Multi-Agente · Datos en Tiempo Real · Fallover Inteligente</p>", unsafe_allow_html=True)

    t1, t2 = st.tabs(["💬 Quantum Chat", "⚡ Quick Scan"])
    with t1:
        _render_chat_section()
    with t2:
        _render_quick_scan_section()
