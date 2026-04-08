import re

with open(r"d:\dasboard\sections\screener.py", "r", encoding="utf-8") as f:
    text = f.read()

# REFACTOR FETCHING LOOP TO CONCURRENT FUTURES
loop_search = r'''        with st.spinner\(f"Escaneando \{len\(tickers\)\} acciones..."\):
            results = \[\]
            progress = st.progress\(0\)

            for i, ticker in enumerate\(tickers\):
                progress.progress\(\(i \+ 1\) / len\(tickers\)\)
                try:
                    tk = yf.Ticker\(ticker\)
                    info = tk.info
                    if not info.get\("currentPrice"\) and not info.get\("regularMarketPrice"\):
                        continue

                    price = info.get\("currentPrice"\) or info.get\("regularMarketPrice", 0\)
                    sector = info.get\("sector", ""\)
                    country = info.get\("country", ""\)
                    name = info.get\("shortName", ticker\)

                    # ── Apply dynamic filters ──
                    passed = True
                    for metric_name, \(slider_lo, slider_hi\) in filter_values.items\(\):
                        metric = AVAILABLE_METRICS\[metric_name\]
                        yf_key = metric\["key"\]
                        scale = metric.get\("scale", 1\)

                        # Handle computed metrics
                        if metric.get\("computed"\) and yf_key == "fiftyTwoWeekHigh_pct":
                            high52 = info.get\("fiftyTwoWeekHigh"\)
                            if high52 and high52 > 0:
                                raw_val = \(\(price - high52\) / high52\) \* 100
                            else:
                                raw_val = None
                        else:
                            raw_val = info.get\(yf_key\)

                        if raw_val is None:
                            # Skip filter if data not available \(don't exclude\)
                            continue

                        # Convert raw value to display units
                        # For large numbers \(marketCap, volume\): divide by scale \(1e9, 1e6\)
                        # For ratios \(dividendYield, ROE, margins\): multiply by scale \(100\)
                        if yf_key in \("marketCap", "averageVolume"\):
                            display_val = raw_val / scale
                        elif scale != 1:
                            display_val = raw_val \* scale
                        else:
                            display_val = raw_val

                        # Check if value is within slider range
                        if display_val < slider_lo or display_val > slider_hi:
                            passed = False
                            break

                    if not passed:
                        continue

                    # Extract common values for results table
                    pe = info.get\("trailingPE"\)
                    pe_fwd = info.get\("forwardPE"\)
                    roe = \(info.get\("returnOnEquity"\) or 0\) \* 100
                    margin = \(info.get\("profitMargins"\) or 0\) \* 100
                    mcap = info.get\("marketCap", 0\)
                    de = info.get\("debtToEquity"\) or 0
                    div_y = \(info.get\("dividendYield"\) or 0\) \* 100
                    peg = info.get\("pegRatio"\)
                    beta = info.get\("beta"\)
                    rev_growth = \(info.get\("revenueGrowth"\) or 0\) \* 100
                    earn_growth = \(info.get\("earningsGrowth"\) or 0\) \* 100
                    avg_volume = info.get\("averageVolume"\) or info.get\("averageDailyVolume10Day"\) or 0

                    # Score \(simple scoring: count how many criteria are "good"\)
                    score = 0
                    if pe and pe < 20: score \+= 1
                    if roe > 15: score \+= 1
                    if margin > 15: score \+= 1
                    if de < 100: score \+= 1
                    if peg and peg < 1.5: score \+= 1
                    if rev_growth > 10: score \+= 1

                    results.append\(\{
                        "Ticker": ticker, "Empresa": name\[:25\], "Sector": sector,
                        "Pais": country,
                        "Precio": price, "P/E": pe, "P/E Fwd": pe_fwd,
                        "ROE %": round\(roe, 1\), "Margen %": round\(margin, 1\),
                        "D/E": round\(de, 2\), "PEG": peg, "Beta": beta,
                        "Div %": round\(div_y, 2\), "Crec Rev %": round\(rev_growth, 1\),
                        "Crec Earn %": round\(earn_growth, 1\),
                        "Mkt Cap": mcap, "Vol Prom": avg_volume, "Score": score,
                    \}\)
                except Exception:
                    continue

            progress.empty\(\)'''

