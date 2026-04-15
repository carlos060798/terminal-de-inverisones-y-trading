"""
pdf_parser.py — Intelligent PDF parser for InvestingPro reports
Extracts structured financial data using PyMuPDF text extraction + pattern matching.
Falls back to legacy regex for non-InvestingPro PDFs.
"""
import re
import json
import io

# Try PyMuPDF first (much cleaner text), fall back to pdfplumber
try:
    import fitz as _fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

import pdfplumber


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_number(text):
    """Parse a string like '$133.1B', '20.4', '-21.8%', '(1,234)' into a float."""
    if not text or text.strip() in ("", "-", "N/A", "—", "n/a"):
        return None
    s = text.strip().replace(",", "").replace("\u2011", "-").replace("−", "-")
    # Parenthetical negatives
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    # Remove currency symbols
    s = s.replace("$", "").replace("€", "").replace("£", "")
    # Handle suffixes
    multiplier = 1.0
    pct = False
    if s.endswith("%"):
        s = s[:-1]
        pct = True
    elif s.upper().endswith("T"):
        s = s[:-1]; multiplier = 1e12
    elif s.upper().endswith("B"):
        s = s[:-1]; multiplier = 1e9
    elif s.upper().endswith("M"):
        s = s[:-1]; multiplier = 1e6
    elif s.upper().endswith("K"):
        s = s[:-1]; multiplier = 1e3
    elif s.endswith("x"):
        s = s[:-1]
    try:
        val = float(s) * multiplier
        return val
    except (ValueError, TypeError):
        return None


def _extract_text_pages(file_bytes):
    """Extract text per page using best available library."""
    pages = []
    if HAS_FITZ:
        doc = _fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            pages.append(page.get_text() or "")
        doc.close()
    else:
        pdf = pdfplumber.open(io.BytesIO(file_bytes))
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
        pdf.close()
    return pages


def _classify_page(text):
    """Classify a page by its content fingerprint."""
    t = text[:400].lower().replace("\xa0", " ")
    if "key indicators" in t:
        return "key_indicators"
    if "valuation" in t and "reporting date" in t:
        return "valuation"
    if "analyst" in t and ("eps forecast" in t or "latest ratings" in t):
        return "analyst"
    if re.search(r"q[1-4]\s*financials", t):
        return "financials_quarterly"
    if "ltm financials" in t or ("income statement" in t and "balance sheet" in t):
        return "financials_annual"
    if "momentum" in t or "technical" in t:
        return "momentum"
    if "peer benchmark" in t:
        return "peers"
    if "swot" in t:
        return "swot"
    if "latest insights" in t or ("bull case" in t and "bear case" in t):
        return "insights"
    if "earnings call" in t:
        return "earnings_call"
    if "top news" in t:
        return "news"
    return "unknown"


# ── Page Parsers ─────────────────────────────────────────────────────────────

