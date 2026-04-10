"""
report_generator.py - PDF Report Generator for Quantum Retail Terminal
Generates professional investment reports using fpdf2.
"""
import io
from datetime import datetime
from fpdf import FPDF


class InvestmentReport(FPDF):
    """Custom PDF with header/footer for investment reports."""

    def __init__(self, ticker: str, company_name: str = ""):
        super().__init__()
        self.ticker = ticker
        self.company_name = company_name or ticker
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"Quantum Retail Terminal  |  {self.ticker}", align="L")
        self.cell(0, 8, datetime.now().strftime("%Y-%m-%d"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 120, 200)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Quantum Terminal - Confidencial | Pagina {self.page_no()}/{{nb}}", align="C")

    # ── Helpers ──

    def section_title(self, title: str):
        self.ln(6)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(0, 51, 102) # Navy Blue
        self.cell(0, 10, title.upper(), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 51, 102)
        self.set_line_width(0.8)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def kv_row(self, label: str, value, bold_value: bool = False):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(80, 7, label + ":")
        style = "B" if bold_value else ""
        self.set_font("Helvetica", style, 10)
        self.set_text_color(0, 0, 0)
        self.cell(0, 7, str(value) if value is not None else "N/A",
                  new_x="LMARGIN", new_y="NEXT")

    def table(self, headers: list, rows: list, col_widths: list = None):
        if not col_widths:
            w = (190) / len(headers)
            col_widths = [w] * len(headers)

        # Header row
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(0, 100, 180)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 8, str(h), border=1, fill=True, align="C")
        self.ln()

        # Data rows
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        fill = False
        for row in rows:
            if self.get_y() > 260:
                self.add_page()
            if fill:
                self.set_fill_color(240, 245, 250)
            else:
                self.set_fill_color(255, 255, 255)
            for i, val in enumerate(row):
                align = "L" if i == 0 else "C"
                self.cell(col_widths[i], 7, str(val) if val is not None else "-",
                          border=1, fill=True, align=align)
            self.ln()
            fill = not fill

    def signal_badge(self, signal: str, color: str, upside_pct: float,
                     avg_fv: float, price: float):
        colors = {
            "green": (34, 197, 94),
            "yellow": (234, 179, 8),
            "red": (239, 68, 68),
        }
        labels = {
            "undervalued": "INFRAVALORADO",
            "fair": "VALORACION JUSTA",
            "overvalued": "SOBREVALORADO",
        }
        r, g, b = colors.get(color, (100, 100, 100))

        self.set_fill_color(r, g, b)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 14)
        label = labels.get(signal, signal.upper() if signal else "SIN DATOS")
        upside_str = f"  ({upside_pct:+.1f}%)" if upside_pct is not None else ""
        self.cell(190, 12, f"{label}{upside_str}", align="C",
                  fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

        self.set_text_color(60, 60, 60)
        self.set_font("Helvetica", "", 10)
        price_str = f"${price:,.2f}" if price else "N/A"
        fv_str = f"${avg_fv:,.2f}" if avg_fv else "N/A"
        self.cell(95, 7, f"Precio actual: {price_str}", align="C")
        self.cell(95, 7, f"Fair Value promedio: {fv_str}", align="C",
                  new_x="LMARGIN", new_y="NEXT")


def _fmt(val, suffix="", decimals=2):
    if val is None:
        return "N/A"
    if isinstance(val, (int, float)):
        if abs(val) >= 1e9:
            return f"${val/1e9:,.1f}B"
        if abs(val) >= 1e6:
            return f"${val/1e6:,.1f}M"
        if suffix == "%":
            return f"{val:.{decimals}f}%"
        if suffix == "x":
            return f"{val:.{decimals}f}x"
        return f"{val:,.{decimals}f}"
    return str(val)


def generate_report(ticker: str, parsed_data: dict = None,
                    fair_value: dict = None, advanced: dict = None,
                    thesis: dict = None) -> bytes:
    """
    Generate a PDF investment report.

    Returns bytes of the PDF file.
    """
    company = ""
    if parsed_data:
        company = parsed_data.get("key_indicators", {}).get("company_name", "")

    pdf = InvestmentReport(ticker, company)
    pdf.alias_nb_pages()
    pdf.add_page()

    # ── TITLE ──
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(0, 80, 160)
    title = f"{ticker}"
    if company:
        title = f"{company} ({ticker})"
    pdf.cell(0, 14, title, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f"Informe generado: {datetime.now().strftime('%d %b %Y %H:%M')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── FAIR VALUE SIGNAL ──
    if fair_value and fair_value.get("signal"):
        pdf.section_title("Semaforo de Fair Value")
        pdf.signal_badge(
            fair_value.get("signal", ""),
            fair_value.get("signal_color", ""),
            fair_value.get("upside_pct"),
            fair_value.get("avg_fair_value"),
            fair_value.get("current_price"),
        )
        pdf.ln(2)

        fv_rows = []
        if fair_value.get("pe_fair_value"):
            fv_rows.append(["P/E Multiples", f"${fair_value['pe_fair_value']:,.2f}"])
        if fair_value.get("dcf_fair_value"):
            fv_rows.append(["DCF Simplificado", f"${fair_value['dcf_fair_value']:,.2f}"])
        if fair_value.get("peg_fair_value"):
            fv_rows.append(["PEG (Lynch)", f"${fair_value['peg_fair_value']:,.2f}"])
        if fair_value.get("avg_fair_value"):
            fv_rows.append(["Promedio", f"${fair_value['avg_fair_value']:,.2f}"])
        if fv_rows:
            pdf.table(["Metodo", "Fair Value"], fv_rows, [95, 95])

    # ── KEY INDICATORS ──
    if parsed_data:
        ki = parsed_data.get("key_indicators", {})
        if ki:
            pdf.section_title("Indicadores Clave")
            indicators = [
                ("Precio", _fmt(ki.get("price"), decimals=2)),
                ("Market Cap", _fmt(ki.get("market_cap"))),
                ("P/E Ratio", _fmt(ki.get("pe_ratio"), "x")),
                ("P/E Forward", _fmt(ki.get("pe_fwd"), "x")),
                ("EPS (actual)", _fmt(ki.get("eps_actual"))),
                ("EPS (estimado)", _fmt(ki.get("eps_estimate"))),
                ("PEG Ratio", _fmt(ki.get("peg_ratio"), "x")),
                ("FCF Yield", _fmt(ki.get("fcf_yield"), "%")),
                ("EV/EBITDA", _fmt(ki.get("ev_ebitda"), "x")),
                ("Beta", _fmt(ki.get("beta"))),
                ("Div. Yield", _fmt(ki.get("div_yield"), "%")),
                ("Cambio 1Y", _fmt(ki.get("one_year_change"), "%")),
            ]
            rows = [[k, v] for k, v in indicators]
            pdf.table(["Metrica", "Valor"], rows, [95, 95])

    # ── ADVANCED METRICS ──
    if advanced:
        has_data = any(v is not None for k, v in advanced.items())
        if has_data:
            pdf.section_title("Metricas Avanzadas")

            # DuPont
            dupont_data = []
            if advanced.get("dupont_net_margin") is not None:
                dupont_data = [
                    ["Margen Neto", _fmt(advanced["dupont_net_margin"], "%")],
                    ["Rotacion Activos", _fmt(advanced.get("dupont_asset_turnover"), "x")],
                    ["Multiplicador Equity", _fmt(advanced.get("dupont_equity_multiplier"), "x")],
                    ["ROE (DuPont)", _fmt(advanced.get("dupont_roe"), "%")],
                ]
            returns_data = [
                ["ROE", _fmt(advanced.get("roe"), "%")],
                ["ROA", _fmt(advanced.get("roa"), "%")],
                ["ROIC", _fmt(advanced.get("roic"), "%")],
                ["ROCE", _fmt(advanced.get("roce"), "%")],
            ]
            margins_data = [
                ["Margen Bruto", _fmt(advanced.get("gross_margin"), "%")],
                ["Margen Operativo", _fmt(advanced.get("operating_margin"), "%")],
                ["Margen Neto", _fmt(advanced.get("net_margin"), "%")],
            ]
            solvency_data = [
                ["Deuda/EBITDA", _fmt(advanced.get("debt_ebitda"), "x")],
                ["Cobertura Intereses", _fmt(advanced.get("interest_coverage"), "x")],
                ["Deuda/Equity", _fmt(advanced.get("debt_equity"), "x")],
            ]

            all_rows = []
            if dupont_data:
                all_rows.append(["--- DuPont ---", ""])
                all_rows.extend(dupont_data)
            all_rows.append(["--- Retornos ---", ""])
            all_rows.extend(returns_data)
            all_rows.append(["--- Margenes ---", ""])
            all_rows.extend(margins_data)
            all_rows.append(["--- Solvencia ---", ""])
            all_rows.extend(solvency_data)

            if advanced.get("sustainable_growth") is not None:
                all_rows.append(["Crec. Sostenible", _fmt(advanced["sustainable_growth"], "%")])
            if advanced.get("revenue_cagr_3y") is not None:
                all_rows.append(["CAGR Revenue 3Y", _fmt(advanced["revenue_cagr_3y"], "%")])

            pdf.table(["Metrica", "Valor"], all_rows, [95, 95])

    # ── FINANCIAL STATEMENTS (from parsed PDF) ──
    if parsed_data:
        financials = parsed_data.get("financials", {})
        for stmt_name, stmt_label in [("income", "Estado de Resultados"),
                                       ("balance", "Balance General"),
                                       ("cashflow", "Flujo de Efectivo")]:
            stmt = financials.get(stmt_name, {})
            if stmt:
                pdf.section_title(stmt_label)
                # Get years from first row
                years = []
                first_key = next(iter(stmt), None)
                if first_key and isinstance(stmt[first_key], dict):
                    years = sorted(stmt[first_key].keys())[-5:]
                elif first_key and isinstance(stmt[first_key], list):
                    years = [str(i) for i in range(len(stmt[first_key]))]

                if years:
                    headers = ["Concepto"] + years
                    widths = [60] + [130 // max(len(years), 1)] * len(years)
                    rows = []
                    for concept, values in stmt.items():
                        row = [concept[:25]]
                        if isinstance(values, dict):
                            for y in years:
                                row.append(_fmt(values.get(y)))
                        elif isinstance(values, list):
                            for v in values[:len(years)]:
                                row.append(_fmt(v))
                        rows.append(row)
                    pdf.table(headers, rows[:20], widths)  # Limit rows

    # ── SWOT ──
    if parsed_data:
        swot = parsed_data.get("swot", {})
        if any(swot.get(k) for k in ["strengths", "weaknesses", "opportunities", "threats"]):
            pdf.section_title("Analisis SWOT")
            for key, label in [("strengths", "Fortalezas"), ("weaknesses", "Debilidades"),
                               ("opportunities", "Oportunidades"), ("threats", "Amenazas")]:
                items = swot.get(key, [])
                if items:
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.set_text_color(0, 80, 160)
                    pdf.cell(0, 7, label, new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(40, 40, 40)
                    for item in items[:5]:
                        if pdf.get_y() > 265:
                            pdf.add_page()
                        text = str(item).encode("latin-1", "xmlcharrefreplace").decode("latin-1")
                        pdf.multi_cell(180, 5, f"  - {text}")
                    pdf.ln(2)

    # ── ANALYST RATINGS ──
    if parsed_data:
        analyst = parsed_data.get("analyst", {})
        ratings = analyst.get("ratings", [])
        if ratings:
            pdf.section_title("Ratings de Analistas")
            headers = ["Firma/Fuente", "Rating"]
            rows = [[str(r.get("firm", r.get("source", ""))),
                      str(r.get("rating", r.get("action", "")))]
                     for r in ratings[:15]]
            pdf.table(headers, rows, [95, 95])

    # ── INVESTMENT THESIS ──
    if thesis and thesis.get("ticker"):
        pdf.section_title("Tesis de Inversion")

        pdf.kv_row("MOAT", f"{thesis.get('moat_type', 'N/A')} ({thesis.get('moat_rating', 0)}/5)",
                    bold_value=True)
        pdf.ln(2)

        # Porter summary
        porter_labels = [
            ("Rivalidad", "porter_rivalry_r"),
            ("Nuevos Entrantes", "porter_new_entrants_r"),
            ("Sustitutos", "porter_substitutes_r"),
            ("Poder Compradores", "porter_buyer_power_r"),
            ("Poder Proveedores", "porter_supplier_power_r"),
        ]
        porter_rows = [[l, f"{thesis.get(k, 0)}/5"] for l, k in porter_labels]
        avg_p = sum(thesis.get(k, 0) for _, k in porter_labels) / 5
        porter_rows.append(["PROMEDIO", f"{avg_p:.1f}/5"])
        pdf.table(["Fuerza Porter", "Rating"], porter_rows, [95, 95])
        pdf.ln(2)

        # Bull/Bear
        if thesis.get("thesis_bull"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(34, 197, 94)
            pdf.cell(0, 7, "Caso Bull:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 40)
            text = thesis["thesis_bull"].encode("latin-1", "xmlcharrefreplace").decode("latin-1")
            pdf.multi_cell(180, 5, text)
            pdf.ln(2)

        if thesis.get("thesis_bear"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(239, 68, 68)
            pdf.cell(0, 7, "Caso Bear:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 40)
            text = thesis["thesis_bear"].encode("latin-1", "xmlcharrefreplace").decode("latin-1")
            pdf.multi_cell(180, 5, text)
            pdf.ln(2)

        verdict = thesis.get("thesis_verdict", "")
        if verdict and verdict != "Sin veredicto":
            v_colors = {"Comprar": (34, 197, 94), "Mantener": (234, 179, 8), "Evitar": (239, 68, 68)}
            r, g, b = v_colors.get(verdict, (100, 100, 100))
            pdf.set_fill_color(r, g, b)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(190, 12, f"VEREDICTO: {verdict.upper()}", align="C",
                     fill=True, new_x="LMARGIN", new_y="NEXT")

    # ── SURVEILLANCE & SMART MONEY ──
    pdf.section_title("Vigilancia Institucional (Smart Money)")
    if advanced and advanced.get("insiders"):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, "Movimientos Recientes de Insiders:", new_x="LMARGIN", new_y="NEXT")
        insiders = advanced["insiders"].head(10)
        i_rows = []
        for _, row in insiders.iterrows():
            i_rows.append([str(row.get('officer_name', 'N/A')), str(row.get('type', 'N/A')), str(row.get('shares', 'N/A'))])
        pdf.table(["Persona", "Operacion", "Acciones"], i_rows, [80, 50, 60])
    
    # ── PRO TIPS ──
    if parsed_data:
        tips = parsed_data.get("pro_tips", [])
        if tips:
            pdf.section_title("Pro Tips & Señales IA")
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 40)
            for tip in tips[:10]:
                if pdf.get_y() > 265:
                    pdf.add_page()
                text = str(tip).encode("latin-1", "xmlcharrefreplace").decode("latin-1")
                pdf.multi_cell(180, 5, f"  [SIGNAL] {text}")
                pdf.ln(1)

    # Output
    return pdf.output()


def generate_backtest_report(ticker: str, strategy_name: str, params: dict,
                              metrics: dict, trades_summary: dict = None) -> bytes:
    """
    Generate a PDF report for backtest results.

    Args:
        ticker: Stock ticker symbol
        strategy_name: Name of the strategy used
        params: Dictionary of strategy parameters
        metrics: Dictionary with keys like total_return_strat, total_return_bh,
                 sharpe, max_drawdown, buy_signals, sell_signals
        trades_summary: Optional extra trade-level info

    Returns bytes of the PDF file.
    """
    pdf = InvestmentReport(ticker, f"Backtest — {ticker}")
    pdf.alias_nb_pages()
    pdf.add_page()

    # ── TITLE ──
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(0, 80, 160)
    pdf.cell(0, 14, f"Backtest Report: {ticker}", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f"Generado: {datetime.now().strftime('%d %b %Y %H:%M')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── STRATEGY INFO ──
    pdf.section_title(f"Estrategia: {strategy_name}")
    for k, v in params.items():
        pdf.kv_row(str(k), str(v))
    pdf.ln(2)

    # ── PERFORMANCE METRICS ──
    pdf.section_title("Metricas de Rendimiento")

    strat_ret = metrics.get("total_return_strat", 0)
    bh_ret = metrics.get("total_return_bh", 0)
    alpha = strat_ret - bh_ret

    perf_rows = [
        ["Retorno Estrategia", f"{strat_ret:+.2f}%"],
        ["Retorno Buy & Hold", f"{bh_ret:+.2f}%"],
        ["Alpha", f"{alpha:+.2f}%"],
        ["Sharpe Ratio", f"{metrics.get('sharpe', 0):.2f}"],
        ["Max Drawdown", f"{metrics.get('max_drawdown', 0):.2f}%"],
    ]
    pdf.table(["Metrica", "Valor"], perf_rows, [95, 95])
    pdf.ln(2)

    # Signal badge for alpha
    if alpha >= 0:
        pdf.set_fill_color(34, 197, 94)
        label = f"SUPERO Buy & Hold por {abs(alpha):.1f}%"
    else:
        pdf.set_fill_color(239, 68, 68)
        label = f"POR DEBAJO de Buy & Hold por {abs(alpha):.1f}%"
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(190, 10, label, align="C", fill=True,
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── TRADE SUMMARY ──
    pdf.section_title("Resumen de Operaciones")
    buy_sig = metrics.get("buy_signals", 0)
    sell_sig = metrics.get("sell_signals", 0)
    total_ops = buy_sig + sell_sig

    trade_rows = [
        ["Senales de Compra", str(buy_sig)],
        ["Senales de Venta", str(sell_sig)],
        ["Total Operaciones", str(total_ops)],
    ]
    if trades_summary:
        for k, v in trades_summary.items():
            trade_rows.append([str(k), str(v)])

    pdf.table(["Concepto", "Valor"], trade_rows, [95, 95])

    # ── DISCLAIMER ──
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(190, 4,
        "Disclaimer: Este reporte es generado automaticamente con fines informativos. "
        "Los resultados pasados no garantizan rendimientos futuros. "
        "No constituye asesoria financiera.")

    return pdf.output()