threaded_logic = '''        with st.spinner(f"Escaneando {len(tickers)} acciones con procesamiento paralelo..."):
            results = []
            progress = st.progress(0)
            
            import concurrent.futures

            def _process_ticker(ticker):
                try:
                    tk = yf.Ticker(ticker)
                    info = tk.info
                    if not info.get("currentPrice") and not info.get("regularMarketPrice"):
                        return None

                    price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
                    sector = info.get("sector", "")
                    country = info.get("country", "")
                    name = info.get("shortName", ticker)

                    passed = True
                    for metric_name, (slider_lo, slider_hi) in filter_values.items():
                        metric = AVAILABLE_METRICS[metric_name]
                        yf_key = metric["key"]
                        scale = metric.get("scale", 1)

                        if metric.get("computed") and yf_key == "fiftyTwoWeekHigh_pct":
                            high52 = info.get("fiftyTwoWeekHigh")
                            if high52 and high52 > 0:
                                raw_val = ((price - high52) / high52) * 100
                            else:
                                raw_val = None
                        else:
                            raw_val = info.get(yf_key)

                        if raw_val is None:
                            continue

                        if yf_key in ("marketCap", "averageVolume"):
                            display_val = raw_val / scale
                        elif scale != 1:
                            display_val = raw_val * scale
                        else:
                            display_val = raw_val

                        if display_val < slider_lo or display_val > slider_hi:
                            passed = False
                            break

                    if not passed:
                        return None

                    pe = info.get("trailingPE")
                    pe_fwd = info.get("forwardPE")
                    roe = (info.get("returnOnEquity") or 0) * 100
                    margin = (info.get("profitMargins") or 0) * 100
                    mcap = info.get("marketCap", 0)
                    de = info.get("debtToEquity") or 0
                    div_y = (info.get("dividendYield") or 0) * 100
                    peg = info.get("pegRatio")
                    beta = info.get("beta")
                    rev_growth = (info.get("revenueGrowth") or 0) * 100
                    earn_growth = (info.get("earningsGrowth") or 0) * 100
                    avg_volume = info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0

                    score = 0
                    if pe and pe < 20: score += 1
                    if roe > 15: score += 1
                    if margin > 15: score += 1
                    if de < 100: score += 1
                    if peg and peg < 1.5: score += 1
                    if rev_growth > 10: score += 1

                    return {
                        "Ticker": ticker, "Empresa": name[:25], "Sector": sector,
                        "Pais": country, "Precio": price, "P/E": pe, "P/E Fwd": pe_fwd,
                        "ROE %": round(roe, 1), "Margen %": round(margin, 1),
                        "D/E": round(de, 2), "PEG": peg, "Beta": beta,
                        "Div %": round(div_y, 2), "Crec Rev %": round(rev_growth, 1),
                        "Crec Earn %": round(earn_growth, 1),
                        "Mkt Cap": mcap, "Vol Prom": avg_volume, "Score": score,
                    }
                except Exception:
                    return None

            completed = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_ticker = {executor.submit(_process_ticker, t): t for t in tickers}
                for future in concurrent.futures.as_completed(future_to_ticker):
                    completed += 1
                    progress.progress(completed / len(tickers))
                    res = future.result()
                    if res:
                        results.append(res)

            progress.empty()'''

text = re.sub(loop_search, threaded_logic, text, flags=re.MULTILINE)