def _parse_key_indicators(text):
    """Parse page 1: key indicators + executive summary."""
    result = {}
    lines = text.split("\n")

    # Extract ticker and exchange from first line
    m = re.match(r"(.+?)\s*\((\w+):(\w+)\)", lines[0] if lines else "")
    if m:
        result["company_name"] = m.group(1).strip()
        result["exchange"] = m.group(2)
        result["ticker"] = m.group(3)

    # Only parse key-value pairs before "Executive Summary" or "5-Year Chart"
    cutoff = len(lines)
    for i, line in enumerate(lines):
        if "Executive Summary" in line or "5-Year Chart" in line:
            cutoff = i
            break

    # Key-value pairs: label on one line, value on next
    kv_map = {
        "Stock Price": "price",
        "52\u2011Week Range": "week_52_range",
        "52-Week Range": "week_52_range",
        "Market Cap": "market_cap",
        "P/E Ratio": "pe_ratio",
        "P/E (Fwd.)": "pe_fwd",
        "EPS Actual": "eps_actual",
        "EPS Estimate": "eps_estimate",
        "PEG Ratio": "peg_ratio",
        "FCF Yield": "fcf_yield",
        "EV / EBITDA": "ev_ebitda",
        "Book / Share": "book_per_share",
        "Beta (5Y)": "beta",
        "Revenue": "revenue",
        "Revenue Forecast": "revenue_forecast",
        "1-Year Change": "one_year_change",
        "Div Yield": "div_yield",
        "Div. Growth Streak": "div_growth_streak",
        "Next Earnings": "next_earnings",
    }

    # Process Revenue Forecast BEFORE Revenue to avoid overwriting
    # (iterate in order; "Revenue Forecast" is longer so check it first)
    matched_lines = set()
    for i in range(cutoff):
        stripped = lines[i].strip()
        if i in matched_lines:
            continue
        # Check longer labels first
        for label in sorted(kv_map.keys(), key=len, reverse=True):
            if stripped == label and i + 1 < len(lines):
                key = kv_map[label]
                raw_val = lines[i + 1].strip()
                if key in ("week_52_range", "next_earnings", "div_growth_streak"):
                    result[key] = raw_val
                else:
                    result[key] = _parse_number(raw_val)
                matched_lines.add(i)
                matched_lines.add(i + 1)
                break

    # Date
    date_m = re.search(r"Date:\s*(\w+\s+\d+,\s*\d{4})", text)
    if date_m:
        result["date"] = date_m.group(1)

    # EPS Revisions
    rev_m = re.search(r"EPS Revisions.*?\n↑\s*(\d+)\s*↓\s*(\d+)", text)
    if rev_m:
        result["eps_revisions_up"] = int(rev_m.group(1))
        result["eps_revisions_down"] = int(rev_m.group(2))

    # Executive Summary
    es_start = text.find("Executive Summary")
    if es_start >= 0:
        # Stop at chart/noise sections
        es_text = text[es_start + len("Executive Summary"):]
        for stop in ["Revenue\nEPS", "page ", "Analyst High"]:
            pos = es_text.find(stop)
            if pos > 0:
                es_text = es_text[:pos]
        result["executive_summary"] = es_text.strip()

    return result


def _parse_valuation(text):
    """Parse page 2: valuation multiples table + pro tips.

    Format: same label/values pattern as financials:
        Reporting Date
        2023
        2024
        ...
        Capitalization
        $143.3B
        $181.0B
        ...
    """
    result = {"multiples": {}, "pro_tips": []}
    # Normalize non-breaking spaces
    text = text.replace("\xa0", " ")
    lines = [l.strip() for l in text.split("\n")]

    metrics_map = {
        "Capitalization": "capitalization",
        "P/E Ratio": "pe_ratio",
        "Div. Yield": "div_yield",
        "Capitalization / Revenue": "cap_revenue",
        "EV / Revenue": "ev_revenue",
        "EV / EBITDA": "ev_ebitda",
        "EV / FCF": "ev_fcf",
        "FCF Yield": "fcf_yield",
        "Price / Book": "price_book",
    }

    # Find years after "Reporting Date"
    years = []
    i = 0
    while i < len(lines):
        if lines[i] == "Reporting Date":
            j = i + 1
            while j < len(lines):
                if re.match(r"^\d{4}$", lines[j]):
                    years.append(lines[j])
                    j += 1
                else:
                    break
            i = j
            break
        i += 1

    num_years = len(years)

    # Skip "Period Ending" row + its values
    if i < len(lines) and lines[i] == "Period Ending":
        i += 1 + num_years

    # Parse metric rows
    while i < len(lines):
        line = lines[i]
        if line == "Pro Tips":
            break
        if line in metrics_map:
            vals = []
            j = i + 1
            while len(vals) < num_years and j < len(lines):
                v = _parse_number(lines[j])
                if v is not None or lines[j] == "-":
                    vals.append(v)
                    j += 1
                else:
                    break
            if vals:
                result["multiples"][metrics_map[line]] = dict(zip(years[:len(vals)], vals))
            i = j
            continue
        i += 1

    # Pro Tips: combine wrapped lines
    tips_start = text.find("Pro Tips")
    if tips_start >= 0:
        tips_text = text[tips_start + len("Pro Tips"):]
        # Remove meta description line
        tips_text = re.sub(r"Tips that distill.*?\.\n", "", tips_text)
        page_end = tips_text.find("page ")
        if page_end > 0:
            tips_text = tips_text[:page_end]

        # Join wrapped lines into complete tips
        current_tip = ""
        for line in tips_text.split("\n"):
            line = line.strip()
            if not line:
                if current_tip:
                    result["pro_tips"].append(current_tip)
                    current_tip = ""
                continue
            if line[0].isupper() and current_tip:
                result["pro_tips"].append(current_tip)
                current_tip = line
            elif current_tip:
                current_tip += " " + line
            else:
                current_tip = line
        if current_tip:
            result["pro_tips"].append(current_tip)

    return result


