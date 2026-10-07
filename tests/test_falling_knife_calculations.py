from decimal import Decimal
import unittest

from scripts.falling_knife_calculations import (
    MARKET_CAP_CUTOFF,
    ScreeningRecord,
    SixFactorScores,
    aggregate_ttm,
    daily_decline_percentage,
    derive_standalone_period,
    earnings_quality_ratio,
    earnings_quality_score,
    enterprise_value,
    ev_revenue_score,
    ev_to_revenue,
    fcf_yield,
    fcf_yield_score,
    free_cash_flow,
    is_market_cap_eligible,
    research_label,
    round_one_decimal,
    top_decliners,
    weighted_final_score,
)


D = Decimal


class ScreeningCalculationTests(unittest.TestCase):
    def test_daily_decline_and_unavailable_inputs(self) -> None:
        self.assertEqual(daily_decline_percentage(D("90"), D("100")), D("-10.0"))
        self.assertIsNone(daily_decline_percentage(None, D("100")))
        self.assertIsNone(daily_decline_percentage(D("100"), None))
        self.assertIsNone(daily_decline_percentage(D("100"), D("0")))

    def test_market_cap_cutoff_is_inclusive(self) -> None:
        self.assertTrue(is_market_cap_eligible(MARKET_CAP_CUTOFF))
        self.assertFalse(is_market_cap_eligible(MARKET_CAP_CUTOFF - D("1")))
        self.assertFalse(is_market_cap_eligible(None))

    def test_top_decliners_excludes_incomplete_records_and_breaks_ties_by_ticker(self) -> None:
        records = (
            ScreeningRecord("zeta", D("3000000000"), D("100"), D("90")),
            ScreeningRecord("alpha", D("3000000000"), D("100"), D("90")),
            ScreeningRecord("smaller", D("1999999999"), D("100"), D("1")),
            ScreeningRecord("missing", D("3000000000"), None, D("1")),
            ScreeningRecord("mild", D("3000000000"), D("100"), D("95")),
        )
        self.assertEqual([record.normalized_ticker for record in top_decliners(records)], ["ALPHA", "ZETA", "MILD"])


class TTMCalculationTests(unittest.TestCase):
    def test_standalone_period_derivation_covers_q2_q3_and_q4_patterns(self) -> None:
        self.assertEqual(derive_standalone_period(D("60"), D("25")), D("35"))
        self.assertEqual(derive_standalone_period(D("95"), D("60")), D("35"))
        self.assertEqual(derive_standalone_period(D("140"), D("95")), D("45"))
        self.assertIsNone(derive_standalone_period(D("60"), None))

    def test_ttm_aggregation_requires_exactly_four_complete_quarters(self) -> None:
        metrics = aggregate_ttm(
            (D("1"), D("2"), D("3"), D("4")),
            (D("2"), D("4"), D("6"), D("8")),
        )
        self.assertIsNotNone(metrics)
        assert metrics is not None
        self.assertEqual(metrics.net_income, D("10"))
        self.assertEqual(metrics.operating_cash_flow, D("20"))
        self.assertEqual(metrics.quality_ratio, D("2"))
        self.assertIsNone(aggregate_ttm((D("1"),) * 3, (D("1"),) * 3))
        self.assertIsNone(aggregate_ttm((D("1"), D("2"), None, D("4")), (D("1"),) * 4))

    def test_non_positive_net_income_has_no_meaningful_quality_ratio(self) -> None:
        self.assertIsNone(earnings_quality_ratio(D("10"), D("0")))
        self.assertIsNone(earnings_quality_ratio(D("10"), D("-1")))

    def test_complete_fiscal_year_uses_standalone_and_derived_quarters(self) -> None:
        # Q2/Q3/Q4 inputs model the cumulative cash-flow values reported in filings.
        quarterly_net_income = (D("10"), D("12"), D("15"), D("18"))
        quarterly_ocf = (
            D("16"),
            derive_standalone_period(D("38"), D("16")),
            derive_standalone_period(D("66"), D("38")),
            derive_standalone_period(D("95"), D("66")),
        )
        quarterly_revenue = (D("100"), D("110"), D("120"), D("130"))
        quarterly_capex = (
            D("-4"),
            derive_standalone_period(D("-11"), D("-4")),
            derive_standalone_period(D("-18"), D("-11")),
            derive_standalone_period(D("-26"), D("-18")),
        )

        metrics = aggregate_ttm(quarterly_net_income, quarterly_ocf)
        self.assertIsNotNone(metrics)
        assert metrics is not None
        self.assertEqual(metrics.net_income, D("55"))
        self.assertEqual(metrics.operating_cash_flow, D("95"))
        self.assertEqual(metrics.quality_ratio, D("95") / D("55"))
        self.assertEqual(sum(quarterly_revenue), D("460"))
        self.assertEqual(sum(quarterly_capex), D("-26"))
        self.assertEqual(free_cash_flow(metrics.operating_cash_flow, sum(quarterly_capex)), D("69"))
        ev = enterprise_value(
            D("1000"), D("100"), D("50"), current_debt=D("25"), long_term_debt=D("175")
        )
        self.assertEqual(ev, D("1050"))
        self.assertEqual(ev_to_revenue(ev, sum(quarterly_revenue)), D("1050") / D("460"))
        self.assertEqual(fcf_yield(D("69"), D("1000")), D("0.069"))


