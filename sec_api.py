"""
sec_api.py — Cliente directo de la SEC EDGAR REST API (data.sec.gov)
=====================================================================
Consume los endpoints JSON públicos de la SEC sin necesidad de API keys
ni librerías externas más allá de `requests`.

Endpoints principales:
  - Ticker→CIK mapping:  https://www.sec.gov/files/company_tickers.json
  - Submissions (filings): https://data.sec.gov/submissions/CIK{cik}.json
  - XBRL CompanyFacts:     https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
  - XBRL CompanyConcept:   https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json

Restricciones SEC:
  - Max 10 requests/second por IP
  - User-Agent obligatorio con nombre + email
  - Datos son 100% públicos y gratuitos
"""

import time
import requests
import streamlit as st
import pandas as pd
from functools import lru_cache
from typing import Optional, Dict, Any, List

# ─── Configuración ────────────────────────────────────────────────────────────
SEC_HEADERS = {
    "User-Agent": "QuantumTerminal (carlosdaniloangaritagarcia2@gmail.com)",
    "Accept-Encoding": "gzip, deflate",
}
_RATE_LIMIT_DELAY = 0.12  # ~8 req/s para mantener margen con el límite de 10/s

_last_request_time = 0.0


def _rate_limited_get(url: str, timeout: int = 15) -> Optional[requests.Response]:
    """GET con rate limiting automático para cumplir política SEC."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _RATE_LIMIT_DELAY:
        time.sleep(_RATE_LIMIT_DELAY - elapsed)
    _last_request_time = time.time()

    try:
        resp = requests.get(url, headers=SEC_HEADERS, timeout=timeout)
        if resp.status_code == 200:
            return resp
        elif resp.status_code == 429:
            # Rate limited — esperar y reintentar una vez
            time.sleep(1.5)
            return requests.get(url, headers=SEC_HEADERS, timeout=timeout)
        else:
            print(f"[SEC API] HTTP {resp.status_code} para {url}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[SEC API] Error de red: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TICKER → CIK MAPPING
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=86400, show_spinner=False)
def _load_ticker_cik_map() -> Dict[str, str]:
    """Descarga el mapeo completo de tickers a CIKs desde SEC (se cachea 24h)."""
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = _rate_limited_get(url)
    if not resp:
        return {}

    data = resp.json()
    mapping = {}
    for entry in data.values():
        ticker = entry.get("ticker", "").upper()
        cik = str(entry.get("cik_str", "")).zfill(10)
        if ticker:
            mapping[ticker] = cik
    return mapping


def ticker_to_cik(ticker: str) -> Optional[str]:
    """Convierte un ticker (ej: 'AAPL') a su CIK de 10 dígitos."""
    mapping = _load_ticker_cik_map()
    return mapping.get(ticker.upper())


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SUBMISSIONS (Historial de Filings)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def get_company_submissions(ticker: str) -> Optional[Dict]:
    """
    Obtiene el historial completo de filings de una empresa.
    Retorna nombre, CIK, SIC, dirección, y lista de filings recientes.
    """
    cik = ticker_to_cik(ticker)
    if not cik:
        return None

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    resp = _rate_limited_get(url)
    if not resp:
        return None

    data = resp.json()
    return {
        "cik": cik,
        "name": data.get("name", ""),
        "sic": data.get("sic", ""),
        "sic_description": data.get("sicDescription", ""),
        "state": data.get("stateOfIncorporation", ""),
        "fiscal_year_end": data.get("fiscalYearEnd", ""),
        "category": data.get("category", ""),
        "entity_type": data.get("entityType", ""),
        "website": data.get("website", ""),
        # Filings recientes
        "recent_filings": _parse_recent_filings(data.get("filings", {}).get("recent", {})),
    }


def _parse_recent_filings(recent: Dict) -> pd.DataFrame:
    """Parsea el bloque 'recent' del JSON de submissions a un DataFrame."""
    if not recent:
        return pd.DataFrame()

    df = pd.DataFrame({
        "form": recent.get("form", []),
        "filing_date": recent.get("filingDate", []),
        "accession_number": recent.get("accessionNumber", []),
        "primary_document": recent.get("primaryDocument", []),
        "description": recent.get("primaryDocDescription", []),
    })
    return df


def get_latest_filing_url(ticker: str, form_type: str = "10-K") -> Optional[str]:
    """Retorna la URL del último filing específico (10-K, 10-Q, 8-K, etc.)."""
    subs = get_company_submissions(ticker)
    if subs is None:
        return None

    filings = subs["recent_filings"]
    if filings.empty:
        return None

    filtered = filings[filings["form"] == form_type]
    if filtered.empty:
        return None

    row = filtered.iloc[0]
    acc = row["accession_number"].replace("-", "")
    doc = row["primary_document"]
    cik = subs["cik"].lstrip("0")

    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. XBRL COMPANY FACTS — Datos Financieros Estructurados
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def get_company_facts(ticker: str) -> Optional[Dict]:
    """
    Obtiene TODOS los datos financieros XBRL de una empresa.
    Esto incluye: Revenue, NetIncome, Assets, Liabilities, EPS, etc.
    Es el endpoint más poderoso de la SEC API.
    """
    cik = ticker_to_cik(ticker)
    if not cik:
        return None

    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    resp = _rate_limited_get(url)
    if not resp:
        return None

    return resp.json()


def get_concept_timeseries(ticker: str, concept: str, taxonomy: str = "us-gaap") -> Optional[pd.DataFrame]:
    """
    Obtiene la serie temporal de un concepto XBRL específico.
    Ejemplos de conceptos:
      - Revenues / RevenueFromContractWithCustomerExcludingAssessedTax
      - NetIncomeLoss
      - Assets
      - Liabilities
      - StockholdersEquity
      - EarningsPerShareDiluted
      - OperatingIncomeLoss
      - CashAndCashEquivalentsAtCarryingValue
      - LongTermDebt
      - CommonStockSharesOutstanding
    """
    cik = ticker_to_cik(ticker)
    if not cik:
        return None

    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{concept}.json"
    resp = _rate_limited_get(url)
    if not resp:
        return None

    data = resp.json()
    units = data.get("units", {})

    # Los valores pueden estar en USD, shares, o pure
    rows = []
    for unit_type, entries in units.items():
        for entry in entries:
            rows.append({
                "end": entry.get("end", ""),
                "val": entry.get("val"),
                "accn": entry.get("accn", ""),
                "fy": entry.get("fy"),
                "fp": entry.get("fp"),
                "form": entry.get("form", ""),
                "filed": entry.get("filed", ""),
                "unit": unit_type,
            })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df["end"] = pd.to_datetime(df["end"], errors="coerce")
    df = df.dropna(subset=["end", "val"])
    df = df.sort_values("end", ascending=False)
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 4. FUNCIONES DE ALTO NIVEL — Datos Financieros Listos para Usar
# ═══════════════════════════════════════════════════════════════════════════════

# Mapeo de campos a posibles conceptos XBRL (en orden de prioridad)
_CONCEPT_MAP = {
    # ── INCOME STATEMENT ──
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfServices", "CostOfGoodsSold"],
    "gross_profit": ["GrossProfit"],
    "operating_expenses": ["OperatingExpenses"],
    "r_and_d": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "sga": ["SellingGeneralAndAdministrativeExpense", "SellingAdministrativeAndGeneralExpense"],
    "operating_income": ["OperatingIncomeLoss"],
    "interest_expense": ["InterestExpense", "InterestExpenseDebt", "InterestExpenseNonoperatingExcludingInterestIncomeFromShortTermInvestments"],
    "net_income": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"],
    
    # ── NEW FORENSIC & PRO MAPPINGS (Sprint 1) ──
    "deferred_revenue_current": ["DeferredRevenueCurrent"],
    "deferred_revenue_noncurrent": ["DeferredRevenueNoncurrent"],
    "income_taxes_paid": ["IncomeTaxesPaid", "IncomeTaxesPaidNet"],
    "deferred_income_tax": ["DeferredIncomeTaxExpenseBenefit"],
    "operating_lease_asset": ["OperatingLeaseRightOfUseAsset"],
    "operating_lease_liability": ["OperatingLeaseLiabilityCurrent", "OperatingLeaseLiabilityNoncurrent"],
    "goodwill_acquired": ["GoodwillAcquiredDuringPeriod", "BusinessCombinationConsiderationTransferred"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    "additional_paid_in_capital": ["AdditionalPaidInCapital"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "eps_basic": ["EarningsPerShareBasic"],
    "ebitda": ["OperatingIncomeLoss"],  # Placeholder — se calcula sintéticamente
    "tax_provision": ["IncomeTaxExpenseBenefit"],
    "pretax_income": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],

    # ── BALANCE SHEET ──
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"],
    "short_term_investments": ["ShortTermInvestments", "MarketableSecuritiesCurrent"],
    "receivables": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "inventory": ["InventoryNet", "InventoryFinishedGoods", "InventoryRawMaterialsAndSupplies"],
    "prepaid_expenses": ["PrepaidExpenseCurrent"],
    "current_assets": ["AssetsCurrent"],
    "ppe": ["PropertyPlantAndEquipmentNet"],
    "goodwill": ["Goodwill"],
    "intangibles": ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"],
    "total_assets": ["Assets"],
    "accounts_payable": ["AccountsPayableCurrent"],
    "accrued_liabilities": ["AccruedLiabilitiesCurrent"],
    "short_term_debt": ["ShortTermBorrowings", "CommercialPaper", "LongTermDebtCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "long_term_debt": ["LongTermDebt", "LongTermDebtNoncurrent", "FinanceLeaseLiabilityNoncurrent"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "total_debt": ["LongTermDebt", "LongTermDebtNoncurrent", "DebtCurrent", "ShortTermBorrowings"],
    "shares_outstanding": ["CommonStockSharesOutstanding", "WeightedAverageNumberOfDilutedSharesOutstanding"],
    # ── INVENTARIO GRANULAR (nuevo) ──
    "inventory_finished": ["InventoryFinishedGoods", "InventoryFinishedGoodsNetOfReserves"],
    "inventory_wip": ["InventoryWorkInProcess", "InventoryWorkInProcessNetOfReserves"],
    "inventory_raw": ["InventoryRawMaterials", "InventoryRawMaterialsNetOfReserves", "InventoryRawMaterialsAndSupplies"],
    # ── DEUDA GRANULAR (nuevo) ──
    "current_debt_mature": ["DebtCurrent", "LongTermDebtCurrent", "CurrentPortionOfLongTermDebt"],
    "commercial_paper": ["CommercialPaper"],
    # ── BUYBACKS (nuevo) ──
    "buyback": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfCommonStockAndPreferredStock"],

    # ── CASH FLOW ──
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "depreciation_amortization": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
    "stock_based_comp": ["ShareBasedCompensation"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireIntangibleAssets"],
    "investing_cash_flow": ["NetCashProvidedByUsedInInvestingActivities"],
    "financing_cash_flow": ["NetCashProvidedByUsedInFinancingActivities"],
    "dividends_paid": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "repurchase_stock": ["PaymentsForRepurchaseOfCommonStock"],

    # ── FORENSIC/QUALITY ──
    "accruals": ["AdjustmentsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivities"],
    "inventory_turnover_input": ["CostOfGoodsAndServicesSold"],
    "receivables_turnover_input": ["Revenues"],
}

# ── Constante de normalización ──────────────────────────────────────────────────
_B = 1_000_000_000  # Billones (billion). Todos los monetos se dividen por esto.


def _to_b(val: Optional[float]) -> Optional[float]:
    """Convierte un valor en USD absolutos a billones (B). Retorna None si None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return round(float(val) / _B, 4)


