import os

filepath = r"d:\dasboard\sections\stock_analyzer.py"
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False

import_added = False

for i, line in enumerate(lines):
    # Just in case imports are missing
    if "import forecast_synthesizer" in line and not import_added:
        new_lines.append(line)
        new_lines.append("from services import ai_report_engine\n")
        new_lines.append("from services import segment_parser\n")
        import_added = True
        continue

    # Add AI button to the sidebar
    if "st.markdown(\"### 📤 Intelligence Exports\")" in line:
        sidebar_addition = """        st.markdown("### ⚡ AI Intelligence")
        if st.button("⚡ Generar Reporte IA", use_container_width=True, type="primary"):
            st.session_state["ai_report_markdown"] = ai_report_engine.generate_ai_report(
                st.session_state.get('active_ticker', 'Ticker'),
                st.session_state.get("analyzer_res", {})
            )
            
        if "ai_report_markdown" in st.session_state:
            with st.expander("Ver Reporte IA", expanded=True):
                st.markdown(st.session_state["ai_report_markdown"])
                if st.button("📋 Copiar Reporte"):
                    st.toast("Reporte copiado", icon="✅")
                    
        st.markdown("---")
"""
        new_lines.append(sidebar_addition)
        new_lines.append(line)
        continue

    if line.startswith("def _render_general_tab(res):") or line.startswith("@st.fragment\ndef _render_general_tab(res):"):
        # We start replacing here
        pass

    new_lines.append(line)

# Since doing line-by-line replacement of HUGE functions in python script is brittle,
# I will use multi_replace_file_content for targeted replacements. Let's not overwrite the file here.
