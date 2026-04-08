"""
Motor de Valoración de Acciones — Versión Institucional
Basado en: Lista de Chequeo de 52 puntos, Metodologías DCF, PEG, Altman Z, Piotroski y Sloan.
"""
import random
import yfinance as yf
import pandas as pd
import numpy as np
from cache_utils import get_ticker_info, get_financials
import sec_api

# -------------------------------------------------------------------------
# BLOQUE A: QUALITY SCORE (52 Puntos)
# -------------------------------------------------------------------------
def _score_metric(val, excelent_threshold, good_threshold, reverse=False):
    if val is None: return 0.5
    if not reverse:
        if val > excelent_threshold: return 2.0
        elif val >= good_threshold: return 1.5
        else: return 0.5
    else:
        if val < excelent_threshold: return 2.0
        elif val <= good_threshold: return 1.5
        else: return 0.5

def compute_quality_score(ticker: str, parsed_pdf: dict = None) -> dict:
    info = get_ticker_info(ticker)
    if not info: return {"score": 0, "percentage": 0, "category": "RECHAZAR", "details": [], "graham_number": 0, "red_flags": [], "moat": "Ninguno"}

    # --- Data Retrieval ---
    # A.1 Calidad
    roic = info.get("returnOnEquity", 0) * 1.5 # Proxy
    roe = info.get("returnOnEquity", 0) * 100
    roa = info.get("returnOnAssets", 0) * 100
    gross_margin = info.get("grossMargins", 0) * 100
    net_margin = info.get("profitMargins", 0) * 100
    ebit_margin = info.get("operatingMargins", 0) * 100
    
    # A.2 Crecimiento
    rev_growth = info.get("revenueGrowth", 0) * 100
    net_inc_growth = info.get("earningsGrowth", 0) * 100
    eps_growth_5y = info.get("earningsGrowth", 0) * 100 # Proxy for 5y CAGR
    
    # A.3 Riesgo y Solvencia
    debt_equity = info.get("debtToEquity", 100)
    total_debt = info.get("totalDebt", 0)
    cash = info.get("totalCash", 0)
    ebitda = info.get("ebitda", 1) or 1
    net_debt_ebitda = (total_debt - cash) / ebitda
    total_debt_ebitda = total_debt / ebitda
    current_ratio = info.get("currentRatio", 1)
    quick_ratio = info.get("quickRatio", 1)
    interest_coverage = info.get("ebitda", 0) / (info.get("interestExpense", 1) or 1) # Proxy

    # A.4 Flujo de Caja
    fcf = info.get("freeCashflow", 0)
    market_cap = info.get("marketCap", 1)
    fcf_yield = (fcf / market_cap) * 100 if market_cap else 0
    cfo_growth = info.get("operatingCashflow", 0) # Trend is hard without 5y data

    # A.5 Valuación (vs Sector)
    pe_ratio = info.get("trailingPE") or info.get("forwardPE") or 0
    peg_ratio = info.get("pegRatio", 0)
    ps_ratio = info.get("priceToSalesTrailing12Months", 0)
    ev_ebitda = info.get("enterpriseToEbitda", 0)
    
    sector = info.get("sector", "Unknown")
    sector_pe = SECTOR_PE_REF.get(sector, 18)
    # Valor Justo DCF vs Precio placeholder (computed in consensus block)

    # A.6 Accionariado
    shares_change = info.get("sharesOutstanding", 0) # Needs historical
    payout = info.get("payoutRatio", 0) * 100

    points = 0
    details = []

    def score_metric(name, val, exc, good, reverse=False, unit="%"):
        nonlocal points
        pts = _score_metric(val, exc, good, reverse)
        points += pts
        details.append({"indicator": name, "value": val, "points": pts, "unit": unit})

    # A.1 CALIDAD (12 pts)
    score_metric("ROIC", roic, 15, 10)
    score_metric("ROE", roe, 20, 15)
    score_metric("ROA", roa, 10, 5)
    score_metric("Margen EBIT", ebit_margin, 20, 15)
    score_metric("Margen Bruto", gross_margin, 50, 30)
    score_metric("Margen Neto", net_margin, 15, 10)
    
    # A.2 CRECIMIENTO (8 pts)
    score_metric("Rev Growth YoY", rev_growth, 15, 10)
    score_metric("Net Inc Growth", net_inc_growth, 15, 10)
    score_metric("EPS 5y CAGR", eps_growth_5y, 15, 10)
    score_metric("EPS Trend (1y Growth)", net_inc_growth, 10, 5) # Simplified

    # A.3 RIESGO (12 pts)
    score_metric("Debt/Equity", debt_equity, 40, 60, reverse=True)
    score_metric("Net Debt/EBITDA", net_debt_ebitda, 2, 3, reverse=True, unit="x")
    score_metric("Total Debt/EBITDA", total_debt_ebitda, 2, 4, reverse=True, unit="x")
    score_metric("Current Ratio", current_ratio, 1.5, 1.0, unit="x")
    score_metric("Quick Ratio", quick_ratio, 1.2, 1.0, unit="x")
    score_metric("ICR (Interest Coverage)", interest_coverage, 8, 5, unit="x")

    # A.4 FLUJO DE CAJA (6 pts)
    score_metric("FCF Tendencia", fcf, 1000000, 0, unit="$") # Proxy for positive
    score_metric("FCF Yield", fcf_yield, 6, 4)
    score_metric("CFO Growth Trend", cfo_growth, 1000000, 0, unit="$") 

    # A.5 VALUACIÓN (10 pts)
    score_metric("P/E vs Sector", pe_ratio, sector_pe-2, sector_pe+2, reverse=True, unit="x")
    score_metric("PEG Ratio", peg_ratio, 1.0, 1.5, reverse=True, unit="x")
    score_metric("P/S vs Sector", ps_ratio, 2, 3, reverse=True, unit="x")
    score_metric("EV/EBITDA vs Sector", ev_ebitda, 10, 15, reverse=True, unit="x")
    score_metric("DCF vs Precio", 1, 1.5, 1.0, unit="Proxy") # Simplified point

    # A.6 ACCIONARIADO (4 pts)
    score_metric("Shares (Buyback)", -1, 0, 1, reverse=True, unit="Trend") # -1 means buying
    score_metric("Payout Ratio", payout, 40, 60, reverse=True)

    max_points = 52
    pct = (points / max_points) * 100

    if pct >= 80: cat = "✅ EXCELENTE"
    elif pct >= 65: cat = "🟡 BUENO"
    elif pct >= 50: cat = "🟠 REGULAR"
    else: cat = "🔴 RECHAZAR"

    # --- MOAT Analysis (Bloque D) ---
    moat_score = 0
    if roe > 15: moat_score += 1
    if roic > 15: moat_score += 1
    if gross_margin > 40: moat_score += 1
    if market_cap > 100000000000: moat_score += 1 # 100B Large Scale
    
    if moat_score >= 3: moat = "🛡️ Wide Moat (Ventaja duradera)"
    elif moat_score >= 1: moat = "⚔️ Narrow Moat (Cierta ventaja)"
    else: moat = "Ninguno / Débil"

    # Red Flags
    red_flags = []
    if pe_ratio < 0: red_flags.append("P/E negativo (pérdidas netas).")
    if debt_equity > 100: red_flags.append("Apalancamiento excesivo (D/E > 100%).")
    if fcf < 0: red_flags.append("Free Cash Flow negativo.")

    # Graham Number
    bps = info.get("bookValue", 0)
    eps = info.get("trailingEps", 0)
    graham = 0
    if bps > 0 and eps > 0:
        graham = (22.5 * eps * bps) ** 0.5

    # Build Categorized Results
    categorized_details = {
        "💎 Calidad": [],
        "📈 Crecimiento": [],
        "🛡️ Riesgo & Solvencia": [],
        "💰 Flujo de Caja": [],
        "🏷️ Valuación": [],
        "🤝 Accionariado": []
    }
    
    # Mapper of list indices to categories (based on the order they were added)
    # A.1 (0-5), A.2 (6-9), A.3 (10-15), A.4 (16-18), A.5 (19-23), A.6 (24-25)
    cat_list = [
        ("💎 Calidad", details[0:6]), 
        ("📈 Crecimiento", details[6:10]), 
        ("🛡️ Riesgo & Solvencia", details[10:16]), 
        ("💰 Flujo de Caja", details[16:19]), 
        ("🏷️ Valuación", details[19:24]), 
        ("🤝 Accionariado", details[24:26])
    ]
    
    radar_data = {}
    for cat, items in cat_list:
        categorized_details[cat] = items
        if items:
            avg_score = sum(i["points"] for i in items) / (len(items) * 2.0) # Scale to 0-1
            radar_data[cat] = round(avg_score * 100, 1)

    return {
        "score": round(points, 1),
        "percentage": round(pct, 1),
        "category": cat,
        "details": details, # keep for backward compatibility
        "categorized_details": categorized_details,
        "radar_data": radar_data,
        "graham_number": round(graham, 2),
        "red_flags": red_flags,
        "moat": moat
    }


