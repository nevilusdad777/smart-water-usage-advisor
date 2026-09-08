"""
Habit-Based Monthly Water Usage Estimator
------------------------------------------
Converts a household's self-reported daily habits into an estimated
monthly water usage breakdown, using published/standard consumption
benchmarks (documented below for transparency). Every number here
is either a widely cited average or an explicit stated assumption —
never silently invented.

Benchmarking Standard:
  - UN/WHO Sustainable Goal (SDG 6) Target: 135 Liters per person per day (LPD)
  
Consumption Benchmarks (Liters):
  SHOWER_LPM        = 9    (average shower flow rate, liters/min)
  EFFICIENT_SHOWER  = 5    (eco low-flow head, liters/min)
  TAP_LPM           = 6    (average kitchen tap flow rate, liters/min)
  GARDEN_HOSE_LPM   = 15   (average garden hose flow rate, liters/min)
  WASHING_MACHINE_L = 65   (average water drawn per wash cycle, liters)
  COST_PER_1000L    = 1.50 (cost per 1,000 Liters)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

SHOWER_LPM = 9
EFFICIENT_SHOWER_LPM = 5
TAP_LPM = 6
GARDEN_HOSE_LPM = 15
WASHING_MACHINE_L = 65
COST_PER_1000L = 1.50

SDG_BENCHMARK_LPD_PER_PERSON = 135
DAYS_PER_MONTH = 30
WEEKS_PER_MONTH = 4.33


@dataclass
class HabitEstimateResult:
    breakdown: List[Dict[str, any]]
    total_liters: int
    household_members: int
    per_capita_daily_lpd: float
    sdg_benchmark_daily_lpd: float
    sdg_comparison_pct: float
    efficiency_status: str
    biggest_waste: Dict[str, any]
    potential_monthly_savings_liters: int
    potential_monthly_savings_cost: float
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "breakdown": self.breakdown,
            "total_liters": self.total_liters,
            "household_members": self.household_members,
            "per_capita_daily_lpd": round(self.per_capita_daily_lpd, 1),
            "sdg_benchmark_daily_lpd": self.sdg_benchmark_daily_lpd,
            "sdg_comparison_pct": round(self.sdg_comparison_pct, 1),
            "efficiency_status": self.efficiency_status,
            "biggest_waste": self.biggest_waste,
            "potential_monthly_savings_liters": self.potential_monthly_savings_liters,
            "potential_monthly_savings_cost": round(self.potential_monthly_savings_cost, 2),
            "assumptions": self.assumptions,
        }


def estimate_monthly_usage(
    shower_minutes_per_day: float,
    tap_left_running_while_washing_dishes: bool,
    garden_minutes_per_day: float,
    washing_machine_runs_per_week: float,
    washing_machine_half_full: bool,
    household_members: int = 3,
) -> HabitEstimateResult:
    assumptions: List[str] = []

    household_members = max(1, int(household_members))

    # 1. Shower Calculation
    shower_total = shower_minutes_per_day * SHOWER_LPM * DAYS_PER_MONTH * household_members
    # Savings potential: cutting shower to 5 min or eco nozzle (5 LPM)
    if shower_minutes_per_day > 5:
        shower_savings = (shower_minutes_per_day - 5) * SHOWER_LPM * DAYS_PER_MONTH * household_members
    else:
        shower_savings = 0

    # 2. Dishwashing tap usage
    if tap_left_running_while_washing_dishes:
        dish_minutes = 10
        assumptions.append(
            "Dish-washing tap time assumed at 10 min/day (tap left running while scrubbing)."
        )
        dish_savings = (10 - 2) * TAP_LPM * DAYS_PER_MONTH
    else:
        dish_minutes = 2
        assumptions.append(
            "Dish-washing tap time assumed at 2 min/day (rinse-only habit, tap turned off during scrubbing)."
        )
        dish_savings = 0
    dish_total = dish_minutes * TAP_LPM * DAYS_PER_MONTH

    # 3. Garden watering
    garden_total = garden_minutes_per_day * GARDEN_HOSE_LPM * DAYS_PER_MONTH
    if garden_minutes_per_day > 5:
        garden_savings = (garden_minutes_per_day - 5) * GARDEN_HOSE_LPM * DAYS_PER_MONTH
    else:
        garden_savings = 0

    # 4. Washing machine
    runs_per_month = washing_machine_runs_per_week * WEEKS_PER_MONTH
    laundry_total = WASHING_MACHINE_L * runs_per_month
    if washing_machine_half_full:
        assumptions.append(
            "Washing machine loads often half-full — consolidating into full loads reduces cycle count by ~40% for the same laundry volume."
        )
        laundry_savings = laundry_total * 0.40
    else:
        laundry_savings = 0

    total_liters = round(shower_total + dish_total + garden_total + laundry_total)

    breakdown_list = [
        {
            "habit": "Shower",
            "calculation": f"{shower_minutes_per_day:g} min/day × {SHOWER_LPM} L/min × {DAYS_PER_MONTH} days × {household_members} person(s)",
            "liters": round(shower_total),
            "percentage": round((shower_total / total_liters * 100) if total_liters > 0 else 0, 1),
            "icon": "shower",
        },
        {
            "habit": "Dishwashing tap",
            "calculation": f"{TAP_LPM} L/min × ~{dish_minutes} min/day × {DAYS_PER_MONTH} days",
            "liters": round(dish_total),
            "percentage": round((dish_total / total_liters * 100) if total_liters > 0 else 0, 1),
            "icon": "faucet",
        },
        {
            "habit": "Garden hose",
            "calculation": f"{garden_minutes_per_day:g} min/day × {GARDEN_HOSE_LPM} L/min × {DAYS_PER_MONTH} days",
            "liters": round(garden_total),
            "percentage": round((garden_total / total_liters * 100) if total_liters > 0 else 0, 1),
            "icon": "flower",
        },
        {
            "habit": "Washing machine",
            "calculation": f"{WASHING_MACHINE_L} L/run × ~{runs_per_month:.1f} runs/month",
            "liters": round(laundry_total),
            "percentage": round((laundry_total / total_liters * 100) if total_liters > 0 else 0, 1),
            "icon": "washing_machine",
        },
    ]

    biggest_row = max(breakdown_list, key=lambda row: row["liters"])
    biggest_waste = {"habit": biggest_row["habit"], "liters": biggest_row["liters"]}

    # Per capita calculations
    per_capita_daily = (total_liters / DAYS_PER_MONTH) / household_members
    sdg_comparison = ((per_capita_daily - SDG_BENCHMARK_LPD_PER_PERSON) / SDG_BENCHMARK_LPD_PER_PERSON) * 100

    if per_capita_daily <= 100:
        efficiency_status = "Optimal / Highly Efficient"
    elif per_capita_daily <= SDG_BENCHMARK_LPD_PER_PERSON:
        efficiency_status = "Good / Aligned with SDG 6 Target"
    elif per_capita_daily <= 200:
        efficiency_status = "Moderate / High Optimization Potential"
    else:
        efficiency_status = "Excessive / Urgent Action Recommended"

    potential_savings_liters = round(shower_savings + dish_savings + garden_savings + laundry_savings)
    potential_savings_cost = (potential_savings_liters / 1000.0) * COST_PER_1000L

    return HabitEstimateResult(
        breakdown=breakdown_list,
        total_liters=total_liters,
        household_members=household_members,
        per_capita_daily_lpd=per_capita_daily,
        sdg_benchmark_daily_lpd=SDG_BENCHMARK_LPD_PER_PERSON,
        sdg_comparison_pct=sdg_comparison,
        efficiency_status=efficiency_status,
        biggest_waste=biggest_waste,
        potential_monthly_savings_liters=potential_savings_liters,
        potential_monthly_savings_cost=potential_savings_cost,
        assumptions=assumptions,
    )


if __name__ == "__main__":
    result = estimate_monthly_usage(
        shower_minutes_per_day=12,
        tap_left_running_while_washing_dishes=True,
        garden_minutes_per_day=10,
        washing_machine_runs_per_week=3.5,
        washing_machine_half_full=True,
        household_members=3,
    )
    print(f"Total: {result.total_liters} L/mo | Per capita: {result.per_capita_daily_lpd:.1f} LPD | Status: {result.efficiency_status}")
    for item in result.breakdown:
        print(f"  {item['habit']:18s}: {item['liters']:6d} L ({item['percentage']}%)")
    print(f"Potential Savings: {result.potential_monthly_savings_liters} L/month (${result.potential_monthly_savings_cost:.2f})")

