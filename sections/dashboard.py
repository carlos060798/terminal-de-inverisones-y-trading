"""sections/dashboard.py - Bloomberg-style Portfolio Analytics Cockpit"""
import streamlit as st, pandas as pd, plotly.graph_objects as go
from datetime import datetime, timedelta
import database as db
from ui_shared import DARK, dark_layout, fmt, kpi
import excel_export, ai_engine

try:
    import yfinance as yf
except ImportError:
    yf = None
try:
    from cache_utils import get_batch_prices, get_history
except ImportError:
    get_batch_prices = get_history = None
try:
    from data_sources import cached_fear_greed_index, cached_vix, cached_spy_put_call_ratio
except ImportError:
    cached_fear_greed_index = cached_vix = cached_spy_put_call_ratio = None

_ZERO = {"price": 0, "prev": 0, "change_pct": 0}

@st.cache_data(ttl=300, show_spinner=False)
def _batch_prices_and_changes(tickers_tuple):
    """Batch-fetch 5d prices for current price + day change."""
    try:
        data = yf.download(list(tickers_tuple), period="5d", group_by="ticker", progress=False)
        result = {}
        for t in tickers_tuple:
            try:
                closes = (data["Close"] if len(tickers_tuple) == 1 else data[t]["Close"]).dropna()
                if len(closes) >= 2:
                    result[t] = {"price": float(closes.iloc[-1]), "prev": float(closes.iloc[-2]),
                                 "change_pct": (float(closes.iloc[-1]) / float(closes.iloc[-2]) - 1) * 100}
                elif len(closes) == 1:
                    result[t] = {"price": float(closes.iloc[-1]), "prev": 0, "change_pct": 0}
                else:
                    result[t] = dict(_ZERO)
            except Exception:
                result[t] = dict(_ZERO)
        return result
    except Exception:
        return {t: dict(_ZERO) for t in tickers_tuple}

def _sec(title):
    st.markdown(f"<div class='sec-title'>{title}</div>", unsafe_allow_html=True)
