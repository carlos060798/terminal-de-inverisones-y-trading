"""
pages/investment_thesis.py - Investment Thesis section (MOAT, Porter, Bull/Bear)
"""
import streamlit as st
import plotly.graph_objects as go
import json
import database as db


def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Tesis de Inversión</h1>
        <p>MOAT · Porter 5 Fuerzas · Bull/Bear Case · Veredicto</p>
      </div>
    </div>""", unsafe_allow_html=True)

    thesis_ticker = st.text_input("Ticker para tesis", value="", placeholder="Ej: AAPL").strip().upper()

    if thesis_ticker:
        existing = db.get_investment_notes(thesis_ticker)

        # Try to load SWOT from most recent stock analysis for auto-fill hints
        swot_hint = {}
        try:
            df_sa = db.get_stock_analyses()
            if not df_sa.empty:
                match = df_sa[df_sa["ticker"].str.upper() == thesis_ticker]
                if not match.empty:
                    raw = match.iloc[0].get("raw_data", "")
                    if raw:
                        parsed = json.loads(raw) if isinstance(raw, str) else raw
                        swot_hint = parsed.get("swot", {})
        except Exception:
            pass

        tab_moat, tab_porter, tab_thesis, tab_notes = st.tabs([
            "🏰 MOAT", "⚡ Porter 5 Fuerzas", "📊 Bull / Bear", "📝 Notas"
        ])

        # ── MOAT TAB ──
        with tab_moat:
            st.markdown("<div class='sec-title'>Evaluación de Ventaja Competitiva (MOAT)</div>", unsafe_allow_html=True)
            moat_types = ["Sin MOAT claro", "Intangibles (marca/patentes)", "Costes de cambio",
                          "Efecto de red", "Ventaja en costes", "Escala eficiente", "Múltiple"]
            moat_type = st.selectbox("Tipo de MOAT", moat_types,
                                     index=moat_types.index(existing.get("moat_type", "Sin MOAT claro"))
                                     if existing.get("moat_type", "") in moat_types else 0)
            moat_rating = st.slider("Solidez del MOAT", 0, 5,
                                    value=existing.get("moat_rating", 0),
                                    help="0 = Sin ventaja, 5 = Franquicia indestructible")

            moat_colors = ["#ef4444", "#f97316", "#eab308", "#84cc16", "#22c55e", "#10b981"]
            moat_labels = ["Sin ventaja", "Débil", "Moderado", "Bueno", "Fuerte", "Excepcional"]
            st.markdown(f"""
            <div style='background:{moat_colors[moat_rating]};color:#000;padding:12px 20px;
                 border-radius:8px;font-weight:600;text-align:center;font-size:18px;margin-top:8px;'>
                {moat_labels[moat_rating]} ({moat_rating}/5)
            </div>""", unsafe_allow_html=True)

        # ── PORTER TAB ──
        with tab_porter:
            st.markdown("<div class='sec-title'>Análisis Porter — 5 Fuerzas Competitivas</div>", unsafe_allow_html=True)
            st.caption("1 = Fuerza baja (favorable) · 5 = Fuerza alta (desfavorable)")

            porter_forces = [
                ("Rivalidad competitiva", "porter_rivalry", "porter_rivalry_r"),
                ("Amenaza nuevos entrantes", "porter_new_entrants", "porter_new_entrants_r"),
                ("Amenaza sustitutos", "porter_substitutes", "porter_substitutes_r"),
                ("Poder de negociación compradores", "porter_buyer_power", "porter_buyer_power_r"),
                ("Poder de negociación proveedores", "porter_supplier_power", "porter_supplier_power_r"),
            ]

            porter_ratings = []
            porter_notes_dict = {}
            for label, note_key, rating_key in porter_forces:
                c1, c2 = st.columns([1, 2])
                with c1:
                    r = st.slider(label, 1, 5, value=max(1, existing.get(rating_key, 3)), key=f"p_{rating_key}")
                    porter_ratings.append(r)
                with c2:
                    n = st.text_area(f"Notas: {label}", value=existing.get(note_key, ""),
                                     height=68, key=f"p_{note_key}")
                    porter_notes_dict[note_key] = n
                    porter_notes_dict[rating_key] = r

            # Radar chart
            categories = ["Rivalidad", "Nuevos\nEntrantes", "Sustitutos", "Poder\nCompradores", "Poder\nProveedores"]
            fig_porter = go.Figure()
            fig_porter.add_trace(go.Scatterpolar(
                r=porter_ratings + [porter_ratings[0]],
                theta=categories + [categories[0]],
                fill='toself',
                fillcolor='rgba(0, 176, 255, 0.15)',
                line=dict(color='#00b0ff', width=2),
                marker=dict(size=8, color='#00b0ff'),
            ))
            fig_porter.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 5], tickvals=[1,2,3,4,5],
                                    gridcolor="#1a1a1a", tickfont=dict(color="#64748b", size=10)),
                    angularaxis=dict(gridcolor="#1a1a1a", tickfont=dict(color="#94a3b8", size=11)),
                    bgcolor="rgba(0,0,0,0)",
                ),
                showlegend=False,
                margin=dict(l=60, r=60, t=40, b=40),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=400,
            )
            st.plotly_chart(fig_porter, use_container_width=True)

            avg_porter = sum(porter_ratings) / len(porter_ratings)
            if avg_porter <= 2:
                porter_verdict = "Industria muy atractiva"
                pv_color = "#22c55e"
            elif avg_porter <= 3:
                porter_verdict = "Industria moderadamente atractiva"
                pv_color = "#eab308"
            else:
                porter_verdict = "Industria poco atractiva"
                pv_color = "#ef4444"
            st.markdown(f"""
            <div style='background:{pv_color};color:#000;padding:10px 16px;border-radius:8px;
                 font-weight:600;text-align:center;'>
                Promedio: {avg_porter:.1f}/5 — {porter_verdict}
            </div>""", unsafe_allow_html=True)

        # ── BULL/BEAR TAB ──
        with tab_thesis:
            st.markdown("<div class='sec-title'>Caso Bull / Bear</div>", unsafe_allow_html=True)

            bull_default = existing.get("thesis_bull", "")
            bear_default = existing.get("thesis_bear", "")
            if not bull_default and swot_hint:
                strengths = swot_hint.get("strengths", [])
                opportunities = swot_hint.get("opportunities", [])
                if strengths or opportunities:
                    bull_default = "\n".join(f"• {s}" for s in (strengths + opportunities)[:5])
            if not bear_default and swot_hint:
                weaknesses = swot_hint.get("weaknesses", [])
                threats = swot_hint.get("threats", [])
                if weaknesses or threats:
                    bear_default = "\n".join(f"• {s}" for s in (weaknesses + threats)[:5])

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🟢 Caso Bull")
                thesis_bull = st.text_area("¿Por qué subiría?", value=bull_default, height=200, key="bull")
            with c2:
                st.markdown("#### 🔴 Caso Bear")
                thesis_bear = st.text_area("¿Por qué bajaría?", value=bear_default, height=200, key="bear")

            verdict_options = ["Sin veredicto", "Comprar", "Mantener", "Evitar"]
            thesis_verdict = st.selectbox("Veredicto",
                                          verdict_options,
                                          index=verdict_options.index(existing.get("thesis_verdict", "Sin veredicto"))
                                          if existing.get("thesis_verdict", "") in verdict_options else 0)

            verdict_colors = {"Comprar": "#22c55e", "Mantener": "#eab308", "Evitar": "#ef4444", "Sin veredicto": "#64748b"}
            st.markdown(f"""
            <div style='background:{verdict_colors.get(thesis_verdict, "#64748b")};color:#000;
                 padding:14px 20px;border-radius:10px;font-weight:700;text-align:center;
                 font-size:22px;margin-top:12px;'>
                {thesis_ticker} → {thesis_verdict}
            </div>""", unsafe_allow_html=True)

        # ── NOTES TAB ──
        with tab_notes:
            st.markdown("<div class='sec-title'>Notas Cualitativas</div>", unsafe_allow_html=True)
            management_notes = st.text_area("Gestión / Management",
                                            value=existing.get("management_notes", ""),
                                            height=120, key="mgmt",
                                            placeholder="Calidad del equipo directivo, track record, alineación con accionistas...")
            culture_notes = st.text_area("Cultura Corporativa",
                                         value=existing.get("culture_notes", ""),
                                         height=120, key="culture",
                                         placeholder="Glassdoor, innovación, retención talento, ESG...")
            custom_notes = st.text_area("Notas adicionales",
                                        value=existing.get("custom_notes", ""),
                                        height=120, key="custom",
                                        placeholder="Cualquier otro factor relevante para la tesis...")

        # ── SAVE BUTTON ──
        if st.button("💾  Guardar Tesis", type="primary", use_container_width=True):
            notes_payload = {
                "moat_type": moat_type,
                "moat_rating": moat_rating,
                "porter_rivalry": porter_notes_dict.get("porter_rivalry", ""),
                "porter_rivalry_r": porter_notes_dict.get("porter_rivalry_r", 3),
                "porter_new_entrants": porter_notes_dict.get("porter_new_entrants", ""),
                "porter_new_entrants_r": porter_notes_dict.get("porter_new_entrants_r", 3),
                "porter_substitutes": porter_notes_dict.get("porter_substitutes", ""),
                "porter_substitutes_r": porter_notes_dict.get("porter_substitutes_r", 3),
                "porter_buyer_power": porter_notes_dict.get("porter_buyer_power", ""),
                "porter_buyer_power_r": porter_notes_dict.get("porter_buyer_power_r", 3),
                "porter_supplier_power": porter_notes_dict.get("porter_supplier_power", ""),
                "porter_supplier_power_r": porter_notes_dict.get("porter_supplier_power_r", 3),
                "management_notes": management_notes,
                "culture_notes": culture_notes,
                "thesis_bull": thesis_bull,
                "thesis_bear": thesis_bear,
                "thesis_verdict": thesis_verdict,
                "custom_notes": custom_notes,
            }
            db.save_investment_notes(thesis_ticker, notes_payload)
            st.success(f"Tesis guardada para {thesis_ticker}")

        # ── SAVED THESES TABLE ──
        st.markdown("---")
        st.markdown("<div class='sec-title'>Tesis Guardadas</div>", unsafe_allow_html=True)
        df_notes = db.get_all_investment_notes()
        if not df_notes.empty:
            cols_display = ["ticker", "moat_type", "moat_rating", "thesis_verdict", "updated_at"]
            df_show = df_notes[[c for c in cols_display if c in df_notes.columns]].copy()
            df_show.columns = ["Ticker", "MOAT", "Rating", "Veredicto", "Actualizado"][:len(df_show.columns)]
            st.dataframe(df_show, use_container_width=True, hide_index=True)
        else:
            st.info("No hay tesis guardadas aún.")
