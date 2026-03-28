import re
STOCK_PATH = r"c:\Users\usuario\Videos\dasboard\sections\stock_analyzer.py"

with open(STOCK_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# Add rag_engine import near ml_engine import
if "import rag_engine" not in content:
    content = content.replace("import ml_engine\n", "import ml_engine\nimport rag_engine\nimport json\n")

# Add the Peter Lynch category near the SCORE section or inside the Absolute Figures 
# Wait, let's just make an expander for Machine Learning Classifier
lynch_ui = """
                # ── MACHINE LEARNING (PETER LYNCH CLASSIFIER) ──
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    try:
                        import ml_engine
                        ml_res = ml_engine.analyze_ticker(ticker_name)
                        if ml_res:
                            lynch_t = ml_res.get("lynch_profile", "Unknown")
                            lynch_c = ml_res.get("lynch_confidence", 0)
                            st.markdown(f\"\"\"
                            <div style='background:linear-gradient(90deg, #1e1b4b, #312e81);border:1px solid #4f46e5;
                                        border-radius:12px;padding:16px;margin-bottom:20px;display:flex;align-items:center;gap:15px;'>
                              <div style='font-size:36px;'>🧠</div>
                              <div>
                                <div style='color:#a5b4fc;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;'>Clasificador Neural de Peter Lynch</div>
                                <div style='color:#f0f6ff;font-size:20px;font-weight:800;'>{lynch_t} <span style='font-size:14px;color:#818cf8;font-weight:500;'>({lynch_c}% precision)</span></div>
                              </div>
                            </div>
                            \"\"\", unsafe_allow_html=True)
                    except Exception as e:
                        pass
"""

# Insert lynch UI right before the Fair Value traffic light
content = content.replace(
    "# ── FAIR VALUE TRAFFIC LIGHT ──",
    lynch_ui + "\n                # ── FAIR VALUE TRAFFIC LIGHT ──"
)

# Add RAG Memory ingestion near Auto Save
rag_ui = """
                # ── RAG MEMORY VECTOR DB ──
                if rag_engine.HAS_CHROMA:
                    doc_json = json.dumps(parsed, ensure_ascii=False)
                    if st.button("🧠 Guardar Reporte en Memoria Vectorial Avanzada (RAG)"):
                        with st.spinner("Generando Embeddings y Guardando en base local..."):
                            success = rag_engine.ingest_document(ticker_name, uploaded.name, doc_json)
                            if success:
                                st.success(f"Reporte '{uploaded.name}' integrado en tu cerebro vectorial de inversiones. (Total base: {rag_engine.get_memory_stats()} chunks)")
                            else:
                                st.error("No se pudo guardar en ChromaDB. Revisa la consola.")
"""

# Insert after: st.success("Analisis guardado automaticamente.")
content = re.sub(
    r'(st\.success\("Analisis guardado automaticamente\."\))',
    r'\1\n' + rag_ui,
    content,
    flags=re.DOTALL
)

with open(STOCK_PATH, "w", encoding="utf-8") as f:
    f.write(content)