def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Portfolio Analytics</h1>
        <p>Bloomberg-style cockpit · Real-time overview · Risk · Events</p>
      </div>
    </div>""", unsafe_allow_html=True)

    wl = db.get_watchlist()
    trades_stock = db.get_trades()
    trades_fx = db.get_forex_trades()
    analyses = db.get_stock_analyses()
    total_val = total_inv = n_positions = 0
    prices_map, position_rows = {}, []

    if not wl.empty and yf:
        n_positions = len(wl)
        tickers_list = [row["ticker"] for _, row in wl.iterrows()]
        try:
            prices_map = _batch_prices_and_changes(tuple(tickers_list))
        except Exception:
            prices_map = {}

        for _, row in wl.iterrows():
            t = row["ticker"]
            pd_info = prices_map.get(t, {})
            price = pd_info.get("price", 0)
            change_pct = pd_info.get("change_pct", 0)

            if price == 0:
                try:
                    price = yf.Ticker(t).fast_info.last_price or 0
                except Exception:
                    price = 0

            val = row["shares"] * price
            inv = row["shares"] * row["avg_cost"]
            pnl_pos = val - inv
            pnl_pct_pos = (pnl_pos / inv * 100) if inv > 0 else 0
            weight = 0  # computed after totals

            total_val += val
            total_inv += inv

            position_rows.append({
                "Ticker": t,
                "Shares": row["shares"],
                "Avg Cost": row["avg_cost"],
                "Price": price,
                "P&L $": pnl_pos,
                "P&L %": pnl_pct_pos,
                "Day %": change_pct,
                "Value": val,
                "Sector": row.get("sector", ""),
            })

    total_pnl = total_val - total_inv

    # Weights
    for p in position_rows:
        p["Weight %"] = (p["Value"] / total_val * 100) if total_val > 0 else 0

    # Trading P&L
    stock_pnl = trades_stock[trades_stock["pnl"].notna()]["pnl"].sum() if not trades_stock.empty else 0
    fx_pnl = trades_fx[trades_fx["pnl"].notna()]["pnl"].sum() if not trades_fx.empty else 0
    total_trading_pnl = stock_pnl + fx_pnl

    all_closed = []
    if not trades_stock.empty:
        all_closed.extend(trades_stock[trades_stock["pnl"].notna()]["pnl"].tolist())
    if not trades_fx.empty:
        all_closed.extend(trades_fx[trades_fx["pnl"].notna()]["pnl"].tolist())
    win_rate = (sum(1 for p in all_closed if p > 0) / len(all_closed) * 100) if all_closed else 0
    sharpe = sortino = var_95 = max_dd = calmar = 0
    returns = pd.Series(all_closed) if all_closed else pd.Series(dtype=float)
    if len(returns) >= 2:
        mean_ret = returns.mean()
        std_ret = returns.std()
        downside = returns[returns < 0].std()
        sharpe = mean_ret / std_ret if std_ret > 0 else 0
        sortino = mean_ret / downside if downside > 0 else 0
        var_95 = returns.quantile(0.05)
        cumulative = returns.cumsum()
        running_max = cumulative.cummax()
        drawdown = cumulative - running_max
        max_dd = drawdown.min()
        calmar = mean_ret / abs(max_dd) if max_dd != 0 else 0

    # ── ROW 0: Earnings Alert Banner ──
    try:
        if not wl.empty and yf:
            upcoming_earnings = []
            for row_idx in range(min(10, len(wl))):
                try:
                    row = wl.iloc[row_idx]
                    cal = yf.Ticker(row["ticker"]).calendar
                    if cal is not None:
                        if isinstance(cal, dict):
                            ed = cal.get("Earnings Date", [None])
                            if ed and ed[0]:
                                diff = (ed[0] - datetime.now()).days
                                if 0 <= diff <= 7:
                                    upcoming_earnings.append((row["ticker"], ed[0].strftime("%Y-%m-%d"), diff))
                        elif isinstance(cal, pd.DataFrame) and not cal.empty:
                            if "Earnings Date" in cal.index:
                                ed_vals = cal.loc["Earnings Date"]
                                for ed_val in ed_vals:
                                    if pd.notna(ed_val):
                                        ed_ts = pd.Timestamp(ed_val)
                                        diff = (ed_ts - pd.Timestamp(datetime.now())).days
                                        if 0 <= diff <= 7:
                                            upcoming_earnings.append((row["ticker"], ed_ts.strftime("%Y-%m-%d"), diff))
                                        break
                except Exception:
                    pass
            if upcoming_earnings:
                msg = " | ".join([f"**{t}** reporta en {d} dias ({dt})" for t, dt, d in upcoming_earnings])
                st.warning(f"Earnings proximos: {msg}")
    except Exception:
        pass

    _sec("Portfolio Overview")
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    pct_total = (total_pnl / total_inv * 100) if total_inv > 0 else 0

    k1.markdown(kpi("Portfolio Value", fmt(total_val) if total_val > 0 else "$0",
                     f"{n_positions} positions", "blue"), unsafe_allow_html=True)

    pnl_color = "green" if total_pnl >= 0 else "red"
    k2.markdown(kpi("P&L Total", fmt(total_pnl),
                     f"{pct_total:+.2f}%", pnl_color), unsafe_allow_html=True)

    k3.markdown(kpi("Trading P&L", f"${total_trading_pnl:+,.0f}",
                     f"Stocks: ${stock_pnl:+,.0f} | FX: ${fx_pnl:+,.0f}",
                     "green" if total_trading_pnl >= 0 else "red"), unsafe_allow_html=True)

    k4.markdown(kpi("Win Rate", f"{win_rate:.1f}%",
                     f"{len(all_closed)} closed trades",
                     "green" if win_rate >= 50 else "red"), unsafe_allow_html=True)

    k5.markdown(kpi("Sharpe Ratio", f"{sharpe:.2f}",
                     "return / risk",
                     "green" if sharpe > 0 else "red"), unsafe_allow_html=True)

    k6.markdown(kpi("VaR 95%", f"${var_95:,.2f}" if len(returns) >= 2 else "N/A",
                     "max probable loss",
                     "red" if var_95 < 0 else "blue"), unsafe_allow_html=True)

    _sec("Market Pulse")
    try:
        mp1, mp2, mp3 = st.columns(3)

        # Fear & Greed Gauge
        with mp1:
            try:
                fg = cached_fear_greed_index() if cached_fear_greed_index else None
                if fg:
                    fg_val = fg["value"]
                    if fg_val <= 25:
                        fg_color = "#f87171"
                    elif fg_val <= 45:
                        fg_color = "#fb923c"
                    elif fg_val <= 55:
                        fg_color = "#fbbf24"
                    elif fg_val <= 75:
                        fg_color = "#a3e635"
                    else:
                        fg_color = "#34d399"

                    fig_fg = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=fg_val,
                        title={"text": "Fear & Greed Index", "font": {"color": "#94a3b8", "size": 13}},
                        number={"font": {"color": fg_color, "size": 36}},
                        gauge={
                            "axis": {"range": [0, 100], "tickcolor": "#334155", "dtick": 25},
                            "bar": {"color": fg_color, "thickness": 0.3},
                            "bgcolor": "#0a0a0a",
                            "bordercolor": "#1a1a1a",
                            "steps": [
                                {"range": [0, 25], "color": "rgba(248,113,113,0.15)"},
                                {"range": [25, 45], "color": "rgba(251,146,60,0.12)"},
                                {"range": [45, 55], "color": "rgba(251,191,36,0.10)"},
                                {"range": [55, 75], "color": "rgba(163,230,53,0.10)"},
                                {"range": [75, 100], "color": "rgba(52,211,153,0.12)"},
                            ],
                            "threshold": {
                                "line": {"color": "#f0f6ff", "width": 2},
                                "thickness": 0.8, "value": fg_val,
                            },
                        },
                    ))
                    fig_fg.update_layout(**DARK, height=250)
                    st.plotly_chart(fig_fg, use_container_width=True)
                    st.caption(f"Classification: **{fg['label']}**")
                else:
                    st.markdown(kpi("Fear & Greed", "N/A", "API unavailable", "blue"), unsafe_allow_html=True)
            except Exception:
                st.markdown(kpi("Fear & Greed", "N/A", "Error loading", "blue"), unsafe_allow_html=True)

        # VIX Level + Status
        with mp2:
            try:
                vix = cached_vix() if cached_vix else None
                if vix:
                    if vix < 15:
                        vix_label, vix_c, vix_hex = "Low Volatility", "green", "#34d399"
                    elif vix < 20:
                        vix_label, vix_c, vix_hex = "Normal", "blue", "#60a5fa"
                    elif vix < 30:
                        vix_label, vix_c, vix_hex = "Elevated", "yellow", "#fbbf24"
                    else:
                        vix_label, vix_c, vix_hex = "Panic", "red", "#f87171"

                    fig_vix = go.Figure(go.Indicator(
                        mode="number+delta",
                        value=vix,
                        title={"text": "VIX Volatility Index", "font": {"color": "#94a3b8", "size": 13}},
                        number={"font": {"color": vix_hex, "size": 48}},
                    ))
                    fig_vix.update_layout(**DARK, height=250)
                    st.plotly_chart(fig_vix, use_container_width=True)
                    st.caption(f"Status: **{vix_label}**")
                else:
                    st.markdown(kpi("VIX", "N/A", "No data", "blue"), unsafe_allow_html=True)
            except Exception:
                st.markdown(kpi("VIX", "N/A", "Error loading", "blue"), unsafe_allow_html=True)

        # SPY Put/Call + Market Direction
        with mp3:
            try:
                pcr = cached_spy_put_call_ratio() if cached_spy_put_call_ratio else None
                if pcr:
                    ratio = pcr["ratio"]
                    if ratio > 1.0:
                        pcr_label, pcr_color = "Bearish", "#f87171"
                    elif ratio > 0.7:
                        pcr_label, pcr_color = "Neutral", "#fbbf24"
                    else:
                        pcr_label, pcr_color = "Bullish", "#34d399"

                    fig_pcr = go.Figure(go.Indicator(
                        mode="number",
                        value=ratio,
                        title={"text": "SPY Put/Call Ratio", "font": {"color": "#94a3b8", "size": 13}},
                        number={"font": {"color": pcr_color, "size": 48}, "valueformat": ".3f"},
                    ))
                    fig_pcr.update_layout(**DARK, height=200)
                    st.plotly_chart(fig_pcr, use_container_width=True)
                    st.caption(f"Direction: **{pcr_label}** | Calls: {pcr['calls_vol']:,} · Puts: {pcr['puts_vol']:,} | Exp: {pcr['expiry']}")
                else:
                    st.markdown(kpi("SPY Put/Call", "N/A", "No data", "blue"), unsafe_allow_html=True)
            except Exception:
                st.markdown(kpi("SPY Put/Call", "N/A", "Error loading", "blue"), unsafe_allow_html=True)
    except Exception as e:
        st.info(f"Market pulse unavailable: {e}")

    try:
        if position_rows:
            _sec("Live Positions")
            pos_df = pd.DataFrame(position_rows)

            # Sort selector
            sort_col = st.selectbox("Sort by", ["P&L %", "P&L $", "Day %", "Weight %", "Value", "Ticker"],
                                    index=0, key="pos_sort", label_visibility="collapsed")
            ascending = sort_col == "Ticker"
            pos_df = pos_df.sort_values(sort_col, ascending=ascending)

            display_df = pos_df[["Ticker", "Shares", "Avg Cost", "Price", "P&L $", "P&L %", "Day %", "Weight %"]].copy()

            def _color_pnl(val):
                if isinstance(val, (int, float)):
                    if val > 0:
                        return "color: #34d399"
                    elif val < 0:
                        return "color: #f87171"
                return "color: #94a3b8"

            styled = display_df.style.format({
                "Shares": "{:.0f}",
                "Avg Cost": "${:.2f}",
                "Price": "${:.2f}",
                "P&L $": "${:+,.2f}",
                "P&L %": "{:+.2f}%",
                "Day %": "{:+.2f}%",
                "Weight %": "{:.1f}%",
            }).map(_color_pnl, subset=["P&L $", "P&L %", "Day %"])

            st.dataframe(styled, use_container_width=True, hide_index=True, height=min(400, 60 + 35 * len(display_df)))
    except Exception as e:
        st.info(f"Could not load positions table: {e}")

    try:
        if position_rows:
            r4c1, r4c2 = st.columns(2)

            # LEFT: Allocation Pie Chart
            with r4c1:
                _sec("Allocation")
                pos_df_alloc = pd.DataFrame(position_rows)

                # Try sector allocation first, fall back to ticker
                if pos_df_alloc["Sector"].str.strip().ne("").any():
                    alloc_group = pos_df_alloc.groupby("Sector")["Value"].sum().reset_index()
                    alloc_group = alloc_group[alloc_group["Value"] > 0]
                    labels = alloc_group["Sector"].tolist()
                    values = alloc_group["Value"].tolist()
                    alloc_title = "By Sector"
                else:
                    alloc_sorted = pos_df_alloc[pos_df_alloc["Value"] > 0].sort_values("Value", ascending=False)
                    labels = alloc_sorted["Ticker"].tolist()
                    values = alloc_sorted["Value"].tolist()
                    alloc_title = "By Ticker"

                if labels:
                    colors_palette = ["#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#f87171",
                                      "#c084fc", "#fb923c", "#38bdf8", "#e879f9", "#4ade80"]
                    fig_alloc = go.Figure(go.Pie(
                        labels=labels, values=values,
                        marker_colors=colors_palette[:len(labels)], hole=0.55,
                        textfont=dict(color="white"), textinfo="label+percent"))
                    fig_alloc.update_layout(**DARK, height=350,
                        title=dict(text=f"Allocation {alloc_title}", font=dict(color="#94a3b8", size=13), x=0.5),
                        showlegend=False,
                        annotations=[dict(text=fmt(total_val), x=0.5, y=0.5, showarrow=False,
                                          font=dict(size=18, color="#f0f6ff", family="Inter"))])
                    st.plotly_chart(fig_alloc, use_container_width=True)

            # RIGHT: Top Movers Today
            with r4c2:
                _sec("Top Movers Today")
                movers_df = pd.DataFrame(position_rows)
                movers_df = movers_df[movers_df["Price"] > 0].sort_values("Day %", ascending=False)

                if not movers_df.empty:
                    for _, m in movers_df.iterrows():
                        chg = m["Day %"]
                        icon = "+" if chg >= 0 else ""
                        color = "#34d399" if chg >= 0 else "#f87171"
                        dot = "&#x1F7E2;" if chg >= 0 else "&#x1F534;"
                        st.markdown(
                            f"<div style='display:flex;justify-content:space-between;align-items:center;"
                            f"padding:8px 14px;margin:4px 0;background:#0a0a0a;border:1px solid #1a1a1a;"
                            f"border-radius:10px;'>"
                            f"<span style='font-weight:600;color:#f0f6ff;font-size:14px;'>{dot} {m['Ticker']}</span>"
                            f"<span style='color:{color};font-weight:700;font-size:14px;'>{icon}{chg:.2f}%</span>"
                            f"</div>", unsafe_allow_html=True)
                else:
                    st.info("No price data available for movers.")
    except Exception as e:
        st.info(f"Could not load allocation / movers: {e}")

    r5c1, r5c2 = st.columns(2)

    # LEFT: Equity Curve (12M) with SPY overlay
    with r5c1:
        try:
            _sec("Equity Curve")
            all_pnl = []
            if not trades_stock.empty:
                closed_s = trades_stock[trades_stock["pnl"].notna()].copy()
                if not closed_s.empty:
                    for _, t in closed_s.iterrows():
                        all_pnl.append({"date": t["trade_date"], "pnl": t["pnl"]})
            if not trades_fx.empty:
                closed_f = trades_fx[trades_fx["pnl"].notna()].copy()
                if not closed_f.empty:
                    for _, t in closed_f.iterrows():
                        all_pnl.append({"date": t["trade_date"], "pnl": t["pnl"]})

            if all_pnl:
                eq_df = pd.DataFrame(all_pnl).sort_values("date")
                eq_df["cum"] = eq_df["pnl"].cumsum()

                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(
                    x=eq_df["date"], y=eq_df["cum"],
                    mode="lines", name="Portfolio Equity",
                    line=dict(color="#60a5fa", width=2.5),
                    fill="tozeroy", fillcolor="rgba(96,165,250,0.08)"))

                # SPY overlay attempt
                try:
                    if get_history:
                        spy_hist = get_history("SPY", "1y")
                        if not spy_hist.empty:
                            spy_close = spy_hist["Close"]
                            if hasattr(spy_close, "squeeze"):
                                spy_close = spy_close.squeeze()
                            spy_ret = (spy_close / spy_close.iloc[0] - 1) * total_inv if total_inv > 0 else spy_close * 0
                            fig_eq.add_trace(go.Scatter(
                                x=spy_ret.index, y=spy_ret.values,
                                mode="lines", name="SPY (scaled)",
                                line=dict(color="#475569", width=1.5, dash="dot")))
                except Exception:
                    pass

                fig_eq.add_hline(y=0, line_dash="dot", line_color="#334155")
                fig_eq.update_layout(**DARK, height=350,
                    title=dict(text="Cumulative P&L", font=dict(color="#94a3b8", size=13), x=0.5),
                    legend=dict(bgcolor="#0a0a0a", bordercolor="#1a1a1a",
                                font=dict(color="#94a3b8")))
                st.plotly_chart(fig_eq, use_container_width=True)
            else:
                st.info("Record trades to see your equity curve.")
        except Exception as e:
            st.info(f"Could not load equity curve: {e}")

    # RIGHT: Upcoming Events (earnings + dividends + macro)
    with r5c2:
        try:
            _sec("Upcoming Events")
            events = []
            today = datetime.now().date()

            # Earnings + Dividends from watchlist
            if not wl.empty and yf:
                for _, row in wl.iterrows():
                    t = row["ticker"]
                    try:
                        tk = yf.Ticker(t)

                        # Earnings date
                        try:
                            cal_data = tk.calendar
                            if cal_data is not None:
                                if isinstance(cal_data, pd.DataFrame) and not cal_data.empty:
                                    if "Earnings Date" in cal_data.index:
                                        ed_vals = cal_data.loc["Earnings Date"]
                                        for ed_val in ed_vals:
                                            if pd.notna(ed_val):
                                                ed = pd.Timestamp(ed_val).date()
                                                diff = (ed - today).days
                                                if diff >= 0:
                                                    events.append({"icon": "&#x1F4CA;", "event": f"{t} Earnings",
                                                                   "date": ed, "days": diff})
                                                break
                                elif isinstance(cal_data, dict):
                                    ed_list = cal_data.get("Earnings Date", [])
                                    if ed_list:
                                        ed = pd.Timestamp(ed_list[0]).date()
                                        diff = (ed - today).days
                                        if diff >= 0:
                                            events.append({"icon": "&#x1F4CA;", "event": f"{t} Earnings",
                                                           "date": ed, "days": diff})
                        except Exception:
                            pass

                        # Ex-dividend date
                        try:
                            info = tk.info
                            ex_div = info.get("exDividendDate")
                            if ex_div:
                                if isinstance(ex_div, (int, float)):
                                    ex_date = datetime.fromtimestamp(ex_div).date()
                                else:
                                    ex_date = pd.Timestamp(ex_div).date()
                                diff = (ex_date - today).days
                                if diff >= 0:
                                    events.append({"icon": "&#x1F4B0;", "event": f"{t} Ex-Dividend",
                                                   "date": ex_date, "days": diff})
                        except Exception:
                            pass
                    except Exception:
                        continue

            # Sort and display
            events.sort(key=lambda x: x["days"])
            events = events[:12]

            if events:
                for ev in events:
                    days = ev["days"]
                    if days <= 3:
                        badge_color = "#f87171"
                        badge_bg = "rgba(248,113,113,0.15)"
                    elif days <= 7:
                        badge_color = "#fbbf24"
                        badge_bg = "rgba(251,191,36,0.12)"
                    else:
                        badge_color = "#94a3b8"
                        badge_bg = "rgba(148,163,184,0.08)"

                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;align-items:center;"
                        f"padding:8px 14px;margin:4px 0;background:#0a0a0a;border:1px solid #1a1a1a;"
                        f"border-radius:10px;'>"
                        f"<span style='color:#e2e8f0;font-size:13px;'>{ev['icon']} {ev['event']}</span>"
                        f"<span style='color:{badge_color};background:{badge_bg};padding:2px 10px;"
                        f"border-radius:8px;font-size:12px;font-weight:600;'>"
                        f"{'TODAY' if days == 0 else f'in {days}d'}</span>"
                        f"</div>", unsafe_allow_html=True)
            else:
                st.info("No upcoming events found for your watchlist.")
        except Exception as e:
            st.info(f"Could not load events: {e}")

    try:
        if len(returns) >= 2:
            _sec("Risk Dashboard")

            rk1, rk2, rk3, rk4 = st.columns(4)
            rk1.markdown(kpi("Sharpe Ratio", f"{sharpe:.2f}", "return / risk",
                             "green" if sharpe > 0 else "red"), unsafe_allow_html=True)
            rk2.markdown(kpi("Sortino Ratio", f"{sortino:.2f}", "return / downside",
                             "green" if sortino > 0 else "red"), unsafe_allow_html=True)
            rk3.markdown(kpi("Max Drawdown", f"${max_dd:,.2f}", "maximum decline",
                             "red"), unsafe_allow_html=True)
            rk4.markdown(kpi("Calmar Ratio", f"{calmar:.2f}", "return / max DD",
                             "green" if calmar > 0 else "red"), unsafe_allow_html=True)

            # Drawdown chart
            try:
                risk_trades = trades_stock if not trades_stock.empty else pd.DataFrame()
                if not risk_trades.empty and "trade_date" in risk_trades.columns:
                    closed_trades = risk_trades[risk_trades["pnl"].notna()].copy()
                    closed_trades = closed_trades.sort_values("trade_date")
                    if not closed_trades.empty:
                        dd_cum = closed_trades["pnl"].cumsum()
                        dd_max = dd_cum.cummax()
                        dd_series = dd_cum - dd_max

                        fig_dd = go.Figure()
                        fig_dd.add_trace(go.Scatter(
                            x=closed_trades["trade_date"], y=dd_series.values,
                            mode="lines", name="Drawdown",
                            line=dict(color="#f87171", width=1.5),
                            fill="tozeroy", fillcolor="rgba(248,113,113,0.15)"))
                        fig_dd.add_hline(y=0, line_dash="dot", line_color="#334155")
                        fig_dd.update_layout(**dark_layout(
                            height=250,
                            title=dict(text="Drawdown", font=dict(color="#94a3b8", size=13), x=0.5),
                            yaxis=dict(gridcolor="#1a1a1a", linecolor="#1a1a1a",
                                       zerolinecolor="#1a1a1a", tickprefix="$"),
                            xaxis=dict(gridcolor="#1a1a1a", linecolor="#1a1a1a",
                                       zerolinecolor="#1a1a1a"),
                        ))
                        st.plotly_chart(fig_dd, use_container_width=True)
            except Exception:
                pass
        else:
            _sec("Risk Dashboard")
            st.info("Need at least 2 closed trades for risk metrics.")
    except Exception as e:
        st.info(f"Could not compute risk metrics: {e}")

    _sec("Quick Actions")
    qa1, qa2, qa3 = st.columns(3)

    # Excel Export
    with qa1:
        try:
            wl_data = db.get_watchlist()
            trades_data = db.get_trades()
            forex_data = db.get_forex_trades()
            if not wl_data.empty or not trades_data.empty:
                xlsx = excel_export.export_portfolio(wl_data, trades_data, forex_data)
                import file_saver
                file_saver.save_or_download(xlsx, "cartera_quantum.xlsx",
                                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                  "Export Portfolio (Excel)", key="exp_cartera_dash")
            analyses_data = db.get_stock_analyses()
            if not analyses_data.empty:
                xlsx2 = excel_export.export_analyses(analyses_data)
                import file_saver
                file_saver.save_or_download(xlsx2, "analisis_quantum.xlsx",
                                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                  "Export Analyses (Excel)", key="exp_analisis_dash")
        except Exception as e:
            st.info(f"Excel export unavailable: {e}")

    # QuantStats Tearsheet
    with qa2:
        with st.expander("QuantStats Tearsheet"):
            try:
                import quantstats as qs
                trades_qs = db.get_trades()
                if trades_qs.empty:
                    st.info("Record trades to generate tearsheet")
                else:
                    df_qs = trades_qs.copy()
                    df_closed = df_qs[df_qs["exit_price"] > 0].copy()
                    if len(df_closed) < 2:
                        st.info("Need at least 2 closed trades")
                    else:
                        df_closed["trade_date"] = pd.to_datetime(df_closed["trade_date"])
                        df_closed = df_closed.sort_values("trade_date")
                        df_closed["pnl"] = (df_closed["exit_price"] - df_closed["entry_price"]) * df_closed["shares"]
                        returns_qs = df_closed.set_index("trade_date")["pnl"]
                        returns_qs = returns_qs.resample("D").sum().fillna(0)
                        base = 10000
                        returns_pct = returns_qs / base

                        if st.button("Generate Tearsheet", key="qs_btn_dash"):
                            with st.spinner("Generating..."):
                                try:
                                    html = qs.reports.html(returns_pct, benchmark="SPY",
                                                           output="string", title="Quantum Portfolio")
                                    st.components.v1.html(html, height=800, scrolling=True)
                                except Exception as e_qs:
                                    st.error(f"Tearsheet error: {e_qs}")
            except ImportError:
                st.info("Install quantstats: pip install quantstats")
            except Exception as e:
                st.error(f"Tearsheet error: {e}")

    # AI Portfolio Insight
    with qa3:
        try:
            providers = ai_engine.get_available_providers()
            if providers and not wl.empty and yf:
                st.caption(f"AI Providers: {', '.join(providers)}")
                if st.button("AI Portfolio Analysis", key="ai_btn_dash"):
                    with st.spinner("Analyzing portfolio with AI..."):
                        ai_positions = []
                        for _, row in wl.iterrows():
                            try:
                                price = prices_map.get(row["ticker"], {}).get("price", 0)
                                if price == 0:
                                    price = yf.Ticker(row["ticker"]).fast_info.last_price or 0
                                pnl_pct = ((price / row["avg_cost"]) - 1) * 100 if row["avg_cost"] > 0 else 0
                                ai_positions.append({
                                    "ticker": row["ticker"], "shares": row["shares"],
                                    "avg_cost": row["avg_cost"], "current_price": price,
                                    "pnl_pct": pnl_pct, "sector": row.get("sector", ""),
                                })
                            except Exception:
                                ai_positions.append({
                                    "ticker": row["ticker"], "shares": row["shares"],
                                    "avg_cost": row["avg_cost"], "current_price": 0,
                                    "pnl_pct": 0, "sector": row.get("sector", ""),
                                })
                        ai_result = ai_engine.analyze_portfolio(ai_positions)
                        if ai_result:
                            st.markdown(f"""<div style='background:rgba(96,165,250,0.06);
                                border:1px solid rgba(96,165,250,0.2);
                                border-radius:14px;padding:20px;color:#c8d6e5;
                                font-size:13px;line-height:1.7;'>
                              {ai_result}
                            </div>""", unsafe_allow_html=True)
                        else:
                            st.info("Could not generate AI analysis.")
            else:
                st.info("Configure AI providers and add positions for AI insights.")
        except Exception as e:
            st.info(f"AI analysis unavailable: {e}")
