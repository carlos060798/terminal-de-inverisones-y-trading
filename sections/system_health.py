"""sections/system_health.py - Unified Technical Control Center v3.5"""
import streamlit as st
import pandas as pd
import os
import time
import balancer
import database as db
import plotly.graph_objects as go
from ui_shared import DARK, kpi, badge, latency_label, fmt
from services import backup_service

# Optional engine import for Data Fabric health
try:
    from adapters.execution_engine import ExecutionEngine
except ImportError:
    ExecutionEngine = None

@st.cache_resource
def get_engine():
    if ExecutionEngine:
        return ExecutionEngine()
    return None

def get_dir_size(path='.'):
    total = 0
    try:
        if not os.path.exists(path): return 0
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except Exception:
        pass
    return total

def render():
    st.markdown("""
    <style>
        .rack-container {
            background: rgba(10, 10, 10, 0.4);
            border: 1px solid rgba(59, 130, 246, 0.2);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
        }
        .rack-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.03);
        }
        .server-led {
            height: 8px;
            width: 8px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
            box-shadow: 0 0 8px currentColor;
        }
        .led-green { color: #10b981; background-color: #10b981; }
        .led-amber { color: #f59e0b; background-color: #f59e0b; }
        .led-red { color: #ef4444; background-color: #ef4444; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Technical Control Center</h1>
        <p>Data Fabric · System Resources · Network Latency · Backups</p>
      </div>
    </div>""", unsafe_allow_html=True)

    engine = get_engine()
    
    # --- ROW 1: CORE ENGINE KPIs ---
    st.markdown("<div class='sec-title'>Data Engine & Observability</div>", unsafe_allow_html=True)
    
    k1, k2, k3, k4 = st.columns(4)
    
    summary = []
    res_stats = {}
    if engine:
        summary = engine.health_summary()
        res_stats = engine.resource_stats()
        
        total_prov = len(summary)
        active_prov = sum(1 for s in summary if s["configured"])
        error_pids = [s["provider_id"] for s in summary if s["state"].lower() == "open"]
        
        with k1:
            st.markdown(kpi("Proveedores", f"{active_prov}/{total_prov}", "Data Fabric Ready", "blue"), unsafe_allow_html=True)
        with k2:
            st.markdown(kpi("Salud Motor", "100%" if not error_pids else f"{100 - (len(error_pids)/total_prov*100):.0f}%", "Disponibilidad Global", "green" if not error_pids else "red"), unsafe_allow_html=True)
        with k3:
            st.markdown(kpi("Carga CPU", f"{res_stats.get('cpu_used_pct', 0):.1f}%", f"Limit: {res_stats.get('cpu_limit_pct', 70)}%", "blue"), unsafe_allow_html=True)
        with k4:
            st.markdown(kpi("RAM Utilizada", f"{res_stats.get('ram_used_mb', 0):.0f}MB", f"Limit: {res_stats.get('ram_limit_mb', 1500)}MB", "purple"), unsafe_allow_html=True)
    else:
        st.warning("Engine 'ExecutionEngine' no disponible.")

    # --- ROW 2: SERVER RACK (OBSERVABILITY) ---
    st.markdown("<div class='sec-title'>Live Adapter Rack</div>", unsafe_allow_html=True)
    
    if summary:
        with st.container():
            st.markdown("<div class='rack-container'>", unsafe_allow_html=True)
            for s in summary[:12]: # Show top 12
                status_color = "led-green" if s["state"].lower() != "open" else "led-red"
                latency = s["latency_ms"] if s["latency_ms"] else 0
                latency_color = "color:#10b981" if latency < 800 else "color:#f59e0b" if latency < 2000 else "color:#ef4444"
                
                st.markdown(f"""
                <div class='rack-row'>
                    <div style='display:flex; align-items:center;'>
                        <span class='server-led {status_color}'></span>
                        <span style='font-family:monospace; color:#f0f6ff; font-weight:600; width:120px;'>{s['provider_id'].upper()}</span>
                        <span style='font-size:10px; color:#64748b; margin-left:20px;'>{s['category'].upper()}</span>
                    </div>
                    <div style='display:flex; gap:30px; align-items:center;'>
                        <span style='font-size:11px; color:#475569;'>RATE: <b style='color:#94a3b8;'>{s['total_successes']} / {s['total_failures'] + s['total_successes']}</b></span>
                        <span style='font-family:monospace; font-size:12px; {latency_color}'>{latency}ms</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            if len(summary) > 12:
                with st.expander("Ver otros adaptadores de red..."):
                    st.dataframe(pd.DataFrame(summary[12:]), use_container_width=True, hide_index=True)

    # --- ROW 3: STORAGE & DB ---
    st.markdown("<div class='sec-title'>Almacenamiento e Integridad</div>", unsafe_allow_html=True)
    col_str, col_int = st.columns([1, 1])
    
    with col_str:
        db_size = os.path.getsize(db.DB_PATH) if os.path.exists(db.DB_PATH) else 0
        backup_size = get_dir_size("backups")
        cache_size = get_dir_size(".streamlit/cache")
        
        st.markdown(f"""
        <div class='metric-card'>
            <div style='display:flex; justify-content:space-between; margin-bottom:10px;'>
                <span style='color:#94a3b8; font-size:11px;'>FICHERO DB</span>
                <span style='color:#60a5fa; font-weight:700;'>{db_size/1024/1024:.2f} MB</span>
            </div>
            <div style='display:flex; justify-content:space-between; margin-bottom:10px;'>
                <span style='color:#94a3b8; font-size:11px;'>BACKUPS</span>
                <span style='color:#a78bfa; font-weight:700;'>{backup_size/1024/1024:.2f} MB</span>
            </div>
            <div style='display:flex; justify-content:space-between;'>
                <span style='color:#94a3b8; font-size:11px;'>CACHÉ DISCO</span>
                <span style='color:#34d399; font-weight:700;'>{cache_size/1024/1024:.2f} MB</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚀 Crear Respaldo Ahora", use_container_width=True):
            path = backup_service.run_backup(db.DB_PATH)
            if path:
                st.success(f"Respaldo creado: {os.path.basename(path)}")
                st.rerun()

    with col_int:
        try:
            conn = db.get_connection()
            tables = ["watchlist", "trades", "market_sentiment", "stock_analyses", "alerts"]
            integrity_rows = []
            for t in tables:
                try:
                    cnt = pd.read_sql(f"SELECT COUNT(*) as c FROM {t}", conn).iloc[0]["c"]
                    integrity_rows.append({"Table": t, "Count": cnt, "Health": "✅ OK"})
                except:
                    integrity_rows.append({"Table": t, "Count": 0, "Health": "❌ ERROR"})
            conn.close()
            st.dataframe(pd.DataFrame(integrity_rows), use_container_width=True, hide_index=True)
        except:
            st.error("No se pudo conectar a la DB.")

    # --- ROW 4: AI INFERENCE BALANCER ---
    st.markdown("<div class='sec-title'>AI Balancer & Model Inference</div>", unsafe_allow_html=True)
    ai_data = balancer.dashboard_data()
    df_ai = pd.DataFrame(ai_data)
    
    st.dataframe(
        df_ai[["name", "backend", "model", "pct", "limit", "available"]].sort_values("pct", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "pct": st.column_config.ProgressColumn("Usage %", format="%.1f%%", min_value=0, max_value=100),
            "available": st.column_config.CheckboxColumn("Active"),
        }
    )

    # --- ROW 5: PORTFOLIO MANAGEMENT ---
    with st.expander("💼 Administración Avanzada de Portafolios"):
        pm1, pm2 = st.columns([1, 2])
        with pm1:
            st.markdown("##### Crear Portafolio")
            n_name = st.text_input("Name", key="p_name_add")
            n_type = st.selectbox("Type", ["Standard", "Fondos Propios", "Cuenta de Fondeo", "Simulación", "Largo Plazo"], key="p_type_add")
            if st.button("➕ Crear New", use_container_width=True):
                if n_name.strip():
                    db.add_portfolio(n_name.strip(), "", n_type)
                    st.success("Portafolio creado.")
                    st.rerun()
        with pm2:
            st.markdown("##### Portafolios Activos")
            p_df = db.get_portfolios()
            if not p_df.empty:
                st.dataframe(p_df[["id", "name", "type", "created_at"]], use_container_width=True, hide_index=True)
                p_to_del = st.selectbox("Delete", p_df[p_df["id"] != 1]["name"].tolist(), key="p_del_select")
                if st.button("🗑️ Eliminar permanentemente", use_container_width=True):
                    db.delete_portfolio(p_df[p_df["name"] == p_to_del]["id"].iloc[0])
                    st.error("Eliminado.")
                    st.rerun()