def _parse_analyst(text):
    """Parse page 3: EPS forecasts + analyst ratings."""
    result = {"eps_forecasts": [], "ratings": []}
    lines = text.split("\n")

    # EPS Forecasts table
    in_eps = False
    for i, line in enumerate(lines):
        if "Analyst EPS Forecasts" in line:
            in_eps = True
            continue
        if in_eps and "Latest Ratings" in line:
            in_eps = False
        if in_eps:
            # Look for year rows: "2024  23.54  15.1%  20.4x  34"
            m = re.match(r"\s*(\d{4})\s*$", line.strip())
            if m:
                year = m.group(1)
                # Collect next values
                vals = []
                for j in range(1, 5):
                    if i + j < len(lines):
                        vals.append(lines[i + j].strip())
                if len(vals) >= 4:
                    result["eps_forecasts"].append({
                        "year": int(year),
                        "eps_avg": _parse_number(vals[0]),
                        "yoy_growth": vals[1],
                        "fwd_pe": vals[2],
                        "num_analysts": _parse_number(vals[3]),
                    })

    # Analyst Ratings
    rating_pattern = re.compile(
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s*(?:\d{4}|\d{2}))\s+"
        r"(.+?)\s+(Buy|Hold|Sell|Strong Buy|Strong Sell|Outperform|Underperform|Neutral|Overweight|Underweight)\s+"
        r"(\$[\d,.]+|N/A)"
    )
    for line in lines:
        m = rating_pattern.search(line)
        if m:
            result["ratings"].append({
                "date": m.group(1),
                "analyst": m.group(2).strip(),
                "rating": m.group(3),
                "target": m.group(4),
            })

    # Also try line-by-line for multi-line ratings
    if not result["ratings"]:
        i = 0
        while i < len(lines):
            date_m = re.match(r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s*\d{2})", lines[i].strip())
            if date_m and i + 3 < len(lines):
                result["ratings"].append({
                    "date": date_m.group(1),
                    "analyst": lines[i + 1].strip(),
                    "rating": lines[i + 2].strip(),
                    "target": lines[i + 3].strip(),
                })
                i += 4
                continue
            i += 1

    return result