def _safe_latest(df: Optional[pd.DataFrame], form: str = "10-K") -> Optional[float]:
    """Obtiene el último valor de un DataFrame de concepto XBRL filtrado por form."""
    if df is None or df.empty:
        return None
    filtered = df[df["form"] == form]
    if filtered.empty:
        filtered = df
    return float(filtered.iloc[0]["val"])


def _yearly_series(df: Optional[pd.DataFrame], form: str = "10-K", years: int = 5) -> Dict[int, float]:
    """
    Retorna un dict {año_fiscal: valor_en_B} de los últimos N años (10-K).
    Deduplica por año fiscal tomando el filing más reciente.
    """
    if df is None or df.empty:
        return {}
    filtered = df[df["form"] == form] if form else df
    if filtered.empty:
        filtered = df
    yearly = filtered.dropna(subset=["fy"]).drop_duplicates(subset=["fy"], keep="first").head(years)
    return {int(r["fy"]): round(float(r["val"]) / _B, 4) for _, r in yearly.iterrows()}


def _get_yf_metric(yf_cashflow: Optional[Any], metric_name: str, year_idx: int = 0) -> Optional[float]:
    """
    Extrae una métrica del DataFrame de cashflow de yfinance.
    yf_cashflow es el resultado de yf.Ticker().cashflow.
    Retorna el valor absoluto en USD (no normalizado).
    """
    if yf_cashflow is None:
        return None
    try:
        if hasattr(yf_cashflow, "loc") and metric_name in yf_cashflow.index:
            row = yf_cashflow.loc[metric_name]
            vals = row.dropna()
            if not vals.empty and year_idx < len(vals):
                return float(vals.iloc[year_idx])
    except Exception:
        pass
    return None


