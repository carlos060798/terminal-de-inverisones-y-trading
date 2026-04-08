"""
sections/alerts.py - Price Alerts section
Create, monitor, and manage price alerts against live yfinance data.
"""
import streamlit as st
import pandas as pd
import yfinance as yf
import database as db
from ui_shared import DARK, fmt, kpi


def _send_telegram(message, bot_token, chat_id):
    """Send message via Telegram Bot API — no dependencies needed."""
    try:
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        try:
            r = requests.post(url, data=data, timeout=5)
            return r.json().get("ok", False)
        except Exception:
            return False
    except Exception:
        return False


def _check_alerts(alerts_df: pd.DataFrame) -> list:
    """Check active (non-triggered) alerts against live prices.
    Returns list of dicts with alert info + current price for triggered ones."""
    triggered = []
    # Time check for sessions (Colombia COT, UTC-5)
    now_hour = datetime.now().hour
    
    def _is_in_session(session_name, hour):
        if session_name == "Any": return True
        if session_name == "Londres" and 3 <= hour < 8: return True
        if session_name == "Nueva York" and 8 <= hour < 16: return True
        if session_name == "Tokio" and (20 <= hour <= 23 or hour == 0): return True
        return False

    active = alerts_df[alerts_df["triggered"] == 0]
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
            
            ac4, _ = st.columns([1, 2])
            with ac4:
                alert_sess = st.selectbox(
                    "Sesión Activa", ["Any", "Londres", "Nueva York", "Tokio"],
                    index=0, key="alert_session_input"
                )
                
            submitted = st.form_submit_button("Crear Alerta", type="primary", use_container_width=True)
            if submitted:
                if alert_ticker.strip():
                    try:
                        db.add_alert(alert_ticker.strip().upper(), alert_dir, alert_threshold, alert_sess)
                        st.success(
                            f"Alerta creada: {alert_ticker.strip().upper()} "
                            f"{'por encima de' if alert_dir == 'above' else 'por debajo de'} "
                            f"${alert_threshold:,.2f} [Sesión: {alert_sess}]"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear alerta: {e}")
                else:
                    st.warning("Ingresa un ticker valido.")
    except Exception as e:
        st.info(f"No se pudo mostrar el formulario de alertas: {e}")

    # ── TELEGRAM CONFIG ────────────────────────────────────────────────────────
    try:
        with st.expander("⚙️ Configurar Telegram"):
            bot_token = st.text_input("Bot Token", type="password",
                                       value=st.session_state.get('telegram_bot_token', ''))
            chat_id = st.text_input("Chat ID",
                                     value=st.session_state.get('telegram_chat_id', ''))
            if st.button("Guardar config Telegram"):
                st.session_state.telegram_bot_token = bot_token
                st.session_state.telegram_chat_id = chat_id
                st.success("Config guardada")
            if st.button("Enviar test"):
                try:
                    result = _send_telegram("🧪 Test desde Quantum Terminal", bot_token, chat_id)
                    if result:
                        st.success("Mensaje de test enviado correctamente.")
                    else:
                        st.error("No se pudo enviar el mensaje. Verifica token y chat ID.")
                except Exception as e:
                    st.error(f"Error enviando test: {e}")
    except Exception as e:
        st.info(f"No se pudo mostrar config Telegram: {e}")

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
                    # Send Telegram notification if configured
                    try:
                        tg_token = st.session_state.get('telegram_bot_token', '')
                        tg_chat = st.session_state.get('telegram_chat_id', '')
                        if tg_token and tg_chat:
                            cond = "Por encima de" if t["direction"] == "above" else "Por debajo de"
                            msg = (
                                f"🔔 <b>ALERTA ACTIVADA</b>\n"
                                f"Ticker: {t['ticker']}\n"
                                f"Precio: ${t['price']:,.2f}\n"
                                f"Condición: {cond} ${t['threshold']:,.2f}"
                            )
                            _send_telegram(msg, tg_token, tg_chat)
                    except Exception:
                        pass
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

            show_cols = ["id", "Ticker", "Dirección", "Umbral", "session", "Estado", "Creada"]
            available_cols = [c for c in show_cols if c in display.columns]
            df_show = display[available_cols]
            df_show.rename(columns={"session": "Sesión"}, inplace=True)

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
