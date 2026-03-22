"""
valuation.py — Fair Value engine for Quantum Retail Terminal
Computes fair value estimates using multiple methods:
1. Multiples-based (P/E sector median)
2. Simple DCF (discounted free cash flow)
3. PEG-based valuation
"""
import yfinance as yf

# Sector median P/E ratios (approximate, based on historical averages)
SECTOR_PE = {
    "Technology":         25,
    "Healthcare":         20,
    "Financial Services": 14,
    "Consumer Cyclical":  20,
    "Consumer Defensive": 22,
    "Industrials":        18,
    "Energy":             12,
    "Basic Materials":    15,
    "Communication Services": 18,
    "Real Estate":        35,
    "Utilities":          16,
}

SECTOR_EV_EBITDA = {
    "Technology":         18,
    "Healthcare":         14,
    "Financial Services": 10,
    "Consumer Cyclical":  12,
    "Consumer Defensive": 14,
    "Industrials":        12,
    "Energy":              7,
    "Basic Materials":    10,
    "Communication Services": 10,
    "Real Estate":        20,
    "Utilities":          12,
}


def compute_fair_values(ticker: str, parsed_data: dict = None):
    """
    Compute multiple fair value estimates for a stock.

    Returns dict with:
        pe_fair_value: P/E based fair value
        dcf_fair_value: Simple DCF fair value
        peg_fair_value: PEG-based fair value
        avg_fair_value: Average of available estimates
        current_price: Current market price
        signal: 'undervalued', 'fair', 'overvalued'
        signal_color: 'green', 'yellow', 'red'
        upside_pct: Percentage upside/downside to avg fair value
        details: Dict with computation details
    """
    result = {
        "pe_fair_value": None,
        "dcf_fair_value": None,
        "peg_fair_value": None,
        "avg_fair_value": None,
        "current_price": None,
        "signal": None,
        "signal_color": None,
        "upside_pct": None,
        "details": {},
    }

    try:
        tk = yf.Ticker(ticker)
        info = tk.info
    except Exception:
        return result

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not price:
        # Try from parsed data
        if parsed_data:
            ki = parsed_data.get("key_indicators", {})
            price = ki.get("price")
    if not price:
        return result

    result["current_price"] = price
    sector = info.get("sector", "")
    estimates = []

    # ── Method 1: P/E Based ──
    eps_fwd = info.get("forwardEps")
    if not eps_fwd and parsed_data:
        eps_fwd = parsed_data.get("key_indicators", {}).get("eps_estimate")

    if eps_fwd and eps_fwd > 0:
        # Use peer P/E from parsed data if available, else sector median
        sector_pe = SECTOR_PE.get(sector, 20)

        # Check if we have analyst data with forward P/E
        if parsed_data:
            analyst = parsed_data.get("analyst", {})
            forecasts = analyst.get("eps_forecasts", [])
            if forecasts:
                # Use next year forward P/E as reference
                fwd_pe_vals = [f.get("fwd_pe") for f in forecasts if f.get("fwd_pe")]
                if fwd_pe_vals:
                    # Parse "20.4x" -> 20.4
                    parsed_pes = []
                    for v in fwd_pe_vals:
                        if isinstance(v, str):
                            try:
                                parsed_pes.append(float(v.replace("x", "")))
                            except ValueError:
                                pass
                        elif isinstance(v, (int, float)):
                            parsed_pes.append(v)
                    if parsed_pes:
                        sector_pe = sum(parsed_pes) / len(parsed_pes)

        pe_fv = eps_fwd * sector_pe
        result["pe_fair_value"] = pe_fv
        result["details"]["pe_method"] = {
            "eps_fwd": eps_fwd,
            "applied_pe": sector_pe,
            "sector": sector,
        }
        estimates.append(pe_fv)

    # ── Method 2: Simple DCF ──
    try:
        cashflow = tk.cashflow
        if cashflow is not None and not cashflow.empty:
            # Get operating cash flow
            ocf_row = None
            for label in ["Operating Cash Flow", "Total Cash From Operating Activities",
                         "Cash Flow From Continuing Operating Activities"]:
                if label in cashflow.index:
                    ocf_row = cashflow.loc[label]
                    break

            capex_row = None
            for label in ["Capital Expenditure", "Capital Expenditures"]:
                if label in cashflow.index:
                    capex_row = cashflow.loc[label]
                    break

            if ocf_row is not None:
                ocf = ocf_row.iloc[0]  # Most recent
                capex = abs(capex_row.iloc[0]) if capex_row is not None else 0
                fcf = ocf - capex

                if fcf > 0:
                    shares = info.get("sharesOutstanding", 1)
                    roe = info.get("returnOnEquity")
                    payout = info.get("payoutRatio", 0.3)
                    if roe and roe > 0:
                        g = min(roe * (1 - payout), 0.25)  # Cap growth at 25%
                    else:
                        g = 0.08  # Default 8%

                    discount = 0.10  # 10% discount rate
                    terminal_g = 0.03  # 3% terminal growth

                    # 5-year DCF
                    pv_fcf = 0
                    projected_fcf = fcf
                    for yr in range(1, 6):
                        projected_fcf *= (1 + g)
                        pv_fcf += projected_fcf / (1 + discount) ** yr

                    # Terminal value
                    terminal_fcf = projected_fcf * (1 + terminal_g)
                    terminal_value = terminal_fcf / (discount - terminal_g)
                    pv_terminal = terminal_value / (1 + discount) ** 5

                    total_value = pv_fcf + pv_terminal
                    dcf_per_share = total_value / shares

                    result["dcf_fair_value"] = dcf_per_share
                    result["details"]["dcf_method"] = {
                        "fcf": fcf,
                        "growth_rate": g,
                        "discount_rate": discount,
                        "terminal_growth": terminal_g,
                        "shares": shares,
                    }
                    estimates.append(dcf_per_share)
    except Exception:
        pass

    # ── Method 3: PEG-based ──
    peg = info.get("pegRatio")
    if not peg and parsed_data:
        peg = parsed_data.get("key_indicators", {}).get("peg_ratio")

    earnings_growth = info.get("earningsGrowth")
    if peg and eps_fwd and peg > 0 and earnings_growth and earnings_growth > 0:
        # Fair PEG = 1.0 (Peter Lynch's rule)
        fair_pe = earnings_growth * 100 * 1.0  # PEG=1 means P/E = growth rate
        peg_fv = eps_fwd * fair_pe
        # Sanity check: cap at 3x current price
        if peg_fv < price * 3:
            result["peg_fair_value"] = peg_fv
            result["details"]["peg_method"] = {
                "peg_ratio": peg,
                "earnings_growth": earnings_growth,
                "fair_pe_from_growth": fair_pe,
            }
            estimates.append(peg_fv)

    # ── Average & Signal ──
    if estimates:
        avg = sum(estimates) / len(estimates)
        result["avg_fair_value"] = avg
        upside = (avg - price) / price * 100
        result["upside_pct"] = upside

        if price < avg * 0.80:
            result["signal"] = "undervalued"
            result["signal_color"] = "green"
        elif price > avg * 1.10:
            result["signal"] = "overvalued"
            result["signal_color"] = "red"
        else:
            result["signal"] = "fair"
            result["signal_color"] = "yellow"

    return result