def _get_yf_metric_all_years(yf_cashflow: Optional[Any], metric_name: str) -> Dict[int, float]:
    """
    Extrae todos los años disponibles de una métrica de yfinance cashflow.
    Retorna dict {año: valor_en_B}.
    """
    result_map: Dict[int, float] = {}
    if yf_cashflow is None:
        return result_map
    try:
        if hasattr(yf_cashflow, "loc") and metric_name in yf_cashflow.index:
            row = yf_cashflow.loc[metric_name].dropna()
            for col, val in row.items():
                try:
                    yr = int(pd.Timestamp(col).year)
                    result_map[yr] = round(float(val) / _B, 4)
                except Exception:
                    pass
    except Exception:
        pass
    return result_map


def _resolve_concept(ticker: str, field_name: str, form_filter: Any = ("10-K", "10-Q")) -> Optional[pd.DataFrame]:
    """Intenta resolver un campo financiero probando múltiples conceptos XBRL.
       Prioriza los formularios en form_filter (ej: 10-K antes de 10-Q)."""
    concepts = _CONCEPT_MAP.get(field_name, [])
    for concept in concepts:
        df = get_concept_timeseries(ticker, concept)
        if df is not None and not df.empty:
            # Si form_filter es una lista/tupla, intentamos en ese orden
            if isinstance(form_filter, (list, tuple)):
                for ftype in form_filter:
                    df_filtered = df[df["form"] == ftype]
                    if not df_filtered.empty:
                        return df_filtered
            elif form_filter:
                df_filtered = df[df["form"] == form_filter]
                if not df_filtered.empty:
                    return df_filtered
            return df
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_financials_from_sec(ticker: str) -> Dict[str, Any]:
    """
    Extrae datos financieros principales de la SEC API (XBRL CompanyFacts).
    Retorna un diccionario con los últimos valores anuales (10-K).

    Este es el reemplazo directo de edgartools: no necesita librerías externas.
    """
    # ── Campos base (valores en USD absolutos — se normalizan a B en funciones deep) ──
    result = {
        "ticker": ticker,
        "source": "SEC EDGAR API (data.sec.gov)",
        # P&L principales
        "revenue": None,
        "net_income": None,
        "gross_profit": None,
        "operating_income": None,
        "pretax_income": None,
        "tax_provision": None,
        "eps_diluted": None,
        # Balance
        "total_assets": None,
        "total_liabilities": None,
        "stockholders_equity": None,
        "cash": None,
        "long_term_debt": None,
        "current_assets": None,
        "current_liabilities": None,
        "shares_outstanding": None,
        # Inventario granular (NUEVO)
        "inventory_finished": None,
        "inventory_wip": None,
        "inventory_raw": None,
        # Deuda granular (NUEVO)
        "current_debt_mature": None,
        "commercial_paper": None,
        # Cash flow
        "operating_cash_flow": None,
        "capex": None,
        "dividends_paid": None,
        "stock_based_comp": None,   # SBC — crítico para True FCF
        "buyback": None,            # Recompras (NUEVO)
        # Historias series temporales (valores en B)
        "revenue_history": {},      # {año: valor_B}
        "net_income_history": {},   # {año: valor_B}
        "fcf_history": {},          # {año: valor_B} — FCF GAAP
        "error": None,
    }

    try:
        # ── Info de la empresa ──
        subs = get_company_submissions(ticker)
        if subs:
            result["company_name"] = subs.get("name", "")
            result["sic_description"] = subs.get("sic_description", "")
            result["fiscal_year_end"] = subs.get("fiscal_year_end", "")

        # ── Extraer todos los campos (incluidos los nuevos) ──
        _scalar_fields = [
            # P&L
            "revenue", "net_income", "gross_profit", "operating_income",
            "pretax_income", "tax_provision", "eps_diluted",
            # Balance
            "total_assets", "total_liabilities", "stockholders_equity",
            "cash", "long_term_debt", "shares_outstanding",
            "current_assets", "current_liabilities",
            # Inventario granular
            "inventory_finished", "inventory_wip", "inventory_raw",
            # Deuda granular
            "current_debt_mature", "commercial_paper",
            # Cash flow
            "operating_cash_flow", "capex", "dividends_paid",
            "stock_based_comp", "buyback",
        ]
        for field in _scalar_fields:
            df = _resolve_concept(ticker, field, form_filter="10-K")
            if df is not None and not df.empty:
                result[field] = float(df.iloc[0]["val"])

        # ── Series históricas en billones ──
        for field, key in [("revenue", "revenue_history"), ("net_income", "net_income_history")]:
            df = _resolve_concept(ticker, field, form_filter="10-K")
            result[key] = _yearly_series(df, form="10-K", years=5)

        # ── FCF GAAP = OCF - |CapEx| (con fallback: si capex=None se deja vacío) ──
        ocf_df = _resolve_concept(ticker, "operating_cash_flow", form_filter="10-K")
        capex_df = _resolve_concept(ticker, "capex", form_filter="10-K")
        if ocf_df is not None and not ocf_df.empty:
            ocf_map = _yearly_series(ocf_df, form="10-K", years=5)  # en B
            if capex_df is not None and not capex_df.empty:
                cap_map = _yearly_series(capex_df, form="10-K", years=5)  # en B
                result["fcf_history"] = {
                    yr: round(ocf_val - abs(cap_map.get(yr, 0)), 4)
                    for yr, ocf_val in ocf_map.items()
                    if yr in cap_map
                }
            # Si capex vacío (ej: QCOM), guardamos al menos el OCF para que no quede []
            if not result["fcf_history"]:
                result["fcf_history"] = {}  # Se completará con YF en get_true_fcf()

    except Exception as e:
        result["error"] = str(e)

    return result


