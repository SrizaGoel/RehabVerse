const WS_URL = 'ws://localhost:8765';
let ws = null;

const screens = {
  intro: document.getElementById('screen-intro'),
  gameplay: document.getElementById('screen-gameplay'),
  summary: document.getElementById('screen-summary'),
  records: document.getElementById('screen-records'),
};

function showScreen(name) {
  Object.entries(screens).forEach(([key, el]) => el.classList.toggle('active', key === name));
}

function connect() {
  ws = new WebSocket(WS_URL);
  ws.onopen = () => console.log('[archers_draw] connected');
  ws.onclose = () => setTimeout(connect, 1000);
  ws.onerror = () => ws.close();
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'state') render(msg);
  };
}

function send(key) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ key }));
}

document.addEventListener('keydown', (e) => {
  const k = e.key.toLowerCase();
  const map = { ' ': 'space', 'e': 'e', 'p': 'p', 'r': 'r', 't': 't', 'b': 'b' };
  const key = e.code === 'Space' ? 'space' : map[k];
  if (key) {
    e.preventDefault();
    send(key);
  }
});

// ----------------------------------------------------------------
function qualityColor(value) {
  if (value >= 0.8) return 'var(--sea-green)';
  if (value >= 0.5) return 'var(--gold)';
  return 'var(--sunset)';
}

