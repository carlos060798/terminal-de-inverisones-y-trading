"""
sections/alerts.py - Price Alerts section
Create, monitor, and manage price alerts against live yfinance data.
"""
import streamlit as st
import pandas as pd
import yfinance as yf
import database as db
from datetime import datetime
from ui_shared import DARK, fmt, kpi

def _check_alerts(alerts_df: pd.DataFrame) -> list:
    """Check active (non-triggered) alerts against live prices."""
    triggered = []
    now_hour = datetime.now().hour
    
    def _is_in_session(session_name, hour):
        if session_name == "Any": return True
        if session_name == "Londres" and 3 <= hour < 8: return True
        if session_name == "Nueva York" and 8 <= hour < 16: return True
        if session_name == "Tokio" and (20 <= hour <= 23 or hour == 0): return True
        return False

    active = alerts_df[alerts_df["triggered"] == 0].copy()
    if active.empty:
        return triggered

    active["in_session"] = active["session"].apply(lambda s: _is_in_session(s, now_hour))
    active = active[active["in_session"]]
    
    if active.empty:
        return triggered

    unique_tickers = active["ticker"].unique().tolist()
    prices = {}
    for tk in unique_tickers:
        try:
            obj = yf.Ticker(tk)
            # Fast price check
            price = obj.fast_info.get("last_price")
            if price:
                prices[tk] = price
        except Exception:
            continue

    for _, row in active.iterrows():
        tk = row["ticker"]
        if tk not in prices:
            continue
        price = prices[tk]
        hit = False
        if row["direction"] == "above" and price >= row["threshold"]:
            hit = True
        elif row["direction"] == "below" and price <= row["threshold"]:
            hit = True

        if hit:
            try:
                db.mark_triggered(int(row["id"]))
            except Exception:
                pass
            triggered.append({
                "id": row["id"],
                "ticker": tk,
                "direction": row["direction"],
                "threshold": row["threshold"],
                "price": price,
            })
    return triggered

def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Price Alerts</h1>
        <p>Configura alertas de precio para monitoreo local</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── CREATE ALERT FORM ─────────────────────────────────────────────────────
    st.markdown("<div class='sec-title'>Nueva Alerta</div>", unsafe_allow_html=True)
    with st.form("add_alert_form", clear_on_submit=True):
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            alert_ticker = st.text_input("Ticker", placeholder="AAPL")
        with ac2:
            alert_dir = st.selectbox("Dirección", ["above", "below"],
                                    format_func=lambda x: "Por encima de" if x == "above" else "Por debajo de")
        with ac3:
            alert_threshold = st.number_input("Precio umbral ($)", min_value=0.01, value=100.0, step=1.0)
        
        ac4, _ = st.columns([1, 2])
        with ac4:
            alert_sess = st.selectbox("Sesión Activa", ["Any", "Londres", "Nueva York", "Tokio"])
            
        submitted = st.form_submit_button("Crear Alerta", type="primary", use_container_width=True)
        if submitted and alert_ticker.strip():
            p_id = st.session_state.get("active_portfolio_id", 1)
            db.add_alert(alert_ticker.strip().upper(), alert_dir, alert_threshold, alert_sess, portfolio_id=p_id)
            st.success("Alerta creada con éxito.")
            st.rerun()

    # ── CHECK LIVE ALERTS ─────────────────────────────────────────────────────
    st.markdown("<div class='sec-title'>Monitoreo en Vivo</div>", unsafe_allow_html=True)
    p_id = st.session_state.get("active_portfolio_id", 1)
    alerts_df = db.get_alerts(portfolio_id=p_id)
    
    if not alerts_df.empty:
        if st.button("Verificar precios ahora", type="primary"):
            with st.spinner("Consultando yfinance..."):
                newly_triggered = _check_alerts(alerts_df)

            if newly_triggered:
                for t in newly_triggered:
                    direction_label = "superado" if t["direction"] == "above" else "caido por debajo de"
                    st.warning(f"**{t['ticker']}** ha {direction_label} ${t['threshold']:,.2f} — actual: ${t['price']:,.2f}")
                st.rerun()
            else:
                st.success("Ninguna alerta activada.")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    if not alerts_df.empty:
        total = len(alerts_df)
        active_count = len(alerts_df[alerts_df["triggered"] == 0])
        triggered_count = total - active_count

        k1, k2, k3 = st.columns(3)
        k1.markdown(kpi("Total Alertas", str(total), "", "blue"), unsafe_allow_html=True)
        k2.markdown(kpi("Activas", str(active_count), "", "green"), unsafe_allow_html=True)
        k3.markdown(kpi("Activadas", str(triggered_count), "", "purple"), unsafe_allow_html=True)

    # ── ALERTS TABLE ──────────────────────────────────────────────────────────
    st.markdown("<div class='sec-title'>Todas las Alertas</div>", unsafe_allow_html=True)
    if not alerts_df.empty:
        display = alerts_df.copy()
        display["Dirección"] = display["direction"].apply(lambda x: "Por encima" if x == "above" else "Por debajo")
        display["Estado"] = display["triggered"].apply(lambda x: "Activada" if x == 1 else "Activa")
        display["Umbral"] = display["threshold"].apply(lambda x: f"${x:,.2f}")
        
        show_cols = ["id", "ticker", "Dirección", "Umbral", "session", "Estado", "created_at"]
        df_show = display[show_cols].rename(columns={"ticker": "Ticker", "session": "Sesión", "created_at": "Creada"})

        def state_color(v):
            if v == "Activada": return "background-color: rgba(251,191,36,0.15); color: #fbbf24"
            return "background-color: rgba(52,211,153,0.1); color: #34d399"

        st.dataframe(df_show.style.map(state_color, subset=["Estado"]), use_container_width=True, hide_index=True)

        with st.expander("Eliminar Alerta"):
            del_id = st.number_input("ID de la alerta a eliminar", min_value=1, step=1)
            if st.button("Eliminar", type="secondary"):
                db.delete_alert(int(del_id))
                st.success(f"Alerta {del_id} eliminada.")
                st.rerun()
    else:
        st.info("No hay alertas configuradas.")