@st.cache_data(ttl=86400, show_spinner=False)
def extract_full_company_dna(ticker: str) -> Dict[str, Any]:
    """
    EXTRACTOR ULTRA: Mapea +100 conceptos XBRL y los persiste en la base de datos.
    Retorna un reporte estructurado de Salud Financiera y Auditoría.
    """
    from database import save_ultra_financials, get_ultra_financials
    
    # 1. Intentar cargar de la BD primero
    db_hist = get_ultra_financials(ticker)
    if not db_hist.empty:
        # Si tenemos datos de hace menos de 24h, podríamos usarlos.
        # Por ahora, si hay datos, los retornamos formateados.
        pass

    cik = ticker_to_cik(ticker)
    if not cik: return {"error": "Ticker no encontrado"}

    facts = get_company_facts(ticker)
    if not facts: return {"error": "No se pudieron obtener facts de la SEC"}

    gaap = facts.get("facts", {}).get("us-gaap", {})
    records_to_save = []
    summary = {}

    for field, concepts in _CONCEPT_MAP.items():
        for concept in concepts:
            if concept in gaap:
                data = gaap[concept]
                units = data.get("units", {})
                for unit_name, entries in units.items():
                    for entry in entries:
                        # Guardamos solo 10-K y 10-Q para no saturar
                        if entry.get("form") in ("10-K", "10-Q", "8-K"):
                            # Preparar para BD
                            records_to_save.append({
                                "concept": concept,
                                "end": entry["end"],
                                "val": entry["val"],
                                "unit": unit_name,
                                "form": entry.get("form"),
                                "filed": entry.get("filed"),
                                "accn": entry.get("accn"),
                                "fy": entry.get("fy"),
                                "fp": entry.get("fp")
                            })
                
                # Para el summary, tomamos el último 10-K disponible
                df = get_concept_timeseries(ticker, concept)
                if df is not None and not df.empty:
                    anual = df[df["form"] == "10-K"]
                    if not anual.empty:
                        summary[field] = float(anual.iloc[0]["val"])
                    else:
                        summary[field] = float(df.iloc[0]["val"])
                break # Encontrado concepto prioritario
    
    # Persistir en BD (Background)
    if records_to_save:
        save_ultra_financials(ticker, cik, records_to_save)

    # Añadir meta-info
    subs = get_company_submissions(ticker)
    if subs:
        summary["company_name"] = subs.get("name", "")
        summary["cik"] = cik
        summary["whales"] = get_whale_holdings_13f(ticker)

    return summary


def get_whale_holdings_13f(ticker: str) -> List[Dict]:
    """
    WHALE TRACKER: Rastrea qué fondos han reportado posiciones en el ticker
    basándose en los filings de la SEC.
    """
    subs = get_company_submissions(ticker)
    if not subs: return []

    # Buscamos en 'recent_filings' por si hay menciones (esto es una simplificación)
    # El 13F se reporta por el FONDO, no por la EMPRESA. 
    # Para hacerlo real requeriría mapear todos los 13F del trimestre.
    # En este módulo, usaremos un mock inteligente o buscaremos datos institucionales previos.
    from database import get_institutional_holdings
    db_whales = get_institutional_holdings(ticker)
    if not db_whales.empty:
        return db_whales.to_dict('records')
        
    return []

    return result


@st.cache_data(ttl=3600, show_spinner=False)
def get_filing_list(ticker: str, form_type: str = None, limit: int = 20) -> pd.DataFrame:
    """
    Lista los filings recientes de una empresa, opcionalmente filtrados por tipo.
    Útil para mostrar en la UI qué documentos están disponibles.
    """
    subs = get_company_submissions(ticker)
    if subs is None:
        return pd.DataFrame()

    df = subs["recent_filings"]
    if df.empty:
        return df

    if form_type:
        df = df[df["form"] == form_type]

    return df.head(limit)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. COMPARACIÓN HISTÓRICA — Para Análisis de Tendencias
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def get_historical_financials(ticker: str, years: int = 5) -> pd.DataFrame:
    """
    Construye un DataFrame con el histórico financiero detallado de los últimos N años.
    Columnas: Year, Revenue, Cost of Revenue, Gross Profit, Operating Expenses, 
             Operating Income, Net Income, Assets, Equity, EPS, Operating CF
    Ideal para tablas de estados de resultados y análisis de tendencias.
    """
    fields = {
        "Revenue": "revenue",
        "COGS": "cost_of_revenue",
        "Gross Profit": "gross_profit",
        "Operating Expenses": "operating_expenses",
        "Operating Income": "operating_income",
        "Net Income": "net_income",
        "Total Assets": "total_assets",
        "Equity": "stockholders_equity",
        "EPS": "eps_diluted",
        "Operating CF": "operating_cash_flow",
    }

    all_data = {}
    for label, field_name in fields.items():
        df = _resolve_concept(ticker, field_name, form_filter="10-K")
        if df is not None and not df.empty:
            # Deduplicar por año fiscal (fy) para evitar duplicados de filings corregidos
            yearly = df.drop_duplicates(subset=["fy"], keep="first").head(years)
            for _, row in yearly.iterrows():
                yr = row["fy"]
                end_date = row["end"]
                if pd.notna(yr):
                    yr = int(yr)
                    if yr not in all_data:
                        all_data[yr] = {"Year": yr, "Date": end_date}
                    all_data[yr][label] = float(row["val"])

    if not all_data:
        return pd.DataFrame()

    result = pd.DataFrame(list(all_data.values()))
    result = result.sort_values("Year", ascending=False) # Más reciente primero como en InvestingPro
    
    # Calcular campos faltantes si es posible (Lógica de autocompletado)
    if not result.empty:
        if "Revenue" in result.columns and "COGS" in result.columns and "Gross Profit" not in result.columns:
            result["Gross Profit"] = result["Revenue"] - result["COGS"].abs()
        if "Revenue" in result.columns and "Gross Profit" in result.columns and "COGS" not in result.columns:
            result["COGS"] = result["Revenue"] - result["Gross Profit"]
            
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# 6. SMART MONEY — Formularios 4 y Operaciones Insider
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def get_insider_trades(ticker: str, limit: int = 15) -> pd.DataFrame:
    """
    Rastrea las operaciones de insiders directos (CEO, Directores) buscando 
    el "Formulario 4" en la lista de submissions de la empresa.
    """
    subs = get_company_submissions(ticker)
    if subs is None:
        return pd.DataFrame()

    filings = subs.get("recent_filings")
    if filings is None or filings.empty:
        return pd.DataFrame()

    # Filtrar solo Formulario 4
    form4 = filings[filings["form"] == "4"].head(limit).copy()
    if form4.empty:
        return pd.DataFrame()

    cik = subs["cik"].lstrip("0")
    
    # Construir el link directo del documento en SEC EDGAR
    urls = []
    for _, row in form4.iterrows():
        acc = str(row["accession_number"]).replace("-", "")
        # Link primario html index
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{row['primary_document']}"
        urls.append(url)

    form4["document_url"] = urls
    
    # Renombrar para legibilidad de UI
    form4 = form4.rename(columns={
        "filing_date": "Fecha", 
        "description": "Descripción", 
        "form": "Formulario"
    })
    
    return form4[["Fecha", "Formulario", "Descripción", "document_url"]]