def compute_advanced_metrics(ticker: str):
    """
    Compute advanced metrics from yfinance: DuPont, ROIC, ROCE, Debt/EBITDA, etc.

    Returns dict with all computed metrics or None values if data unavailable.
    """
    result = {
        # DuPont decomposition
        "dupont_net_margin": None,
        "dupont_asset_turnover": None,
        "dupont_equity_multiplier": None,
        "dupont_roe": None,
        # Returns
        "roic": None,
        "roce": None,
        "roa": None,
        "roe": None,
        # Margins
        "gross_margin": None,
        "operating_margin": None,
        "net_margin": None,
        # Solvency
        "debt_ebitda": None,
        "interest_coverage": None,
        "debt_equity": None,
        # Growth
        "sustainable_growth": None,
        "revenue_cagr_3y": None,
    }

    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        financials = tk.financials
        balance = tk.balance_sheet
    except Exception:
        return result

    # From info dict
    result["roe"] = info.get("returnOnEquity")
    if result["roe"]:
        result["roe"] *= 100
    result["roa"] = info.get("returnOnAssets")
    if result["roa"]:
        result["roa"] *= 100
    result["gross_margin"] = info.get("grossMargins")
    if result["gross_margin"]:
        result["gross_margin"] *= 100
    result["operating_margin"] = info.get("operatingMargins")
    if result["operating_margin"]:
        result["operating_margin"] *= 100
    result["net_margin"] = info.get("profitMargins")
    if result["net_margin"]:
        result["net_margin"] *= 100
    result["debt_equity"] = info.get("debtToEquity")
    if result["debt_equity"]:
        result["debt_equity"] /= 100  # yfinance returns as percentage

    # DuPont decomposition
    try:
        if financials is not None and not financials.empty and balance is not None and not balance.empty:
            # Net Income
            net_income = None
            for label in ["Net Income", "Net Income Common Stockholders"]:
                if label in financials.index:
                    net_income = financials.loc[label].iloc[0]
                    break

            revenue = None
            for label in ["Total Revenue", "Revenue"]:
                if label in financials.index:
                    revenue = financials.loc[label].iloc[0]
                    break

            total_assets = None
            for label in ["Total Assets"]:
                if label in balance.index:
                    total_assets = balance.loc[label].iloc[0]
                    break

            total_equity = None
            for label in ["Total Stockholders Equity", "Stockholders Equity",
                         "Total Equity Gross Minority Interest"]:
                if label in balance.index:
                    total_equity = balance.loc[label].iloc[0]
                    break

            if all(v and v != 0 for v in [net_income, revenue, total_assets, total_equity]):
                result["dupont_net_margin"] = (net_income / revenue) * 100
                result["dupont_asset_turnover"] = revenue / total_assets
                result["dupont_equity_multiplier"] = total_assets / total_equity
                result["dupont_roe"] = (net_income / total_equity) * 100

            # EBIT for ROCE and interest coverage
            ebit = None
            for label in ["EBIT", "Operating Income"]:
                if label in financials.index:
                    ebit = financials.loc[label].iloc[0]
                    break

            # Interest expense
            interest = None
            for label in ["Interest Expense", "Net Interest Income"]:
                if label in financials.index:
                    val = financials.loc[label].iloc[0]
                    interest = abs(val) if val else None
                    break

            # EBITDA
            ebitda = None
            for label in ["EBITDA", "Normalized EBITDA"]:
                if label in financials.index:
                    ebitda = financials.loc[label].iloc[0]
                    break
            if not ebitda:
                ebitda = info.get("ebitda")

            # Total debt
            total_debt = None
            for label in ["Total Debt", "Long Term Debt"]:
                if label in balance.index:
                    total_debt = balance.loc[label].iloc[0]
                    break
            if not total_debt:
                total_debt = info.get("totalDebt")

            # ROCE = EBIT / Capital Employed (Equity + Net Debt)
            if ebit and total_equity:
                net_debt = (total_debt or 0)
                capital_employed = total_equity + net_debt
                if capital_employed > 0:
                    result["roce"] = (ebit / capital_employed) * 100

            # ROIC = NOPAT / Invested Capital
            tax_rate = info.get("effectiveTaxRate", 0.21)
            if ebit and total_assets:
                nopat = ebit * (1 - (tax_rate or 0.21))
                # Invested capital approx: Total Assets - Current Liabilities (non-interest bearing)
                current_liab = None
                for label in ["Current Liabilities", "Total Current Liabilities"]:
                    if label in balance.index:
                        current_liab = balance.loc[label].iloc[0]
                        break
                invested_capital = total_assets - (current_liab or 0)
                if invested_capital > 0:
                    result["roic"] = (nopat / invested_capital) * 100

            # Debt/EBITDA
            if total_debt and ebitda and ebitda > 0:
                result["debt_ebitda"] = total_debt / ebitda

            # Interest Coverage
            if ebit and interest and interest > 0:
                result["interest_coverage"] = ebit / interest

            # Sustainable growth rate
            payout = info.get("payoutRatio", 0)
            if result["roe"] and payout is not None:
                result["sustainable_growth"] = result["roe"] * (1 - payout)

    except Exception:
        pass

    # Revenue CAGR 3Y
    try:
        if financials is not None and not financials.empty:
            rev_row = None
            for label in ["Total Revenue", "Revenue"]:
                if label in financials.index:
                    rev_row = financials.loc[label]
                    break
            if rev_row is not None and len(rev_row) >= 3:
                recent = rev_row.iloc[0]
                old = rev_row.iloc[min(2, len(rev_row) - 1)]
                years = min(2, len(rev_row) - 1)
                if recent and old and old > 0 and years > 0:
                    result["revenue_cagr_3y"] = ((recent / old) ** (1 / years) - 1) * 100
    except Exception:
        pass

    return result


