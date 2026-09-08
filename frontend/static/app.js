// ==========================================================================
// Smart Water Usage Advisor — Frontend Application Logic
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  // Global Answers State
  const answers = {
    meter_moves: false,
    bill_spike: false,
    damp_patches: false,
    cistern_running: false,
  };

  let currentHabitData = null;

  // --------------------------------------------------------------------------
  // 1. Navigation Tabs
  // --------------------------------------------------------------------------
  const tabBtns = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.panel');

  tabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      tabBtns.forEach((b) => b.classList.remove('active'));
      panels.forEach((p) => p.classList.remove('active'));

      btn.classList.add('active');
      const tabName = btn.dataset.tab;
      const targetId = `panel-${tabName}`;
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) {
        targetPanel.classList.add('active');
      }
      if (tabName === 'savings' && currentHabitData) {
        updateSavingsPlanner(currentHabitData);
      }
    });
  });

  // --------------------------------------------------------------------------
  // 2. Interactive Form Controls (Sliders, Stepper, Y/N Toggles)
  // --------------------------------------------------------------------------
  // Stepper for Members Count
  const membersInput = document.getElementById('members');
  const btnStepDown = document.getElementById('btnStepDown');
  const btnStepUp = document.getElementById('btnStepUp');

  btnStepDown.addEventListener('click', () => {
    let val = parseInt(membersInput.value) || 1;
    if (val > 1) {
      membersInput.value = val - 1;
    }
  });

  btnStepUp.addEventListener('click', () => {
    let val = parseInt(membersInput.value) || 1;
    if (val < 10) {
      membersInput.value = val + 1;
    }
  });

  // Sliders Live Preview
  const showerInput = document.getElementById('shower');
  const showerVal = document.getElementById('showerVal');
  showerInput.addEventListener('input', () => {
    showerVal.textContent = showerInput.value;
  });

  const gardenInput = document.getElementById('garden');
  const gardenVal = document.getElementById('gardenVal');
  gardenInput.addEventListener('input', () => {
    gardenVal.textContent = gardenInput.value;
  });

  // Quiz Yes/No Toggles
  document.querySelectorAll('.yn-toggle').forEach((group) => {
    const q = group.dataset.q;
    if (!q) return;
    group.querySelectorAll('button').forEach((b) => {
      b.addEventListener('click', () => {
        group.querySelectorAll('button').forEach((x) => x.classList.remove('selected'));
        b.classList.add('selected');
        answers[q] = b.dataset.val === 'yes';
      });
    });
  });

  // --------------------------------------------------------------------------
  // 3. Preset Scenarios Quick Loader
  // --------------------------------------------------------------------------
  async function loadScenarios() {
    try {
      const res = await fetch('/api/scenarios');
      if (!res.ok) return;
      const scenarios = await res.json();
      const container = document.getElementById('scenarioButtons');
      container.innerHTML = '';

      scenarios.forEach((s) => {
        const btn = document.createElement('button');
        btn.className = 'btn-preset';
        btn.textContent = s.name;
        btn.addEventListener('click', () => applyScenario(s));
        container.appendChild(btn);
      });
    } catch (e) {
      console.warn('Scenarios load error:', e);
    }
  }

  function applyScenario(scenario) {
    // 1. Set Quiz answers
    for (const key in scenario.leak) {
      answers[key] = scenario.leak[key];
      const toggle = document.querySelector(`.yn-toggle[data-q="${key}"]`);
      if (toggle) {
        toggle.querySelectorAll('button').forEach((b) => {
          b.classList.toggle('selected', (b.dataset.val === 'yes') === scenario.leak[key]);
        });
      }
    }

    // 2. Set Habit fields
    if (scenario.habit) {
      document.getElementById('shower').value = scenario.habit.shower;
      showerVal.textContent = scenario.habit.shower;

      document.getElementById('tapDishes').value = scenario.habit.tapDishes;

      document.getElementById('garden').value = scenario.habit.garden;
      gardenVal.textContent = scenario.habit.garden;

      document.getElementById('laundry').value = scenario.habit.laundry;
      document.getElementById('laundryFreq').value = scenario.habit.laundryFreq;
      document.getElementById('members').value = scenario.habit.members;
    }

    // 3. Automatically run calculation for both tabs to keep panels in sync
    runLeakAssessment();
    runHabitAssessment();
  }

  // --------------------------------------------------------------------------
  // 4. SVG Gauge Ring Animation
  let gaugeTimer = null;

  function setGaugeScore(score) {
    const progressCircle = document.getElementById('gaugeProgress');
    const scoreVal = document.getElementById('leakScoreVal');
    const maxOffset = 326.7; // 2 * PI * 52

    // Clear any existing counter animation timer immediately
    if (gaugeTimer) {
      clearInterval(gaugeTimer);
      gaugeTimer = null;
    }

    // Calculate offset
    const offset = maxOffset - (score / 100) * maxOffset;
    progressCircle.style.strokeDashoffset = offset;

    // Color based on risk level
    if (score === 0) {
      progressCircle.style.stroke = '#10b981'; // emerald
    } else if (score < 50) {
      progressCircle.style.stroke = '#d97706'; // amber
    } else {
      progressCircle.style.stroke = '#dc2626'; // crimson
    }

    // Smooth counter animation from current displayed value to target score
    let current = parseInt(scoreVal.textContent) || 0;
    if (current === score) {
      scoreVal.textContent = score;
      return;
    }

    const step = current < score ? 1 : -1;
    gaugeTimer = setInterval(() => {
      current += step;
      scoreVal.textContent = current;
      if ((step > 0 && current >= score) || (step < 0 && current <= score)) {
        scoreVal.textContent = score;
        clearInterval(gaugeTimer);
        gaugeTimer = null;
      }
    }, 15);
  }

  // --------------------------------------------------------------------------
  // 5. Leak Detection API Execution
  // --------------------------------------------------------------------------
  async function runLeakAssessment() {
    const runBtn = document.getElementById('runLeak');
    runBtn.disabled = true;
    runBtn.style.opacity = '0.7';

    const urgencyBadge = document.getElementById('leakUrgencyBadge');
    const flagBadge = document.getElementById('leakFlagBadge');
    const estWater = document.getElementById('leakEstWater');
    const estCost = document.getElementById('leakEstCost');
    const signalsList = document.getElementById('leakSignalsList');
    const aiText = document.getElementById('leakAiText');
    const loading = document.getElementById('leakLoading');

    try {
      // 1. Fetch risk calculation
      const res = await fetch('/api/leak-risk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(answers),
      });
      const data = await res.json();

      // 2. Render Gauge & Metrics
      setGaugeScore(data.score);

      flagBadge.textContent = data.flag;
      urgencyBadge.textContent = `Urgency: ${data.urgency_level}`;
      urgencyBadge.className = 'status-pill ' + (data.score === 0 ? 'green' : data.score < 50 ? 'amber' : 'red');

      estWater.textContent = `${data.estimated_monthly_loss_liters.toLocaleString()} L`;
      estCost.textContent = `$${data.estimated_monthly_cost_loss.toFixed(2)}`;

      // 3. Render Signals List
      if (data.detected_signal_details && data.detected_signal_details.length > 0) {
        signalsList.innerHTML = data.detected_signal_details
          .map(
            (s) => `
          <div class="signal-card">
            <div class="signal-card-header">
              <span>⚠️ ${s.name}</span>
              <span style="color:var(--red-val);">+${s.weight} pts</span>
            </div>
            <div class="signal-card-action">Action: ${s.recommended_action}</div>
          </div>
        `
          )
          .join('');
      } else {
        signalsList.innerHTML = `
          <div class="empty-state">✅ No active leak signals detected. All monitoring checks clean!</div>
        `;
      }

      // 4. Fetch AI explanation
      loading.style.display = 'flex';
      aiText.style.display = 'none';

      const aiRes = await fetch('/api/explain-leak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers,
          score: data.score,
          flag: data.flag,
          details: data.detected_signal_details,
        }),
      });
      const aiData = await aiRes.json();

      loading.style.display = 'none';
      aiText.style.display = 'block';
      aiText.textContent = aiData.explanation;
    } catch (err) {
      console.error(err);
      loading.style.display = 'none';
      aiText.style.display = 'block';
      aiText.textContent = 'Unable to fetch leak calculation. Please check backend API server.';
    } finally {
      runBtn.disabled = false;
      runBtn.style.opacity = '1';
    }
  }

  document.getElementById('runLeak').addEventListener('click', runLeakAssessment);

  // --------------------------------------------------------------------------
  // 6. Habit Advisor API Execution & Bar Chart Rendering
  // --------------------------------------------------------------------------
  async function runHabitAssessment() {
    const runBtn = document.getElementById('runHabit');
    runBtn.disabled = true;
    runBtn.style.opacity = '0.7';

    const payload = {
      shower_minutes_per_day: parseFloat(document.getElementById('shower').value) || 0,
      tap_left_running_while_washing_dishes: document.getElementById('tapDishes').value === 'on',
      garden_minutes_per_day: parseFloat(document.getElementById('garden').value) || 0,
      washing_machine_runs_per_week: parseFloat(document.getElementById('laundryFreq').value) || 0,
      washing_machine_half_full: document.getElementById('laundry').value === 'half',
      household_members: parseInt(document.getElementById('members').value) || 3,
    };

    const statusBadge = document.getElementById('habitEfficiencyStatus');
    const totalLiters = document.getElementById('habitTotalLiters');
    const perCapita = document.getElementById('habitPerCapita');
    const savingsVal = document.getElementById('habitSavingsVal');
    const stackedBar = document.getElementById('stackedBar');
    const breakdownGrid = document.getElementById('breakdownGrid');
    const assumptionsList = document.getElementById('habitAssumptionsList');
    const aiText = document.getElementById('habitAiText');
    const loading = document.getElementById('habitLoading');

    try {
      const res = await fetch('/api/habit-estimate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      currentHabitData = data;

      // Update Summary Cards
      statusBadge.textContent = data.efficiency_status;
      statusBadge.className = 'status-pill ' + (data.per_capita_daily_lpd <= 135 ? 'green' : data.per_capita_daily_lpd <= 200 ? 'amber' : 'red');

      totalLiters.textContent = `${data.total_liters.toLocaleString()} L`;
      perCapita.textContent = `${data.per_capita_daily_lpd.toFixed(1)} LPD`;
      savingsVal.textContent = `${data.potential_monthly_savings_liters.toLocaleString()} L/mo`;

      // Update Stacked Bar Chart
      stackedBar.innerHTML = data.breakdown
        .map((b) => `<div class="bar-segment ${b.icon}" style="width: ${b.percentage}%;" title="${b.habit}: ${b.percentage}%"></div>`)
        .join('');

      // Update Breakdown Grid
      breakdownGrid.innerHTML = data.breakdown
        .map(
          (b) => `
        <div class="breakdown-item">
          <div>
            <div class="breakdown-item-title">${b.habit}</div>
            <div class="breakdown-item-sub">${b.calculation}</div>
          </div>
          <div class="breakdown-item-val">${b.liters.toLocaleString()} L</div>
        </div>
      `
        )
        .join('');

      // Update Assumptions List
      assumptionsList.innerHTML = data.assumptions.map((a) => `<div>• ${a}</div>`).join('');

      // Update Savings Planner tab metrics
      updateSavingsPlanner(data);

      // Fetch AI habit advice
      loading.style.display = 'flex';
      aiText.style.display = 'none';

      const aiRes = await fetch('/api/explain-habit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      const aiData = await aiRes.json();

      loading.style.display = 'none';
      aiText.style.display = 'block';
      aiText.textContent = aiData.explanation;
    } catch (err) {
      console.error(err);
      loading.style.display = 'none';
      aiText.style.display = 'block';
      aiText.textContent = 'Unable to calculate habit estimate. Please check backend API server.';
    } finally {
      runBtn.disabled = false;
      runBtn.style.opacity = '1';
    }
  }

  document.getElementById('runHabit').addEventListener('click', runHabitAssessment);

  // --------------------------------------------------------------------------
  // 7. Savings Simulator Logic
  // --------------------------------------------------------------------------
  function updateSavingsPlanner(habitData) {
    if (!habitData) return;

    const currentLpd = document.getElementById('plannerCurrentLpd');
    const statusPct = document.getElementById('plannerStatusPct');
    const statusLbl = document.getElementById('plannerStatusLbl');

    currentLpd.textContent = `${habitData.per_capita_daily_lpd.toFixed(1)} LPD`;
    const diffPct = habitData.sdg_comparison_pct;

    if (diffPct > 0) {
      statusPct.textContent = `+${diffPct.toFixed(1)}%`;
      statusPct.style.color = 'var(--red-val)';
      statusLbl.textContent = 'Above SDG 6 Target';
    } else {
      statusPct.textContent = `${diffPct.toFixed(1)}%`;
      statusPct.style.color = 'var(--emerald-accent)';
      statusLbl.textContent = 'Under SDG 6 Target (Optimal)';
    }

    calculateSimulator();
  }

  const simShower = document.getElementById('simShower');
  const simShowerVal = document.getElementById('simShowerVal');
  const simTapToggle = document.getElementById('simTapToggle');

  let simTapFixed = true;

  simShower.addEventListener('input', () => {
    simShowerVal.textContent = simShower.value;
    calculateSimulator();
  });

  simTapToggle.querySelectorAll('button').forEach((btn) => {
    btn.addEventListener('click', () => {
      simTapToggle.querySelectorAll('button').forEach((b) => b.classList.remove('selected'));
      btn.classList.add('selected');
      simTapFixed = btn.dataset.val === 'yes';
      document.getElementById('simTapVal').textContent = simTapFixed ? 'Yes' : 'No';
      calculateSimulator();
    });
  });

  function calculateSimulator() {
    const members = parseInt(document.getElementById('members').value) || 3;
    const showerReduceMins = parseInt(simShower.value) || 0;

    // Shower savings: 9 L/min * reduceMins * 365 days * members
    const annualShowerSavings = showerReduceMins * 9 * 365 * members;
    // Tap fix savings: ~8 min * 6 L/min * 365 days
    const annualTapSavings = simTapFixed ? 8 * 6 * 365 : 0;

    const totalAnnualLiters = annualShowerSavings + annualTapSavings;
    const totalAnnualMoney = (totalAnnualLiters / 1000.0) * 1.5;
    const treesEquiv = Math.round(totalAnnualLiters / 15); // ~15L/day tree watering

    document.getElementById('simAnnualLiters').textContent = `${totalAnnualLiters.toLocaleString()} L`;
    document.getElementById('simAnnualMoney').textContent = `$${totalAnnualMoney.toFixed(2)}`;
    document.getElementById('simTreesEquiv').textContent = `${treesEquiv.toLocaleString()} Days`;
  }

  // --------------------------------------------------------------------------
  // 8. Printable Sustainability Report
  // --------------------------------------------------------------------------
  document.getElementById('btnPrintReport').addEventListener('click', () => {
    window.print();
  });

  // Initial setup
  loadScenarios();
  runLeakAssessment();
  runHabitAssessment();
});