@st.cache_data(ttl=3600, show_spinner=False)
def get_detailed_insider_transactions(ticker: str) -> pd.DataFrame:
    """
    Rastrea transacciones de insiders (Formulario 4) filtrando por adquisiciones/disposiciones.
    Nota: Parsear el XML completo es complejo por red, así que recolectamos los meta-datos
    disponibles en los filings recientes y pre-procesamos los links.
    """
    df_trades = get_insider_trades(ticker, limit=40)
    if df_trades.empty:
        return pd.DataFrame()
    
    # Intentamos identificar si es Compra o Venta por la descripción
    # Normalmente la SEC pone "Statement of changes in beneficial ownership of securities"
    # Para ver si compró o vendió necesitamos el XML, pero podemos agrupar filings recientes.
    
    return df_trades

def get_short_interest_data(ticker: str) -> Dict[str, Any]:
    """
    Obtiene datos de Short Interest combinando YFinance (float %) y 
    estimaciones de volumen de short consolidado.
    """
    import yfinance as yf
    tk = yf.Ticker(ticker)
    info = tk.info
    
    return {
        "short_percent_float": info.get("shortPercentOfFloat", 0) * 100,
        "short_ratio": info.get("shortRatio", 0),
        "shares_short": info.get("sharesShort", 0),
        "shares_float": info.get("floatShares", 0),
        "date": info.get("dateShortInterest", "")
    }
@st.cache_data(ttl=3600, show_spinner=False)
def search_whale_activity(ticker: str, limit: int = 10) -> pd.DataFrame:
    """
    Search for 13F (Hedge Funds), 13D/G (5% ownership) filings.
    """
    subs = get_company_submissions(ticker)
    if not subs: return pd.DataFrame()
    
    filings = subs.get("recent_filings")
    if filings.empty: return pd.DataFrame()
    
    # Whale forms
    whale_forms = ["13F-HR", "13D", "13G", "SC 13D", "SC 13G"]
    filtered = filings[filings["form"].isin(whale_forms)].head(limit).copy()
    
    if filtered.empty: return pd.DataFrame()
    
    cik = subs["cik"].lstrip("0")
    urls = []
    for _, row in filtered.iterrows():
        acc = str(row["accession_number"]).replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{row['primary_document']}"
        urls.append(url)
        
    filtered["document_url"] = urls
    return filtered


# ═══════════════════════════════════════════════════════════════════════════════
# 7. ANÁLISIS FORENSE — True FCF, Inventario, Deuda, Capital Allocation
#    Todos los valores monetarios se expresan en BILLONES (B) para normalización UI
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def get_true_fcf(ticker: str, yf_cashflow: Optional[Any] = None) -> Dict[str, Any]:
    """
    Calcula el Free Cash Flow verdadero ajustado por Stock-Based Compensation (SBC).
    Usa Yahoo Finance como fallback cuando SEC no puede obtener CapEx (ej: QCOM).

    Fórmula:
        FCF GAAP     = Operating Cash Flow − |CapEx|
        True FCF     = FCF GAAP − |SBC|
        SBC Inflat.% = (SBC / FCF GAAP) × 100

    Args:
        ticker:       Símbolo bursátil
        yf_cashflow:  yf.Ticker(ticker).cashflow (DataFrame transpuesto de yfinance)

    Returns:  dict con todos los valores en BILLONES (B), formato:
        {
            "by_year": {
                2025: {
                    "ocf_b": 14.39,       # Operating Cash Flow
                    "capex_b": -1.192,    # CapEx (negativo = salida)
                    "sbc_b": -2.05,       # Share-Based Comp
                    "fcf_gaap_b": 13.198, # OCF - |CapEx|
                    "true_fcf_b": 11.148, # FCF GAAP - |SBC|
                    "sbc_inflation_pct": 15.5,   # SBC/FCF GAAP %
                    "capex_source": "YF"  # o "SEC"
                }, ...
            },
            "latest_year": 2025,
            "latest_fcf_gaap_b": 13.198,
            "latest_true_fcf_b": 11.148,
            "latest_sbc_b": -2.05,
            "latest_sbc_inflation_pct": 15.5,
            "fcf_yield_true_pct": None,   # Se calcula si se pasa market_cap
            "signal": "Tech inflation: ~16% — typical for semiconductor sector",
            "has_capex_fallback": True     # True si usó YF en lugar de SEC
        }
    """
    result: Dict[str, Any] = {
        "by_year": {},
        "latest_year": None,
        "latest_fcf_gaap_b": None,
        "latest_true_fcf_b": None,
        "latest_sbc_b": None,
        "latest_sbc_inflation_pct": None,
        "fcf_yield_true_pct": None,
        "signal": "",
        "has_capex_fallback": False,
        "error": None,
    }

    try:
        # 1. OCF desde SEC EDGAR
        ocf_df  = _resolve_concept(ticker, "operating_cash_flow", form_filter="10-K")
        capex_df = _resolve_concept(ticker, "capex", form_filter="10-K")
        sbc_df   = _resolve_concept(ticker, "stock_based_comp", form_filter="10-K")

        ocf_map: Dict[int, float]   = _yearly_series(ocf_df,  form="10-K", years=5)  # B
        capex_map: Dict[int, float] = _yearly_series(capex_df, form="10-K", years=5)  # B
        sbc_map: Dict[int, float]   = _yearly_series(sbc_df,   form="10-K", years=5)  # B

        # 2. Fallback CapEx desde YF si SEC no lo tiene
        capex_source = "SEC"
        if not capex_map and yf_cashflow is not None:
            capex_map = _get_yf_metric_all_years(yf_cashflow, "Capital Expenditure")
            if capex_map:
                capex_source = "YF"
                result["has_capex_fallback"] = True

        # 3. Calcular por año fiscal
        common_years = sorted(set(ocf_map) & (set(capex_map) if capex_map else set(ocf_map)), reverse=True)
        for yr in common_years[:5]:
            ocf_b   = ocf_map.get(yr, 0.0)
            capex_b = capex_map.get(yr, 0.0) if capex_map else 0.0
            sbc_b   = sbc_map.get(yr, 0.0)

            fcf_gaap_b = round(ocf_b - abs(capex_b), 4)
            true_fcf_b = round(fcf_gaap_b - abs(sbc_b), 4)
            sbc_inf    = round(abs(sbc_b) / fcf_gaap_b * 100, 1) if fcf_gaap_b > 0 else 0.0

            result["by_year"][yr] = {
                "ocf_b":              round(ocf_b, 4),
                "capex_b":            round(-abs(capex_b), 4),  # siempre negativo
                "sbc_b":              round(-abs(sbc_b), 4),    # siempre negativo
                "fcf_gaap_b":         fcf_gaap_b,
                "true_fcf_b":         true_fcf_b,
                "sbc_inflation_pct":  sbc_inf,
                "capex_source":       capex_source,
            }

        # 4. Últimos valores (año más reciente)
        if result["by_year"]:
            latest_yr = sorted(result["by_year"].keys(), reverse=True)[0]
            latest    = result["by_year"][latest_yr]
            result["latest_year"]              = latest_yr
            result["latest_fcf_gaap_b"]        = latest["fcf_gaap_b"]
            result["latest_true_fcf_b"]        = latest["true_fcf_b"]
            result["latest_sbc_b"]             = latest["sbc_b"]
            result["latest_sbc_inflation_pct"] = latest["sbc_inflation_pct"]

            sbc_pct = latest["sbc_inflation_pct"]
            if sbc_pct >= 20:
                result["signal"] = f"Alta inflación de FCF: SBC representa {sbc_pct:.1f}% — típico tech agresivo"
            elif sbc_pct >= 10:
                result["signal"] = f"Inflación moderada: SBC {sbc_pct:.1f}% del FCF — típico sector semiconductor"
            else:
                result["signal"] = f"FCF conservador: SBC solo {sbc_pct:.1f}% — bajo ajuste requerido"

    except Exception as e:
        result["error"] = str(e)

    return result


