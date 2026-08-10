"""Offline, deterministic calculations for the Falling Knife research workflow.

This module deliberately contains no data retrieval, I/O, report generation, or
qualitative-analysis logic. Callers must validate accounting comparability before
passing reported values to these helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Sequence, Tuple


ONE_DECIMAL = Decimal("0.1")
MARKET_CAP_CUTOFF = Decimal("2000000000")


@dataclass(frozen=True)
class ScreeningRecord:
    """The quantitative fields needed to screen a single equity."""

    ticker: str
    market_cap: Optional[Decimal]
    previous_close: Optional[Decimal]
    latest_price: Optional[Decimal]

    def __post_init__(self) -> None:
        if not self.ticker or not self.ticker.strip():
            raise ValueError("ticker must be non-empty")

    @property
    def normalized_ticker(self) -> str:
        return self.ticker.strip().upper()


@dataclass(frozen=True)
class TTMMetrics:
    """Comparable trailing-twelve-month income and cash-flow totals."""

    net_income: Decimal
    operating_cash_flow: Decimal
    quality_ratio: Optional[Decimal]


@dataclass(frozen=True)
class SixFactorScores:
    """The six report subscores before the documented weighted calculation."""

    financial_strength: Decimal
    earnings_quality: Decimal
    decline_cause: Decimal
    disclosed_risks: Decimal
    ev_revenue: Decimal
    fcf_yield: Decimal

    def __post_init__(self) -> None:
        for name, score in self._items():
            _validate_score(name, score)

    def _items(self) -> Tuple[Tuple[str, Decimal], ...]:
        return (
            ("financial_strength", self.financial_strength),
            ("earnings_quality", self.earnings_quality),
            ("decline_cause", self.decline_cause),
            ("disclosed_risks", self.disclosed_risks),
            ("ev_revenue", self.ev_revenue),
            ("fcf_yield", self.fcf_yield),
        )


@dataclass(frozen=True)
class ScoreResult:
    """A rounded final score and its non-actionable research label."""

    final_score: Decimal
    label: str


def daily_decline_percentage(
    latest_price: Optional[Decimal], previous_close: Optional[Decimal]
) -> Optional[Decimal]:
    """Return the percentage change from the prior regular close, if usable."""
    if latest_price is None or previous_close is None or previous_close <= 0:
        return None
    if latest_price < 0:
        raise ValueError("latest_price cannot be negative")
    return ((latest_price - previous_close) / previous_close) * Decimal("100")


def is_market_cap_eligible(market_cap: Optional[Decimal]) -> bool:
    """Apply the inclusive $2.0B market-cap screen."""
    return market_cap is not None and market_cap >= MARKET_CAP_CUTOFF


def top_decliners(
    records: Sequence[ScreeningRecord], limit: int = 5
) -> Tuple[ScreeningRecord, ...]:
    """Return complete, market-cap-eligible records ranked by price decline.

    Records without all screening values are excluded. Exact daily-decline ties are
    resolved by normalized ticker ascending so API or batch order cannot affect the
    result.
    """
    if limit <= 0:
        raise ValueError("limit must be positive")

    ranked = []
    for record in records:
        if not is_market_cap_eligible(record.market_cap):
            continue
        decline = daily_decline_percentage(record.latest_price, record.previous_close)
        if decline is not None:
            ranked.append((decline, record.normalized_ticker, record))

    ranked.sort(key=lambda item: (item[0], item[1]))
    return tuple(item[2] for item in ranked[:limit])


def derive_standalone_period(
    current_cumulative_value: Optional[Decimal], previous_cumulative_value: Optional[Decimal]
) -> Optional[Decimal]:
    """Derive a standalone quarter from matching cumulative reported values."""
    if current_cumulative_value is None or previous_cumulative_value is None:
        return None
    return current_cumulative_value - previous_cumulative_value


def earnings_quality_ratio(
    operating_cash_flow: Optional[Decimal], net_income: Optional[Decimal]
) -> Optional[Decimal]:
    """Return OCF divided by net income when the ratio is meaningful."""
    if operating_cash_flow is None or net_income is None or net_income <= 0:
        return None
    return operating_cash_flow / net_income


def aggregate_ttm(
    net_incomes: Sequence[Optional[Decimal]],
    operating_cash_flows: Sequence[Optional[Decimal]],
) -> Optional[TTMMetrics]:
    """Aggregate exactly four comparable quarterly observations."""
    if len(net_incomes) != 4 or len(operating_cash_flows) != 4:
        return None
    if any(value is None for value in net_incomes) or any(
        value is None for value in operating_cash_flows
    ):
        return None

    net_income = sum(net_incomes, Decimal("0"))
    operating_cash_flow = sum(operating_cash_flows, Decimal("0"))
    return TTMMetrics(
        net_income=net_income,
        operating_cash_flow=operating_cash_flow,
        quality_ratio=earnings_quality_ratio(operating_cash_flow, net_income),
    )


def enterprise_value(
    market_cap: Optional[Decimal],
    cash_and_equivalents: Optional[Decimal],
    short_term_investments: Optional[Decimal] = Decimal("0"),
    *,
    current_debt: Optional[Decimal] = None,
    long_term_debt: Optional[Decimal] = None,
    total_debt: Optional[Decimal] = None,
) -> Optional[Decimal]:
    """Calculate EV without double-counting debt components.

    Supply either both current and long-term debt, or a standalone total-debt amount.
    Pass an explicit zero for a confirmed absent cash-like or debt balance; ``None``
    denotes unavailable data.
    """
    if (
        market_cap is None
        or cash_and_equivalents is None
        or short_term_investments is None
    ):
        return None
    _validate_non_negative("market_cap", market_cap)
    _validate_non_negative("cash_and_equivalents", cash_and_equivalents)
    _validate_non_negative("short_term_investments", short_term_investments)

    has_component = current_debt is not None or long_term_debt is not None
    if total_debt is not None and has_component:
        raise ValueError("total_debt cannot be combined with debt components")
    if total_debt is not None:
        _validate_non_negative("total_debt", total_debt)
        debt = total_debt
    elif current_debt is not None and long_term_debt is not None:
        _validate_non_negative("current_debt", current_debt)
        _validate_non_negative("long_term_debt", long_term_debt)
        debt = current_debt + long_term_debt
    else:
        return None

    return market_cap + debt - cash_and_equivalents - short_term_investments


def ev_to_revenue(
    enterprise_value_amount: Optional[Decimal], ttm_revenue: Optional[Decimal]
) -> Optional[Decimal]:
    """Return EV divided by positive, comparable TTM revenue."""
    if enterprise_value_amount is None or ttm_revenue is None or ttm_revenue <= 0:
        return None
    return enterprise_value_amount / ttm_revenue


def free_cash_flow(
    operating_cash_flow: Optional[Decimal], capital_expenditures: Optional[Decimal]
) -> Optional[Decimal]:
    """Return OCF less the absolute cash-outflow magnitude of capital expenditures."""
    if operating_cash_flow is None or capital_expenditures is None:
        return None
    return operating_cash_flow - abs(capital_expenditures)


def fcf_yield(
    free_cash_flow_amount: Optional[Decimal], market_cap: Optional[Decimal]
) -> Optional[Decimal]:
    """Return free-cash-flow yield for a positive market capitalization."""
    if free_cash_flow_amount is None or market_cap is None or market_cap <= 0:
        return None
    return free_cash_flow_amount / market_cap


def earnings_quality_score(
    quality_ratio: Optional[Decimal], persistently_worsening: bool = False
) -> Optional[Decimal]:
    """Map a meaningful quality ratio to the fixed score-band floor."""
    if quality_ratio is None:
        return None
    if quality_ratio >= Decimal("1.2"):
        score = Decimal("9.0")
    elif quality_ratio >= Decimal("1.0"):
        score = Decimal("7.0")
    elif quality_ratio >= Decimal("0.8"):
        score = Decimal("5.0")
    elif quality_ratio >= Decimal("0.5"):
        score = Decimal("3.0")
    else:
        score = Decimal("0.0")
    return max(Decimal("0.0"), score - Decimal("2.0")) if persistently_worsening else score


def ev_revenue_score(multiple: Optional[Decimal]) -> Optional[Decimal]:
    """Map EV/Revenue to the documented fixed valuation bands."""
    if multiple is None:
        return None
    if multiple <= Decimal("2.0"):
        return Decimal("10.0")
    if multiple <= Decimal("4.0"):
        return Decimal("8.0")
    if multiple <= Decimal("6.0"):
        return Decimal("6.0")
    if multiple <= Decimal("10.0"):
        return Decimal("4.0")
    return Decimal("2.0")


def fcf_yield_score(yield_value: Optional[Decimal]) -> Optional[Decimal]:
    """Map FCF Yield expressed as a decimal (0.10 equals 10%) to score bands."""
    if yield_value is None:
        return None
    if yield_value >= Decimal("0.10"):
        return Decimal("10.0")
    if yield_value >= Decimal("0.075"):
        return Decimal("8.0")
    if yield_value >= Decimal("0.05"):
        return Decimal("6.0")
    if yield_value >= Decimal("0.025"):
        return Decimal("4.0")
    if yield_value > Decimal("0"):
        return Decimal("2.0")
    return Decimal("0.0")


def round_one_decimal(value: Decimal) -> Decimal:
    """Round with conventional financial half-up behavior."""
    return value.quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP)


def research_label(final_score: Decimal) -> str:
    """Assign the documented label after one-decimal rounding."""
    _validate_score("final_score", final_score)
    rounded_score = round_one_decimal(final_score)
    if rounded_score <= Decimal("3.0"):
        return "High Risk"
    if rounded_score <= Decimal("6.0"):
        return "Investigate"
    if rounded_score <= Decimal("8.0"):
        return "Watchlist"
    return "Strong Research Candidate"


def weighted_final_score(scores: SixFactorScores) -> ScoreResult:
    """Apply the documented 20/20/20/20/10/10 score weights."""
    final_score = round_one_decimal(
        (scores.financial_strength * Decimal("0.20"))
        + (scores.earnings_quality * Decimal("0.20"))
        + (scores.decline_cause * Decimal("0.20"))
        + (scores.disclosed_risks * Decimal("0.20"))
        + (scores.ev_revenue * Decimal("0.10"))
        + (scores.fcf_yield * Decimal("0.10"))
    )
    return ScoreResult(final_score=final_score, label=research_label(final_score))


def _validate_non_negative(name: str, value: Decimal) -> None:
    if value < 0:
        raise ValueError(f"{name} cannot be negative")


def _validate_score(name: str, score: Decimal) -> None:
    if score < 0 or score > 10:
        raise ValueError(f"{name} must be between 0.0 and 10.0")
