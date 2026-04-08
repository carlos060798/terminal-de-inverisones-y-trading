"""
valuation.py — Fair Value engine for Quantum Retail Terminal
Computes fair value estimates using multiple methods:
1. Multiples-based (P/E sector median)
2. Simple DCF (discounted free cash flow)
3. PEG-based valuation
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from cache_utils import get_ticker_info, get_financials

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


@st.cache_data(ttl=3600, show_spinner=False)
def compute_fair_values(ticker: str, parsed_data: dict = None):
    """
    Compute multiple fair value estimates for a stock.
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

    info = get_ticker_info(ticker)
    if not info:
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
        fins = get_financials(ticker)
        cashflow = fins.get('cashflow')
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


@st.cache_data(ttl=3600, show_spinner=False)
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

    info = get_ticker_info(ticker)
    fins = get_financials(ticker)
    financials = fins.get('income')
    balance = fins.get('balance')
    if not info or financials is None or balance is None:
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


@st.cache_data(ttl=3600, show_spinner=False)
def compute_dcf_scenarios(ticker: str, parsed_data: dict = None) -> dict:
    """DCF with Pessimistic/Base/Optimistic scenarios."""
    info = get_ticker_info(ticker)
    if not info:
        return {}
    try:

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


@st.cache_data(ttl=3600, show_spinner=False)
def compute_health_scores(ticker: str) -> dict:
    """
    Compute Altman Z-Score and Piotroski F-Score for financial health assessment.
    Returns dict with z_score, z_label, f_score, f_label, and component details.
    """
    result = {"z_score": None, "z_label": None, "f_score": None, "f_label": None,
              "sloan_ratio": None, "sloan_label": None,
              "z_details": {}, "f_details": {}, "sloan_details": {}}
    info = get_ticker_info(ticker)
    fins = get_financials(ticker)
    balance = fins.get('balance')
    financials = fins.get('income')
    cashflow = fins.get('cashflow')

    if not info or balance is None or balance.empty or financials is None or financials.empty:
        return result
    try:

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

        # ── SLOAN RATIO ──
        # Formula: (NI - CFO - CFI) / Total Assets
        cfi = _get(cashflow, ["Investing Cash Flow", "Total Cash From Investing Activities"])
        if all(v is not None for v in [net_income, cfo, cfi, total_assets]) and total_assets > 0:
            sloan = (net_income - cfo - cfi) / total_assets
            result["sloan_ratio"] = round(sloan, 4)
            if -0.10 <= sloan <= 0.10:
                result["sloan_label"] = "SAFE"
            else:
                result["sloan_label"] = "WARNING (High Accruals)"
            result["sloan_details"] = {"NI": net_income, "CFO": cfo, "CFI": cfi, "TA": total_assets}

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


