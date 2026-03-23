"""
sections/chart_vision.py - AI Chart Vision
Upload screenshots of ANY asset (stocks, forex, crypto, commodities) for AI analysis.
Uses Gemini Vision (primary) or HuggingFace Qwen2.5-VL (fallback).
"""
import streamlit as st
from datetime import datetime


def render():
    st.markdown("""<div class='top-header'>
        <h1>AI Chart Vision</h1>
        <p>Sube screenshots de cualquier grafico para analisis tecnico con IA</p>
    </div>""", unsafe_allow_html=True)

    # ── Upload Section ──
    col_upload, col_config = st.columns([3, 1])

    with col_config:
        asset_name = st.text_input("Activo *", placeholder="AAPL, EUR/USD, BTC, Gold...",
                                   key="vision_asset")
        timeframe = st.selectbox("Timeframe", [
            "1 min", "5 min", "15 min", "1H", "4H", "Daily", "Weekly", "Monthly"
        ], index=5, key="vision_tf")
        analysis_type = st.selectbox("Tipo de Analisis", [
            "Tecnico Completo", "Soportes y Resistencias",
            "Patrones Chartistas", "Accion de Precio"
        ], key="vision_type")

    with col_upload:
        uploaded_files = st.file_uploader(
            "Sube screenshots de tu chart",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="vision_uploader",
            help="Acepta PNG, JPG, WEBP. Puedes subir varios (ej: Daily + 4H del mismo par)"
        )

        if uploaded_files:
            # Preview thumbnails
            preview_cols = st.columns(min(len(uploaded_files), 4))
            for i, f in enumerate(uploaded_files[:4]):
                with preview_cols[i]:
                    st.image(f, caption=f.name, use_container_width=True)

    # ── Analyze Button ──
    if uploaded_files and asset_name.strip():
        if st.button("Analizar con AI Vision", type="primary", key="btn_vision_analyze"):
            from ai_engine import analyze_chart_image

            for i, uploaded in enumerate(uploaded_files):
                img_bytes = uploaded.read()
                uploaded.seek(0)  # Reset for re-read if needed

                with st.spinner(f"Analizando {uploaded.name} ({i+1}/{len(uploaded_files)})..."):
                    result = analyze_chart_image(
                        image_bytes=img_bytes,
                        asset=asset_name.strip().upper(),
                        timeframe=timeframe,
                        analysis_type=analysis_type,
                        file_name=uploaded.name
                    )

                # Display result
                st.markdown(f"""<div style='background:linear-gradient(145deg,#0a0a0a,#111111);
                    border:1px solid #1e293b;border-radius:16px;padding:24px;margin:16px 0;'>
                    <div style='display:flex;align-items:center;margin-bottom:12px;'>
                        <span style='font-size:20px;margin-right:10px;'>📊</span>
                        <span style='font-size:16px;font-weight:700;color:#60a5fa;'>
                            {asset_name.upper()} — {timeframe} — {analysis_type}
                        </span>
                        <span style='margin-left:auto;color:#475569;font-size:11px;'>
                            {uploaded.name} | {datetime.now().strftime('%H:%M:%S')}
                        </span>
                    </div>
                </div>""", unsafe_allow_html=True)
                st.markdown(result)
                st.markdown("---")

                # Save to session history
                if "vision_history" not in st.session_state:
                    st.session_state.vision_history = []
                st.session_state.vision_history.insert(0, {
                    "asset": asset_name.upper(),
                    "timeframe": timeframe,
                    "type": analysis_type,
                    "file": uploaded.name,
                    "result": result,
                    "time": datetime.now().strftime('%Y-%m-%d %H:%M')
                })
                # Keep last 20
                st.session_state.vision_history = st.session_state.vision_history[:20]

    elif uploaded_files and not asset_name.strip():
        st.warning("Ingresa el nombre del activo para analizar")

    # ── History ──
    history = st.session_state.get("vision_history", [])
    if history:
        st.markdown("### Historial de Analisis")
        for h in history[:10]:
            with st.expander(f"{h['asset']} | {h['timeframe']} | {h['type']} — {h['time']}", expanded=False):
                st.markdown(h["result"])

    # ── Provider Status ──
    with st.expander("Estado de Providers AI Vision", expanded=False):
        try:
            from ai_engine import get_usage_dashboard
            providers_data = get_usage_dashboard()
            vision_providers = [p for p in providers_data if p.get("vision")]
            if vision_providers:
                for p in vision_providers:
                    status = "🟢" if p.get("available") else "🔴"
                    used = p.get("used", 0)
                    limit = p.get("limit", 0)
                    pct = p.get("pct", 0)
                    bar_color = "#10b981" if pct < 50 else "#f59e0b" if pct < 80 else "#ef4444"
                    st.markdown(f"""{status} **{p.get('name', p.get('id','?'))}** — {used}/{limit} req
                    <div style='background:#1e293b;border-radius:4px;height:8px;margin:4px 0 8px 0;'>
                        <div style='background:{bar_color};height:100%;border-radius:4px;width:{min(pct,100):.0f}%;'></div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.warning("No hay providers de vision disponibles")
        except Exception as e:
            st.error(f"Error cargando providers: {e}")
        st.markdown("""
        **Configuracion**: Agrega las keys en `.streamlit/secrets.toml`:
        ```
        GEMINI_API_KEY = "tu-api-key"
        HF_TOKEN = "hf_tu-token"
        ```
        """)