def _parse_financials(text):
    """Parse pages 4-5: financial statements (Income, Balance, Cash Flow).

    The PDF text format is:
        Income Statement
        Date
        2022
        2023
        ...
        Revenue
        12,726
        14,368
        ...
        Operating        <- multi-line label
        Income
        2,634
        ...
    """
    result = {"income": {}, "balance": {}, "cashflow": {}, "segments": {}}
    lines = [l.strip() for l in text.split("\n")]

    statement_map = {
        "Income Statement": "income",
        "Balance Sheet": "balance",
        "Cash Flow Statement": "cashflow",
    }

    # Multi-line label definitions: first_line -> (second_line, canonical_key)
    multiline_labels = {
        "Operating": ("Income", "operating_income"),
        "Net Income to": ("Stockholders", "net_income_to_stockholders"),
        "Shares": ("Outstanding", "shares_outstanding"),
        "Total Current": None,  # context-dependent
        "Total": None,  # context-dependent
        "Cash from": None,  # context-dependent
        "Levered Free": ("Cash Flow", "levered_free_cash_flow"),
    }

    # Single-line labels
    single_labels = {
        "Revenue": "revenue",
        "Diluted EPS": "diluted_eps",
        "EBITDA": "ebitda",
        "Total Assets": "total_assets",
        "Total Equity": "total_equity",
        "Total Debt": "total_debt",
    }

    current_statement = None
    years = []
    num_years = 0

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect statement header
        if line in statement_map:
            current_statement = statement_map[line]
            i += 1
            continue

        # Detect "Date" row followed by year labels
        if line == "Date" and current_statement:
            years = []
            j = i + 1
            while j < len(lines) and len(years) < 10:
                yr = lines[j].replace("\xa0", " ")
                if re.match(r"^\d{4}$", yr) or yr in ("LTM", "TTM"):
                    years.append(yr)
                    j += 1
                elif re.match(r"^Q\d\s+\d{4}$", yr):
                    years.append(yr)
                    j += 1
                else:
                    break
            num_years = len(years)
            i = j
            continue

        if not current_statement or not years:
            i += 1
            continue

        # Stop parsing at chart/footnote section
        if line.startswith("*In USD") or line.startswith("* Revenue segments"):
            current_statement = None
            i += 1
            continue

        # Try to identify a row label and collect its values
        label_key = None
        data_start = i + 1

        # Check single-line labels
        if line in single_labels:
            label_key = single_labels[line]

        # Check multi-line labels
        elif line in multiline_labels and i + 1 < len(lines):
            spec = multiline_labels[line]
            next_line = lines[i + 1]
            if spec is not None:
                expected_second, key = spec
                if next_line == expected_second:
                    label_key = key
                    data_start = i + 2
            else:
                # Context-dependent multi-line labels
                if line == "Total Current" and next_line == "Assets":
                    label_key = "total_current_assets"
                    data_start = i + 2
                elif line == "Total Current" and next_line == "Liabilities":
                    label_key = "total_current_liabilities"
                    data_start = i + 2
                elif line == "Total" and next_line == "Liabilities":
                    label_key = "total_liabilities"
                    data_start = i + 2
                elif line == "Cash from" and next_line == "Operations":
                    label_key = "cash_from_operations"
                    data_start = i + 2
                elif line == "Cash from" and next_line == "Investing":
                    label_key = "cash_from_investing"
                    data_start = i + 2
                elif line == "Cash from" and next_line == "Financing":
                    label_key = "cash_from_financing"
                    data_start = i + 2

        if label_key:
            # Collect exactly num_years values
            vals = []
            j = data_start
            while len(vals) < num_years and j < len(lines):
                v = _parse_number(lines[j])
                if v is not None or re.match(r"^-?[\d,.]+\.?\d*$", lines[j]):
                    vals.append(v if v is not None else 0.0)
                    j += 1
                else:
                    break
            if vals:
                result[current_statement][label_key] = dict(zip(years[:len(vals)], vals))
            i = j
            continue

        # Segments: look for pattern like "Consumer Segment\n$6.2B" in the chart section
        if not current_statement:
            seg_m = re.search(r"^(.+?(?:Segment|Solut\.|Inc)\.?)\s*$", line)
            if seg_m and i + 1 < len(lines):
                next_val = lines[i + 1]
                val = _parse_number(next_val)
                if val and val > 1e6:
                    seg_name = seg_m.group(1).strip()
                    if seg_name not in result["segments"]:
                        result["segments"][seg_name] = val

        i += 1

    return result


