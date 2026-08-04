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

## Playbook: Run Today's Falling Knife Report

**Trigger:** Run this workflow when the user says a normalized variation of `Run today's Falling Knife report`, including case variations and straight or curly apostrophes. Normalize whitespace, case, and apostrophes before matching.

**Purpose:** Produce a research-only Markdown report on the largest daily decliners in Robinhood's curated Software universe. Never treat a price decline as an investment opportunity by itself.

**Safety boundary:** Do not place, review, preview, cancel, replace, exercise, or otherwise manage any equity or option order. Do not create, follow, modify, or remove a watchlist. Do not access accounts, positions, tax lots, P&L, or portfolio data. For Robinhood, use only these read-only tools:

- `get_popular_watchlists`
- `get_watchlist_items`
- `get_equity_fundamentals`
- `get_equity_quotes`
- `get_equity_historicals`

Use only `get_company_profile`, `list_filings`, `get_filing_section`, and `get_financial_statements` from SEC EDGAR. Use public web research only for the decline catalyst and cite direct sources.

### Output and session rules

- Use US Eastern Time for the run timestamp, session date, and filename.
- Save every run as `reports/YYYY-MM-DD-HHmmss-ET.md`. If that name already exists, append `-2`, `-3`, and so on; never overwrite a prior report.
- Support intraday execution. During regular hours, compare the latest regular-market trade price with the adjusted previous regular close. Outside regular hours, or when the current session has no regular trade, use the two latest completed regular-session closes from split-adjusted daily history.
- For weekends, holidays, or before a usable current-session trade, analyze the most recent completed US trading day.
- Apply split-adjusted prices. Exclude and flag any symbol whose relevant split, spin-off, or distribution adjustment cannot be validated.

### 1. Build the candidate list

1. Call `get_popular_watchlists` and find the curated list whose `display_name` equals `Software` case-insensitively. This list is the complete software universe; do not replace it with another sector, industry, or custom ticker list.
2. If the Software list cannot be retrieved, create the timestamped report with a clear failure note and stop. Do not substitute a universe.
3. Call `get_watchlist_items`, retain instruments with usable equity symbols, and call `get_equity_fundamentals` in batches of at most 10 symbols using regular-session data.
4. Retain companies with current market capitalization of at least $2.0B, inclusive.
5. Retrieve price data in the relevant MCP batch limits. Calculate:

   ```text
   daily decline % = ((latest regular-market price - previous regular-session close)
                      / previous regular-session close) * 100
   ```

6. Exclude from ranking any company without a valid market cap, current/latest-session price, or previous close. List each exclusion and its missing field in a screening-data-gaps section; do not assign it a neutral score.
7. Rank eligible companies by the most negative decline percentage. Select the top five, or every eligible company when fewer than five qualify.
8. If no candidate qualifies, still save a report containing the session details, universe count, filtering results, and data gaps, then stop.

### 2. Research each selected company

For every selected company, preserve the ticker, current market cap, prior close, latest regular-market price, decline percentage, and price-session basis.

**Reason for the decline**

- Research the window from the prior completed regular-market close through the run timestamp. This includes intervening weekends and holidays.
- Prioritize company press releases, relevant SEC 8-K filings, and established publicly accessible financial news outlets.
- Distinguish confirmed facts from interpretation. Cite every news source as a Markdown link with its source title.
- Classify the decline cause before assigning its score:
  - **Unconfirmed — `5.0`:** Assign exactly `5.0` when the available evidence does not establish a credible connection between a specific event and the stock decline. Do not score above or below neutral based only on timing, correlation, speculation, background risks, or incomplete information.
  - **Temporary or limited — `6.0–10.0`:** Assign a score above `5.0` only when credible evidence connects the decline to a temporary, market-wide, technical, or otherwise limited event whose expected long-term fundamental impact is modest.
  - **Fundamental — `0.0–4.0`:** Assign a score below `5.0` only when credible evidence connects the decline to adverse changes in revenue, growth, margins, cash flow, liquidity, competitive position, governance, or another material business fundamental.
- Before assigning any Decline Cause score other than `5.0`, the report must identify the specific catalyst, cite a credible source supporting the connection, explain the expected business impact, and justify why the impact is temporary/limited or fundamental.
- If those evidence requirements are not satisfied, classify the cause as `Unconfirmed` and assign exactly `5.0`.
- Before finalizing the report, verify that the narrative classification, evidence, and numerical Decline Cause score are consistent. Do not describe a cause as unconfirmed while assigning a non-neutral score.

**Financial strength and disclosed risks**

1. Call `get_company_profile`.
2. Call `list_filings` to find the latest relevant annual filing. Use a relevant 10-K/A instead of its original 10-K when it revises the required information; never double count both filings.
3. Call `get_filing_section` by annual-filing accession number with `section_name: "Item 1A"`.
4. Call `get_financial_statements` to evaluate liquidity versus short-term obligations, debt/leverage, cash-flow generation, and recent revenue/profitability direction with equal consideration.
5. Assess the severity of disclosed risks, including when relevant customer concentration, refinancing pressure, litigation/regulation, competition, dilution, and going-concern language.
6. Cite each SEC-based conclusion with filing type, reporting period, and accession number.

