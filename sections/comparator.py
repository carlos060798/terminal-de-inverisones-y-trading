"""
sections/comparator.py - Stock Comparator
Compare 2-4 tickers side-by-side: KPIs, normalized price chart, radar chart.
"""
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ui_shared import DARK, dark_layout, fmt, kpi


# ── Color palette for compared tickers ────────────────────────────────────────
COLORS = ["#60a5fa", "#34d399", "#a78bfa", "#fbbf24"]


def _safe_get(info, key, default=None):
    """Safely get a value from yfinance info dict."""
    try:
        v = info.get(key, default)
        if v is None:
            return default
        return v
    except Exception:
        return default


def _compute_radar_scores(info):
    """
    Compute 5 radar dimensions (0-100 scale) from fundamentals.
    Dimensions: Value, Growth, Profitability, Safety, Dividend.
    """
    scores = {}

    # VALUE (lower P/E and P/B = higher score)
    pe = _safe_get(info, "trailingPE", 30)
    pb = _safe_get(info, "priceToBook", 5)
    pe_score = max(0, min(100, (50 - pe) * 2.5)) if pe else 25
    pb_score = max(0, min(100, (5 - pb) * 20)) if pb else 25
    scores["Value"] = (pe_score + pb_score) / 2

    # GROWTH (revenue growth + earnings growth)
    rev_g = (_safe_get(info, "revenueGrowth", 0) or 0) * 100
    earn_g = (_safe_get(info, "earningsGrowth", 0) or 0) * 100
    scores["Growth"] = max(0, min(100, (rev_g + earn_g) / 2 * 2))

    # PROFITABILITY (profit margin + ROE)
    pm = (_safe_get(info, "profitMargins", 0) or 0) * 100
    roe = (_safe_get(info, "returnOnEquity", 0) or 0) * 100
    scores["Profitability"] = max(0, min(100, (pm * 1.5 + roe * 1.0) / 2))

    # SAFETY (current ratio + low debt/equity)
    cr = _safe_get(info, "currentRatio", 1) or 1
    de = _safe_get(info, "debtToEquity", 100) or 100
    cr_score = max(0, min(100, cr * 33))
    de_score = max(0, min(100, (200 - de) / 2))
    scores["Safety"] = (cr_score + de_score) / 2

    # DIVIDEND
    dy = (_safe_get(info, "dividendYield", 0) or 0) * 100
    pr = (_safe_get(info, "payoutRatio", 0) or 0) * 100
    dy_score = max(0, min(100, dy * 20))
    pr_score = max(0, min(100, pr)) if 0 < pr < 80 else max(0, 50 - abs(pr - 40))
    scores["Dividend"] = (dy_score * 0.6 + pr_score * 0.4)

    # Clamp all values
    for k in scores:
        scores[k] = max(0, min(100, scores[k]))

    return scores


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Comparador de Acciones</h1>
        <p>Compara fundamentales, precio normalizado y perfil radar de 2-4 tickers</p>
      </div>
    </div>""", unsafe_allow_html=True)

    try:
        # ── Ticker selection ──────────────────────────────────────────
        default_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
        selected = st.multiselect(
            "Selecciona 2-4 tickers para comparar",
            options=[],
            default=[],
            placeholder="Escribe tickers separados (ej: AAPL, MSFT, GOOGL)",
            key="comparator_tickers",
        )

        # Allow free-form input since multiselect with empty options won't work well
        ticker_input = st.text_input(
            "Tickers a comparar (separados por coma)",
            value="AAPL, MSFT, GOOGL",
            key="comparator_input",
        )
        tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

        if len(tickers) < 2:
            st.warning("Ingresa al menos 2 tickers separados por coma.")
            return
        if len(tickers) > 4:
            st.warning("Maximo 4 tickers. Se usaran los primeros 4.")
            tickers = tickers[:4]

        if not st.button("Comparar", type="primary", key="comp_btn"):
            st.info("Haz clic en 'Comparar' para iniciar el analisis.")
            return

        # ── Fetch data ────────────────────────────────────────────────
        infos = {}
        histories = {}

        with st.spinner("Descargando datos de mercado..."):
            for t in tickers:
                try:
                    obj = yf.Ticker(t)
                    infos[t] = obj.info
                    hist = obj.history(period="1y")
                    if not hist.empty:
                        histories[t] = hist
                except Exception:
                    st.warning(f"No se pudieron obtener datos para {t}")

        valid_tickers = [t for t in tickers if t in infos and t in histories]
        if len(valid_tickers) < 2:
            st.error("No se pudieron obtener datos suficientes. Verifica los tickers.")
            return

        # ══════════════════════════════════════════════════════════════
        # SECTION 1: KPI CARDS SIDE-BY-SIDE
        # ══════════════════════════════════════════════════════════════
        st.markdown("<div class='sec-title'>Fundamentales Clave</div>", unsafe_allow_html=True)

        cols = st.columns(len(valid_tickers))
        for i, t in enumerate(valid_tickers):
            info = infos[t]
            color = ["blue", "green", "purple", "blue"][i]
            with cols[i]:
                st.markdown(
                    f"<div style='text-align:center;font-size:16px;font-weight:800;"
                    f"color:{COLORS[i]};margin-bottom:12px;'>{t}</div>",
                    unsafe_allow_html=True,
                )

                price = _safe_get(info, "currentPrice") or _safe_get(info, "regularMarketPrice", 0)
                st.markdown(kpi("Precio", f"${price:,.2f}" if price else "N/A", "", color), unsafe_allow_html=True)

                pe = _safe_get(info, "trailingPE")
                st.markdown(kpi("P/E", f"{pe:.1f}" if pe else "N/A", "", color), unsafe_allow_html=True)

                fpe = _safe_get(info, "forwardPE")
                st.markdown(kpi("Forward P/E", f"{fpe:.1f}" if fpe else "N/A", "", color), unsafe_allow_html=True)

                pb = _safe_get(info, "priceToBook")
                st.markdown(kpi("P/B", f"{pb:.2f}" if pb else "N/A", "", color), unsafe_allow_html=True)

                roe = _safe_get(info, "returnOnEquity")
                st.markdown(kpi("ROE", f"{roe*100:.1f}%" if roe else "N/A", "", color), unsafe_allow_html=True)

                pm = _safe_get(info, "profitMargins")
                st.markdown(kpi("Margen Neto", f"{pm*100:.1f}%" if pm else "N/A", "", color), unsafe_allow_html=True)

                mc = _safe_get(info, "marketCap")
                st.markdown(kpi("Market Cap", fmt(mc) if mc else "N/A", "", color), unsafe_allow_html=True)

                dy = _safe_get(info, "dividendYield")
                st.markdown(kpi("Div Yield", f"{dy*100:.2f}%" if dy else "0%", "", color), unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════
        # SECTION 2: NORMALIZED PRICE CHART
        # ══════════════════════════════════════════════════════════════
        st.markdown("<div class='sec-title'>Precio Normalizado (Base 100 — 1 Ano)</div>", unsafe_allow_html=True)

        fig_norm = go.Figure()
        for i, t in enumerate(valid_tickers):
            hist = histories[t]
            close = hist["Close"]
            if hasattr(close, "columns"):
                close = close.iloc[:, 0]
            normalized = (close / close.iloc[0]) * 100
            fig_norm.add_trace(go.Scatter(
                x=normalized.index,
                y=normalized,
                name=t,
                mode="lines",
                line=dict(color=COLORS[i], width=2),
            ))

        fig_norm.add_hline(y=100, line_dash="dot", line_color="#475569", line_width=0.8)
        fig_norm.update_layout(
            **DARK,
            height=450,
            title=dict(
                text="Rendimiento Normalizado (Base 100)",
                font=dict(color="#94a3b8", size=14),
                x=0.5,
            ),
            yaxis_title="Valor normalizado",
            legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a"),
            hovermode="x unified",
        )
        st.plotly_chart(fig_norm, use_container_width=True)

        # ── Return summary table ──
        summary_rows = []
        for t in valid_tickers:
            hist = histories[t]
            close = hist["Close"]
            if hasattr(close, "columns"):
                close = close.iloc[:, 0]
            ret_1y = (close.iloc[-1] / close.iloc[0] - 1) * 100
            vol = close.pct_change().std() * np.sqrt(252) * 100
            max_val = close.cummax()
            dd = ((close - max_val) / max_val * 100).min()
            summary_rows.append({
                "Ticker": t,
                "Retorno 1Y %": round(ret_1y, 2),
                "Volatilidad %": round(vol, 2),
                "Max Drawdown %": round(dd, 2),
            })

        sum_df = pd.DataFrame(summary_rows)
        st.dataframe(
            sum_df.style.map(
                lambda v: "color:#34d399" if isinstance(v, (int, float)) and v > 0 else "color:#f87171",
                subset=["Retorno 1Y %"],
            ).format({
                "Retorno 1Y %": "{:+.2f}%",
                "Volatilidad %": "{:.2f}%",
                "Max Drawdown %": "{:.2f}%",
            }),
            use_container_width=True,
            hide_index=True,
        )

        # ══════════════════════════════════════════════════════════════
        # SECTION 3: RADAR CHART
        # ══════════════════════════════════════════════════════════════
        st.markdown("<div class='sec-title'>Perfil Radar — Fundamentales</div>", unsafe_allow_html=True)

        categories = ["Value", "Growth", "Profitability", "Safety", "Dividend"]

        fig_radar = go.Figure()
        for i, t in enumerate(valid_tickers):
            scores = _compute_radar_scores(infos[t])
            values = [scores.get(c, 0) for c in categories]
            # Close the polygon
            values_closed = values + [values[0]]
            cats_closed = categories + [categories[0]]

            fig_radar.add_trace(go.Scatterpolar(
                r=values_closed,
                theta=cats_closed,
                fill="toself",
                fillcolor=COLORS[i].replace(")", ",0.1)").replace("rgb", "rgba") if "rgb" in COLORS[i] else COLORS[i] + "1A",
                name=t,
                line=dict(color=COLORS[i], width=2),
                marker=dict(size=5, color=COLORS[i]),
            ))

        fig_radar.update_layout(
            paper_bgcolor="#000000",
            plot_bgcolor="#0a0a0a",
            font=dict(color="#94a3b8", size=12, family="Inter"),
            margin=dict(l=60, r=60, t=40, b=40),
            height=450,
            polar=dict(
                bgcolor="#0a0a0a",
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    gridcolor="#1a1a1a",
                    linecolor="#1a1a1a",
                    tickfont=dict(color="#5a6f8a", size=9),
                ),
                angularaxis=dict(
                    gridcolor="#1a1a1a",
                    linecolor="#1a1a1a",
                    tickfont=dict(color="#94a3b8", size=11),
                ),
            ),
            legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a", font=dict(color="#94a3b8")),
            title=dict(
                text="Comparacion de Perfil Fundamental",
                font=dict(color="#94a3b8", size=14),
                x=0.5,
            ),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        # ── Radar scores table ──
        radar_rows = []
        for t in valid_tickers:
            scores = _compute_radar_scores(infos[t])
            row = {"Ticker": t}
            row.update({k: round(v, 1) for k, v in scores.items()})
            row["Total"] = round(sum(scores.values()), 1)
            radar_rows.append(row)

        radar_df = pd.DataFrame(radar_rows)
        st.dataframe(radar_df, use_container_width=True, hide_index=True)

        st.markdown("""
        <div style='background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.2);
                    border-radius:12px;padding:14px;color:#94a3b8;font-size:12px;margin-top:8px;'>
          <strong>Metodologia Radar:</strong> Cada dimension se puntua de 0-100.<br>
          <strong>Value:</strong> P/E y P/B bajos = mejor score &middot;
          <strong>Growth:</strong> Crecimiento de ingresos y ganancias &middot;
          <strong>Profitability:</strong> Margen neto y ROE &middot;
          <strong>Safety:</strong> Ratio corriente y deuda/patrimonio &middot;
          <strong>Dividend:</strong> Yield y payout ratio
        </div>""", unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════
        # SECTION 4: COMPARATIVE RETURNS (Bloomberg-style)
        # ══════════════════════════════════════════════════════════════
        try:
            from datetime import datetime as _dt, timedelta as _td
            st.markdown("<div class='sec-title'>📊 Retornos Comparativos</div>", unsafe_allow_html=True)

            _periods = {
                "1D": 2, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365, "YTD": None,
            }
            _ret_rows = []
            for _t in valid_tickers:
                try:
                    _hist_full = yf.Ticker(_t).history(period="1y")
                    if _hist_full.empty:
                        continue
                    _cl = _hist_full["Close"]
                    if hasattr(_cl, "columns"):
                        _cl = _cl.iloc[:, 0]
                    _last = _cl.iloc[-1]
                    _row = {"Ticker": _t}
                    for _pname, _days in _periods.items():
                        try:
                            if _pname == "YTD":
                                _year_start = _dt(_dt.now().year, 1, 1)
                                _ytd_data = _cl[_cl.index >= str(_year_start)]
                                if not _ytd_data.empty:
                                    _row[_pname] = round((_last / _ytd_data.iloc[0] - 1) * 100, 2)
                                else:
                                    _row[_pname] = None
                            else:
                                if len(_cl) > _days:
                                    _row[_pname] = round((_last / _cl.iloc[-_days] - 1) * 100, 2)
                                else:
                                    _row[_pname] = None
                        except Exception:
                            _row[_pname] = None
                    _ret_rows.append(_row)
                except Exception:
                    continue

            if _ret_rows:
                _ret_df = pd.DataFrame(_ret_rows)
                _period_cols = [c for c in _ret_df.columns if c != "Ticker"]

                def _color_returns(val):
                    if isinstance(val, (int, float)) and pd.notna(val):
                        return f"color: {'#34d399' if val >= 0 else '#f87171'}; font-weight: 600"
                    return "color: #5a6f8a"

                _styled = _ret_df.style.map(_color_returns, subset=_period_cols)
                _format_dict = {c: "{:+.2f}%" for c in _period_cols}
                _styled = _styled.format(_format_dict, na_rep="N/A")
                st.dataframe(_styled, use_container_width=True, hide_index=True)
        except Exception as _e_ret:
            st.warning(f"Error calculando retornos comparativos: {_e_ret}")

    except Exception as e:
        st.error(f"Error en el comparador: {e}")