def compute_quality_score(ticker: str, moat_rating: int = None) -> dict:
    """Buffett/Dorsey quality checklist — Score 0-100."""
    adv = compute_advanced_metrics(ticker)

    criteria = [
        ("ROE > 15%", adv.get("roe"), lambda v: v is not None and v > 15),
        ("ROIC > 10%", adv.get("roic"), lambda v: v is not None and v > 10),
        ("Deuda/EBITDA < 3x", adv.get("debt_ebitda"), lambda v: v is not None and v < 3),
        ("Margen Bruto > 40%", adv.get("gross_margin"), lambda v: v is not None and v > 40),
        ("Margen Operativo > 15%", adv.get("operating_margin"), lambda v: v is not None and v > 15),
        ("CAGR Ingresos > 5%", adv.get("revenue_cagr_3y"), lambda v: v is not None and v > 5),
        ("Cobertura Int. > 5x", adv.get("interest_coverage"), lambda v: v is not None and v > 5),
        ("Crec. Sostenible > 8%", adv.get("sustainable_growth"), lambda v: v is not None and v > 8),
        ("MOAT Rating >= 3", moat_rating, lambda v: v is not None and v >= 3),
        ("FCF Positivo", None, None),  # special case
    ]

    # Check FCF from yfinance
    try:
        tk = yf.Ticker(ticker)
        cf = tk.cashflow
        if cf is not None and not cf.empty:
            fcf_row = cf.loc["Free Cash Flow"] if "Free Cash Flow" in cf.index else None
            if fcf_row is not None:
                latest_fcf = fcf_row.iloc[0]
                criteria[9] = ("FCF Positivo", latest_fcf, lambda v: v is not None and v > 0)
    except Exception:
        pass

    results = []
    passed = 0
    for name, value, check in criteria:
        if check is not None and value is not None:
            ok = check(value)
        else:
            ok = False
        results.append({"criterion": name, "value": value, "passed": ok})
        if ok:
            passed += 1

    score = int(passed / len(criteria) * 100)
    return {
        "score": score,
        "passed": passed,
        "total": len(criteria),
        "details": results,
        "advanced": adv,
    }