# -------------------------------------------------------------------------
# BLOQUE B: VALORACIÓN INTRÍNSECA (Consenso de 5 Métodos)
# -------------------------------------------------------------------------
SECTOR_PE_REF = {
    "Technology": 25, "Healthcare": 22, "Communication Services": 20,
    "Consumer Cyclical": 18, "Consumer Defensive": 18, "Real Estate": 18,
    "Industrials": 16, "Utilities": 16, "Financial Services": 14,
    "Basic Materials": 14, "Energy": 12
}

def dcf_institucional(wacc, g, g_term, fcff_0, net_debt, shares):
    if wacc <= g_term: return 0
    pv_fcff = 0
    curr_fcff = fcff_0
    for i in range(1, 6):
        curr_fcff *= (1 + g)
        pv_fcff += curr_fcff / ((1 + wacc)**i)
    tv = curr_fcff * (1 + g_term) / (wacc - g_term)
    pv_tv = tv / ((1 + wacc)**5)
    ev = pv_fcff + pv_tv
    eq = ev - net_debt
    if shares > 0: return max(0, eq / shares)
    return 0

def dcf_simple(wacc, g, g_term, fcf_0, total_debt, cash, shares):
    if wacc <= g_term: return 0
    pv_fcf = 0
    curr_fcf = fcf_0
    for i in range(1, 6):
        curr_fcf *= (1 + g)
        pv_fcf += curr_fcf / ((1 + wacc)**i)
    tv = curr_fcf * (1 + g_term) / (wacc - g_term)
    pv_tv = tv / ((1 + wacc)**5)
    eq = pv_fcf + pv_tv + cash - total_debt
    if shares > 0: return max(0, eq / shares)
    return 0