@st.cache_data(ttl=3600, show_spinner=False)
def get_inventory_health(ticker: str, yf_balance: Optional[Any] = None) -> Dict[str, Any]:
    """
    Semáforo de salud de inventario granular (Finished Goods / WIP / Raw Materials).
    Calcula la composición y tendencia año-a-año para detectar acumulación.

    Args:
        ticker:     Símbolo bursátil
        yf_balance: yf.Ticker(ticker).balance_sheet (DataFrame de yfinance)

    Returns: dict con valores en BILLONES (B):
        {
            "finished_goods": {"value_b": 2.205, "yoy_pct": -14.5, "signal": "GREEN", "label": "✅ Saludable"},
            "work_in_process": {"value_b": 3.985, "yoy_pct": 14.1, "signal": "YELLOW","label": "⚠️ Vigilar"},
            "raw_materials":   {"value_b": 0.336, "yoy_pct": -1.2, "signal": "GREEN", "label": "✅ OK"},
            "total_b": 6.526,
            "fg_pct_total": 33.8,    # % Finished Goods del total
            "health_score": "SALUDABLE",
            "health_color": "#10b981",
            "alert": "WIP subiendo +14% — posible bottleneck fabril",
            "source": "SEC"  # o "YF"
        }
    """
    def _signal(yoy_pct: Optional[float], inv_type: str) -> tuple:
        """Retorna (signal, label) según tipo y variación YoY."""
        if yoy_pct is None:
            return "GREY", "⚪ Sin datos"
        # Finished goods: bajar es bueno (ventas), subir mucho es malo
        if inv_type == "finished":
            if yoy_pct <= 5:   return "GREEN",  "✅ Saludable"
            if yoy_pct <= 20:  return "YELLOW", "⚠️ Vigilar"
            return "RED", "🔴 Acumulación"
        # WIP y Raw: subir moderado es normal (producción futura)
        if yoy_pct <= 15:  return "GREEN",  "✅ OK"
        if yoy_pct <= 30:  return "YELLOW", "⚠️ Vigilar"
        return "RED", "🔴 Sobrecarga"

    result: Dict[str, Any] = {
        "finished_goods": None, "work_in_process": None, "raw_materials": None,
        "total_b": None, "fg_pct_total": None,
        "health_score": "SIN DATOS", "health_color": "#64748b",
        "alert": "", "source": "SEC", "error": None,
    }

    try:
        # Intentar SEC primero
        fg_df  = _resolve_concept(ticker, "inventory_finished", form_filter="10-K")
        wip_df = _resolve_concept(ticker, "inventory_wip",      form_filter="10-K")
        raw_df = _resolve_concept(ticker, "inventory_raw",      form_filter="10-K")

        def _extract_two_years(df):
            """Retorna (año_actual, valor_B_actual, año_prev, valor_B_prev)."""
            if df is None or df.empty:
                return None, None, None, None
            ser = _yearly_series(df, form="10-K", years=2)
            years_sorted = sorted(ser.keys(), reverse=True)
            if len(years_sorted) >= 2:
                yr0, yr1 = years_sorted[0], years_sorted[1]
                return yr0, ser[yr0], yr1, ser[yr1]
            elif len(years_sorted) == 1:
                yr0 = years_sorted[0]
                return yr0, ser[yr0], None, None
            return None, None, None, None

        # Fallback a YF balance sheet si SEC no tiene los datos
        source = "SEC"
        if (fg_df is None or fg_df.empty) and yf_balance is not None:
            source = "YF"
            # YF usa "Finished Goods", "Work In Process", "Raw Materials"
            fg_map  = _get_yf_metric_all_years(yf_balance, "Finished Goods")
            wip_map = _get_yf_metric_all_years(yf_balance, "Work In Process")
            raw_map = _get_yf_metric_all_years(yf_balance, "Raw Materials")

            def _from_map(m):
                yrs = sorted(m.keys(), reverse=True)
                if len(yrs) >= 2:
                    return yrs[0], m[yrs[0]], yrs[1], m[yrs[1]]
                elif len(yrs) == 1:
                    return yrs[0], m[yrs[0]], None, None
                return None, None, None, None

            fg_yr,  fg_val,  fg_prev_yr,  fg_prev  = _from_map(fg_map)
            wip_yr, wip_val, wip_prev_yr, wip_prev = _from_map(wip_map)
            raw_yr, raw_val, raw_prev_yr, raw_prev = _from_map(raw_map)
        else:
            fg_yr,  fg_val,  fg_prev_yr,  fg_prev  = _extract_two_years(fg_df)
            wip_yr, wip_val, wip_prev_yr, wip_prev = _extract_two_years(wip_df)
            raw_yr, raw_val, raw_prev_yr, raw_prev = _extract_two_years(raw_df)

        result["source"] = source

        def _yoy(curr, prev):
            if curr is None or prev is None or prev == 0:
                return None
            return round((curr - prev) / abs(prev) * 100, 1)

        fg_yoy  = _yoy(fg_val,  fg_prev)
        wip_yoy = _yoy(wip_val, wip_prev)
        raw_yoy = _yoy(raw_val, raw_prev)

        fg_sig,  fg_lbl  = _signal(fg_yoy,  "finished")
        wip_sig, wip_lbl = _signal(wip_yoy, "wip")
        raw_sig, raw_lbl = _signal(raw_yoy, "raw")

        result["finished_goods"]  = {"value_b": fg_val,  "yoy_pct": fg_yoy,  "signal": fg_sig,  "label": fg_lbl,  "year": fg_yr}
        result["work_in_process"] = {"value_b": wip_val, "yoy_pct": wip_yoy, "signal": wip_sig, "label": wip_lbl, "year": wip_yr}
        result["raw_materials"]   = {"value_b": raw_val, "yoy_pct": raw_yoy, "signal": raw_sig, "label": raw_lbl, "year": raw_yr}

        vals = [v for v in [fg_val, wip_val, raw_val] if v is not None]
        if vals:
            total = sum(vals)
            result["total_b"] = round(total, 4)
            result["fg_pct_total"] = round((fg_val or 0) / total * 100, 1) if total > 0 else None

        # Score consolidado
        signals = [fg_sig, wip_sig, raw_sig]
        if "RED" in signals:
            result["health_score"] = "RIESGO DETECTADO"
            result["health_color"] = "#ef4444"
        elif signals.count("YELLOW") >= 2:
            result["health_score"] = "VIGILAR"
            result["health_color"] = "#f59e0b"
        elif "YELLOW" in signals:
            result["health_score"] = "SALUDABLE"
            result["health_color"] = "#10b981"
        else:
            result["health_score"] = "ÓPTIMO"
            result["health_color"] = "#10b981"

        # Alerta automática
        alerts = []
        if wip_yoy and wip_yoy > 10:
            alerts.append(f"WIP ↑ {wip_yoy:+.1f}% — posible bottleneck fabril o pre-build")
        if fg_yoy and fg_yoy > 20:
            alerts.append(f"Finished Goods ↑ {fg_yoy:+.1f}% — riesgo de acumulación de producto terminado")
        if fg_yoy and fg_yoy < -25:
            alerts.append(f"Finished Goods ↓ {fg_yoy:.1f}% — ventas muy fuertes vs inventario")
        result["alert"] = " | ".join(alerts) if alerts else "Supply chain fluye con normalidad"

    except Exception as e:
        result["error"] = str(e)

    return result