def _parse_momentum_peers(text):
    """Parse page 6: momentum indicators + peer benchmarks."""
    result = {"momentum": {}, "technical_summary": "", "peer_benchmarks": {}}
    lines = text.split("\n")

    # Technical Summary
    for phrase in ("Strong Buy", "Buy", "Strong Sell", "Sell", "Neutral"):
        if f"Technical Summary\n{phrase}" in text or f"Technical Summary {phrase}" in text:
            result["technical_summary"] = phrase
            break
    if not result["technical_summary"]:
        for i, line in enumerate(lines):
            if line.strip() == "Technical Summary" and i + 1 < len(lines):
                result["technical_summary"] = lines[i + 1].strip()
                break

    # Peer benchmarks tables
    peer_tickers = []
    current_section = None
    section_metrics = {}

    for i, line in enumerate(lines):
        stripped = line.strip()
        if "Peer Benchmarks" in stripped:
            continue
        if stripped in ("Market and Yield Metrics", "Growth Metrics", "Financial Statement Metrics"):
            current_section = stripped
            section_metrics[current_section] = {}
            continue
        if stripped == "Metric" and i + 1 < len(lines):
            # Header row with ticker names
            header_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            # Tickers follow on same or next lines
            tkrs = re.findall(r"\b([A-Z]{2,5})\b", stripped + " " + header_line)
            if tkrs:
                peer_tickers = tkrs

    result["peer_tickers"] = peer_tickers
    return result


def _parse_swot(text):
    """Parse SWOT page: 4 quadrants of bullet points.

    InvestingPro SWOT layout: content appears BEFORE its label.
    Text flows as:
        [strengths content...]
        Strengths
        [weaknesses content...]
        Weaknesses
        [opportunities content...]
        Opportunities
        [threats content...]
        Threats
        page X/Y
    """
    result = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}
    labels = ["Strengths", "Weaknesses", "Opportunities", "Threats"]

    # Find positions of each label
    positions = {}
    for label in labels:
        pos = text.find(label + "\n")
        if pos < 0:
            pos = text.find(label + "\r")
        if pos < 0:
            # Try exact line match
            for i, line in enumerate(text.split("\n")):
                if line.strip() == label:
                    pos = text.find(line)
                    break
        if pos >= 0:
            positions[label] = pos

    if not positions:
        return result

    # Build ordered list of (label, position)
    ordered = sorted(positions.items(), key=lambda x: x[1])

    # Content BEFORE "Strengths" label = strengths content
    # Content between "Strengths" and "Weaknesses" labels = weaknesses content
    # Content between "Weaknesses" and "Opportunities" = opportunities content
    # Content between "Opportunities" and "Threats" = threats content

    # Find start of content (after "SWOT Analysis" header)
    content_start = text.find("SWOT Analysis")
    if content_start >= 0:
        content_start += len("SWOT Analysis")
    else:
        content_start = 0

    mapping = list(zip(labels, ["strengths", "weaknesses", "opportunities", "threats"]))

    for idx, (label, key) in enumerate(mapping):
        if label not in positions:
            continue

        # Content is usually BEFORE the label in some InvestPro versions, 
        # or grouped by sections. We will try a hybrid "nearest anchor" search.
        if idx == 0:
            chunk_start = content_start
        else:
            prev_label = mapping[idx - 1][0]
            chunk_start = positions.get(prev_label, content_start) + len(prev_label)

        chunk_end = positions[label]
        
        # If the label is at the start of its content block (normal) vs at the end ( InvestPro weirdness)
        # We check both regions.
        inner_text = text[chunk_start:chunk_end].strip()
        
        # Split into bullets
        for p in re.split(r"(?:\.\n|\n\u2022|\n-|\n\*)", inner_text):
            p = p.strip().replace("\n", " ")
            if len(p) > 15:
                # Add punctuation if missing
                if p[-1] not in ".!?": p += "."
                result[key].append(p)

    # Threats: content is between "Opportunities" label and "Threats" label
    # But we also need content AFTER "Threats" label until "page"
    if "Threats" in positions:
        after_threats = text[positions["Threats"] + len("Threats"):].strip()
        page_m = re.search(r"page \d+/\d+", after_threats)
        if page_m:
            after_threats = after_threats[:page_m.start()].strip()
        if after_threats:
            for p in re.split(r"\.\n(?=[A-Z])", after_threats):
                p = p.strip().replace("\n", " ")
                if not p.endswith("."):
                    p += "."
                if len(p) > 20:
                    result["threats"].append(p)

    return result


