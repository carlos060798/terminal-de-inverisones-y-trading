"""
sections/alerts.py - Price Alerts section
Create, monitor, and manage price alerts against live yfinance data.
"""
import streamlit as st
import pandas as pd
import yfinance as yf
import database as db
from ui_shared import DARK, fmt, kpi


def _check_alerts(alerts_df: pd.DataFrame) -> list:
    """Check active (non-triggered) alerts against live prices.
    Returns list of dicts with alert info + current price for triggered ones."""
    triggered = []
    active = alerts_df[alerts_df["triggered"] == 0]
    if active.empty:
        return triggered

    unique_tickers = active["ticker"].unique().tolist()
    prices = {}
    for tk in unique_tickers:
        try:
            obj = yf.Ticker(tk)
            info = obj.info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
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
        <p>Configura alertas de precio y monitorea en tiempo real</p>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── CREATE ALERT FORM ─────────────────────────────────────────────────────
    st.markdown("<div class='sec-title'>Nueva Alerta</div>", unsafe_allow_html=True)
    try:
        with st.form("add_alert_form", clear_on_submit=True):
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                alert_ticker = st.text_input(
                    "Ticker", placeholder="AAPL", key="alert_ticker_input"
                )
            with ac2:
                alert_dir = st.selectbox(
                    "Dirección", ["above", "below"],
                    format_func=lambda x: "Por encima de" if x == "above" else "Por debajo de",
                    key="alert_dir_input",
                )
            with ac3:
                alert_threshold = st.number_input(
                    "Precio umbral ($)", min_value=0.01, value=100.0,
                    step=1.0, key="alert_threshold_input",
                )
            submitted = st.form_submit_button("Crear Alerta", type="primary")
            if submitted:
                if alert_ticker.strip():
                    try:
                        db.add_alert(alert_ticker.strip(), alert_dir, alert_threshold)
                        st.success(
                            f"Alerta creada: {alert_ticker.strip().upper()} "
                            f"{'por encima de' if alert_dir == 'above' else 'por debajo de'} "
                            f"${alert_threshold:,.2f}"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear alerta: {e}")
                else:
                    st.warning("Ingresa un ticker valido.")
    except Exception as e:
        st.info(f"No se pudo mostrar el formulario de alertas: {e}")

    # ── CHECK LIVE ALERTS ─────────────────────────────────────────────────────
    st.markdown("<div class='sec-title'>Monitoreo en Vivo</div>", unsafe_allow_html=True)
    try:
        alerts_df = db.get_alerts()
        if alerts_df.empty:
            st.info("No hay alertas configuradas. Crea una arriba para comenzar.")
            return

        if st.button("Verificar precios ahora", type="primary", key="check_alerts_btn"):
            with st.spinner("Consultando precios en vivo..."):
                newly_triggered = _check_alerts(alerts_df)

            if newly_triggered:
                for t in newly_triggered:
                    direction_label = "superado" if t["direction"] == "above" else "caido por debajo de"
                    st.warning(
                        f"**{t['ticker']}** ha {direction_label} "
                        f"${t['threshold']:,.2f} — Precio actual: ${t['price']:,.2f}"
                    )
                # Reload after marking
                alerts_df = db.get_alerts()
            else:
                st.success("Ninguna alerta activada. Precios verificados correctamente.")
    except Exception as e:
        st.info(f"No se pudo verificar alertas: {e}")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    try:
        alerts_df = db.get_alerts()
        total = len(alerts_df)
        active_count = len(alerts_df[alerts_df["triggered"] == 0])
        triggered_count = len(alerts_df[alerts_df["triggered"] == 1])

        k1, k2, k3 = st.columns(3)
        k1.markdown(kpi("Total Alertas", str(total), "", "blue"), unsafe_allow_html=True)
        k2.markdown(kpi("Activas", str(active_count), "", "green"), unsafe_allow_html=True)
        k3.markdown(kpi("Activadas", str(triggered_count), "", "purple"), unsafe_allow_html=True)
    except Exception as e:
        st.info(f"No se pudieron cargar KPIs de alertas: {e}")

    # ── ALERTS TABLE ──────────────────────────────────────────────────────────
    st.markdown("<div class='sec-title'>Todas las Alertas</div>", unsafe_allow_html=True)
    try:
        alerts_df = db.get_alerts()
        if not alerts_df.empty:
            display = alerts_df.copy()
            display["Dirección"] = display["direction"].apply(
                lambda x: "Por encima" if x == "above" else "Por debajo"
            )
            display["Estado"] = display["triggered"].apply(
                lambda x: "Activada" if x == 1 else "Activa"
            )
            display["Umbral"] = display["threshold"].apply(lambda x: f"${x:,.2f}")
            display.rename(columns={
                "ticker": "Ticker",
                "created_at": "Creada",
                "triggered_at": "Activada en",
            }, inplace=True)

            show_cols = ["id", "Ticker", "Dirección", "Umbral", "Estado", "Creada", "Activada en"]
            available_cols = [c for c in show_cols if c in display.columns]
            df_show = display[available_cols]

            def state_color(v):
                if v == "Activada":
                    return "background-color: rgba(251,191,36,0.15); color: #fbbf24"
                return "background-color: rgba(52,211,153,0.1); color: #34d399"

            st.dataframe(
                df_show.style.map(state_color, subset=["Estado"]),
                use_container_width=True, hide_index=True,
            )

            # ── DELETE ALERT ──
            with st.expander("Eliminar Alerta"):
                alert_ids = alerts_df["id"].tolist()
                alert_labels = [
                    f"ID {row['id']} — {row['ticker']} "
                    f"{'>' if row['direction'] == 'above' else '<'} "
                    f"${row['threshold']:,.2f}"
                    for _, row in alerts_df.iterrows()
                ]
                del_choice = st.selectbox(
                    "Selecciona alerta a eliminar", alert_labels, key="del_alert_sel"
                )
                if st.button("Eliminar", key="del_alert_btn"):
                    try:
                        idx = alert_labels.index(del_choice)
                        db.delete_alert(int(alert_ids[idx]))
                        st.success("Alerta eliminada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")
        else:
            st.info("No hay alertas para mostrar.")
    except Exception as e:
        st.info(f"No se pudo cargar la tabla de alertas: {e}")