class ValuationCalculationTests(unittest.TestCase):
    def test_enterprise_value_uses_debt_components_and_cash_like_deductions(self) -> None:
        self.assertEqual(
            enterprise_value(
                D("1000"), D("100"), D("50"), current_debt=D("25"), long_term_debt=D("200")
            ),
            D("1075"),
        )

    def test_enterprise_value_supports_total_debt_and_rejects_ambiguous_debt(self) -> None:
        self.assertEqual(enterprise_value(D("1000"), D("100"), total_debt=D("400")), D("1300"))
        self.assertIsNone(enterprise_value(D("1000"), D("100")))
        with self.assertRaises(ValueError):
            enterprise_value(D("1000"), D("100"), current_debt=D("10"), total_debt=D("20"))

    def test_valuation_multiples_and_free_cash_flow_handle_missing_and_negative_capex(self) -> None:
        self.assertEqual(ev_to_revenue(D("200"), D("100")), D("2"))
        self.assertIsNone(ev_to_revenue(D("200"), D("0")))
        self.assertEqual(free_cash_flow(D("100"), D("-25")), D("75"))
        self.assertEqual(free_cash_flow(D("100"), D("25")), D("75"))
        self.assertEqual(fcf_yield(D("10"), D("100")), D("0.1"))
        self.assertEqual(fcf_yield(D("-10"), D("100")), D("-0.1"))
        self.assertIsNone(fcf_yield(None, D("100")))


class ScoreCalculationTests(unittest.TestCase):
    def test_earnings_quality_score_boundaries_and_deterioration_floor(self) -> None:
        cases = (
            (D("1.2"), D("9.0")),
            (D("1.19"), D("7.0")),
            (D("1.0"), D("7.0")),
            (D("0.8"), D("5.0")),
            (D("0.79"), D("3.0")),
            (D("0.5"), D("3.0")),
            (D("0.49"), D("0.0")),
        )
        for ratio, expected in cases:
            with self.subTest(ratio=ratio):
                self.assertEqual(earnings_quality_score(ratio), expected)
        self.assertEqual(earnings_quality_score(D("1.2"), True), D("7.0"))
        self.assertEqual(earnings_quality_score(D("0.49"), True), D("0.0"))
        self.assertIsNone(earnings_quality_score(None))

    def test_ev_revenue_score_boundaries(self) -> None:
        cases = (
            (D("2.0"), D("10.0")),
            (D("2.01"), D("8.0")),
            (D("4.0"), D("8.0")),
            (D("4.01"), D("6.0")),
            (D("6.0"), D("6.0")),
            (D("6.01"), D("4.0")),
            (D("10.0"), D("4.0")),
            (D("10.01"), D("2.0")),
        )
        for multiple, expected in cases:
            with self.subTest(multiple=multiple):
                self.assertEqual(ev_revenue_score(multiple), expected)
        self.assertIsNone(ev_revenue_score(None))

    def test_fcf_yield_score_boundaries(self) -> None:
        cases = (
            (D("0.10"), D("10.0")),
            (D("0.075"), D("8.0")),
            (D("0.05"), D("6.0")),
            (D("0.025"), D("4.0")),
            (D("0.001"), D("2.0")),
            (D("0"), D("0.0")),
            (D("-0.01"), D("0.0")),
        )
        for yield_value, expected in cases:
            with self.subTest(yield_value=yield_value):
                self.assertEqual(fcf_yield_score(yield_value), expected)
        self.assertIsNone(fcf_yield_score(None))

    def test_rounding_weighted_score_and_labels(self) -> None:
        self.assertEqual(round_one_decimal(D("3.05")), D("3.1"))
        self.assertEqual(round_one_decimal(D("3.04")), D("3.0"))
        result = weighted_final_score(
            SixFactorScores(D("5.5"), D("9.0"), D("5.0"), D("4.0"), D("6.0"), D("4.0"))
        )
        self.assertEqual(result.final_score, D("5.7"))
        self.assertEqual(result.label, "Investigate")
        self.assertEqual(research_label(D("3.0")), "High Risk")
        self.assertEqual(research_label(D("3.1")), "Investigate")
        self.assertEqual(research_label(D("6.0")), "Investigate")
        self.assertEqual(research_label(D("6.1")), "Watchlist")
        self.assertEqual(research_label(D("8.0")), "Watchlist")
        self.assertEqual(research_label(D("8.1")), "Strong Research Candidate")

    def test_invalid_subscores_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SixFactorScores(D("10.1"), D("5"), D("5"), D("5"), D("5"), D("5"))


if __name__ == "__main__":
    unittest.main()