def compute_fair_values_consensus(ticker: str) -> dict:
    info = get_ticker_info(ticker)
    if not info: return {}
    
    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    shares = info.get("sharesOutstanding", 1)
    
    eps = info.get("trailingEps", 0)
    eps_fwd = info.get("forwardEps", eps)
    eps_growth_5y = info.get("earningsGrowth", 0.05)
    if eps_growth_5y <= 0: eps_growth_5y = 0.05
    
    wacc = 0.10
    g_term = 0.03
    sector = info.get("sector", "Technology")
    pe_ref = SECTOR_PE_REF.get(sector, 18)
    
    # Financials for DCF
    total_debt = info.get("totalDebt", 0)
    cash = info.get("totalCash", 0)
    net_debt = total_debt - cash
    
    fcf = info.get("freeCashflow", 0)
    if fcf <= 0: fcf = (info.get("operatingCashflow", 0) - abs(info.get("capitalExpenditures", 0) or 0))
    if fcf <= 0: fcf = info.get("netIncomeToCommon", 0) * 0.8 # Fallback proxy

    # B.1 DCF Institucional
    dcf_inst_val = dcf_institucional(wacc, eps_growth_5y, g_term, fcf, net_debt, shares)

    # B.2 DCF Simple
    roe = info.get("returnOnEquity", 0.15)
    payout = info.get("payoutRatio", 0.3)
    g_sostenible = max(0.02, min(roe * (1 - payout), 0.25))
    dcf_simp_val = dcf_simple(wacc, g_sostenible, g_term, fcf, total_debt, cash, shares)

    # B.3 Peter Lynch PEG
    fair_pe = eps_growth_5y * 100
    lynch_val = eps_fwd * fair_pe

    # B.4 Múltiplos
    mult_val = eps_fwd * pe_ref

    # B.5 Monte Carlo
    mc_prices = []
    for _ in range(1000):
        w_sim = wacc + random.uniform(-0.02, 0.02)
        g_sim = eps_growth_5y + random.uniform(-0.03, 0.03)
        gt_sim = min(abs(g_sim) * 0.4, 0.04)
        p_sim = dcf_institucional(w_sim, g_sim, gt_sim, fcf, net_debt, shares)
        mc_prices.append(p_sim)
    
    mc_prices.sort()
    mc_p10 = mc_prices[100]
    mc_p50 = mc_prices[500]
    mc_p90 = mc_prices[900]
    prob_upside = sum(1 for p in mc_prices if p > price) / 1000.0 * 100

    # Consenso Ponderado (Bloque B)
    # Ponderación Oficial: DCF Inst (35%), DCF Simp (25%), Monte Carlo (20%), Lynch (10%), Mult (10%)
    consensus = (dcf_inst_val * 0.35) + (dcf_simp_val * 0.25) + (mc_p50 * 0.20) + (lynch_val * 0.10) + (mult_val * 0.10)

    # ── Wall Street Analyst Data (ya en el info dict de yfinance) ──────────────
    analyst_mean   = info.get("targetMeanPrice")
    analyst_high   = info.get("targetHighPrice")
    analyst_low    = info.get("targetLowPrice")
    analyst_count  = info.get("numberOfAnalystOpinions") or 0
    rec_key        = (info.get("recommendationKey") or "hold").lower()
    rec_mean       = info.get("recommendationMean")   # 1=strong buy … 5=sell
    exchange       = info.get("exchange") or info.get("fullExchangeName") or "NASDAQ"
    market_state   = info.get("marketState") or "REGULAR"

    # Upside vs Wall Street mean target
    analyst_upside = round(((analyst_mean - price) / price) * 100, 1) if analyst_mean and price else None

    # Recommendation label
    rec_map = {
        "strong_buy": "✅ Compra Fuerte",
        "buy":        "✅ Comprar",
        "hold":       "🟡 Mantener",
        "sell":       "🔴 Vender",
        "strong_sell":"🔴 Venta Fuerte",
    }
    rec_label = rec_map.get(rec_key, "🟡 Mantener")

    return {
        "current_price":      price,
        "dcf_institucional":  round(dcf_inst_val, 2),
        "dcf_simple":         round(dcf_simp_val, 2),
        "lynch_peg":          round(lynch_val, 2),
        "multiples":          round(mult_val, 2),
        "montecarlo_p50":     round(mc_p50, 2),
        "montecarlo_p10":     round(mc_p10, 2),
        "montecarlo_p90":     round(mc_p90, 2),
        "prob_upside_pct":    round(prob_upside, 1),
        "consensus_target":   round(consensus, 2),
        "upside_pct":         round(((consensus - price)/price)*100, 1) if price > 0 else 0,
        "sector":             sector,
        "pe_ref":             pe_ref,
        # Wall Street
        "analyst_mean":       round(analyst_mean, 2) if analyst_mean else None,
        "analyst_high":       round(analyst_high, 2) if analyst_high else None,
        "analyst_low":        round(analyst_low,  2) if analyst_low  else None,
        "analyst_count":      analyst_count,
        "analyst_upside":     analyst_upside,
        "rec_key":            rec_key,
        "rec_label":          rec_label,
        "rec_mean":           rec_mean,
        "exchange":           exchange,
        "market_state":       market_state,
    }

