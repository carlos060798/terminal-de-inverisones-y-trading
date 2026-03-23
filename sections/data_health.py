"""sections/data_health.py - Panel de salud de Data Fabric Engine v7"""
import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from ui_shared import DARK
from adapters.execution_engine import ExecutionEngine

@st.cache_resource
def get_engine():
    return ExecutionEngine()

def _sec(title):
    st.markdown(f"<div class='sec-title'>{title}</div>", unsafe_allow_html=True)

def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Data Fabric Health</h1>
        <p>Monitoreo de observabilidad: Circuit breakers, Latencias, APIs</p>
      </div>
    </div>""", unsafe_allow_html=True)

    engine = get_engine()

    c1, c2, c3 = st.columns(3)
    
    # Trigger fetch dashboard
    if st.button("Fetch Dashboard Snapshot (Cold Start)"):
        with st.spinner("Fetching data..."):
            engine.fetch_dashboard_snapshot()
            st.rerun()

    # Get summaries
    summary = engine.health_summary()
    res_stats = engine.resource_stats()

    c1.markdown(f"**CPU Limit Usage:** {res_stats.get('cpu_used_pct', 0):.1f}% / {res_stats.get('cpu_limit_pct', 70)}%")
    c2.markdown(f"**RAM Limit Usage:** {res_stats.get('ram_used_mb', 0):.1f}MB / {res_stats.get('ram_limit_mb', 1500)}MB")
    c3.markdown(f"**Providers Total:** {len(summary)}")

    _sec("Métricas por proveedor")
    
    # We create a dataframe
    rows = []
    for s in summary:
        pid = s["provider_id"]
        last = s["last_fetch"]
        ttl = s["ttl_seconds"]
        ttl_rem = None
        if last:
            # wait, last_fetch is an ISO string fetched_at, but what if it's empty?
            pass # we can skip or display as is
        
        status = "OK"
        if s["state"].lower() == "open":
            status = "FAIL"
        elif s["state"].lower() == "half_open":
            status = "WARN"

        rows.append({
            "Provider": pid,
            "Category": s["category"],
            "State": status,
            "Latency (ms)": s["latency_ms"] if s["latency_ms"] else 0,
            "Success": f"{s['total_successes']} / {s['total_failures'] + s['total_successes']}",
            "Last Fetch": last if last else "Never",
            "Configured": "Yes" if s["configured"] else "No"
        })
    
    df = pd.DataFrame(rows)
    # Style logic based on "State"
    def _color_state(val):
        if val == "OK": return "color: #34d399;"
        if val == "WARN": return "color: #fbbf24;"
        if val == "FAIL": return "color: #f87171;"
        return ""

    if not df.empty:
        st.dataframe(df.style.map(_color_state, subset=["State"]), use_container_width=True, height=600)

    _sec("Resource Operations")
    colA, colB = st.columns(2)
    with colA:
        prov_id = st.selectbox("Provider", [s["provider_id"] for s in summary])
    with colB:
        st.write("")
        st.write("")
        if st.button(f"Refetch Now {prov_id}"):
            with st.spinner(f"Refetching {prov_id}..."):
                engine.fetch_one(prov_id, use_cache=False)
                st.rerun()

    # Dynamic charts (Mock placeholders mapping to architecture reqs)
    _sec("Dynamic Charts Sample")
    cat = [s["category"] for s in summary if s["provider_id"] == prov_id]
    if cat:
        ccat = cat[0]
        st.caption(f"Category: {ccat}")
        fig = go.Figure()
        
        from adapters.execution_engine import _cache_get
        data = _cache_get(prov_id)
        
        if data and data.data is not None and isinstance(data.data, pd.DataFrame):
            # Dynamic chart rules
            if ccat in ["stocks", "crypto"] and set(["open","high","low","close","date"]).issubset(data.data.columns):
                fig.add_trace(go.Candlestick(x=data.data["date"], open=data.data["open"], high=data.data["high"], low=data.data["low"], close=data.data["close"]))
            elif ccat in ["macro", "forex"]:
                y_col = "value" if "value" in data.data.columns else data.data.columns[1] if len(data.data.columns)>1 else None
                x_col = "date" if "date" in data.data.columns else data.data.columns[0]
                if y_col:
                    fig.add_trace(go.Scatter(x=data.data[x_col], y=data.data[y_col], mode='lines'))
            elif ccat == "volatility":
                y_col = "value" if "value" in data.data.columns else data.data.columns[1] if len(data.data.columns)>1 else None
                x_col = "date" if "date" in data.data.columns else data.data.columns[0]
                if y_col:
                    fig.add_trace(go.Scatter(x=data.data[x_col], y=data.data[y_col], fill='tozeroy', line=dict(color='red')))
            else:
                st.info("Bar Chart visualization placeholder for news/alternative")
        else:
            st.info("No cache data or data is not a dataframe for visualization")
            
        if len(fig.data) > 0:
            fig.update_layout(**DARK, title=f"Data preview: {prov_id}")
            st.plotly_chart(fig, use_container_width=True)