@st.cache_data(ttl=3600, show_spinner=False)
def get_debt_maturity_ladder(ticker: str, yf_balance: Optional[Any] = None,
                              yf_info: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Estructura de vencimientos de deuda y perfil de riesgo de refinanciamiento.

    Returns: dict con valores en BILLONES (B):
        {
            "commercial_paper_b": 0.0,   # Vence < 90 días
            "current_debt_1yr_b": 0.0,   # Vence en < 12 meses
            "long_term_debt_b": 14.811,  # Deuda largo plazo
            "total_debt_b": 14.811,
            "cash_b": 5.52,
            "net_debt_b": 9.291,
            "net_debt_ebitda": 0.62,
            "interest_coverage": 18.8,   # EBITDA / Interest Expense
            "refinance_risk": "BAJO",    # BAJO / MEDIO / ALTO
            "refinance_color": "#10b981",
            "next_maturity_note": "Sin vencimientos significativos hasta 2028+",
            "debt_to_equity": 0.64
        }
    """
    result: Dict[str, Any] = {
        "commercial_paper_b": None,
        "current_debt_1yr_b": None,
        "long_term_debt_b": None,
        "total_debt_b": None,
        "cash_b": None,
        "net_debt_b": None,
        "net_debt_ebitda": None,
        "interest_coverage": None,
        "refinance_risk": "DESCONOCIDO",
        "refinance_color": "#64748b",
        "next_maturity_note": "",
        "debt_to_equity": None,
        "error": None,
    }

    try:
        # Extraer conceptos de deuda de SEC
        cp_df  = _resolve_concept(ticker, "commercial_paper",  form_filter="10-K")
        std_df = _resolve_concept(ticker, "current_debt_mature", form_filter="10-K")
        ltd_df = _resolve_concept(ticker, "long_term_debt",    form_filter="10-K")
        cash_df = _resolve_concept(ticker, "cash",             form_filter="10-K")
        int_df  = _resolve_concept(ticker, "interest_expense", form_filter="10-K")
        ocf_df  = _resolve_concept(ticker, "operating_cash_flow", form_filter="10-K")
        eq_df   = _resolve_concept(ticker, "stockholders_equity", form_filter="10-K")

        cp_b   = _to_b(_safe_latest(cp_df))  or 0.0
        std_b  = _to_b(_safe_latest(std_df)) or 0.0
        ltd_b  = _to_b(_safe_latest(ltd_df)) or 0.0
        cash_b = _to_b(_safe_latest(cash_df))
        int_b  = _to_b(_safe_latest(int_df))
        eq_b   = _to_b(_safe_latest(eq_df))

        # Fallback desde yf_info si disponible
        if yf_info:
            if cash_b is None:
                cash_b = round(yf_info.get("totalCash", 0) / _B, 4) or None
            if ltd_b == 0:
                ltd_b = round(yf_info.get("totalDebt", 0) / _B, 4)
            if eq_b is None:
                eq_b = round(yf_info.get("bookValue", 0) * yf_info.get("sharesOutstanding", 0) / _B, 4)

        total_debt_b = round(cp_b + std_b + ltd_b, 4)
        net_debt_b   = round(total_debt_b - (cash_b or 0), 4) if cash_b is not None else None

        # EBITDA aproximado: operating_cash_flow como proxy si no tenemos EBITDA directo
        ebitda_b = None
        if yf_info and yf_info.get("ebitda"):
            ebitda_b = round(yf_info["ebitda"] / _B, 4)

        net_debt_ebitda    = round(net_debt_b / ebitda_b, 2) if (net_debt_b is not None and ebitda_b and ebitda_b > 0) else None
        interest_coverage  = round(ebitda_b / int_b, 1) if (ebitda_b and int_b and int_b > 0) else None
        debt_to_equity     = round(total_debt_b / eq_b, 2) if (eq_b and eq_b > 0) else None

        # Clasificar riesgo de refinanciamiento
        short_term_pct = (cp_b + std_b) / total_debt_b * 100 if total_debt_b > 0 else 0
        if short_term_pct > 30 or (net_debt_ebitda and net_debt_ebitda > 4):
            risk, color = "ALTO",  "#ef4444"
            note = f"Deuda corto plazo = {short_term_pct:.0f}% del total — riesgo de refinanciamiento"
        elif short_term_pct > 15 or (net_debt_ebitda and net_debt_ebitda > 2.5):
            risk, color = "MEDIO", "#f59e0b"
            note = f"Deuda corto plazo = {short_term_pct:.0f}% — monitorear vencimientos"
        else:
            risk, color = "BAJO",  "#10b981"
            note = "Sin vencimientos significativos de corto plazo — balance conservador"

        result.update({
            "commercial_paper_b": round(cp_b, 4),
            "current_debt_1yr_b": round(std_b, 4),
            "long_term_debt_b":   round(ltd_b, 4),
            "total_debt_b":       total_debt_b,
            "cash_b":             cash_b,
            "net_debt_b":         net_debt_b,
            "net_debt_ebitda":    net_debt_ebitda,
            "interest_coverage":  interest_coverage,
            "refinance_risk":     risk,
            "refinance_color":    color,
            "next_maturity_note": note,
            "debt_to_equity":     debt_to_equity,
        })

    except Exception as e:
        result["error"] = str(e)

    return result


@st.cache_data(ttl=3600, show_spinner=False)
def get_capital_allocation(ticker: str, yf_cashflow: Optional[Any] = None,
                            yf_info: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Waterfall completo de capital allocation: cómo usa la empresa su FCF.

    Returns: dict con valores en BILLONES (B):
        {
            "fcf_base_b": 12.82,          # FCF GAAP (base para el waterfall)
            "dividends_b": -2.055,        # Dividendos pagados (negativo)
            "buybacks_b": -8.791,         # Recompras de acciones (negativo)
            "debt_net_b": 0.122,          # Deuda neta emitida/repagada
            "retained_b": 2.052,          # FCF no distribuido
            "shareholder_return_b": 10.846,      # dividends + buybacks (positivo)
            "shareholder_return_pct": 84.6,      # vs FCF base
            "buyback_yield_pct": 6.4,            # buybacks / market_cap * 100
            "dividend_yield_pct": 2.78,          # de yf_info si disponible
            "total_yield_pct": 9.18,             # buyback + dividend yield
            "waterfall_items": [                 # lista para gráfico waterfall
                {"label": "FCF Total",    "value": 12.82,  "type": "absolute"},
                {"label": "Dividendos",   "value": -2.055, "type": "relative"},
                {"label": "Recompras",    "value": -8.791, "type": "relative"},
                {"label": "Deuda neta",   "value": 0.122,  "type": "relative"},
                {"label": "Saldo",        "value": 2.052,  "type": "total"},
            ],
            "insight": "80%+ del FCF retornado al accionista — política muy agresiva"
        }
    """
    result: Dict[str, Any] = {
        "fcf_base_b": None,
        "dividends_b": None,
        "buybacks_b": None,
        "debt_net_b": None,
        "retained_b": None,
        "shareholder_return_b": None,
        "shareholder_return_pct": None,
        "buyback_yield_pct": None,
        "dividend_yield_pct": None,
        "total_yield_pct": None,
        "waterfall_items": [],
        "insight": "",
        "error": None,
    }

    try:
        # 1. FCF base desde SEC/YF
        tf = get_true_fcf(ticker, yf_cashflow=yf_cashflow)
        fcf_b = tf.get("latest_fcf_gaap_b")  # Usamos GAAP (no ajustado por SBC) como base

        # Fallback FCF desde YF info
        if fcf_b is None and yf_info:
            fcf_b = round(yf_info.get("freeCashflow", 0) / _B, 4) or None

        result["fcf_base_b"] = fcf_b

        # 2. Dividendos
        div_df = _resolve_concept(ticker, "dividends_paid", form_filter="10-K")
        div_b  = _to_b(_safe_latest(div_df))
        if div_b is None and yf_cashflow is not None:
            raw = _get_yf_metric(yf_cashflow, "Cash Dividends Paid")
            div_b = _to_b(raw) if raw else None
        if div_b is not None:
            div_b = -abs(div_b)  # siempre negativo (salida)

        # 3. Recompras
        buy_df = _resolve_concept(ticker, "buyback", form_filter="10-K")
        buy_b  = _to_b(_safe_latest(buy_df))
        if buy_b is None and yf_cashflow is not None:
            raw = _get_yf_metric(yf_cashflow, "Repurchase Of Capital Stock")
            buy_b = _to_b(raw) if raw else None
        if buy_b is not None:
            buy_b = -abs(buy_b)  # siempre negativo

        # 4. Deuda neta (emisión - pago): dato de financing CF
        fin_df = _resolve_concept(ticker, "financing_cash_flow", form_filter="10-K")
        fin_b  = _to_b(_safe_latest(fin_df)) or 0.0
        div_safe = div_b or 0.0
        buy_safe = buy_b or 0.0
        # Aproximar deuda neta = financing CF - dividendos - recompras
        debt_net_b = round(fin_b - div_safe - buy_safe, 4)

        # 5. Saldo (FCF no distribuido)
        fcf_safe   = fcf_b or 0.0
        retained_b = round(fcf_safe + div_safe + buy_safe + debt_net_b, 4) if fcf_b else None

        # 6. KPIs de retorno al accionista
        sh_return_b   = round(abs(div_safe) + abs(buy_safe), 4)
        sh_return_pct = round(sh_return_b / fcf_safe * 100, 1) if fcf_safe > 0 else None

        # 7. Yields
        market_cap_b = round(yf_info.get("marketCap", 0) / _B, 4) if yf_info else None
        div_yield    = yf_info.get("dividendYield", 0) * 100 if yf_info else None
        buyback_yield_pct = round(abs(buy_safe) / market_cap_b * 100, 2) if (market_cap_b and market_cap_b > 0) else None
        total_yield_pct   = round((div_yield or 0) + (buyback_yield_pct or 0), 2)

        # 8. Waterfall items
        waterfall = []
        if fcf_b is not None:
            waterfall.append({"label": "FCF Total",  "value": round(fcf_b, 3),     "type": "absolute"})
        if div_b is not None:
            waterfall.append({"label": "Dividendos", "value": round(div_safe, 3),   "type": "relative"})
        if buy_b is not None:
            waterfall.append({"label": "Recompras",  "value": round(buy_safe, 3),   "type": "relative"})
        waterfall.append(    {"label": "Deuda neta", "value": round(debt_net_b, 3), "type": "relative"})
        if retained_b is not None:
            waterfall.append({"label": "Saldo libre","value": round(retained_b, 3), "type": "total"})

        # 9. Insight automático
        if sh_return_pct and sh_return_pct >= 80:
            insight = f"🔥 Retorno agresivo: {sh_return_pct:.0f}% del FCF al accionista — política shareholder-friendly"
        elif sh_return_pct and sh_return_pct >= 50:
            insight = f"✅ Retorno equilibrado: {sh_return_pct:.0f}% del FCF distribuido"
        else:
            insight = f"💰 Capital retenido: {100 - (sh_return_pct or 0):.0f}% del FCF reinvertido en el negocio"

        result.update({
            "dividends_b":            div_b,
            "buybacks_b":             buy_b,
            "debt_net_b":             debt_net_b,
            "retained_b":             retained_b,
            "shareholder_return_b":   sh_return_b,
            "shareholder_return_pct": sh_return_pct,
            "buyback_yield_pct":      buyback_yield_pct,
            "dividend_yield_pct":     div_yield,
            "total_yield_pct":        total_yield_pct,
            "waterfall_items":        waterfall,
            "insight":                insight,
        })

    except Exception as e:
        result["error"] = str(e)

    return result