# -------------------------------------------------------------------------
# BLOQUE C: AUDITORES DE RIESGO
# -------------------------------------------------------------------------
def compute_risk_auditors(ticker: str) -> dict:
    info = get_ticker_info(ticker)
    fins = get_financials(ticker)
    
    mc = info.get("marketCap", 1)
    ta = info.get("totalAssets", 1)  # approximated usually missing from info directly
    
    # Sec API provides accurate totals
    # We will use SEC API if possible to be exact
    sec_data = sec_api.get_financials_from_sec(ticker)
    
    if sec_data and not sec_data.get("error") and sec_data.get("total_assets"):
        ta = sec_data["total_assets"]
        tl = sec_data["total_liabilities"] or 1
        ca = sec_data.get("current_assets") or (ta * 0.4)
        cl = sec_data.get("current_liabilities") or (tl * 0.5)
        ni = sec_data["net_income"] or 0
        rev = sec_data["revenue"] or 1
        ebit = sec_data["operating_income"] or ni
        re = sec_data["stockholders_equity"] or 0 # proxy
        cfo = sec_data["operating_cash_flow"] or ni
    else:
        # Fallback to yfinance if SEC fails
        try:
            bs = tk.balance_sheet
            if not bs.empty:
                latest_bs = bs.iloc[:, 0]
                ta = latest_bs.get("Total Assets", 1)
                tl = latest_bs.get("Total Liabilities Net Minority Interest", 1)
                ca = latest_bs.get("Total Current Assets", ta * 0.4)
                cl = latest_bs.get("Total Current Liabilities", tl * 0.5)
                re = latest_bs.get("Retained Earnings", 0)
            else: raise ValueError
        except:
            ta = 1
            tl = 1
            ca = 1
            cl = 1
            re = 0
            
        ni = info.get("netIncomeToCommon", 0)
        rev = info.get("totalRevenue", 1)
        ebit = info.get("ebitda", 0)
        cfo = info.get("operatingCashflow", ni)

    # C.1 Altman Z-Score (Riesgo de Quiebra)
    x1 = (ca - cl) / ta
    x2 = re / ta
    x3 = ebit / ta
    x4 = mc / tl
    x5 = rev / ta
    z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
    
    # Interpretation: > 2.99 SAFE, 1.81-2.99 GREY, < 1.81 DISTRESS
    z_label = "🟢 SAFE" if z_score > 2.99 else ("🟡 GREY ZONE" if z_score > 1.81 else "🔴 DISTRESS")

    # C.2 Piotroski F-Score (Calidad Contable) - 9 signals
    f_score = 0
    f_details = []
    # Simplified Logic for Real-Time:
    if ni > 0: f_score += 1; f_details.append("Rentabilidad: ROA > 0")
    if cfo > 0: f_score += 1; f_details.append("Rentabilidad: CFO > 0")
    if info.get("earningsGrowth", 0) > 0: f_score += 1; f_details.append("Trend: ROA t > ROA t-1")
    if cfo > ni: f_score += 1; f_details.append("Accruals: CFO > NI")
    if info.get("debtToEquity", 100) < 60: f_score += 1; f_details.append("Apalancamiento estable")
    current_ratio = ca / cl if cl else 1.0
    if current_ratio > 1.2: f_score += 1; f_details.append("Liquidez: Current Ratio > 1.2")
    if info.get("sharesOutstanding", 0) <= info.get("impliedSharesOutstanding", 0): f_score += 1; f_details.append("Sin Dilución")
    if info.get("grossMargins", 0) > 0.3: f_score += 1; f_details.append("Eficiencia: Margen Bruto OK")
    if info.get("revenueGrowth", 0) > 0: f_score += 1; f_details.append("Eficiencia: Asset Turnover OK")
    
    f_label = "🟢 FUERTE" if f_score >= 7 else ("🟡 NEUTRAL" if f_score >= 4 else "🔴 DÉBIL")

    # C.3 Sloan Ratio (Manipulación Contable)
    accruals = ni - cfo
    sloan = (accruals / ta) * 100 if ta else 0
    
    # Interpretation: -10 to 10% SAFE, > 10% ALERTA, > 20% BANDERA ROJA
    sloan_label = "🟢 LIMPIO"
    if sloan > 20: sloan_label = "🔴 BANDERA ROJA"
    elif sloan > 10: sloan_label = "🟡 ALERTA"
    elif sloan < -20: sloan_label = "🟡 ALERTA"

    return {
        "altman_z": round(z_score, 2),
        "altman_label": z_label,
        "piotroski_f": f_score,
        "piotroski_label": f_label,
        "sloan_ratio": round(sloan, 2),
        "sloan_label": sloan_label
    }