def _parse_insights(text):
    """Parse insights page: bull/bear/additional."""
    result = {"bull_case": [], "bear_case": [], "latest_insights": []}

    # Split by Bull Case / Bear Case
    for section, key in [("Bull Case", "bull_case"), ("Bear Case", "bear_case"),
                         ("Additional Insights", "latest_insights")]:
        start = text.find(section)
        if start < 0:
            continue
        chunk = text[start + len(section):]
        # Find next section
        for next_sec in ["Bull Case", "Bear Case", "Additional Insights", "page "]:
            if next_sec == section:
                continue
            pos = chunk.find(next_sec)
            if pos > 0:
                chunk = chunk[:pos]
                break
        # Split into paragraphs
        for line in chunk.split("\n"):
            line = line.strip()
            if len(line) > 20:
                result[key].append(line)

    # Also extract latest insights bullets from the main text before bull/bear
    insights_start = text.find("Latest Insights")
    bull_start = text.find("Bull Case")
    if insights_start >= 0 and bull_start > insights_start:
        chunk = text[insights_start + len("Latest Insights"):bull_start]
        for line in chunk.split("\n"):
            line = line.strip()
            if len(line) > 30:
                result["latest_insights"].append(line)

    return result


def _parse_earnings_call(text):
    """Parse earnings call summary page."""
    result = {"bullets": [], "date": None}
    # Date
    date_m = re.search(r"(\d{2}/\d{2}/\d{2})", text)
    if date_m:
        result["date"] = date_m.group(1)
    # Bullet points
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if len(line) > 40 and not line.startswith("Intuit") and "Pro Research" not in line:
            result["bullets"].append(line)
    return result


# ── Main Parser ──────────────────────────────────────────────────────────────

def parse_investingpro_pdf(file_bytes):
    """
    Parse an InvestingPro Pro Research PDF report.
    Returns a structured dict with all extracted data.
    """
    pages = _extract_text_pages(file_bytes)
    result = {
        "source": "investingpro",
        "pages_count": len(pages),
        "key_indicators": {},
        "valuation": {},
        "analyst": {},
        "financials_annual": {},
        "financials_quarterly": {},
        "momentum": {},
        "peers": {},
        "swot": {},
        "insights": {},
        "earnings_call": {},
        "pro_tips": [],
        "executive_summary": "",
    }

    for i, page_text in enumerate(pages):
        page_type = _classify_page(page_text)

        if page_type == "key_indicators":
            ki = _parse_key_indicators(page_text)
            result["key_indicators"] = ki
            result["executive_summary"] = ki.pop("executive_summary", "")
        elif page_type == "valuation":
            val = _parse_valuation(page_text)
            if not result.get("valuation"):
                result["valuation"] = val.get("multiples", {})
            if not result.get("pro_tips"):
                result["pro_tips"] = val.get("pro_tips", [])
        elif page_type == "analyst":
            result["analyst"] = _parse_analyst(page_text)
        elif page_type == "financials_annual":
            result["financials_annual"] = _parse_financials(page_text)
        elif page_type == "financials_quarterly":
            result["financials_quarterly"] = _parse_financials(page_text)
        elif page_type == "momentum":
            result["momentum"] = _parse_momentum_peers(page_text)
            # Also check this page for peer data
            if "Peer Benchmarks" in page_text:
                result["peers"] = _parse_momentum_peers(page_text).get("peer_benchmarks", {})
                result["peers"]["tickers"] = _parse_momentum_peers(page_text).get("peer_tickers", [])
        elif page_type == "swot":
            result["swot"] = _parse_swot(page_text)
        elif page_type == "insights":
            result["insights"] = _parse_insights(page_text)
        elif page_type == "earnings_call":
            result["earnings_call"] = _parse_earnings_call(page_text)

    return result