def compute_dcf_scenarios(ticker: str, parsed_data: dict = None) -> dict:
    """DCF with Pessimistic/Base/Optimistic scenarios."""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info

        # Get base growth rate (same logic as existing DCF)
        roe = (info.get("returnOnEquity") or 0)
        payout = info.get("payoutRatio") or 0.3
        base_growth = roe * (1 - payout)
        if base_growth <= 0:
            base_growth = (info.get("revenueGrowth") or 0.05)
        base_growth = max(0.02, min(base_growth, 0.30))

        # Get EPS
        eps = info.get("trailingEps") or 0
        if eps <= 0:
            return {}

        scenarios = {
            "pessimistic": {"growth": base_growth * 0.5, "discount": 0.12, "terminal": 0.02, "label": "Pesimista"},
            "base":        {"growth": base_growth,       "discount": 0.10, "terminal": 0.03, "label": "Base"},
            "optimistic":  {"growth": base_growth * 1.5, "discount": 0.08, "terminal": 0.04, "label": "Optimista"},
        }

        results = {}
        for key, params in scenarios.items():
            g = params["growth"]
            r = params["discount"]
            tg = params["terminal"]

            # 5-year projected EPS
            future_eps = []
            current = eps
            for _ in range(5):
                current *= (1 + g)
                future_eps.append(current)

            # Terminal value
            terminal = future_eps[-1] * (1 + tg) / (r - tg) if r > tg else 0

            # Discount all to present
            pv_eps = sum(e / (1 + r)**(i+1) for i, e in enumerate(future_eps))
            pv_terminal = terminal / (1 + r)**5
            fair_value = pv_eps + pv_terminal

            results[key] = {
                "fair_value": round(fair_value, 2),
                "growth": round(g * 100, 1),
                "discount": round(r * 100, 1),
                "terminal": round(tg * 100, 1),
                "label": params["label"],
            }

        results["current_price"] = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        results["eps"] = eps
        results["base_growth"] = round(base_growth * 100, 1)
        return results
    except Exception:
        return {}


