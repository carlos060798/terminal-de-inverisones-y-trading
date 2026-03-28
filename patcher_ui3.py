import re
STOCK_PATH = r"c:\Users\usuario\Videos\dasboard\sections\stock_analyzer.py"

with open(STOCK_PATH, "r", encoding="utf-8") as f:
    content = f.read()

if "import sentiment" not in content:
    content = content.replace("import ml_engine\n", "import ml_engine\nimport sentiment\nimport sys\nsys.path.append('c:/Users/usuario/Videos/dasboard/agents')\ntry:\n    from agents import devil_advocate\nexcept:\n    import devil_advocate\n")

# Analista Sentimiento UI
sentiment_ui = '''
                # ── ANALISTA SENTIMIENTO (FINBERT) ──
                if ticker_name and ticker_name != uploaded.name.replace(".pdf", ""):
                    with st.expander("🎭 Sentimiento Rápido de Noticias (NLP Local)"):
                        st.markdown("<div style='font-size:12px;color:#94a3b8;margin-bottom:10px;'>Simulación de Mr. Market impulsada por modelo ProsusAI/FinBERT procesado localmente con CUDA.</div>", unsafe_allow_html=True)
                        mock_headlines = [
                            f"{ticker_name} supera estimaciones pero guia a la baja",
                            "Analistas advierten de problemas en la cadena de suministro",
                            f"El CEO de {ticker_name} abandona su cargo de forma sorpresiva",
                            "Fuerte incremento en margenes operativos dispara optimismo"
                        ]
                        if st.button("Ejecutar Análisis de Sentimiento", key="finbert_btn"):
                            with st.spinner("Procesando con FinBERT Local..."):
                                s_res = sentiment.aggregate_sentiment(mock_headlines)
                                st.markdown(f"**Score Promedio (-1 Bearish a +1 Bullish): {s_res['avg_score']}**")
                                st.write(f"Bullish: {s_res['bullish']} | Bearish: {s_res['bearish']}")
                                st.dataframe(pd.DataFrame(s_res['details']), use_container_width=True)
'''

# Abogado del Diablo UI
devil_ui = '''
    # ══════════════════════════════════════════════════════════════
    # POST-MORTEM & PRE-MORTEM (El Abogado del Diablo)
    # ══════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 😈 Diario de Inversión y Pre-Mortem (Orquestado por LangGraph)")
    col_thesis, col_advocate = st.columns([1, 1])
    with col_thesis:
        st.write("Escribe tu tesis de inversión brevemente para someterla al juez:")
        user_thesis = st.text_area("Mi tesis para comprar/mantener", 
            value=f"Creo que {st.session_state.get('active_ticker', 'la empresa')} tiene un foso gigante y va a crecer a largo plazo...", height=200)
        btn_advocate = st.button("Someter Tesis al Abogado", type="primary")

    with col_advocate:
        if btn_advocate:
            with st.spinner("Despertando al Agente (LangGraph + Llama)..."):
                try:
                    score_simulated = 85
                    res = devil_advocate.run_pre_mortem(st.session_state.get('active_ticker', 'UNKN'), user_thesis, score_simulated)
                    
                    st.markdown("""<div style='background:#451a03;border:2px solid #f87171;border-radius:10px;padding:15px;color:#fca5a5;'>
                      <h4 style='color:#f87171;margin-top:0;'>X Destruccion de la Tesis (Pre-Mortem)</h4>
                      <b>Sesgos Cognitivos Detectados:</b><br>
                      {}<br><br>
                      <b>Riesgos Catastróficos Fatales (Por qué quebrarás):</b><br>
                      {}
                    </div>""".format("<br>".join(res["biases_detected"]), "<br>".join(res["fatal_flaws"])), unsafe_allow_html=True)
                    st.success("Tesis procesada en Diario de Inversiones -> Final: " + res.get("final_decision", "Revisión"))
                except Exception as e:
                    st.error(f"Error invocando LangGraph: {e}")
        else:
            st.info("Presiona 'Someter' para evaluar tus sesgos (Kahneman) mediante RAG y el modelo generativo.")
'''

# Inserción de UI Sentimiento cerca del análisis AI
content = content.replace(
    "# ── AI ANALYSIS (PDF) ──",
    sentiment_ui + "\n                # ── AI ANALYSIS (PDF) ──"
)

# Inserción de UI Post-Mortem al final del archivo
content = content + "\n" + devil_ui

with open(STOCK_PATH, "w", encoding="utf-8") as f:
    f.write(content)
