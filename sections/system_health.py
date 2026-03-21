"""
sections/system_health.py — System Health Dashboard
Shows API connectivity status, DB stats, and terminal version.
"""
import streamlit as st
import os
import time
from datetime import datetime
from ui_shared import kpi


VERSION = "5.0"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "investment_data.db")


def _check_yfinance():
    """Test yfinance connectivity."""
    try:
        import yfinance as yf
        t0 = time.time()
        tk = yf.Ticker("AAPL")
        _ = tk.fast_info.get("lastPrice", None) or tk.info.get("currentPrice")
        latency = int((time.time() - t0) * 1000)
        return True, latency
    except Exception:
        return False, 0


def _check_fred():
    """Test FRED API connectivity."""
    try:
        from fredapi import Fred
        key = st.secrets.get("FRED_API_KEY", "")
        if not key:
            return False, 0
        t0 = time.time()
        fred = Fred(api_key=key)
        fred.get_series("GS10", observation_start="2025-01-01")
        latency = int((time.time() - t0) * 1000)
        return True, latency
    except Exception:
        return False, 0


def _check_ai_providers():
    """Check which AI providers are available."""
    try:
        import ai_engine
        providers = ai_engine.get_available_providers()
        return providers
    except Exception:
        return []


def _db_stats():
    """Get database statistics."""
    import database as db
    conn = db.get_connection()
    stats = {}
    try:
        for table in ["trades", "stock_analyses", "pdf_analyses", "investment_notes", "forex_trades", "watchlist"]:
            try:
                cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cur.fetchone()[0]
            except Exception:
                stats[table] = 0
    finally:
        conn.close()
    return stats


def render():
    st.markdown("""
    <div class='top-header'>
      <h1>⚙️ Salud del Sistema</h1>
      <p>Estado de APIs, base de datos y conectividad</p>
    </div>""", unsafe_allow_html=True)

    # ── VERSION + TIMESTAMP ──
    c1, c2, c3 = st.columns(3)
    c1.markdown(kpi("Versión", f"v{VERSION}", "Quantum Retail Terminal", "blue"), unsafe_allow_html=True)
    c2.markdown(kpi("Sesión", datetime.now().strftime("%H:%M:%S"), datetime.now().strftime("%Y-%m-%d"), "purple"), unsafe_allow_html=True)
    db_size = os.path.getsize(DB_PATH) / 1024 if os.path.exists(DB_PATH) else 0
    c3.markdown(kpi("Base de Datos", f"{db_size:,.0f} KB", "investment_data.db", "green"), unsafe_allow_html=True)

    st.markdown("<div class='sec-title'>Conectividad de APIs</div>", unsafe_allow_html=True)

    # ── API CHECKS ──
    checks = []

    with st.spinner("Verificando yfinance…"):
        ok, lat = _check_yfinance()
        checks.append(("yfinance", "Datos de mercado", ok, lat))

    with st.spinner("Verificando FRED…"):
        ok, lat = _check_fred()
        checks.append(("FRED API", "Macro económico", ok, lat))

    with st.spinner("Verificando IA…"):
        ai_providers = _check_ai_providers()

    for name in ["Gemini", "Groq", "OpenRouter"]:
        is_ok = name.lower() in [p.lower() for p in ai_providers]
        checks.append((name, "Motor IA", is_ok, 0))

    # Display as table
    for name, category, ok, latency in checks:
        icon = "✅" if ok else "❌"
        lat_str = f" ({latency}ms)" if latency > 0 else ""
        color = "#34d399" if ok else "#f87171"
        status_text = "Conectado" if ok else "No disponible"
        st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:space-between;
                    padding:12px 16px;border-bottom:1px solid #1a1a1a;'>
          <div style='display:flex;align-items:center;gap:12px;'>
            <span style='font-size:18px;'>{icon}</span>
            <div>
              <div style='color:#f0f6ff;font-weight:600;font-size:14px;'>{name}</div>
              <div style='color:#5a6f8a;font-size:11px;'>{category}</div>
            </div>
          </div>
          <div style='text-align:right;'>
            <div style='color:{color};font-weight:600;font-size:13px;'>{status_text}{lat_str}</div>
          </div>
        </div>""", unsafe_allow_html=True)

    # ── DB STATS ──
    st.markdown("<div class='sec-title'>Estadísticas de Base de Datos</div>", unsafe_allow_html=True)

    stats = _db_stats()
    cols = st.columns(3)
    stat_items = [
        ("Trades", stats.get("trades", 0), "blue"),
        ("Análisis PDF", stats.get("pdf_analyses", 0), "purple"),
        ("Análisis Stock", stats.get("stock_analyses", 0), "green"),
        ("Tesis", stats.get("investment_notes", 0), "blue"),
        ("Forex Trades", stats.get("forex_trades", 0), "purple"),
        ("Watchlist", stats.get("watchlist", 0), "green"),
    ]
    for i, (label, count, color) in enumerate(stat_items):
        cols[i % 3].markdown(kpi(label, str(count), "registros", color), unsafe_allow_html=True)

    # ── SESSION STATE ──
    st.markdown("<div class='sec-title'>Estado de Sesión</div>", unsafe_allow_html=True)
    active = st.session_state.get("active_ticker", "—")
    st.markdown(f"""
    <div style='background:#0a0a0a;border:1px solid #1a1a1a;border-radius:14px;padding:16px;'>
      <div style='display:flex;gap:40px;'>
        <div><span style='color:#5a6f8a;font-size:11px;text-transform:uppercase;'>Ticker Activo</span><br>
             <span style='color:#60a5fa;font-size:18px;font-weight:700;'>{active if active else '—'}</span></div>
        <div><span style='color:#5a6f8a;font-size:11px;text-transform:uppercase;'>Keys en Session</span><br>
             <span style='color:#f0f6ff;font-size:18px;font-weight:700;'>{len(st.session_state)}</span></div>
      </div>
    </div>""", unsafe_allow_html=True)
