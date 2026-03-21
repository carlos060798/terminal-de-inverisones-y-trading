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
