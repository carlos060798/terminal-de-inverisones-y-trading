"""SEC EDGAR — Integración con edgartools para fundamentales directos (10-K/10-Q)"""
import pandas as pd
from edgar import Company, set_identity
from adapters.base import BaseDataAdapter, DataResult, ProviderConfig
from adapters.registry import register

# SEC requires an identity string (User-Agent) for all requests
set_identity("QuantumTerminal User (admin@quantumterminal.ai)")

@register
class SecEdgarAdapter(BaseDataAdapter):
    config = ProviderConfig(
        provider_id="sec_edgar", category="stocks",
        credential_key="",
        rate_limit_rpm=10, ttl_seconds=86400, priority="medium", # TTL alto para fundamentales
    )

    def _fetch_raw(self, ticker: str = "AAPL", form_type: str = "10-K", year: int = None, **kwargs):
        """Fetch real financial statements using edgartools."""
        try:
            company = Company(ticker)
            filings = company.get_filings(form=form_type)
            
            if not filings:
                return None
                
            latest_filing = filings.latest()
            financials = latest_filing.obj()
            
            # Extract metrics from financials
            data = {
                "ticker": ticker,
                "form": form_type,
                "filed_at": latest_filing.filing_date,
                "accession_number": latest_filing.accession_number,
                "revenue": 0.0,
                "net_income": 0.0,
                "total_assets": 0.0,
                "total_liabilities": 0.0,
                "total_equity": 0.0,
                "eps": 0.0,
                "dividend_paid": 0.0,
                "operating_cash_flow": 0.0,
                "shares_outstanding": 0,
            }
            
            if financials:
                try:
                    # Extracts text for RAG (Item 1A, Item 7, etc or full)
                    # latest_filing has a .html() and .text() method
                    data["full_text"] = latest_filing.text()

                    # In edgartools v2.x, financials are accessed via financial_statements
                    # balance_sheet, income_statement, etc are dataframes themselves or have .to_pandas()
                    bs = financials.balance_sheet
                    is_ = financials.income_statement
                    cf = financials.cash_flow
                    
                    if bs is not None:
                        df_bs = bs.to_pandas() if hasattr(bs, "to_pandas") else bs
                        data["balance_sheet_raw"] = df_bs
                        # Simple extraction logic (heuristic)
                        for idx, row in df_bs.iterrows():
                            lbl = str(idx).lower()
                            val = row.iloc[0] if len(row) > 0 else 0
                            if "total assets" in lbl: data["total_assets"] = val
                            if "total liabilities" in lbl: data["total_liabilities"] = val
                            if "total stockholders' equity" in lbl: data["total_equity"] = val

                    if is_ is not None:
                        df_is = is_.to_pandas() if hasattr(is_, "to_pandas") else is_
                        data["income_statement_raw"] = df_is
                        for idx, row in df_is.iterrows():
                            lbl = str(idx).lower()
                            val = row.iloc[0] if len(row) > 0 else 0
                            if "revenue" in lbl or "sales" in lbl: data["revenue"] = val
                            if "net income" in lbl: data["net_income"] = val
                            if "earnings per share" in lbl and "diluted" in lbl: data["eps"] = val

                    if cf is not None:
                        df_cf = cf.to_pandas() if hasattr(cf, "to_pandas") else cf
                        data["cash_flow_raw"] = df_cf
                        for idx, row in df_cf.iterrows():
                            lbl = str(idx).lower()
                            val = row.iloc[0] if len(row) > 0 else 0
                            if "operating activities" in lbl and "net cash" in lbl: data["operating_cash_flow"] = val

                except Exception as e:
                    data["extraction_error"] = str(e)
            
            return data
        except Exception as e:
            print(f"Error fetching SEC data for {ticker}: {e}")
            return None

    def _normalize(self, raw) -> DataResult:
        if raw is None:
            return self._empty_result("No filings found")
            
        return DataResult(
            provider_id="sec_edgar", 
            category="stocks",
            fetched_at="", 
            latency_ms=0, 
            success=True, 
            data=raw,
        )