def compute_health_scores(ticker: str) -> dict:
    """
    Compute Altman Z-Score and Piotroski F-Score for financial health assessment.
    Returns dict with z_score, z_label, f_score, f_label, and component details.
    """
    result = {"z_score": None, "z_label": None, "f_score": None, "f_label": None,
              "z_details": {}, "f_details": {}}
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        balance = tk.balance_sheet
        financials = tk.financials
        cashflow = tk.cashflow

        if balance.empty or financials.empty:
            return result

        # Helper to get first column value from financial statement
        def _get(df, labels):
            for label in labels:
                if label in df.index:
                    v = df.loc[label].iloc[0]
                    if v is not None and v == v:  # not NaN
                        return float(v)
            return None

        # ── ALTMAN Z-SCORE ──
        # Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
        total_assets = _get(balance, ["Total Assets"])
        current_assets = _get(balance, ["Current Assets"])
        current_liabilities = _get(balance, ["Current Liabilities"])
        retained_earnings = _get(balance, ["Retained Earnings"])
        ebit = _get(financials, ["EBIT", "Operating Income"])
        total_liabilities = _get(balance, ["Total Liabilities Net Minority Interest", "Total Liabilities"])
        revenue = _get(financials, ["Total Revenue"])
        market_cap = info.get("marketCap")

        if total_assets and total_assets > 0:
            x1 = ((current_assets or 0) - (current_liabilities or 0)) / total_assets  # Working capital / TA
            x2 = (retained_earnings or 0) / total_assets  # Retained earnings / TA
            x3 = (ebit or 0) / total_assets  # EBIT / TA
            x4 = (market_cap or 0) / max(total_liabilities or 1, 1)  # Market cap / Total liabilities
            x5 = (revenue or 0) / total_assets  # Revenue / TA

            z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
            result["z_score"] = round(z, 2)
            result["z_details"] = {"X1_WC_TA": round(x1, 3), "X2_RE_TA": round(x2, 3),
                                   "X3_EBIT_TA": round(x3, 3), "X4_MC_TL": round(x4, 3),
                                   "X5_Rev_TA": round(x5, 3)}
            if z > 2.99:
                result["z_label"] = "SAFE"
            elif z > 1.81:
                result["z_label"] = "GREY"
            else:
                result["z_label"] = "DISTRESS"

        # ── PIOTROSKI F-SCORE (9 binary criteria) ──
        f_points = 0
        f_details = {}

        net_income = _get(financials, ["Net Income"])
        cfo = _get(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
        roa_current = (net_income / total_assets) if net_income and total_assets and total_assets > 0 else None

        # 1. Positive net income
        if net_income and net_income > 0:
            f_points += 1
            f_details["ROA positivo"] = True
        else:
            f_details["ROA positivo"] = False

        # 2. Positive operating cash flow
        if cfo and cfo > 0:
            f_points += 1
            f_details["CFO positivo"] = True
        else:
            f_details["CFO positivo"] = False

        # 3. ROA increasing (compare current vs implied from growth)
        roa_improving = info.get("returnOnAssets", 0) and info.get("returnOnAssets", 0) > 0
        if roa_improving:
            f_points += 1
        f_details["ROA mejorando"] = bool(roa_improving)

        # 4. CFO > Net Income (quality of earnings)
        if cfo and net_income and cfo > net_income:
            f_points += 1
            f_details["CFO > Net Income"] = True
        else:
            f_details["CFO > Net Income"] = False

        # 5. Decreasing leverage (debt/assets)
        total_debt = _get(balance, ["Total Debt", "Long Term Debt"])
        low_leverage = (total_debt or 0) / total_assets < 0.5 if total_assets and total_assets > 0 else False
        if low_leverage:
            f_points += 1
        f_details["Deuda/Activos < 50%"] = bool(low_leverage)

        # 6. Improving current ratio
        cr = (current_assets / current_liabilities) if current_assets and current_liabilities and current_liabilities > 0 else 0
        if cr > 1:
            f_points += 1
        f_details["Current Ratio > 1"] = cr > 1

        # 7. No share dilution
        shares = info.get("sharesOutstanding")
        if shares:
            f_points += 1  # simplified: assume no dilution if data exists
        f_details["Sin dilución"] = True

        # 8. Improving gross margin
        gm = info.get("grossMargins", 0)
        if gm and gm > 0.3:
            f_points += 1
        f_details["Margen bruto > 30%"] = bool(gm and gm > 0.3)

        # 9. Improving asset turnover
        at = (revenue / total_assets) if revenue and total_assets and total_assets > 0 else 0
        if at > 0.5:
            f_points += 1
        f_details["Asset turnover > 0.5"] = at > 0.5

        result["f_score"] = f_points
        result["f_details"] = f_details
        if f_points >= 7:
            result["f_label"] = "STRONG"
        elif f_points >= 4:
            result["f_label"] = "MODERATE"
        else:
            result["f_label"] = "WEAK"

    except Exception:
        pass
    return result


def compute_wacc(ticker: str) -> dict:
    """
    Compute Weighted Average Cost of Capital (WACC).
    WACC = (E/V × Ke) + (D/V × Kd × (1-T))
    Returns dict with all components or empty dict on failure.
    """
    result = {}
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        financials = tk.financials
        balance = tk.balance_sheet

        # Risk-free rate from 10Y Treasury
        try:
            tnx = yf.Ticker("^TNX").history(period="5d")
            rf = tnx["Close"].iloc[-1] / 100 if not tnx.empty else 0.04
            if hasattr(rf, "item"):
                rf = rf.item()
        except Exception:
            rf = 0.04

        # Beta
        beta = info.get("beta", 1.0) or 1.0

        # Equity Risk Premium (standard)
        erp = 0.055

        # Cost of Equity: Ke = Rf + Beta * ERP
        ke = rf + beta * erp

        # Market Cap (equity value)
        market_cap = info.get("marketCap", 0) or 0

        # Total Debt
        total_debt = info.get("totalDebt", 0) or 0

        # Cost of Debt: interest expense / total debt
        kd = 0.05  # default
        try:
            if financials is not None and not financials.empty and total_debt > 0:
                interest = None
                for label in ["Interest Expense", "Net Interest Income"]:
                    if label in financials.index:
                        interest = abs(float(financials.loc[label].iloc[0]))
                        break
                if interest and interest > 0:
                    kd = interest / total_debt
                    kd = min(kd, 0.20)  # cap at 20%
        except Exception:
            pass

        # Tax Rate from income statement
        tax_rate = 0.21  # default US corporate
        try:
            if financials is not None and not financials.empty:
                pretax = None
                tax_exp = None
                for label in ["Pretax Income", "Income Before Tax"]:
                    if label in financials.index:
                        pretax = float(financials.loc[label].iloc[0])
                        break
                for label in ["Tax Provision", "Income Tax Expense"]:
                    if label in financials.index:
                        tax_exp = abs(float(financials.loc[label].iloc[0]))
                        break
                if pretax and pretax > 0 and tax_exp is not None:
                    tax_rate = tax_exp / pretax
                    tax_rate = max(0, min(tax_rate, 0.50))
        except Exception:
            pass

        # Enterprise Value = E + D
        ev = market_cap + total_debt
        if ev <= 0:
            return result

        we = market_cap / ev  # weight of equity
        wd = total_debt / ev  # weight of debt

        wacc = (we * ke) + (wd * kd * (1 - tax_rate))

        result = {
            "wacc": wacc,
            "ke": ke,
            "kd": kd,
            "rf": rf,
            "beta": beta,
            "erp": erp,
            "tax_rate": tax_rate,
            "we": we,
            "wd": wd,
            "market_cap": market_cap,
            "total_debt": total_debt,
        }
    except Exception:
        pass
    return result