def is_investingpro_pdf(file_bytes):
    """Check if a PDF is an InvestingPro report."""
    pages = _extract_text_pages(file_bytes)
    if not pages:
        return False
    first_page = pages[0][:500].lower()
    return "pro research" in first_page and "key indicators" in first_page


def parse_financial_pdf(file_bytes):
    """
    Universal entry point. Tries InvestingPro format first,
    falls back to legacy regex extraction.
    """
    if is_investingpro_pdf(file_bytes):
        return parse_investingpro_pdf(file_bytes)

    # Legacy fallback: use pdfplumber text + regex (same as original extract_metrics)
    return _legacy_parse(file_bytes)


def _legacy_parse(file_bytes):
    """Legacy regex-based parser for generic financial PDFs."""
    full_text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"

    r = {k: None for k in ["revenue", "net_income", "total_debt", "total_equity",
                            "profit_margin", "revenue_growth", "pe_ratio", "roe", "current_ratio"]}
    t = full_text.replace(",", "").lower()
    raw_lines = t.split("\n")

    def find(patterns, mult=1.0):
        for pat in patterns:
            for line in raw_lines:
                m = re.search(pat, line)
                if m:
                    try:
                        return float(m.group(1)) * mult
                    except (ValueError, TypeError):
                        pass
        return None

    r["revenue"] = find([r"revenue\D{0,20}?([\d]+\.?\d*)\s*b(?:illion)?",
                         r"revenue\D{0,20}?([\d]+\.?\d*)\s*t(?:rillion)?"], 1e9)
    if not r["revenue"]:
        for line in raw_lines:
            if "revenue" in line:
                nums = re.findall(r"([\d]+\.?\d*)\s*b", line)
                if nums:
                    r["revenue"] = float(nums[0]) * 1e9
                    break

    r["net_income"] = find([r"net\s+income\D{0,20}?([\d]+\.?\d*)\s*b",
                            r"net\s+profit\D{0,20}?([\d]+\.?\d*)\s*b"], 1e9)
    r["profit_margin"] = find([r"(?:profit|net)\s+margin\D{0,10}?([\d]+\.?\d*)\s*%",
                               r"margin\s*[:\s]\s*([\d]+\.?\d*)\s*%"])
    if not r["profit_margin"] and r["revenue"] and r["net_income"] and r["revenue"] > 0:
        r["profit_margin"] = r["net_income"] / r["revenue"] * 100
    r["revenue_growth"] = find([r"revenue\s+(?:growth|grew)\D{0,20}?([\d]+\.?\d*)\s*%",
                                r"yoy\D{0,20}?([\d]+\.?\d*)\s*%"])
    r["pe_ratio"] = find([r"p\s*/\s*e\s+ratio\D{0,10}?([\d]+\.?\d*)",
                          r"p/e\s*[:\s]\s*([\d]+\.?\d*)"])
    r["roe"] = find([r"roe\D{0,10}?([\d]+\.?\d*)\s*%?",
                     r"return\s+on\s+equity\D{0,10}?([\d]+\.?\d*)"])
    r["current_ratio"] = find([r"current\s+ratio\D{0,10}?([\d]+\.?\d*)"])
    r["total_debt"] = find([r"total\s+debt\D{0,10}?([\d]+\.?\d*)\s*b"], 1e9)
    r["total_equity"] = find([r"(?:total\s+equity|stockholders)\D{0,10}?([\d]+\.?\d*)\s*b"], 1e9)

    return {
        "source": "generic",
        "key_indicators": r,
        "raw_text": full_text,
    }


