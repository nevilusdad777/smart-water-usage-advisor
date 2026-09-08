"""
Weighted Multi-Signal Leak Risk Model
--------------------------------------
Instead of treating every leak indicator as equally important (a plain
if/else rule table), this module assigns each self-reported signal a
weight based on how strongly it correlates with an active leak,
then combines them into a single 0-100 Leak Risk Score.

Weight rationale (documented for transparency, per Responsible AI
guidelines — every number here is justified, not arbitrary):

  - meter_moves_with_taps_off : 35
      The single strongest standalone signal — a moving meter with
      zero water draw almost always means *something* is leaking.
  - bill_spike                : 25
      Strong but noisy — bills can spike for reasons unrelated to leaks
      (guests staying over, seasonal usage), so weighted below "meter".
  - damp_patches              : 20
      A physical, visible symptom — reliable but usually appears only
      after a leak has been active for a while (lagging indicator).
  - cistern_running           : 20
      Common and specific to toilet leaks specifically, not whole-house
      leaks, so weighted alongside damp patches rather than above them.

Total possible score: 100.

Risk bands:
  0        -> No Leak Detected
  1  - 49  -> Possible Minor Leak
  50 - 100 -> Likely Major Leak (multiple corroborating signals)

Estimated Loss Metrics (Benchmark standard averages):
  - Meter movement (unseen line leak): ~200 L/day (~6,000 L/month)
  - Unexplained bill spike (typical hidden leak): ~450 L/day (~13,500 L/month)
  - Damp patches (seepage / wall pipe leak): ~120 L/day (~3,600 L/month)
  - Running toilet cistern (flapper valve / overflow): ~700 L/day (~21,000 L/month)
  - Estimated average cost per 1,000 Liters: $1.50 (or local municipal equivalent)
"""

from dataclasses import dataclass, field
from typing import Dict, List


WEIGHTS: Dict[str, int] = {
    "meter_moves": 35,
    "bill_spike": 25,
    "damp_patches": 20,
    "cistern_running": 20,
}

# Estimated daily water loss in Liters per signal
ESTIMATED_DAILY_LOSS_LITERS: Dict[str, int] = {
    "meter_moves": 200,
    "bill_spike": 450,
    "damp_patches": 120,
    "cistern_running": 700,
}

# Estimated cost per 1,000 Liters ($)
COST_PER_1000L = 1.50

MINOR_THRESHOLD = 1
MAJOR_THRESHOLD = 50


@dataclass
class LeakRiskResult:
    score: int
    flag: str
    contributing_signals: Dict[str, int] = field(default_factory=dict)
    estimated_daily_loss_liters: int = 0
    estimated_monthly_loss_liters: int = 0
    estimated_monthly_cost_loss: float = 0.0
    urgency_level: str = "Low"
    detected_signal_details: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "flag": self.flag,
            "contributing_signals": self.contributing_signals,
            "estimated_daily_loss_liters": self.estimated_daily_loss_liters,
            "estimated_monthly_loss_liters": self.estimated_monthly_loss_liters,
            "estimated_monthly_cost_loss": round(self.estimated_monthly_cost_loss, 2),
            "urgency_level": self.urgency_level,
            "detected_signal_details": self.detected_signal_details,
        }


def compute_leak_risk(
    meter_moves: bool,
    bill_spike: bool,
    damp_patches: bool,
    cistern_running: bool,
) -> LeakRiskResult:
    """Compute a weighted Leak Risk Score from four self-reported signals.

    Each argument is a boolean answer to the corresponding household
    quiz question. Returns a LeakRiskResult with numeric score, flag,
    contributing signals, estimated loss metrics, and urgency level.
    """
    answers = {
        "meter_moves": meter_moves,
        "bill_spike": bill_spike,
        "damp_patches": damp_patches,
        "cistern_running": cistern_running,
    }

    contributing = {k: WEIGHTS[k] for k, v in answers.items() if v}
    score = sum(contributing.values())

    # Calculate estimated water loss
    daily_loss = sum(ESTIMATED_DAILY_LOSS_LITERS[k] for k, v in answers.items() if v)
    monthly_loss = daily_loss * 30
    monthly_cost = (monthly_loss / 1000.0) * COST_PER_1000L

    signal_descriptions = {
        "meter_moves": {
            "name": "Meter Moving with Taps Off",
            "desc": "Continuous draw indicating a pressurized line leak or hidden sub-surface split.",
            "action": "Locate main shut-off valve; inspect underground line or secondary fixtures.",
        },
        "bill_spike": {
            "name": "Unexplained Utility Bill Spike",
            "desc": "Sudden volume increase inconsistent with household occupancy or seasonal changes.",
            "action": "Cross-reference billing cycle with recent fixture upgrades or irrigation schedules.",
        },
        "damp_patches": {
            "name": "Damp Patches or Mold on Surfaces",
            "desc": "Physical water seepage behind drywall, under tiles, or around plumbing joints.",
            "action": "Inspect behind cabinetry and concealed pipe risers immediately to prevent structural damage.",
        },
        "cistern_running": {
            "name": "Running Toilet Cistern",
            "desc": "Worn flapper valve, misaligned float, or faulty fill valve letting water bypass into bowl.",
            "action": "Replace toilet flapper valve or fill mechanism (low complexity, immediate ROI).",
        },
    }

    detected_details = [
        {
            "key": k,
            "name": signal_descriptions[k]["name"],
            "weight": WEIGHTS[k],
            "estimated_daily_loss": ESTIMATED_DAILY_LOSS_LITERS[k],
            "description": signal_descriptions[k]["desc"],
            "recommended_action": signal_descriptions[k]["action"],
        }
        for k, v in answers.items()
        if v
    ]

    if score == 0:
        flag = "No Leak Detected"
        urgency = "Low"
    elif score < MAJOR_THRESHOLD:
        flag = "Possible Minor Leak"
        urgency = "Moderate"
    elif score < 75:
        flag = "Likely Major Leak"
        urgency = "High"
    else:
        flag = "Critical Multi-Point Leak"
        urgency = "Critical"

    return LeakRiskResult(
        score=score,
        flag=flag,
        contributing_signals=contributing,
        estimated_daily_loss_liters=daily_loss,
        estimated_monthly_loss_liters=monthly_loss,
        estimated_monthly_cost_loss=monthly_cost,
        urgency_level=urgency,
        detected_signal_details=detected_details,
    )


if __name__ == "__main__":
    scenarios = {
        "A - Efficient (no leak)": dict(meter_moves=False, bill_spike=False, damp_patches=False, cistern_running=False),
        "B - Minor leak":          dict(meter_moves=True,  bill_spike=False, damp_patches=False, cistern_running=False),
        "C - Wasteful, no leak":   dict(meter_moves=False, bill_spike=False, damp_patches=False, cistern_running=False),
        "D - Major leak":         dict(meter_moves=True,  bill_spike=True,  damp_patches=True,  cistern_running=True),
    }
    for name, answers in scenarios.items():
        result = compute_leak_risk(**answers)
        print(f"{name:28s} -> score={result.score:3d} | flag={result.flag:25s} | Est Loss={result.estimated_monthly_loss_liters:6d} L/mo (${result.estimated_monthly_cost_loss:.2f})")