# REFACTOR RENDER LOOP TO CARDS UI
render_search = r'''        if HAS_AGGRID:
            gb = GridOptionsBuilder\.from_dataframe\(df_show\)
            gb\.configure_pagination\(paginationAutoPageSize=False, paginationPageSize=25\)
            gb\.configure_default_column\(filterable=True, sortable=True, resizable=True\)
            gb\.configure_column\("Ticker", pinned="left", cellStyle=\{"fontWeight": "bold", "color": "#60A5FA"\}\)
            
            # Format numbers
            gb\.configure_column\("Precio", type=\["numericColumn", "numberColumnFilter"\], valueFormatter="x == null \? '--' : '\\$' \+ parseFloat\(x\)\.toFixed\(2\)"\)
            gb\.configure_column\("P/E", type=\["numericColumn", "numberColumnFilter"\], valueFormatter="x == null \? '--' : parseFloat\(x\)\.toFixed\(1\) \+ 'x'"\)
            gb\.configure_column\("P/E Fwd", type=\["numericColumn", "numberColumnFilter"\], valueFormatter="x == null \? '--' : parseFloat\(x\)\.toFixed\(1\) \+ 'x'"\)
            gb\.configure_column\("D/E", type=\["numericColumn", "numberColumnFilter"\], valueFormatter="x == null \? '--' : parseFloat\(x\)\.toFixed\(2\)"\)
            gb\.configure_column\("PEG", type=\["numericColumn", "numberColumnFilter"\], valueFormatter="x == null \? '--' : parseFloat\(x\)\.toFixed\(2\)"\)
            gb\.configure_column\("Beta", type=\["numericColumn", "numberColumnFilter"\], valueFormatter="x == null \? '--' : parseFloat\(x\)\.toFixed\(2\)"\)
            gb\.configure_column\("Div %", type=\["numericColumn", "numberColumnFilter"\], valueFormatter="x == null \? '--' : parseFloat\(x\)\.toFixed\(2\) \+ '%'"\)
            gb\.configure_column\("Vol Prom", type=\["numericColumn"\], valueFormatter="x == null \? '--' : \(x >= 1e6 \? \(x/1e6\)\.toFixed\(1\) \+ 'M' : \(x/1e3\)\.toFixed\(0\) \+ 'K'\)"\)
            
            # Additional UI colors
            jscode = """
            function\(params\) \{
                if \(params\.data\.Score >= 5\) \{
                    return \{'backgroundColor': 'rgba\(52,211,153,0\.15\)', 'color': '#34d399'\};
                \} else if \(params\.data\.Score >= 3\) \{
                    return \{'backgroundColor': 'rgba\(251,191,36,0\.15\)', 'color': '#fbbf24'\};
                \} else \{
                    return \{'backgroundColor': 'rgba\(248,113,113,0\.1\)', 'color': '#f87171'\};
                \}
            \}
            """
            
            go_opts = gb\.build\(\)
            AgGrid\(
                df_show,
                gridOptions=go_opts,
                columns_auto_size_mode=ColumnsAutoSizeMode\.FIT_CONTENTS,
                theme="alpine",
                allow_unsafe_jscode=True,
                height=500
            \)

        else:
            style_obj = df_show\.style\.map\(score_color, subset=\["Score"\]\)
            if "Quant" in df_show\.columns:
                style_obj = style_obj\.map\(quant_color, subset=\["Quant"\]\)
            if "Piotroski" in df_show\.columns:
                style_obj = style_obj\.map\(piotroski_color, subset=\["Piotroski"\]\)
            if "Altman Z" in df_show\.columns:
                style_obj = style_obj\.map\(altman_color, subset=\["Altman Z"\]\)

            st\.dataframe\(
                style_obj\.format\(\{"Precio": "\\${:\.2f}", "P/E": "\{:\.1f\}", "P/E Fwd": "\{:\.1f\}",
                                "D/E": "\{:\.2f\}", "PEG": "\{:\.2f\}", "Beta": "\{:\.2f\}",
                                "Div %": "\{:\.2f\}%",
                                "Vol Prom": lambda v: f"\{v/1e6:\.1f\}M" if v and v > 1e6
                                            else \(f"\{v/1e3:\.0f\}K" if v and v > 1e3 else "--"\)\},
                                na_rep="--"\),
                use_container_width=True, hide_index=True
            \)'''

