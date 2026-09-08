"""
Unit tests for the leak-risk and habit-estimate models.
Run with:  py -m pytest backend/test_models.py -v
"""

import pytest
from leak_model import compute_leak_risk
from habit_model import estimate_monthly_usage


class TestLeakRiskModel:
    def test_no_signals_means_no_leak(self):
        r = compute_leak_risk(False, False, False, False)
        assert r.score == 0
        assert r.flag == "No Leak Detected"
        assert r.estimated_daily_loss_liters == 0
        assert r.estimated_monthly_loss_liters == 0
        assert r.urgency_level == "Low"

    def test_single_meter_signal_is_minor(self):
        r = compute_leak_risk(True, False, False, False)
        assert r.score == 35
        assert r.flag == "Possible Minor Leak"
        assert r.estimated_daily_loss_liters == 200
        assert r.estimated_monthly_loss_liters == 6000
        assert r.estimated_monthly_cost_loss == 9.0  # (6000/1000) * 1.50
        assert r.urgency_level == "Moderate"

    def test_all_signals_is_critical(self):
        r = compute_leak_risk(True, True, True, True)
        assert r.score == 100
        assert r.flag == "Critical Multi-Point Leak"
        assert r.estimated_daily_loss_liters == 200 + 450 + 120 + 700  # 1470 L/day
        assert r.estimated_monthly_loss_liters == 1470 * 30  # 44100 L/month
        assert len(r.detected_signal_details) == 4
        assert r.urgency_level == "Critical"

    def test_two_weak_signals_still_minor(self):
        r = compute_leak_risk(False, False, True, True)  # damp + cistern = 40
        assert r.score == 40
        assert r.flag == "Possible Minor Leak"

    def test_meter_plus_one_other_escalates_to_major(self):
        r = compute_leak_risk(True, True, False, False)  # 35 + 25 = 60
        assert r.score == 60
        assert r.flag == "Likely Major Leak"

    def test_contributing_signals_breakdown(self):
        r = compute_leak_risk(True, False, True, False)
        assert r.contributing_signals == {"meter_moves": 35, "damp_patches": 20}


class TestHabitModel:
    def test_zero_habits_gives_near_zero_total(self):
        r = estimate_monthly_usage(0, False, 0, 0, False, household_members=3)
        # Dishwashing baseline only (2 min * 6 LPM * 30 days = 360 L)
        assert r.total_liters == 360
        assert r.household_members == 3
        assert r.per_capita_daily_lpd == (360 / 30) / 3  # 4 LPD

    def test_shower_only_calculation_scaled_by_household(self):
        r = estimate_monthly_usage(10, False, 0, 0, False, household_members=4)
        shower_row = next(row for row in r.breakdown if row["habit"] == "Shower")
        # 10 min * 9 LPM * 30 days * 4 members = 10,800 L
        assert shower_row["liters"] == 10800
        assert r.household_members == 4

    def test_biggest_waste_is_identified_correctly(self):
        r = estimate_monthly_usage(
            shower_minutes_per_day=5,
            tap_left_running_while_washing_dishes=False,
            garden_minutes_per_day=30,
            washing_machine_runs_per_week=1,
            washing_machine_half_full=False,
            household_members=2,
        )
        assert r.biggest_waste["habit"] == "Garden hose"

    def test_assumptions_are_documented(self):
        r = estimate_monthly_usage(10, True, 10, 3, True, household_members=3)
        assert len(r.assumptions) == 2

    def test_sdg_benchmark_comparison_and_savings(self):
        r = estimate_monthly_usage(15, True, 20, 5, True, household_members=3)
        assert r.per_capita_daily_lpd > 135
        assert "Excessive" in r.efficiency_status or "Moderate" in r.efficiency_status
        assert r.potential_monthly_savings_liters > 0
        assert r.potential_monthly_savings_cost > 0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))