function fmtTime(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, '0')}`;
}

const GRADE_MESSAGES = {
  WIDE: 'WIDE OF THE MARK',
  INNER_RING: 'INNER RING',
  BULLSEYE: 'BULLSEYE',
  PERFECT_SHOT: 'PERFECT SHOT',
};

const STATE_PROMPTS = {
  CALIBRATING: 'FIND YOUR STANCE',
  IDLE: 'DRAW YOUR BOW ARM BACK',
  DRAWING: 'DRAWING...',
  HOLDING: 'HOLD AT FULL DRAW - CHARGING',
  FULL_DRAW: 'RELEASE THE SHOT',
  RELEASING: 'RELEASING - CONTROL THE RETURN',
  PAUSED: 'PAUSED (p to resume)',
};

// ----------------------------------------------------------------
function render(msg) {
  showScreen(msg.screen);
  if (msg.screen === 'intro') renderIntro(msg);
  else if (msg.screen === 'gameplay') renderGameplay(msg);
  else if (msg.screen === 'summary') renderSummary(msg);
  else if (msg.screen === 'records') renderRecords(msg);
}

function renderIntro(msg) {
  const c = msg.campaign;
  document.getElementById('intro-chapter').textContent =
    `CHAPTER ${c.chapter_index + 1}: ${c.chapter_name.toUpperCase()}`;
  document.getElementById('intro-story').textContent = c.chapter_story;
  document.getElementById('intro-day').textContent = `DAY ${c.day_number}`;
  document.getElementById('intro-streak').textContent =
    `Streak: ${c.streak} day${c.streak !== 1 ? 's' : ''}`;
  document.getElementById('rx-depth').textContent = `${Math.round(c.prescription.target_draw_depth)}\u00b0`;
  document.getElementById('rx-hold').textContent = `${c.prescription.hold_seconds.toFixed(1)}s`;
  document.getElementById('rx-arrows').textContent = c.prescription.arrow_target;
  document.getElementById('rx-time').textContent = `${Math.round(c.prescription.time_limit_seconds / 60)} min`;
}

function renderGameplay(msg) {
  const feed = document.getElementById('camera-feed');
  if (msg.jpeg_b64) feed.src = 'data:image/jpeg;base64,' + msg.jpeg_b64;

  const s = msg.session, c = msg.campaign;
  document.getElementById('hud-chapter').textContent = c.chapter_name.toUpperCase();
  document.getElementById('hud-angle').textContent = msg.elbow_angle.toFixed(0);

  const depthEl = document.getElementById('hud-depth');
  depthEl.textContent = msg.draw_depth.toFixed(0);
  const depthFrac = s.target_draw_depth > 0 ? msg.draw_depth / s.target_draw_depth : 0;
  depthEl.style.color = qualityColor(Math.min(1, depthFrac));

  document.getElementById('hud-shots').textContent = `${s.shots_done} / ${s.arrow_target}`;
  document.getElementById('hud-best').textContent = s.best_score;
  document.getElementById('hud-trophies').textContent = s.trophy_count;

  const lastEl = document.getElementById('hud-last');
  if (msg.last_score) {
    lastEl.textContent = `Last: ${msg.last_score.total}  ${msg.last_score.grade.replace('_', ' ')}`;
    lastEl.style.color = qualityColor(msg.last_score.total / 100);
  } else {
    lastEl.textContent = '';
  }

  document.getElementById('hud-progress-fill').style.width = `${s.progress_fraction * 100}%`;

  const timerBox = document.getElementById('timer-box');
  const timerVal = document.getElementById('timer-value');
  if (s.is_overtime) {
    timerBox.classList.add('overtime');
    document.querySelector('.timer-label').textContent = 'TIME (OVER)';
    timerVal.textContent = '+' + fmtTime(-s.remaining);
  } else {
    timerBox.classList.remove('overtime');
    document.querySelector('.timer-label').textContent = 'TIME LEFT';
    timerVal.textContent = fmtTime(s.remaining);
  }

  // draw-charge ring, visible while holding/full-draw
  const ringWrap = document.getElementById('draw-ring-wrap');
  const ringFill = document.getElementById('draw-ring-fill');
  const showRing = msg.arrow_state === 'HOLDING' || msg.arrow_state === 'FULL_DRAW';
  ringWrap.classList.toggle('active', showRing);
  if (showRing) {
    const circumference = 326.7;
    ringFill.style.strokeDashoffset = String(circumference * (1 - msg.charge_fraction));
  }

  // prompt text
  const promptEl = document.getElementById('prompt-text');
  if (msg.arrow_state === 'ARROW_SCORED' && msg.last_score) {
    promptEl.textContent = GRADE_MESSAGES[msg.last_score.grade] || '';
    promptEl.style.color = qualityColor(msg.last_score.total / 100);
    promptEl.style.top = '38%';
  } else {
    promptEl.textContent = STATE_PROMPTS[msg.arrow_state] || '';
    promptEl.style.color = 'var(--neon-blue)';
    promptEl.style.top = '38%';
  }
}

function setGauge(circleEl, valueEl, frac, text) {
  const circumference = 427.3;
  circleEl.style.strokeDashoffset = String(circumference * (1 - Math.max(0, Math.min(1, frac))));
  valueEl.textContent = text;
}

function renderSummary(msg) {
  const s = msg.session, c = msg.campaign;
  const completed = s.shots_done >= s.arrow_target;

  document.getElementById('summary-title').textContent =
    completed ? 'TARGET RECLAIMED' : 'GREAT EFFORT TODAY';

  // hold-quality gauge uses the last score's hold component as a stand-in
  // for "form quality" headline (falls back to 0 if no shots yet)
  const holdFrac = msg.last_score ? msg.last_score.hold : 0;
  setGauge(document.getElementById('gauge-hold'), document.getElementById('gauge-hold-value'),
           holdFrac, `${Math.round(holdFrac * 100)}%`);

  const scoreFrac = s.best_score / 100;
  setGauge(document.getElementById('gauge-score'), document.getElementById('gauge-score-value'),
           scoreFrac, String(s.best_score));

  document.getElementById('perf-shots').textContent = `${s.shots_done} / ${s.arrow_target}`;
  document.getElementById('perf-clean').textContent = s.clean_hits;
  document.getElementById('perf-wide').textContent = s.wide_hits;
  document.getElementById('perf-trophies').textContent = s.trophy_count;
  document.getElementById('perf-best').textContent = s.best_score;
  document.getElementById('perf-depth').textContent = `${Math.round(s.session_max_depth)} deg`;
  document.getElementById('perf-duration').textContent = fmtTime(s.elapsed);

  const drawVal = msg.last_score ? msg.last_score.draw_smoothness : 0;
  const releaseVal = msg.last_score ? msg.last_score.release_smoothness : 0;
  document.getElementById('bar-draw-value').textContent = `${Math.round(drawVal * 100)}%`;
  document.getElementById('bar-draw-fill').style.width = `${drawVal * 100}%`;
  document.getElementById('bar-draw-fill').style.background = qualityColor(drawVal);
  document.getElementById('bar-release-value').textContent = `${Math.round(releaseVal * 100)}%`;
  document.getElementById('bar-release-fill').style.width = `${releaseVal * 100}%`;
  document.getElementById('bar-release-fill').style.background = qualityColor(releaseVal);

  const needed = c.chapter_arrows_to_clear;
  const frac = needed > 0 ? Math.min(1, c.total_clears / needed) : 0;
  document.getElementById('chapter-progress-text').textContent =
    `CHAPTER ${c.chapter_index + 1}: ${c.chapter_name.toUpperCase()}  (${c.total_clears}/${needed} arrows)`;
  document.getElementById('chapter-progress-fill').style.width = `${frac * 100}%`;

  document.getElementById('summary-meta').textContent =
    `Day ${c.day_number} complete   |   ${c.streak} day streak   |   Sessions today: ${c.sessions_today}`;
}

function renderRecords(msg) {
  const data = msg.records_data;
  const empty = document.getElementById('records-empty');
  const content = document.getElementById('records-content');

  if (!data) {
    empty.style.display = 'block';
    content.style.display = 'none';
    return;
  }
  empty.style.display = 'none';
  content.style.display = 'block';

  const fill = (prefix, stats) => {
    document.getElementById(`rec-${prefix}-score`).textContent = stats.best_score;
    document.getElementById(`rec-${prefix}-shots`).textContent = stats.max_shots;
    document.getElementById(`rec-${prefix}-clean`).textContent = stats.max_clean_hits;
    document.getElementById(`rec-${prefix}-sessions`).textContent = stats.sessions;
  };
  fill('today', data.today);
  fill('week', data.this_week);
  fill('all', data.all_time);

  drawChart(data.daily_shots);
}

function drawChart(series) {
  const canvas = document.getElementById('chart-canvas');
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const maxVal = Math.max(1, ...series.map(([, v]) => v));
  const padX = 30, padY = 20;
  const plotW = w - padX * 2, plotH = h - padY * 2 - 20;

  const pts = series.map(([, v], i) => {
    const x = padX + (plotW * i) / Math.max(1, series.length - 1);
    const y = padY + plotH - (plotH * v) / maxVal;
    return [x, y];
  });

  ctx.strokeStyle = '#4fc3f7';
  ctx.lineWidth = 3;
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
  ctx.stroke();

  pts.forEach(([x, y], i) => {
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#e8b04b';
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = '#fff';
    ctx.stroke();

    if (i % 2 === 0) {
      ctx.fillStyle = '#aeb8c2';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(series[i][0].slice(5), x, h - 4);
    }
  });
}

connect();
