"""sections/system_health.py - System Architecture & DataOps Dashboard (Local Excellence)."""
import streamlit as st
import pandas as pd
import os
import time
import balancer
import database as db
from utils import visual_components as vc
from services import backup_service

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
    <div class='top-header'>
      <div>
        <h1>Local System Health</h1>
        <p>Monitoreo de recursos PC · Backups · Integridad de Datos</p>
      </div>
    </div>""", unsafe_allow_html=True)
    
    # --- 1. LOCAL RESOURCES ---
    st.markdown("<div class='sec-title'>Recursos de Almacenamiento</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    # DB Size
    db_size = os.path.getsize(db.DB_PATH) if os.path.exists(db.DB_PATH) else 0
    with col1:
        vc.render_metric_card("Fichero DB", f"{db_size/1024/1024:.2f} MB", subtitle="investment_data.db")
        
    # Backup Size
    backup_size = get_dir_size("backups")
    with col2:
        vc.render_metric_card("Backups Totales", f"{backup_size/1024/1024:.2f} MB", subtitle="Carpeta /backups")
        
    # Cache Size
    cache_size = get_dir_size(".streamlit/cache") # Example path
    with col3:
        vc.render_metric_card("Caché en Disco", f"{cache_size/1024/1024:.2f} MB", subtitle="Persistencia temporal")

    # --- 2. BACKUP MANAGEMENT ---
    st.markdown("<div class='sec-title'>Gestión de Respaldos</div>", unsafe_allow_html=True)
    
    b1, b2 = st.columns([2, 1])
    with b1:
        try:
            if os.path.exists("backups"):
                backup_files = [f for f in os.listdir("backups") if f.startswith("backup_")]
                backup_files.sort(reverse=True)
                if backup_files:
                    st.write(f"Últimos {len(backup_files)} respaldos encontrados:")
                    st.dataframe(pd.DataFrame([{"Archivo": f, "Fecha": time.ctime(os.path.getmtime(os.path.join("backups", f)))} for f in backup_files]), use_container_width=True, hide_index=True)
                else:
                    st.info("No se han encontrado archivos de respaldo.")
            else:
                st.info("El directorio de backups se creará con el primer respaldo.")
        except Exception as e:
            st.error(f"Error leyendo backups: {e}")
            
    with b2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 Crear Respaldo Ahora", use_container_width=True):
            path = backup_service.run_backup(db.DB_PATH)
            if path:
                st.success(f"Respaldo creado: {os.path.basename(path)}")
                st.rerun()
            else:
                st.error("Error al crear el respaldo.")
        
        if st.button("🗑️ Limpiar Backups Antiguos", use_container_width=True):
            backup_service._cleanup_old_backups("backups", limit=3)
            st.success("Limpieza completada (manteniendo los 3 más recientes).")
            st.rerun()

    # --- 3. AI & LATENCY ---
    st.markdown("<div class='sec-title'>Latencias de Inferencia</div>", unsafe_allow_html=True)
    data = balancer.dashboard_data()
    df_ai = pd.DataFrame(data)
    
    st.dataframe(
        df_ai[["name", "backend", "model", "pct", "limit", "available"]].sort_values("pct", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "pct": st.column_config.ProgressColumn("Uso de Cuota %", format="%.1f%%", min_value=0, max_value=100),
            "available": st.column_config.CheckboxColumn("Activo"),
        }
    )

    # --- 4. DATA INTEGRITY ---
    st.markdown("<div class='sec-title'>Integridad de Tablas</div>", unsafe_allow_html=True)
    try:
        conn = db.get_connection()
        tables = ["watchlist", "trades", "market_sentiment", "stock_analyses", "alerts"]
        rows = []
        for t in tables:
            try:
                cnt = pd.read_sql(f"SELECT COUNT(*) as c FROM {t}", conn).iloc[0]["c"]
                rows.append({"Tabla": t, "Registros": cnt, "Status": "OK"})
            except:
                rows.append({"Tabla": t, "Registros": 0, "Status": "ERROR"})
        conn.close()
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except:
        st.error("No se pudo conectar a la DB.")