def flatten_for_db(parsed):
    """
    Flatten parsed data into a flat dict suitable for database storage.
    Keeps the most important metrics at top level.
    """
    ki = parsed.get("key_indicators", {})
    fin = parsed.get("financials_annual", {})
    income = fin.get("income", {})
    balance = fin.get("balance", {})

    def _to_usd(val):
        """Convert from millions (PDF footnote says 'In USD millions') to actual USD."""
        return val * 1e6 if val is not None else None

    # Get most recent values from financial statements
    def latest(data_dict):
        if not data_dict:
            return None
        # Prefer LTM/TTM as most recent
        if "LTM" in data_dict and data_dict["LTM"] is not None:
            return data_dict["LTM"]
        if "TTM" in data_dict and data_dict["TTM"] is not None:
            return data_dict["TTM"]
        # Otherwise get the highest year
        year_keys = sorted([k for k in data_dict if re.match(r"^\d{4}$", k)])
        return data_dict.get(year_keys[-1]) if year_keys else None

    def second_latest(data_dict):
        """Get second most recent year value for growth calculations."""
        if not data_dict:
            return None
        year_keys = sorted([k for k in data_dict if re.match(r"^\d{4}$", k)])
        if len(year_keys) >= 2:
            return data_dict[year_keys[-2]]
        return None

    flat = {
        "ticker": ki.get("ticker", ""),
        "company_name": ki.get("company_name", ""),
        "price": ki.get("price"),
        "market_cap": ki.get("market_cap"),
        "pe_ratio": ki.get("pe_ratio"),
        "pe_fwd": ki.get("pe_fwd"),
        "eps_actual": ki.get("eps_actual"),
        "eps_estimate": ki.get("eps_estimate"),
        "peg_ratio": ki.get("peg_ratio"),
        "fcf_yield": ki.get("fcf_yield"),
        "ev_ebitda": ki.get("ev_ebitda"),
        "book_per_share": ki.get("book_per_share"),
        "beta": ki.get("beta"),
        # Financial statement values are in USD millions per footnote
        "revenue": ki.get("revenue") or (_to_usd(latest(income.get("revenue")))),
        "net_income": _to_usd(latest(income.get("net_income_to_stockholders"))),
        "total_debt": _to_usd(latest(balance.get("total_debt"))),
        "total_equity": _to_usd(latest(balance.get("total_equity"))),
        "div_yield": ki.get("div_yield"),
        "one_year_change": ki.get("one_year_change"),
        "revenue_forecast": ki.get("revenue_forecast"),
        # Computed
        "profit_margin": None,
        "revenue_growth": None,
        "roe": None,
        "current_ratio": None,
        "debt_equity": None,
    }

    # Compute derived metrics if we have financials
    rev = income.get("revenue", {})
    rev_curr = latest(rev)
    rev_prev = second_latest(rev)
    if rev_curr and rev_prev and rev_prev > 0:
        flat["revenue_growth"] = (rev_curr - rev_prev) / rev_prev * 100

    net_inc = latest(income.get("net_income_to_stockholders"))
    rev_latest = latest(income.get("revenue"))
    if net_inc and rev_latest and rev_latest > 0:
        flat["profit_margin"] = net_inc / rev_latest * 100

    eq = latest(balance.get("total_equity"))
    if net_inc and eq and eq > 0:
        flat["roe"] = net_inc / eq * 100

    ca = latest(balance.get("total_current_assets"))
    cl = latest(balance.get("total_current_liabilities"))
    if ca and cl and cl > 0:
        flat["current_ratio"] = ca / cl

    debt = latest(balance.get("total_debt"))
    if debt and eq and eq > 0:
        flat["debt_equity"] = debt / eq

    # Store full parsed data as JSON
    flat["raw_data"] = json.dumps(parsed, default=str)

    return flat
