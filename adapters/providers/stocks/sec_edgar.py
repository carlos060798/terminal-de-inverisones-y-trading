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
        company = Company(ticker)
        filings = company.get_filings(form=form_type)
        
        if not filings:
            return None
            
        latest_filing = filings.latest()
        # In edgartools, .obj() on a filing returns the Financials object for XBRL filings
        financials = latest_filing.obj()
        
        # Extract sheets if available
        data = {
            "ticker": ticker,
            "form": form_type,
            "filed_at": latest_filing.filing_date,
            "accession_number": latest_filing.accession_number,
        }
        
        try:
            # We try to get the balance sheet and income statement
            if financials:
                # edgartools Financials object attributes
                balance_sheet = financials.balance_sheet
                income_statement = financials.income_statement
                cash_flow = financials.cash_flow
                
                if balance_sheet is not None:
                    data["balance_sheet"] = balance_sheet.to_dataframe()
                if income_statement is not None:
                    data["income_statement"] = income_statement.to_dataframe()
                if cash_flow is not None:
                    data["cash_flow"] = cash_flow.to_dataframe()
        except Exception as e:
            data["error_extracting_financials"] = str(e)
            
        return data

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