**TTM earnings quality**

1. Use `list_filings` and accession-specific `get_financial_statements` calls to obtain the latest four comparable fiscal quarters. Use a relevant 10-Q/A or 10-K/A instead of the original filing.
2. Extract standalone quarterly Net Income and Operating Cash Flow (OCF); never add year-to-date values as independent quarters.
3. Derive Q4 only when annual and nine-month amounts have matching fiscal periods, units, accounting scope, and XBRL concepts. Otherwise, treat the TTM data as incomplete.
4. Calculate only when four comparable quarters exist:

   ```text
   TTM Net Income = sum of latest 4 comparable quarterly Net Income values
   TTM Operating Cash Flow = sum of latest 4 comparable quarterly OCF values
   TTM Quality of Earnings Ratio = TTM Operating Cash Flow / TTM Net Income
   ```

5. When TTM Net Income is zero or negative, state that the ratio is not meaningful. When required TTM data is unavailable or non-comparable, assign the Earnings Quality subscore `5.0` and explain the data gap.
6. Analyze the four-quarter trend plus available working-capital changes (including accounts receivable and inventory) and material non-cash drivers.

**Valuation metrics**

1. For each selected company, apply the `Calculate Valuation Metrics` playbook.
2. Calculate EV/Revenue and FCF Yield before assigning their respective subscores.
3. Use the market capitalization already preserved during screening.
4. If either metric cannot be calculated, apply the relevant missing-data scoring rule and explain the limitation.

### 3. Score and label

Score Financial Strength, Earnings Quality, Decline Cause, Disclosed Risks, EV/Revenue, and FCF Yield independently from `0.0` to `10.0`, round each to one decimal place, and calculate:

```text
Final score =
  (Financial Strength * 20%)
+ (Earnings Quality * 20%)
+ (Decline Cause * 20%)
+ (Disclosed Risks * 20%)
+ (EV/Revenue * 10%)
+ (FCF Yield * 10%)
```

- Use common score bands: `0-2` severe, `3-4` weak, `5-6` mixed/neutral, `7-8` strong, `9-10` exceptional.
- Financial Strength: higher scores require strong liquidity, manageable leverage, positive cash generation, and stable/improving operations; strained liquidity, high leverage, persistent negative cash flow, or deterioration lower the score.
- Earnings Quality base bands from TTM OCF / TTM Net Income: `>=1.2` is `9-10`; `1.0-1.19` is `7-8`; `0.8-0.99` is `5-6`; `0.5-0.79` is `3-4`; `<0.5` is `0-2`. Deduct 2.0 points, floored at `0.0`, only for a persistently worsening four-quarter earnings-quality trend.
- Decline Cause: apply the evidence and scoring rules in the **Reason for the decline** section. Evidence-backed temporary or limited causes score `6.0–10.0`; evidence-backed fundamental causes score `0.0–4.0`; and unconfirmed causes score exactly `5.0`.
- Disclosed Risks: fewer and less severe current risks score higher; material concentration, liquidity/refinancing, legal/regulatory, competition, dilution, or going-concern risks score lower.
- A missing required data category receives `5.0` with an explicit limitation. There are no automatic disqualifiers or score caps.
- EV/Revenue valuation subscore bands are: `<=2.0x` = `10.0`; `>2.0x-4.0x` = `8.0`; `>4.0x-6.0x` = `6.0`; `>6.0x-10.0x` = `4.0`; and `>10.0x` = `2.0`.
- FCF Yield valuation subscore bands are: `>=10.0%` = `10.0`; `7.5%-<10.0%` = `8.0`; `5.0%-<7.5%` = `6.0`; `2.5%-<5.0%` = `4.0`; `>0%-<2.5%` = `2.0`; and `<=0%` = `0.0`.
- When FCF Yield cannot be calculated because required data is unavailable or non-comparable, assign `5.0` and explain the limitation. Missing data is not the same as negative FCF.
- The four original factors each carry `20%` of the final score; EV/Revenue and FCF Yield each carry `10%`.
- Round the final score to one decimal place and label it: `0.0-3.0 High Risk`, `3.1-6.0 Investigate`, `6.1-8.0 Watchlist`, or `8.1-10.0 Strong Research Candidate`.

### 4. Required report structure

1. **Header:** Eastern-time run timestamp, analysis session date, intraday/completed-session basis, software-universe count, eligible count, and analyzed count.
2. **Top Decliners:** A Markdown table with rank, ticker, market cap, prior close, latest regular-market price, daily decline percentage, final score, and research label.
3. **Detailed thesis for each selected company:** decline snapshot and cause; raw screening inputs; financial-strength review; Item 1A risk audit; four-quarter TTM table and calculations; valuation inputs and EV/Revenue/FCF Yield calculations; six subscores; weighted score calculation and label; concise opportunity thesis; and principal failure risk.
4. **Sources and limitations:** Direct Markdown links for public news, SEC filing type/period/accession numbers, unconfirmed-catalyst status, data gaps, methodology, and a research-only disclaimer.