cards_logic = '''        # ── STOCK CARDS UI REDESIGN ──
        st.markdown("<br>", unsafe_allow_html=True)
        
        top_n_cards = 15
        df_cards = df_show.head(top_n_cards)

        st.markdown("<div class='sec-title'>Top Oportunidades Identificadas</div>", unsafe_allow_html=True)
        
        cols_per_row = 3
        for i in range(0, len(df_cards), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(df_cards):
                    row = df_cards.iloc[i + j]
                    
                    t_tick = row["Ticker"]
                    t_name = row["Empresa"]
                    t_pe = row.get("P/E", "--")
                    t_pe = f"{t_pe:.1f}x" if pd.notna(t_pe) else "--"
                    
                    t_roe = row.get("ROE %", "--")
                    t_roe = f"{t_roe:.1f}%" if pd.notna(t_roe) else "--"
                    roe_color = "#34d399" if pd.notna(row.get("ROE %")) and row["ROE %"] > 15 else ("#f87171" if pd.notna(row.get("ROE %")) and row["ROE %"] < 5 else "#94a3b8")
                    
                    t_mar = row.get("Margen %", "--")
                    t_mar = f"{t_mar:.1f}%" if pd.notna(t_mar) else "--"
                    mar_color = "#34d399" if pd.notna(row.get("Margen %")) and row["Margen %"] > 15 else ("#f87171" if pd.notna(row.get("Margen %")) and row["Margen %"] < 5 else "#94a3b8")
                    
                    t_score = row.get("Score", 0)
                    t_quant = row.get("Quant", 50)
                    q_color = "#34d399" if pd.notna(t_quant) and t_quant > 70 else ("#fbbf24" if pd.notna(t_quant) and t_quant >= 40 else "#f87171")
                    
                    with col:
                        # Card HTML
                        st.markdown(f"""
                        <div style='background:linear-gradient(145deg, #111827, #1f2937); border: 1px solid #374151; border-radius: 12px; padding: 16px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); transition: transform 0.2s;'>
                            <div style='display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid #374151; padding-bottom: 8px; margin-bottom: 12px;'>
                                <div>
                                    <span style='font-size: 22px; font-weight: 800; color: #60A5FA; letter-spacing: 0.5px;'>{t_tick}</span>
                                    <div style='font-size: 11px; color: #9ca3af; text-overflow: ellipsis; white-space: nowrap; overflow: hidden; max-width: 150px;'>{t_name}</div>
                                </div>
                                <div style='background: {q_color}22; border: 1px solid {q_color}55; padding: 4px 10px; border-radius: 8px; text-align: center;'>
                                    <div style='font-size: 9px; color: {q_color}; font-weight: bold; letter-spacing: 0.5px; opacity: 0.8;'>QUANT</div>
                                    <div style='font-size: 18px; color: {q_color}; font-weight: 800;'>{int(t_quant) if pd.notna(t_quant) else 50}</div>
                                </div>
                            </div>
                            <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;'>
                                <div>
                                    <div style='font-size: 10px; color: #6b7280; text-transform: uppercase;'>P/E Ratio</div>
                                    <div style='font-size: 15px; color: #e5e7eb; font-weight: 700;'>{t_pe}</div>
                                </div>
                                <div>
                                    <div style='font-size: 10px; color: #6b7280; text-transform: uppercase;'>Precio</div>
                                    <div style='font-size: 15px; color: #e5e7eb; font-weight: 700;'>${row.get("Precio", 0):.2f}</div>
                                </div>
                                <div>
                                    <div style='font-size: 10px; color: #6b7280; text-transform: uppercase;'>Margen Neto</div>
                                    <div style='font-size: 15px; color: {mar_color}; font-weight: 700;'>{t_mar}</div>
                                </div>
                                <div>
                                    <div style='font-size: 10px; color: #6b7280; text-transform: uppercase;'>ROE Promedio</div>
                                    <div style='font-size: 15px; color: {roe_color}; font-weight: 700;'>{t_roe}</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Acciones Button Group
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("➕ Watch", key=f"add_{t_tick}", help=f"Agregar {t_tick} a Watchlist", use_container_width=True):
                                db.add_ticker(t_tick, 0, row.get("Precio", 0), row.get("Sector", ""), "Desde screener (Card)")
                                st.success("Añadido!")
                        with b2:
                            if st.button("🔍 Ver Detalle", key=f"analyze_{t_tick}", help=f"Análisis fundamental de {t_tick}", type="primary", use_container_width=True):
                                st.session_state["active_ticker"] = t_tick
                                st.toast(f"{t_tick} marcado activo. Navega a Análisis de Acciones.")
                                
        if len(df_show) > top_n_cards:
            with st.expander(f"Ver {len(df_show) - top_n_cards} resultados adicionales"):
                st.dataframe(
                    df_show.iloc[top_n_cards:].style.map(score_color, subset=["Score"]).map(quant_color, subset=["Quant"]).format({"Precio": "${:.2f}", "P/E": "{:.1f}", "P/E Fwd": "{:.1f}",
                                "D/E": "{:.2f}", "PEG": "{:.2f}", "Beta": "{:.2f}", "Div %": "{:.2f}%"}, na_rep="--"),
                    use_container_width=True, hide_index=True
                )'''

text = re.sub(render_search, cards_logic, text, flags=re.MULTILINE)

with open(r"d:\dasboard\sections\screener.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Refactored screener.py completely")