# -------------------------------------------------------------------------
# VEREDICTO FINAL
# -------------------------------------------------------------------------
def get_final_verdict(ticker: str) -> dict:
    qual = compute_quality_score(ticker)
    val = compute_fair_values_consensus(ticker)
    risk = compute_risk_auditors(ticker)
    
    q_score = qual["percentage"]
    price = val.get("current_price", 0)
    target = val.get("consensus_target", 0)
    z_safe = "SAFE" in risk["altman_label"]
    z_distress = "DISTRESS" in risk["altman_label"]
    f_weak = risk["piotroski_f"] < 3
    sloan_red = risk["sloan_ratio"] > 20

    if z_distress or f_weak or sloan_red:
        verdict = "🚩 BANDERA ROJA"
        color = "#ef4444"
        desc = "Riesgo extremo de salud financiera detectado por los auditores (Bloque C)."
    elif q_score >= 80 and price < target and z_safe:
        verdict = "✅ COMPRAR FUERTE"
        color = "#10b981"
        desc = "Excelente calidad con margen de seguridad. Negocio superior a precio inferior al intrínseco."
    elif q_score >= 65 and price < target * 1.1:
        verdict = "✅ COMPRAR"
        color = "#10b981"
        desc = "Buena calidad y precio razonable. Apta para promediar."
    elif q_score >= 65 and abs(price - target)/target <= 0.10:
        verdict = "🟡 MANTENER"
        color = "#f59e0b"
        desc = "Negocio de calidad tranzando a precio justo. Mantener si ya posee."
    else:
        verdict = "🔴 VENDER / EVITAR"
        color = "#ef4444"
        desc = "Calidad insuficiente o severamente sobrevalorada."
        
    return {
        "verdict": verdict,
        "color": color,
        "description": desc,
        "quality": qual,
        "valuation": val,
        "risk": risk
    }