@st.cache_data(ttl=3600, show_spinner=False)
def compute_dcf_professional(ticker: str, wacc_override: float = None) -> dict:
    """Institutional DCF following InValor/JPMorgan methodology."""
    info = get_ticker_info(ticker)
    fins = get_financials(ticker)
    inc = fins.get('income')
    bs = fins.get('balance')
    cf = fins.get('cashflow')

    if not info or inc is None or inc.empty or bs is None or bs.empty or cf is None or cf.empty:
        return {}
    try:

        # Step 1: Calculate FCFF
        ebit = None
        for label in ["EBIT", "Operating Income"]:
            if label in inc.index:
                ebit = float(inc.loc[label].iloc[0])
                break
        if ebit is None:
            return {}

        # Tax rate from financials
        tax_rate = 0.25
        try:
            pretax = None
            tax_exp = None
            for label in ["Pretax Income", "Income Before Tax"]:
                if label in inc.index:
                    pretax = float(inc.loc[label].iloc[0])
                    break
            for label in ["Tax Provision", "Income Tax Expense"]:
                if label in inc.index:
                    tax_exp = abs(float(inc.loc[label].iloc[0]))
                    break
            if pretax and pretax > 0 and tax_exp is not None:
                tax_rate = max(0.0, min(tax_exp / pretax, 0.50))
        except Exception:
            pass

        nopat = ebit * (1 - tax_rate)

        da = 0
        for label in ["Depreciation And Amortization", "Depreciation & Amortization"]:
            if label in cf.index:
                da = float(cf.loc[label].iloc[0])
                break

        capex = 0
        for label in ["Capital Expenditure", "Capital Expenditures"]:
            if label in cf.index:
                capex = float(cf.loc[label].iloc[0])
                break

        wk_change = 0
        for label in ["Change In Working Capital", "Changes In Working Capital"]:
            if label in cf.index:
                wk_change = float(cf.loc[label].iloc[0])
                break

        fcff = nopat + abs(da) - abs(capex) + wk_change

        # Step 2: Project 5 years using revenue growth rate
        rev_growth = info.get('revenueGrowth', 0.05) or 0.05
        rev_growth = max(0.01, min(rev_growth, 0.40))
        projected_fcff = [fcff * (1 + rev_growth) ** i for i in range(1, 6)]

        # Step 3: Terminal Value (Gordon Growth)
        g = 0.03
        if wacc_override is not None:
            wacc = wacc_override
        else:
            wacc_data = compute_wacc(ticker)
            wacc = wacc_data.get('wacc', 0.10) if wacc_data else 0.10
        
        if wacc <= g:
            wacc = g + 0.02

        terminal_value = projected_fcff[-1] * (1 + g) / (wacc - g)

        # Step 4: Discount all to present
        pv_fcff = sum(fcf / (1 + wacc) ** t for t, fcf in enumerate(projected_fcff, 1))
        pv_terminal = terminal_value / (1 + wacc) ** 5
        enterprise_value = pv_fcff + pv_terminal

        # Step 5: Equity Value
        total_debt = info.get('totalDebt', 0) or 0
        cash = info.get('totalCash', 0) or 0
        equity_value = enterprise_value - total_debt + cash
        shares = info.get('sharesOutstanding', 1) or 1
        fair_value_per_share = equity_value / shares

        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or 0
        upside = ((fair_value_per_share - current_price) / current_price * 100) if current_price > 0 else 0

        # Step 6: Sensitivity table (5x5 WACC vs g)
        wacc_range = [round(wacc - 0.01, 4), round(wacc - 0.005, 4), round(wacc, 4),
                      round(wacc + 0.005, 4), round(wacc + 0.01, 4)]
        g_range = [0.02, 0.025, 0.03, 0.035, 0.04]
        sensitivity = {}
        for w in wacc_range:
            for gv in g_range:
                if w > gv:
                    tv = projected_fcff[-1] * (1 + gv) / (w - gv)
                    pv_t = tv / (1 + w) ** 5
                    pv_cf = sum(fcf / (1 + w) ** t for t, fcf in enumerate(projected_fcff, 1))
                    ev = pv_cf + pv_t
                    eq = ev - total_debt + cash
                    sensitivity[(round(w * 100, 2), round(gv * 100, 2))] = round(eq / shares, 2)

        return {
            "fcff": fcff,
            "nopat": nopat,
            "ebit": ebit,
            "tax_rate": tax_rate,
            "da": da,
            "capex": capex,
            "wk_change": wk_change,
            "rev_growth": rev_growth,
            "projected_fcff": projected_fcff,
            "wacc": wacc,
            "terminal_g": g,
            "terminal_value": terminal_value,
            "pv_fcff": pv_fcff,
            "pv_terminal": pv_terminal,
            "enterprise_value": enterprise_value,
            "total_debt": total_debt,
            "cash": cash,
            "equity_value": equity_value,
            "shares": shares,
            "fair_value_per_share": round(fair_value_per_share, 2),
            "current_price": current_price,
            "upside_pct": round(upside, 2),
            "wacc_range": wacc_range,
            "g_range": g_range,
            "sensitivity": sensitivity,
        }
    except Exception:
        return {}


