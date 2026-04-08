import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
try:
    import yfinance as yf
except ImportError:
    yf = None
from ui_shared import DARK, dark_layout

def render():
    st.markdown("""
    <div class='top-header'>
      <div>
        <h1>Historical Cycle Comparator</h1>
        <p>Buscador de Fractales y Patrones Históricos de Precio</p>
      </div>
    </div>""", unsafe_allow_html=True)

    if not yf:
        st.error("yfinance no está instalado.")
        return

    c1, c2, c3 = st.columns([2, 1, 1])
    ticker = c1.text_input("Ticker para buscar patrones", value="SPY", placeholder="SPY, QQQ, BTC-USD...")
    window = c2.number_input("Días del Patrón (Ventana)", min_value=5, max_value=60, value=20)
    history_years = c3.selectbox("Años de historia", [1, 2, 5, 10], index=1)

    if st.button("Buscar Fractales Similares", type="primary", use_container_width=True):
        with st.spinner("Analizando ciclos históricos..."):
            try:
                # 1. Fetch data
                total_days = history_years * 252 + window
                data = yf.download(ticker, period=f"{history_years+1}y", progress=False)["Close"]
                
                if data.empty or len(data) < window * 2:
                    st.warning("No hay suficientes datos históricos.")
                    return
                
                # Handling multi-index columns if any
                if isinstance(data, pd.DataFrame):
                    data = data.iloc[:, 0]

                # 2. Extract current pattern (last 'window' days)
                current_pattern = data.iloc[-window:]
                current_norm = (current_pattern - current_pattern.mean()) / current_pattern.std()
                
                # 3. Slide window through history (excluding last 'window' days)
                search_data = data.iloc[:-window]
                best_corr = -1
                best_idx = None
                
                # Optimization: Slide every 3 days to be faster
                for i in range(0, len(search_data) - window, 2):
                    hist_window = search_data.iloc[i : i + window]
                    if hist_window.std() == 0: continue
                    
                    hist_norm = (hist_window - hist_window.mean()) / hist_window.std()
                    corr = np.corrcoef(current_norm, hist_norm)[0, 1]
                    
                    if corr > best_corr:
                        best_corr = corr
                        best_idx = i
                
                # 4. Display Results
                if best_idx is not None:
                    matched_pattern = search_data.iloc[best_idx : best_idx + window]
                    
                    st.success(f"¡Patrón encontrado! Máxima correlación: {best_corr:.2f}")
                    st.markdown(f"**Periodo Detectado:** {search_data.index[best_idx].date()} al {search_data.index[best_idx+window].date()}")
                    
                    # Next 10 days after match for 'prediction'
                    future_idx = best_idx + window
                    post_match = search_data.iloc[future_idx : future_idx + 10]
                    
                    fig = go.Figure()
                    # Current norm
                    fig.add_trace(go.Scatter(y=current_norm.values, name="Patrón Actual", line=dict(color="#60a5fa", width=3)))
                    # Matched norm
                    hist_match_norm = (matched_pattern - matched_pattern.mean()) / matched_pattern.std()
                    fig.add_trace(go.Scatter(y=hist_match_norm.values, name="Patrón Histórico", line=dict(color="#f87171", width=2, dash='dot')))
                    
                    fig.update_layout(**DARK, height=400, title="Comparación de Fractales (Normalizados)")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    if not post_match.empty:
                        st.markdown("#### ¿Qué pasó después en ese ciclo?")
                        post_norm = (post_match - matched_pattern.mean()) / matched_pattern.std()
                        fig_post = go.Figure()
                        fig_post.add_trace(go.Scatter(y=list(hist_match_norm.values) + list(post_norm.values), 
                                                    name="Evolución Histórica", line=dict(color="#a78bfa")))
                        fig_post.add_vline(x=len(hist_match_norm)-1, line_dash="dash", line_color="#fbbf24")
                        fig_post.update_layout(**DARK, height=300, title="Proyección basada en el fractal")
                        st.plotly_chart(fig_post, use_container_width=True)
                else:
                    st.info("No se encontró una correlación significativa.")

            except Exception as e:
                st.error(f"Error en el buscador de patrones: {e}")

def main():
    render()

if __name__ == "__main__":
    main()
