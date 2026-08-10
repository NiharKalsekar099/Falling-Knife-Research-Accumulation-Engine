# SEC EDGAR Analysis Playbooks

Use these repeatable workflows when a user requests the corresponding SEC-filing analysis. These are guidance for tool-driven analysis, not executable MCP prompt templates.

## General rules

- Require a non-empty ticker symbol for every company named in a workflow. Trim whitespace and normalize each ticker to uppercase before calling a tool.
- Use the connected `sec_edgar` tools only for SEC filing data. State the company, filing type, reporting period, and accession number when that information is available.
- If a required metric, filing, period, or statement line item is unavailable, say so plainly. Do not invent, estimate, or silently substitute data.
- Present analysis as informational research, not personalized investment advice or a recommendation to buy, sell, or hold a security.
- Use Markdown headings and tables where the requested report structure calls for them.

## Playbook: Compare Competitors

**Use when:** The user asks for a side-by-side comparison of two competing companies.

**Inputs:** `ticker_a`, `ticker_b`.

**Tool sequence:**

1. Call `get_company_profile` for `ticker_a` and `ticker_b`.
2. Call `get_filing_section` for each company with `section_name: "Item 1"` to retrieve its latest Business Overview.
3. Call `get_financial_statements` for each company.

**Report:**

Provide a comparative Markdown table covering:

| Topic | Company A | Company B |
| --- | --- | --- |
| Market and industry segment overlay | | |
| Revenue scale and gross-profit comparison | | |
| Strategic advantages stated in Item 1 | | |
| Balance-sheet leverage assessment | | |

Follow the table with a short, evidence-based comparison that distinguishes reported facts from interpretation. Cite the filing periods used and identify unavailable statement lines or non-comparable reporting periods.

## Playbook: Audit Investment Risks

**Use when:** The user asks for a risk, red-flag, or financial-health audit of one company.

**Input:** `ticker`.

**Tool sequence:**

1. Call `get_company_profile` to establish baseline company metadata and industry classification.
2. Call `get_filing_section` with `section_name: "Item 1A"` to retrieve Risk Factors from the latest annual filing.
3. Call `get_financial_statements` to review the balance sheet, income statement, and cash-flow statement.

**Report:**

Use the following structure:

1. **Executive Summary** - Pass/Fail assessment for material high-risk flags, with a concise rationale.
2. **Top 3 Operational Risks** - Synthesize the three most material hazards disclosed in Item 1A.
3. **Financial Health Check** - Compare cash and short-term investments with short-term debt obligations; discuss the available free-cash-flow trend.
4. **Red Flags / Divergences** - Identify evidence-backed mismatches between management disclosures and balance-sheet or cash-flow realities. State explicitly when the available data does not support a conclusion.

Include the latest filing period and any relevant data limitations.

## Playbook: Analyze TTM Earnings Quality

**Use when:** The user asks for an earnings-quality, cash-conversion, or forensic accounting review.

**Input:** `ticker`.

**Tool sequence:**

1. Call `get_financial_statements` for the normalized ticker.
2. Derive Net Income and Operating Cash Flow (OCF) for each of the last four available quarters from the returned structured statements.
3. If four comparable quarters cannot be derived from the available statements, report the available periods, explain the limitation, and do not calculate a four-quarter total from incomplete data.

**Calculations:**

```text
TTM Net Income = sum of Net Income for the last 4 available quarters
TTM Operating Cash Flow = sum of OCF for the last 4 available quarters
TTM Quality of Earnings Ratio = TTM Operating Cash Flow / TTM Net Income
```

**Report:**

1. Show a Markdown table of each reported quarter, Net Income, OCF, and the relevant filing period.
2. Show TTM totals and the Quality of Earnings Ratio, including the calculation inputs.
3. Evaluate whether weak quarters appear temporary or form a downward trend.
4. Interpret the ratio carefully:
   - Above `1.0`: earnings are more strongly supported by trailing operating cash flow.
   - Below `1.0`: flag that reported profits exceeded trailing operating cash flow and investigate the persistence of the gap.
5. Summarize available working-capital drivers, including accounts receivable and inventory changes, and material non-cash items that may explain a persistent multi-quarter divergence.

Clearly identify all filing periods used, explain any unavailable line items, and avoid conclusions not supported by the returned statements.

## Playbook: Calculate Valuation Metrics

**Use when:** The user asks for EV/Revenue, FCF Yield, or valuation inputs for a company.

**Input:** `ticker`.

**Tool sequence:**

1. Normalize and validate the ticker symbol.
2. Call Robinhood `get_equity_fundamentals` for the current market capitalization.
3. Call SEC EDGAR `list_filings` to identify the latest relevant 10-Q/10-Q/A and 10-K/10-K/A filings.
4. Call SEC EDGAR `get_financial_statements` for the latest comparable balance-sheet, income-statement, and cash-flow data.

**Enterprise Value:**

```text
Enterprise Value =
Market Capitalization
+ Current Portion of Debt
+ Long-Term Debt
- Cash and Cash Equivalents
- Short-Term Investments
```

- Add current and long-term debt separately when both are reported.
- Do not add a separately reported total-debt amount when current and long-term debt have already been included.
- If current and long-term debt components are not separately available, but a clearly defined total-debt balance is available, use total debt once. Never combine total debt with debt components already included.
- Do not double-count debt across balance-sheet line items.
- If short-term investments are separately disclosed, treat them as cash-like and subtract them.
- If a required input is unavailable, state the limitation plainly; do not silently substitute another line item.

**EV/Revenue:**

```text
EV/Revenue = Enterprise Value / TTM Revenue
```

**Free Cash Flow:**

```text
Free Cash Flow = Net Cash Provided by Operating Activities
                 - absolute value of cash paid for Purchases of Property and Equipment
```

SEC cash-flow statements may present purchases of property and equipment as negative numbers. Treat purchases of property and equipment as a positive cash-outflow magnitude before subtracting them from operating cash flow; never subtract a negative capex value.

Use the latest four comparable fiscal quarters. Derive a standalone interim quarter by subtracting the immediately preceding comparable year-to-date amount from the current year-to-date amount. Perform the subtraction only when fiscal periods, units, accounting scope, and statement concepts match. For example:

```text
Standalone Q2 OCF = Six-month YTD OCF - Three-month YTD OCF
Standalone Q3 OCF = Nine-month YTD OCF - Six-month YTD OCF
Standalone Q4 OCF = Annual OCF - Nine-month YTD OCF
```

Derive Q4 as annual revenue or cash flow minus nine-month revenue or cash flow only when fiscal periods, units, accounting scope, and statement concepts match. Do not treat year-to-date values as standalone quarters. Do not use an annual-plus-current-YTD-minus-prior-YTD shortcut when comparable standalone quarters can be derived directly.

**FCF Yield:**

```text
FCF Yield = TTM Free Cash Flow / Market Capitalization
```

**Report:**

- Show the final EV/Revenue and FCF Yield.
- Briefly identify market capitalization, debt components, cash, short-term investments, TTM revenue, operating cash flow, capital expenditures, and TTM free cash flow.
- State the Robinhood tool, SEC filing type, reporting period, and accession number used for each material input.
- State unavailable or non-comparable data and do not invent missing values.
- Present the analysis as informational research, not personalized investment advice.

