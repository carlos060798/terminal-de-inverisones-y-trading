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
    "User-Agent": "QuantumTerminal carlosdaniloangaritagarcia2@gmail.com",
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
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "eps_basic": ["EarningsPerShareBasic"],
    "operating_income": ["OperatingIncomeLoss"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
    ],
    "long_term_debt": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
    ],
    "shares_outstanding": [
        "CommonStockSharesOutstanding",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByOperatingActivities",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
    ],
    "dividends_paid": [
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
    ],
    "total_debt": [
        "LongTermDebt",
        "DebtCurrent",
    ],
    "ebitda": [
        "OperatingIncomeLoss",  # No hay EBITDA directo en US-GAAP, se calcula
    ],
    "current_assets": [
        "AssetsCurrent"
    ],
    "current_liabilities": [
        "LiabilitiesCurrent"
    ],
    "gross_profit": [
        "GrossProfit"
    ]
}


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
    result = {
        "ticker": ticker,
        "source": "SEC EDGAR API (data.sec.gov)",
        "revenue": None,
        "net_income": None,
        "total_assets": None,
        "total_liabilities": None,
        "stockholders_equity": None,
        "eps_diluted": None,
        "operating_income": None,
        "cash": None,
        "long_term_debt": None,
        "shares_outstanding": None,
        "operating_cash_flow": None,
        "capex": None,
        "dividends_paid": None,
        "current_assets": None,
        "current_liabilities": None,
        "gross_profit": None,
        "revenue_history": [],  # Lista de (año, valor) para DCF
        "net_income_history": [],
        "fcf_history": [],
        "error": None,
    }

    try:
        # Obtener info de la empresa
        subs = get_company_submissions(ticker)
        if subs:
            result["company_name"] = subs.get("name", "")
            result["sic_description"] = subs.get("sic_description", "")
            result["fiscal_year_end"] = subs.get("fiscal_year_end", "")

        # Extraer cada métrica
        for field in ["revenue", "net_income", "total_assets", "total_liabilities",
                       "stockholders_equity", "eps_diluted", "operating_income",
                       "cash", "long_term_debt", "shares_outstanding",
                       "operating_cash_flow", "capex", "dividends_paid",
                       "current_assets", "current_liabilities", "gross_profit"]:
            df = _resolve_concept(ticker, field, form_filter="10-K")
            if df is not None and not df.empty:
                # Último valor anual
                latest = df.iloc[0]
                result[field] = float(latest["val"])

                # Histórico para campos clave (últimos 5 años)
                if field in ("revenue", "net_income"):
                    # Deduplicar por año fiscal
                    yearly = df.drop_duplicates(subset=["fy"], keep="first").head(5)
                    history = [(int(r["fy"]), float(r["val"])) for _, r in yearly.iterrows() if pd.notna(r["fy"])]
                    result[f"{field}_history"] = sorted(history, key=lambda x: x[0])

        # Calcular FCF = Operating Cash Flow - CapEx
        ocf_df = _resolve_concept(ticker, "operating_cash_flow", form_filter="10-K")
        capex_df = _resolve_concept(ticker, "capex", form_filter="10-K")
        if ocf_df is not None and capex_df is not None:
            ocf_yearly = ocf_df.drop_duplicates(subset=["fy"], keep="first").set_index("fy")
            capex_yearly = capex_df.drop_duplicates(subset=["fy"], keep="first").set_index("fy")
            common_years = sorted(set(ocf_yearly.index) & set(capex_yearly.index), reverse=True)[:5]
            fcf_hist = []
            for yr in common_years:
                ocf_val = float(ocf_yearly.loc[yr, "val"])
                capex_val = float(capex_yearly.loc[yr, "val"])
                fcf = ocf_val - abs(capex_val)  # CapEx suele venir negativo
                fcf_hist.append((int(yr), fcf))
            result["fcf_history"] = sorted(fcf_hist, key=lambda x: x[0])

    except Exception as e:
        result["error"] = str(e)

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
    Construye un DataFrame con el histórico financiero de los últimos N años.
    Columnas: Year, Revenue, NetIncome, Assets, Equity, EPS, FCF
    Ideal para gráficos de tendencia.
    """
    fields = {
        "Revenue": "revenue",
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
            yearly = df.drop_duplicates(subset=["fy"], keep="first").head(years)
            for _, row in yearly.iterrows():
                yr = row["fy"]
                if pd.notna(yr):
                    yr = int(yr)
                    if yr not in all_data:
                        all_data[yr] = {"Year": yr}
                    all_data[yr][label] = float(row["val"])

    if not all_data:
        return pd.DataFrame()

    result = pd.DataFrame(list(all_data.values()))
    result = result.sort_values("Year", ascending=True)
    return result
