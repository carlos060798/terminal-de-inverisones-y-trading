"""utils/export_utils.py - Universal data export tools for professional reporting."""
import io
import pandas as pd
import streamlit as st

def render_export_buttons(df: pd.DataFrame, file_prefix: str = "quantum_report"):
    """
    Renders export buttons (Excel, CSV) for any given DataFrame.
    """
    if df.empty:
        return
        
    c1, c2 = st.columns(2)
    
    # 1. Excel Export (Requires openpyxl)
    try:
        with c1:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Data')
            processed_data = output.getvalue()
            
            st.download_button(
                label="📤 Exportar a Excel",
                data=processed_data,
                file_name=f"{file_prefix}_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    except Exception as e:
        st.error(f"Error generando Excel: {e}")

    # 2. CSV Export
    with c2:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Exportar a CSV",
            data=csv,
            file_name=f"{file_prefix}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime='text/csv',
            use_container_width=True
        )