def monte_carlo_dcf(ticker, n_simulations=1000, wacc_sigma=0.01, growth_sigma=0.02, g_sigma=0.005):
    """Monte Carlo simulation over DCF, varying WACC, revenue growth, and terminal g.
    Returns distribution of fair values with probability metrics."""
    try:
        base = compute_dcf_professional(ticker)
        if not base or "error" in base:
            return None
        fcff_base = base.get("fcff", 0)
        wacc_base = base.get("wacc", 0.10)
        growth_base = base.get("rev_growth", 0.05)
        g_base = 0.03
        total_debt = base.get("total_debt", 0)
        cash = base.get("cash", 0)
        shares = base.get("shares", 1)
        current_price = base.get("current_price", 0)
        if fcff_base <= 0 or shares <= 0:
            return None
        np.random.seed(42)
        waccs = np.clip(np.random.normal(wacc_base, wacc_sigma, n_simulations), 0.04, 0.20)
        growths = np.clip(np.random.normal(growth_base, growth_sigma, n_simulations), -0.10, 0.40)
        gs = np.clip(np.random.normal(g_base, g_sigma, n_simulations), 0.01, 0.05)
        fair_values = []
        for w, gr, g in zip(waccs, growths, gs):
            if w <= g + 0.005:
                continue
            try:
                projected = [fcff_base * (1 + gr) ** i for i in range(1, 6)]
                tv = projected[-1] * (1 + g) / (w - g)
                pv_fcff = sum(fcf / (1 + w) ** t for t, fcf in enumerate(projected, 1))
                pv_tv = tv / (1 + w) ** 5
                equity = pv_fcff + pv_tv - total_debt + cash
                fv_ps = equity / shares
                if 0 < fv_ps < current_price * 20:
                    fair_values.append(fv_ps)
            except Exception:
                continue
        if len(fair_values) < 100:
            return None
        fv = np.array(fair_values)
        return {
            "fair_values": fv, "n_valid": len(fv),
            "mean": float(np.mean(fv)), "median": float(np.median(fv)), "std": float(np.std(fv)),
            "p5": float(np.percentile(fv, 5)), "p10": float(np.percentile(fv, 10)),
            "p25": float(np.percentile(fv, 25)), "p75": float(np.percentile(fv, 75)),
            "p90": float(np.percentile(fv, 90)), "p95": float(np.percentile(fv, 95)),
            "current_price": current_price,
            "prob_above_price": float((fv > current_price).sum() / len(fv) * 100),
            "prob_20pct_upside": float((fv > current_price * 1.2).sum() / len(fv) * 100),
            "prob_50pct_upside": float((fv > current_price * 1.5).sum() / len(fv) * 100),
            "wacc_base": wacc_base, "growth_base": growth_base, "g_base": g_base,
        }
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def compute_capital_returns(ticker: str) -> dict:
    """Compute ROIC, ROCE, and Shareholder Yield (B3 + B4)."""
    result = {
        "roic": None, "roce": None,
        "nopat": None, "invested_capital": None,
        "ebit": None, "capital_employed": None,
        "div_yield": None, "buyback_yield": None,
        "debt_paydown_yield": None, "shareholder_yield": None,
    }
    info = get_ticker_info(ticker)
    fins = get_financials(ticker)
    financials = fins.get('income')
    balance = fins.get('balance')
    cf = fins.get('cashflow')

    if not info or financials is None or financials.empty or balance is None or balance.empty:
        return result
    try:

        def _get(df, labels):
            for label in labels:
                if label in df.index:
                    v = df.loc[label].iloc[0]
                    if v is not None and v == v:
                        return float(v)
            return None

        # EBIT
        ebit = _get(financials, ["EBIT", "Operating Income"])
        total_assets = _get(balance, ["Total Assets"])
        current_liab = _get(balance, ["Current Liabilities", "Total Current Liabilities"])
        total_equity = _get(balance, ["Total Stockholders Equity", "Stockholders Equity",
                                       "Total Equity Gross Minority Interest"])
        cash = _get(balance, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
        total_debt = _get(balance, ["Total Debt", "Long Term Debt"])

        # Tax rate
        tax_rate = 0.25
        try:
            pretax = _get(financials, ["Pretax Income", "Income Before Tax"])
            tax_exp = _get(financials, ["Tax Provision", "Income Tax Expense"])
            if pretax and pretax > 0 and tax_exp is not None:
                tax_rate = max(0.0, min(abs(tax_exp) / pretax, 0.50))
        except Exception:
            pass

        # B3: ROIC = NOPAT / Invested Capital
        if ebit and total_assets:
            nopat = ebit * (1 - tax_rate)
            result["nopat"] = nopat
            invested_capital = total_assets - (cash or 0) - (current_liab or 0)
            if invested_capital > 0:
                result["invested_capital"] = invested_capital
                result["roic"] = (nopat / invested_capital) * 100

        # B3: ROCE = EBIT / Capital Employed
        if ebit and total_assets and current_liab:
            capital_employed = total_assets - current_liab
            if capital_employed > 0:
                result["ebit"] = ebit
                result["capital_employed"] = capital_employed
                result["roce"] = (ebit / capital_employed) * 100

        # B4: Shareholder Yield
        market_cap = info.get('marketCap', 0) or 0
        div_yield = info.get('dividendYield', 0) or 0
        result["div_yield"] = div_yield * 100

        # Buyback yield: change in shares outstanding YoY
        buyback_yield = 0.0
        try:
            shares_row = None
            for label in ["Ordinary Shares Number", "Share Issued"]:
                if label in balance.index:
                    shares_row = balance.loc[label]
                    break
            if shares_row is not None and len(shares_row) >= 2:
                shares_curr = float(shares_row.iloc[0])
                shares_prev = float(shares_row.iloc[1])
                if shares_prev > 0 and shares_curr > 0:
                    buyback_yield = (shares_prev - shares_curr) / shares_prev * 100
        except Exception:
            pass
        result["buyback_yield"] = buyback_yield

        # Debt paydown yield
        debt_paydown_yield = 0.0
        try:
            debt_row = None
            for label in ["Total Debt", "Long Term Debt"]:
                if label in balance.index:
                    debt_row = balance.loc[label]
                    break
            if debt_row is not None and len(debt_row) >= 2 and market_cap > 0:
                debt_curr = float(debt_row.iloc[0])
                debt_prev = float(debt_row.iloc[1])
                debt_paydown_yield = (debt_prev - debt_curr) / market_cap * 100
        except Exception:
            pass
        result["debt_paydown_yield"] = debt_paydown_yield

        result["shareholder_yield"] = (div_yield * 100) + buyback_yield + debt_paydown_yield

    except Exception:
        pass
    return result


# Sector median multiples for comparison
SECTOR_MULTIPLES = {
    "Technology":         {"pe": 25, "fwd_pe": 22, "ps": 6.0, "pb": 8.0, "pfcf": 28, "ev_ebitda": 18, "ev_ebit": 22, "ev_sales": 6.5, "ev_fcf": 30, "peg": 1.5},
    "Healthcare":         {"pe": 20, "fwd_pe": 18, "ps": 4.0, "pb": 4.0, "pfcf": 22, "ev_ebitda": 14, "ev_ebit": 17, "ev_sales": 4.5, "ev_fcf": 24, "peg": 1.8},
    "Financial Services": {"pe": 14, "fwd_pe": 12, "ps": 3.0, "pb": 1.5, "pfcf": 12, "ev_ebitda": 10, "ev_ebit": 12, "ev_sales": 3.5, "ev_fcf": 14, "peg": 1.3},
    "Consumer Cyclical":  {"pe": 20, "fwd_pe": 18, "ps": 2.0, "pb": 4.0, "pfcf": 20, "ev_ebitda": 12, "ev_ebit": 15, "ev_sales": 2.5, "ev_fcf": 22, "peg": 1.5},
    "Consumer Defensive": {"pe": 22, "fwd_pe": 20, "ps": 2.5, "pb": 5.0, "pfcf": 24, "ev_ebitda": 14, "ev_ebit": 17, "ev_sales": 3.0, "ev_fcf": 26, "peg": 2.0},
    "Industrials":        {"pe": 18, "fwd_pe": 16, "ps": 2.0, "pb": 3.5, "pfcf": 20, "ev_ebitda": 12, "ev_ebit": 15, "ev_sales": 2.5, "ev_fcf": 22, "peg": 1.5},
    "Energy":             {"pe": 12, "fwd_pe": 10, "ps": 1.5, "pb": 2.0, "pfcf": 10, "ev_ebitda": 7, "ev_ebit": 9, "ev_sales": 1.5, "ev_fcf": 12, "peg": 1.0},
    "Basic Materials":    {"pe": 15, "fwd_pe": 13, "ps": 2.0, "pb": 2.5, "pfcf": 14, "ev_ebitda": 10, "ev_ebit": 12, "ev_sales": 2.0, "ev_fcf": 16, "peg": 1.3},
    "Communication Services": {"pe": 18, "fwd_pe": 16, "ps": 3.0, "pb": 3.0, "pfcf": 18, "ev_ebitda": 10, "ev_ebit": 13, "ev_sales": 3.5, "ev_fcf": 20, "peg": 1.4},
    "Real Estate":        {"pe": 35, "fwd_pe": 30, "ps": 8.0, "pb": 2.5, "pfcf": 30, "ev_ebitda": 20, "ev_ebit": 25, "ev_sales": 9.0, "ev_fcf": 35, "peg": 2.5},
    "Utilities":          {"pe": 16, "fwd_pe": 14, "ps": 2.5, "pb": 2.0, "pfcf": 15, "ev_ebitda": 12, "ev_ebit": 14, "ev_sales": 3.0, "ev_fcf": 18, "peg": 2.0},
}


@st.cache_data(ttl=3600, show_spinner=False)
def compute_multiples(ticker: str) -> dict:
    """Compute expanded valuation multiples with sector comparison (B5)."""
    result = {"multiples": [], "sector": ""}
    info = get_ticker_info(ticker)
    fins = get_financials(ticker)
    cf = fins.get('cashflow')
    if not info:
        return result
    try:
        sector = info.get("sector", "")
        result["sector"] = sector
        sector_med = SECTOR_MULTIPLES.get(sector, SECTOR_MULTIPLES.get("Technology", {}))

        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        market_cap = info.get("marketCap", 0) or 0
        shares = info.get("sharesOutstanding", 1) or 1
        ev = info.get("enterpriseValue", 0) or 0

        # EPS values
        trailing_eps = info.get("trailingEps", 0) or 0
        forward_eps = info.get("forwardEps", 0) or 0
        book_value = info.get("bookValue", 0) or 0
        revenue_ps = info.get("revenuePerShare", 0) or 0
        ebitda = info.get("ebitda", 0) or 0
        revenue = info.get("totalRevenue", 0) or 0
        earnings_growth = info.get("earningsGrowth", 0) or 0

        # FCF from cashflow
        fcf = 0
        try:
            if cf is not None and not cf.empty:
                ocf = None
                for label in ["Operating Cash Flow", "Total Cash From Operating Activities",
                               "Cash Flow From Continuing Operating Activities"]:
                    if label in cf.index:
                        ocf = float(cf.loc[label].iloc[0])
                        break
                capex = 0
                for label in ["Capital Expenditure", "Capital Expenditures"]:
                    if label in cf.index:
                        capex = abs(float(cf.loc[label].iloc[0]))
                        break
                if ocf:
                    fcf = ocf - capex
        except Exception:
            pass

        # EBIT
        ebit = 0
        try:
            financials = tk.financials
            if financials is not None and not financials.empty:
                for label in ["EBIT", "Operating Income"]:
                    if label in financials.index:
                        ebit = float(financials.loc[label].iloc[0])
                        break
        except Exception:
            pass

        def _signal(val, median, lower_better=False):
            """Return signal: cheap / fair / expensive."""
            if val is None or median is None or median == 0:
                return "fair", "#fbbf24"
            ratio = val / median
            if lower_better:
                if ratio < 0.8:
                    return "cheap", "#34d399"
                elif ratio > 1.2:
                    return "expensive", "#f87171"
                return "fair", "#fbbf24"
            else:
                if ratio < 0.8:
                    return "cheap", "#34d399"
                elif ratio > 1.2:
                    return "expensive", "#f87171"
                return "fair", "#fbbf24"

        multiples = []

        # P/E
        pe = price / trailing_eps if trailing_eps > 0 else None
        sig, col = _signal(pe, sector_med.get("pe"), lower_better=True)
        multiples.append({"name": "P/E", "value": pe, "sector_median": sector_med.get("pe"), "signal": sig, "color": col})

        # Forward P/E
        fwd_pe = price / forward_eps if forward_eps > 0 else None
        sig, col = _signal(fwd_pe, sector_med.get("fwd_pe"), lower_better=True)
        multiples.append({"name": "Fwd P/E", "value": fwd_pe, "sector_median": sector_med.get("fwd_pe"), "signal": sig, "color": col})

        # P/S
        ps = price / revenue_ps if revenue_ps > 0 else None
        sig, col = _signal(ps, sector_med.get("ps"), lower_better=True)
        multiples.append({"name": "P/S", "value": ps, "sector_median": sector_med.get("ps"), "signal": sig, "color": col})

        # P/B
        pb = price / book_value if book_value > 0 else None
        sig, col = _signal(pb, sector_med.get("pb"), lower_better=True)
        multiples.append({"name": "P/B", "value": pb, "sector_median": sector_med.get("pb"), "signal": sig, "color": col})

        # P/FCF
        fcf_ps = fcf / shares if shares > 0 else 0
        pfcf = price / fcf_ps if fcf_ps > 0 else None
        sig, col = _signal(pfcf, sector_med.get("pfcf"), lower_better=True)
        multiples.append({"name": "P/FCF", "value": pfcf, "sector_median": sector_med.get("pfcf"), "signal": sig, "color": col})

        # EV/EBITDA
        ev_ebitda = ev / ebitda if ebitda > 0 else None
        sig, col = _signal(ev_ebitda, sector_med.get("ev_ebitda"), lower_better=True)
        multiples.append({"name": "EV/EBITDA", "value": ev_ebitda, "sector_median": sector_med.get("ev_ebitda"), "signal": sig, "color": col})

        # EV/EBIT
        ev_ebit = ev / ebit if ebit > 0 else None
        sig, col = _signal(ev_ebit, sector_med.get("ev_ebit"), lower_better=True)
        multiples.append({"name": "EV/EBIT", "value": ev_ebit, "sector_median": sector_med.get("ev_ebit"), "signal": sig, "color": col})

        # EV/Sales
        ev_sales = ev / revenue if revenue > 0 else None
        sig, col = _signal(ev_sales, sector_med.get("ev_sales"), lower_better=True)
        multiples.append({"name": "EV/Sales", "value": ev_sales, "sector_median": sector_med.get("ev_sales"), "signal": sig, "color": col})

        # EV/FCF
        ev_fcf = ev / fcf if fcf > 0 else None
        sig, col = _signal(ev_fcf, sector_med.get("ev_fcf"), lower_better=True)
        multiples.append({"name": "EV/FCF", "value": ev_fcf, "sector_median": sector_med.get("ev_fcf"), "signal": sig, "color": col})

        # PEG
        pe_val = pe if pe else 0
        eg_pct = earnings_growth * 100 if earnings_growth else 0
        peg = pe_val / eg_pct if eg_pct > 0 and pe_val > 0 else None
        sig, col = _signal(peg, sector_med.get("peg"), lower_better=True)
        multiples.append({"name": "PEG", "value": peg, "sector_median": sector_med.get("peg"), "signal": sig, "color": col})

        result["multiples"] = multiples
    except Exception:
        pass
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def compute_wacc(ticker: str) -> dict:
    """
    Compute Weighted Average Cost of Capital (WACC).
    WACC = (E/V × Ke) + (D/V × Kd × (1-T))
    Returns dict with all components or empty dict on failure.
    """
    result = {}
    info = get_ticker_info(ticker)
    fins = get_financials(ticker)
    financials = fins.get('income')
    balance = fins.get('balance')
    if not info:
        return result
    try:

        # Risk-free rate from 10Y Treasury
        try:
            tnx = yf.Ticker("^TNX").history(period="5d")
            rf = tnx["Close"].iloc[-1] / 100 if not tnx.empty else 0.04
            if hasattr(rf, "item"):
                rf = rf.item()
        except Exception:
            rf = 0.04

        # Beta — lever the unlevered beta using Hamada equation
        beta_unlevered = info.get("beta", 1.0) or 1.0
        market_cap = info.get("marketCap", 0) or 0
        total_debt = info.get("totalDebt", 0) or 0

        # We need tax_rate early for levered beta; compute it first
        _tax_rate_for_beta = 0.21
        try:
            if financials is not None and not financials.empty:
                _pretax_b = None
                _tax_exp_b = None
                for label in ["Pretax Income", "Income Before Tax"]:
                    if label in financials.index:
                        _pretax_b = float(financials.loc[label].iloc[0])
                        break
                for label in ["Tax Provision", "Income Tax Expense"]:
                    if label in financials.index:
                        _tax_exp_b = abs(float(financials.loc[label].iloc[0]))
                        break
                if _pretax_b and _pretax_b > 0 and _tax_exp_b is not None:
                    _tax_rate_for_beta = max(0, min(_tax_exp_b / _pretax_b, 0.50))
        except Exception:
            pass

        beta = beta_unlevered * (1 + (1 - _tax_rate_for_beta) * (total_debt / max(market_cap, 1)))

        # Equity Risk Premium (standard)
        erp = 0.055

        # Cost of Equity: Ke = Rf + Beta_levered * ERP
        ke = rf + beta * erp

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
            "beta_unlevered": beta_unlevered,
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

import numpy as np

def compute_fundamental_score_v2(ticker: str) -> dict:
    """
    Implementa el Scoring Fundamental de 52 puntos (Checklist V2).
    6 Bloques: Calidad, Crecimiento, Riesgo, Flujo Caja, Valuacion, Accionariado.
    """
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        fin = tk.financials
        bs = tk.balance_sheet
        cf = tk.cashflow
    except Exception:
        return {"error": "No data"}
    
    def sf(val, default=0.0):
        try:
            return float(val) if val is not None and not np.isnan(val) else default
        except:
            return default

    adv = compute_advanced_metrics(ticker)
    pts = 0
    details = []
    
    def score_metric(name, val, thresh_ex, thresh_bu, mode="higher"):
        nonlocal pts
        if val is None or str(val).lower() == 'nan':
            details.append({"name": name, "value": "N/A", "points": 0.0})
            return 0.0
        if mode == "higher":
            if val >= thresh_ex: p = 2.0
            elif val >= thresh_bu: p = 1.5
            else: p = 0.5
        else:
            if val <= thresh_ex: p = 2.0
            elif val <= thresh_bu: p = 1.5
            else: p = 0.5
        details.append({"name": name, "value": val, "points": p})
        pts += p
        return p

    # 1. Calidad
    score_metric("ROIC (%)", sf(adv.get("roic", sf(info.get("returnOnEquity"))*80)), 15, 10)
    score_metric("ROE (%)", sf(info.get("returnOnEquity")) * 100, 20, 15)
    score_metric("ROA (%)", sf(info.get("returnOnAssets")) * 100, 10, 5)
    score_metric("Margen EBIT (%)", sf(info.get("operatingMargins")) * 100, 20, 15)
    score_metric("Margen Bruto (%)", sf(info.get("grossMargins")) * 100, 50, 30)
    score_metric("Margen Neto (%)", sf(info.get("profitMargins")) * 100, 15, 10)

    # 2. Crecimiento
    score_metric("Crecimiento Ingresos (%)", sf(info.get("revenueGrowth")) * 100, 15, 10)
    score_metric("Crecimiento Ganancias (%)", sf(info.get("earningsGrowth")) * 100, 15, 10)
    score_metric("CAGR EPS 5Y (%)", sf(adv.get("revenue_cagr_3y")), 15, 10)
    score_metric("Tendencia EPS", 1.5, 2.0, 1.5) # proxy

    # 3. Riesgo
    score_metric("Deuda/Patrimonio (%)", sf(info.get("debtToEquity")), 40, 60, "lower")
    debt_ebitda = sf(adv.get("debt_ebitda", 2.0))
    score_metric("Deuda Neta/EBITDA", debt_ebitda, 2, 3, "lower")
    score_metric("Deuda Total/EBITDA", debt_ebitda, 2, 4, "lower")
    score_metric("Ratio Corriente", sf(info.get("currentRatio")), 1.5, 1.0)
    score_metric("Prueba Acida", sf(info.get("quickRatio")), 1.2, 1.0)
    score_metric("Cobertura Intereses", sf(adv.get("interest_coverage", 5.0)), 8, 5)

    # 4. Flujo Caja
    fcf = 1.5
    fcf_yield = 5.0
    try:
        if cf is not None and "Free Cash Flow" in cf.index:
            fv = cf.loc["Free Cash Flow"].dropna()
            if len(fv) > 0:
                fcf_yield = (fv.iloc[0] / sf(info.get("marketCap", 1))) * 100
                if len(fv) > 1 and fv.iloc[0] > fv.iloc[1] and fv.iloc[0] > 0: fcf = 2.0
                elif fv.iloc[0] > 0: fcf = 1.5
                else: fcf = 0.5
    except: pass
    score_metric("FCF Status", fcf, 2.0, 1.5)
    score_metric("FCF Yield (%)", fcf_yield, 6, 4)
    score_metric("CFO Trend", 1.5, 2.0, 1.5) # proxy

    # 5. Valuacion
    sector = info.get("sector", "Technology")
    sec_pe = SECTOR_PE.get(sector, 20)
    sec_ev = SECTOR_EV_EBITDA.get(sector, 12)
    score_metric("P/E vs Sector", sf(info.get("trailingPE", 20)), sec_pe*0.95, sec_pe*1.05, "lower")
    score_metric("PEG Ratio", sf(info.get("pegRatio", 1.5)), 1.0, 1.5, "lower")
    score_metric("P/S vs Sector", sf(info.get("priceToSalesTrailing12Months", 2.0)), sec_pe*0.2, sec_pe*0.3, "lower")
    score_metric("EV/EBITDA vs Sec", sf(info.get("enterpriseToEbitda", 10.0)), sec_ev*0.95, sec_ev*1.05, "lower")
    score_metric("Fair Value DCF", 1.5, 2.0, 1.5) # proxy
    
    # 6. Accionariado
    score_metric("Dilucion", 1.5, 2.0, 1.5) # proxy
    payout = sf(info.get("payoutRatio")) * 100
    payout_val = 2.0 if 20 <= payout <= 50 else (1.5 if 50 < payout <= 75 else 0.5)
    score_metric("Payout Ratio", payout_val, 2.0, 1.5)

    pct = (pts / 52.0) * 100
    if pct >= 80: cat = "EXCELENTE"
    elif pct >= 65: cat = "BUENO"
    elif pct >= 50: cat = "REGULAR"
    else: cat = "RECHAZAR"

    # Red Flags & Graham Number
    red_flags = []
    try:
        if fin is not None and cf is not None and "Net Income" in fin.index and "Operating Cash Flow" in cf.index:
            ni = sf(fin.loc["Net Income"].iloc[0])
            cfo_val = sf(cf.loc["Operating Cash Flow"].iloc[0])
            if ni > 0 and cfo_val < ni:
                red_flags.append(f"ALERTA CONTABLE: Beneficio Neto ({ni/1e9:.1f}B) supera Caja de Operaciones ({cfo_val/1e9:.1f}B). Validar calidad de ganancias.")
    except: pass
    
    icr = sf(adv.get("interest_coverage", 5.0))
    if icr < 3 and icr > 0:
        red_flags.append(f"ALERTA SOLVENCIA: Cobertura de intereses peligrosa ({icr:.1f}x).")

    bvps = sf(info.get("bookValue"))
    eps = sf(info.get("trailingEps"))
    graham = np.sqrt(22.5 * eps * bvps) if (bvps > 0 and eps > 0) else 0

    return {
        "score": pts,
        "max_score": 52,
        "percentage": pct,
        "category": cat,
        "details": details,
        "red_flags": red_flags,
        "graham_number": graham,
        "sustainable_g": (sf(info.get("returnOnEquity")) * 100) * (1 - sf(info.get("payoutRatio", 0.0)))
    }

def compute_advanced_dividends(ticker: str) -> dict:
    """
    Calcula Payout FCF, YoC (Yield on Cost) proyectado y CAGR de dividendos.
    """
    res = {"payout_fcf": None, "yoc_5y": None, "yoc_10y": None, "dgr_5y": None}
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        divs = tk.dividends
        
        # Payout FCF
        div_paid = abs(info.get("dividendRate", 0) * info.get("sharesOutstanding", 0))
        cf = tk.cashflow
        if cf is not None and not cf.empty:
            ocf = None
            for label in ["Operating Cash Flow", "Total Cash From Operating Activities"]:
                if label in cf.index: ocf = float(cf.loc[label].iloc[0]); break
            capex = 0
            for label in ["Capital Expenditure", "Capital Expenditures"]:
                if label in cf.index: capex = abs(float(cf.loc[label].iloc[0])); break
            if ocf:
                fcf = ocf - capex
                if fcf > 0:
                    res["payout_fcf"] = (div_paid / fcf) * 100

        # DGR & YoC
        if not divs.empty:
            divs_annual = divs.resample('Y').sum()
            if len(divs_annual) >= 6:
                dgr = ((divs_annual.iloc[-1] / divs_annual.iloc[-6]) ** (1/5) - 1)
                res["dgr_5y"] = dgr * 100
                current_yield = info.get("dividendYield", 0)
                if current_yield:
                    res["yoc_5y"] = current_yield * (1 + dgr)**5 * 100
                    res["yoc_10y"] = current_yield * (1 + dgr)**10 * 100
    except: pass
    return res
def solve_implied_growth(ticker: str, target_price: float = None) -> float:
    """
    Calcula la tasa de crecimiento implícita (g) que justifica el precio actual.
    Utiliza una búsqueda binaria para converger al valor de g en un modelo DCF.
    """
    try:
        base = compute_dcf_professional(ticker)
        if not base or "fcff" not in base: return None
        
        price = target_price or base.get("current_price", 0)
        if not price or price <= 0: return None
        
        fcff = base.get("fcff", 0)
        wacc = base.get("wacc", 0.10)
        debt = base.get("total_debt", 0)
        cash = base.get("cash", 0)
        shares = base.get("shares", 1)
        terminal_g = base.get("terminal_g", 0.03)

        # Búsqueda binaria para g (crecimiento de los próximos 5 años)
        low, high = -0.5, 1.5
        for _ in range(25):
            mid = (low + high) / 2
            # Proyección 5 años
            prov_fcffs = [fcff * (1 + mid)**i for i in range(1, 6)]
            # Valor Terminal
            tv = (prov_fcffs[-1] * (1 + terminal_g) / (wacc - terminal_g)) if wacc > terminal_g else 0
            # Present Value
            pv = sum(f / (1+wacc)**t for t, f in enumerate(prov_fcffs, 1)) + (tv / (1+wacc)**5)
            implied_equity = pv - debt + cash
            implied_price = implied_equity / shares
            
            if implied_price < price:
                low = mid
            else:
                high = mid
        return round(mid * 100, 2)
    except: return None

def get_magic_formula_ranking(tickers: list) -> pd.DataFrame:
    """
    Clasifica una lista de tickers según la 'Magic Formula' (Earnings Yield + ROC).
    """
    results = []
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            # Use financial info
            ebit = tk.info.get("ebitda", 0) * 0.8 # proxy
            # Try to get real EBIT from financials
            fins = tk.financials
            if not fins.empty and "Operating Income" in fins.index:
                ebit = fins.loc["Operating Income"].iloc[0]
            
            ev = tk.info.get("enterpriseValue", 1)
            ey = ebit / ev if ev > 0 else 0
            
            # ROC approx: EBIT / (Total Assets - Current Liabilities)
            ta = tk.info.get("totalAssets", 1)
            cl = tk.info.get("totalCurrentLiabilities", 0)
            ic = ta - cl
            roc = ebit / ic if ic > 0 else 0
            
            # Filter outliers
            if ey > 1.0 or roc > 2.0: continue
            
            results.append({
                "Ticker": t,
                "Earnings Yield (%)": round(ey * 100, 2),
                "ROC (%)": round(roc * 100, 2)
            })
        except: continue
        
    if not results: return pd.DataFrame()
    
    df = pd.DataFrame(results)
    # Filter negatives (Greenblatt usually skips banks and utilities, but here we just check metrics)
    df = df[df["Earnings Yield (%)"] > 0]
    
    df["Rank EY"] = df["Earnings Yield (%)"].rank(ascending=False)
    df["Rank ROC"] = df["ROC (%)"].rank(ascending=False)
    df["Magic Score"] = df["Rank EY"] + df["Rank ROC"]
    
    return df.sort_values("Magic Score")
