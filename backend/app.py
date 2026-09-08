"""
Smart Water Usage Advisor — Flask API
---------------------------------------
Exposes the leak-risk and habit-estimate models as JSON endpoints, and
proxies natural-language explanation requests to an LLM server-side
(so the API key never reaches the browser). Also includes intelligent
rule-guided offline fallbacks so the app works seamlessly even without an API key.

Run locally:
    python backend/app.py

Then open http://localhost:5000 in your browser.
"""

import os
import sys
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

STATIC_DIR = os.path.join(BASE_DIR, "..", "frontend", "static")
TEMPLATE_DIR = os.path.join(BASE_DIR, "..", "frontend", "templates")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
except ImportError:
    _client = None


def generate_leak_fallback(score: int, flag: str, answers: dict, details: list) -> str:
    """Generate a high-quality, professional structured explanation when LLM API key is not active."""
    if score == 0:
        return (
            "✅ Excellent news! Based on your responses, no active leak indicators were detected. "
            "Your water meter remains stationary when fixtures are off, and no dampness or bill anomalies were reported. "
            "\n\n💡 Next Steps:\n"
            "• Perform a routine monthly check of your water meter before and after a 2-hour no-use period.\n"
            "• Keep monitoring monthly utility bills for unexpected step-changes."
        )
    
    signals = [d["name"] for d in details]
    signals_str = ", ".join(signals) if signals else "reported signals"

    if score < 50:
        return (
            f"⚠️ Moderate Attention Advised — Leak Risk Score: {score}/100 ({flag}).\n"
            f"We detected specific potential leak indicators: {signals_str}.\n\n"
            f"💡 Recommended Actions:\n"
            f"1. Isolate the affected fixture (e.g. check toilet tank flappers or inspect wall dampness).\n"
            f"2. Conduct a 15-minute static meter observation while keeping all interior/exterior taps turned off."
        )
    else:
        return (
            f"🚨 Urgent Action Required — Leak Risk Score: {score}/100 ({flag}).\n"
            f"Multiple corroborating signals indicate an active leak ({signals_str}). "
            f"Unchecked leaks at this level can waste thousands of liters monthly and cause structural wall dampness.\n\n"
            f"💡 Immediate Action Plan:\n"
            f"1. Locate and test your household main water shut-off valve.\n"
            f"2. Contact a licensed plumbing professional immediately to perform pressure testing on main lines.\n"
            f"3. Check toilet cisterns for continuous overflow bypass."
        )


def generate_habit_fallback(total_liters: int, biggest_waste: dict, per_capita: float, sdg_target: float, savings_l: int, savings_cost: float) -> str:
    """Generate a rich, structured habit insight fallback when LLM API key is not active."""
    habit_name = biggest_waste.get("habit", "Shower")
    liters = biggest_waste.get("liters", 0)

    msg = (
        f"🎯 Primary Conservation Opportunity: Your single largest water consumer is **{habit_name}** at {liters:,} Liters/month.\n"
        f"Your current daily consumption is **{per_capita:.1f} LPD per person** (UN SDG 6 baseline target: {sdg_target:g} LPD).\n\n"
        f"🌱 Top Actionable Tips:\n"
        f"1. **Target {habit_name} Optimization**: Installing eco-flow restrictors or adjusting daily habit duration can save up to {savings_l:,} Liters monthly.\n"
        f"2. **Habit Consolidation**: Turn off taps during brushing/scrubbing and ensure appliances (laundry/dishwashers) run full loads only."
    )
    if savings_cost > 0:
        msg += f"\n\n💰 Estimated Savings Impact: Up to **{savings_l:,} L/month** saved (~${savings_cost:.2f}/month on utility bills)."

    return msg


def call_llm(prompt: str, fallback_text: str = "") -> str:
    """Call Claude if an API key is configured, else return a structured fallback."""
    if _client is None:
        return fallback_text
    try:
        response = _client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if hasattr(block, "text")).strip()
    except Exception:
        return fallback_text


@app.route("/")
def index():
    return send_from_directory(TEMPLATE_DIR, "index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.errorhandler(Exception)
def handle_exception(e):
    """Ensure API errors return structured JSON instead of HTML error pages."""
    response = jsonify({"error": str(e), "status": "error"})
    response.status_code = getattr(e, "code", 500)
    return response


@app.route("/api/scenarios", methods=["GET"])
def api_scenarios():
    """Return preset test cases for instant 1-click evaluation in UI."""
    return jsonify([
        {
            "id": "efficient_home",
            "name": "🌱 Eco Champion Household",
            "desc": "Low consumption, short showers, no active leaks detected.",
            "leak": {"meter_moves": False, "bill_spike": False, "damp_patches": False, "cistern_running": False},
            "habit": {"shower": 5, "tapDishes": "off", "garden": 2, "laundry": "full", "laundryFreq": 2, "members": 3}
        },
        {
            "id": "minor_toilet_leak",
            "name": "🚽 Running Toilet & Moderate Habits",
            "desc": "Silent cistern leakage creating hidden ongoing water waste.",
            "leak": {"meter_moves": False, "bill_spike": True, "damp_patches": False, "cistern_running": True},
            "habit": {"shower": 10, "tapDishes": "on", "garden": 10, "laundry": "half", "laundryFreq": 4, "members": 3}
        },
        {
            "id": "major_line_leak",
            "name": "🚨 High Risk Pipe Leak",
            "desc": "Moving meter with taps off, bill spike, and damp patches.",
            "leak": {"meter_moves": True, "bill_spike": True, "damp_patches": True, "cistern_running": True},
            "habit": {"shower": 15, "tapDishes": "on", "garden": 20, "laundry": "half", "laundryFreq": 5, "members": 4}
        }
    ])


@app.route("/api/leak-risk", methods=["POST"])
def api_leak_risk():
    data = request.get_json(force=True) or {}
    result = compute_leak_risk(
        meter_moves=bool(data.get("meter_moves")),
        bill_spike=bool(data.get("bill_spike")),
        damp_patches=bool(data.get("damp_patches")),
        cistern_running=bool(data.get("cistern_running")),
    )
    return jsonify(result.to_dict())


@app.route("/api/explain-leak", methods=["POST"])
def api_explain_leak():
    data = request.get_json(force=True) or {}
    score = int(data.get('score', 0))
    flag = str(data.get('flag', 'No Leak Detected'))
    answers = data.get('answers', {})
    details = data.get('details', [])

    fallback = generate_leak_fallback(score, flag, answers, details)

    prompt = f"""You are a water-conservation assistant. A household answered a leak-check quiz.
Given their answers and resulting flag, explain the result in 2-3 simple sentences and give 2 concrete next steps. Do not use technical jargon. Be reassuring if the flag is "No Leak Detected."

Answers: {answers}
Leak Risk Score: {score}/100
Flag: {flag}

Output only the explanation and next steps, no preamble."""

    explanation = call_llm(prompt, fallback_text=fallback)
    return jsonify({"explanation": explanation})


@app.route("/api/habit-estimate", methods=["POST"])
def api_habit_estimate():
    data = request.get_json(force=True) or {}
    result = estimate_monthly_usage(
        shower_minutes_per_day=float(data.get("shower_minutes_per_day", 0)),
        tap_left_running_while_washing_dishes=bool(data.get("tap_left_running_while_washing_dishes")),
        garden_minutes_per_day=float(data.get("garden_minutes_per_day", 0)),
        washing_machine_runs_per_week=float(data.get("washing_machine_runs_per_week", 0)),
        washing_machine_half_full=bool(data.get("washing_machine_half_full")),
        household_members=int(data.get("household_members", 3)),
    )
    return jsonify(result.to_dict())


@app.route("/api/explain-habit", methods=["POST"])
def api_explain_habit():
    data = request.get_json(force=True) or {}
    total = data.get('total_liters', 0)
    biggest = data.get('biggest_waste', {})
    per_capita = float(data.get('per_capita_daily_lpd', 0))
    sdg_target = float(data.get('sdg_benchmark_daily_lpd', 135))
    savings_l = int(data.get('potential_monthly_savings_liters', 0))
    savings_cost = float(data.get('potential_monthly_savings_cost', 0))

    fallback = generate_habit_fallback(total, biggest, per_capita, sdg_target, savings_l, savings_cost)

    prompt = f"""You are a water-saving advisor. A household's estimated monthly water use breakdown is below.
Identify the single biggest area of waste ({biggest.get('habit')} at {biggest.get('liters')} L/month) and give 2 personalized, practical, encouraging tips to reduce it.

Total: {total} L/month
Per-capita daily: {per_capita} LPD (Target: {sdg_target} LPD)

Output only the biggest-waste callout in one sentence, then 2 short tips."""

    explanation = call_llm(prompt, fallback_text=fallback)
    return jsonify({"explanation": explanation})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

