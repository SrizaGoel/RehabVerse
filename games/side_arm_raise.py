
import cv2
import mediapipe as mp
import numpy as np
from collections import deque
import json, os, sys, time, math
from datetime import date

# ══════════════════════════════════════════════════════
#  MediaPipe
# ══════════════════════════════════════════════════════
mp_pose    = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

pose = mp_pose.Pose(
    model_complexity=1,
    min_detection_confidence=0.55,
    min_tracking_confidence=0.55,
    smooth_landmarks=True,
)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
cap.set(cv2.CAP_PROP_FPS, 30)

# ══════════════════════════════════════════════════════
#  Layout constants  (single-panel, no overlap)
# ══════════════════════════════════════════════════════
WIN_W, WIN_H   = 1280, 760
CAM_W, CAM_H   = 960, 540
PANEL_W        = WIN_W - CAM_W          # 320 px — one panel only
CAM_X, CAM_Y   = 0, 0
BOT_H          = WIN_H - CAM_H          # 220 px bottom bar
BOT_Y          = CAM_H

# ══════════════════════════════════════════════════════
#  TUNABLE CONSTANTS — 8-week programme
#  rom  = fixed ROM target (deg) for every day of that week
#  hold = FINAL hold-time target (sec) reached by Day7-PM
#  reps = FINAL rep-count target reached by Day7-PM
# ══════════════════════════════════════════════════════
WEEK_PROG = [
    {"rom": 30,  "hold": 20, "reps": 10, "name": "Pendulum Swings"},
    {"rom": 45,  "hold": 25, "reps": 12, "name": "Table Slide"},
    {"rom": 60,  "hold": 30, "reps": 15, "name": "Wall Crawl (Low)"},
    {"rom": 75,  "hold": 35, "reps": 15, "name": "Assisted Forward Reach"},
    {"rom": 90,  "hold": 40, "reps": 18, "name": "Shoulder-Height Reach"},
    {"rom": 110, "hold": 45, "reps": 20, "name": "Comb Hair / Eye-Level Shelf"},
    {"rom": 130, "hold": 50, "reps": 20, "name": "Overhead Cabinet Reach"},
    {"rom": 150, "hold": 60, "reps": 25, "name": "Full Overhead / Swim Reach"},
]
DAYS_PER_WEEK   = 7
START_FRACTION  = 0.50   # week-1 day-1 starting hold/reps = 50% of week-1 final
MISS_HOLD_PENALTY_PER_SLOT = 2     # seconds shaved off target per missed slot
MISS_REPS_PENALTY_PER_SLOT = 1     # reps shaved off target per missed slot
MAX_PENALTY_FRACTION = 0.40        # never reduce a target by more than 40%

def lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))

def week_start_targets(week_idx):
    """Baseline hold/reps a week's Day-1 ramps up FROM."""
    if week_idx == 0:
        f = WEEK_PROG[0]
        return f["hold"] * START_FRACTION, f["reps"] * START_FRACTION
    prev = WEEK_PROG[week_idx - 1]
    return prev["hold"], prev["reps"]

def compute_target(week_idx, day, slot):
    """
    ROM  -> constant across the whole week.
    HOLD -> ramps once per day (same value for AM & PM of that day).
    REPS -> ramps once per evening; the AM session carries the PREVIOUS
            day's evening rep-count (i.e. reps only ever go up at night).
    """
    week_idx = min(week_idx, len(WEEK_PROG) - 1)
    wk = WEEK_PROG[week_idx]
    hold_start, reps_start = week_start_targets(week_idx)

    day_hold = lerp(hold_start, wk["hold"], day / DAYS_PER_WEEK)
    reps_today_evening = lerp(reps_start, wk["reps"], day / DAYS_PER_WEEK)
    reps_prev_evening  = lerp(reps_start, wk["reps"], (day - 1) / DAYS_PER_WEEK)

    reps_val = reps_today_evening if slot == "PM" else reps_prev_evening

    return {
        "rom":  wk["rom"],
        "hold": round(day_hold, 1),
        "reps": int(round(reps_val)),
    }

# ══════════════════════════════════════════════════════
#  Milestones (only used for panel colour / label, kept for continuity)
# ══════════════════════════════════════════════════════
MS = [
    (0,   30,  "REST",     (140,140,140)),
    (30,  60,  "STARTER",  (255,200, 80)),
    (60,  90,  "DAILY",    ( 80,210,120)),
    (90,  120, "ACTIVE",   (100,200,255)),
    (120, 150, "CAPABLE",  (255,130, 50)),
    (150, 181, "SUMMIT",   ( 80, 80,255)),
]

def get_ms(rom):
    for lo, hi, name, col in MS:
        if rom < hi:
            return lo, hi, name, tuple(int(c) for c in col)
    m = MS[-1]
    return m[0], m[1], m[2], tuple(int(c) for c in m[3])

# ══════════════════════════════════════════════════════
#  Persistence
# ══════════════════════════════════════════════════════
DATA = "rehabverse_data.json"

def load():
    if os.path.exists(DATA):
        with open(DATA) as f:
            d = json.load(f)
    else:
        d = {}
    d.setdefault("surgery_arm", None)
    d.setdefault("week", 1)
    d.setdefault("next_day", 1)
    d.setdefault("next_slot", "AM")
    d.setdefault("trend", "STEADY")
    d.setdefault("last_session_date", None)
    d.setdefault("perf_penalty_hold", 0.0)   # carried over when a session FALLS SHORT (not skipped)
    d.setdefault("perf_penalty_reps", 0.0)
    d.setdefault("days", [])
    return d

def save(d):
    with open(DATA, "w") as f:
        json.dump(d, f, indent=2)

prog = load()

# ── resolve which arm is the surgery arm ───────────────────────────────
def resolve_surgery_arm():
    if len(sys.argv) > 1 and sys.argv[1].upper() in ("L", "R"):
        prog["surgery_arm"] = sys.argv[1].upper()
    elif prog.get("surgery_arm") in ("L", "R"):
        pass
    else:
        ans = input("Which arm had surgery? Enter L or R: ").strip().upper()
        prog["surgery_arm"] = "R" if ans not in ("L", "R") else ans
    save(prog)

resolve_surgery_arm()
SURGERY_ARM = prog["surgery_arm"]

def week_cfg():
    idx = min(prog["week"] - 1, len(WEEK_PROG) - 1)
    return WEEK_PROG[idx]

def current_target():
    week_idx = prog["week"] - 1
    if week_idx >= len(WEEK_PROG):
        wk = WEEK_PROG[-1]
        return {"rom": wk["rom"], "hold": wk["hold"], "reps": wk["reps"]}, 0
    day, slot = prog["next_day"], prog["next_slot"]
    base = compute_target(week_idx, day, slot)

    # Penalty source 1: fully skipped calendar day(s) since the last session.
    missed_penalty_hold = missed_penalty_reps = 0
    last = prog.get("last_session_date")
    if last:
        gap_days = (date.today() - date.fromisoformat(last)).days
        missed_days = max(0, gap_days - 1)
        if missed_days > 0:
            missed_slots = missed_days * 2
            missed_penalty_hold = missed_slots * MISS_HOLD_PENALTY_PER_SLOT
            missed_penalty_reps = missed_slots * MISS_REPS_PENALTY_PER_SLOT

    # Penalty source 2: you showed up but fell short last time — ease off a
    # bit rather than asking for the same (or a harder) number again.
    perf_penalty_hold = prog.get("perf_penalty_hold", 0.0)
    perf_penalty_reps = prog.get("perf_penalty_reps", 0.0)

    penalty_hold = min(missed_penalty_hold + perf_penalty_hold, base["hold"] * MAX_PENALTY_FRACTION)
    penalty_reps = min(missed_penalty_reps + perf_penalty_reps, base["reps"] * MAX_PENALTY_FRACTION)

    target = {
        "rom":  base["rom"],
        "hold": max(2, round(base["hold"] - penalty_hold, 1)),
        "reps": max(3, int(round(base["reps"] - penalty_reps))),
    }
    had_setback = missed_penalty_hold > 0 or missed_penalty_reps > 0
    return target, (1 if had_setback else 0)

def program_complete():
    return prog["week"] > len(WEEK_PROG)

def end_session(max_rom, best_hold, reps_count):
    if program_complete():
        return None
    today_str = str(date.today())
    week_idx  = prog["week"] - 1
    day, slot = prog["next_day"], prog["next_slot"]
    target, had_setback = current_target()

    met = (max_rom >= target["rom"] and
           best_hold >= target["hold"] and
           reps_count >= target["reps"])

    entry = {
        "date": today_str, "arm": SURGERY_ARM, "week": prog["week"],
        "day": day, "slot": slot,
        "rom": max_rom, "hold": round(best_hold, 1), "reps": reps_count,
        "target_rom": target["rom"], "target_hold": target["hold"],
        "target_reps": target["reps"], "met": met,
    }
    prog["days"].append(entry)
    prog["last_session_date"] = today_str

    # Adapt next session's difficulty to how THIS one actually went.
    if met:
        prog["perf_penalty_hold"] = 0.0
        prog["perf_penalty_reps"] = 0.0
        prog["trend"] = "MET TARGET"
    else:
        shortfall_hold = max(0.0, target["hold"] - best_hold)
        shortfall_reps = max(0,   target["reps"] - reps_count)
        # carry forward HALF of today's shortfall as tomorrow's discount —
        # a small miss eases things a little, a big miss eases more.
        prog["perf_penalty_hold"] = round(shortfall_hold * 0.5, 1)
        prog["perf_penalty_reps"] = round(shortfall_reps * 0.5, 1)
        prog["trend"] = "SETBACK" if had_setback else "ADJUSTING DOWN"

    is_final_gate = (day == DAYS_PER_WEEK and slot == "PM")
    if is_final_gate:
        if met and prog["week"] <= len(WEEK_PROG):
            prog["week"] += 1
            prog["next_day"] = 1
            prog["next_slot"] = "AM"
            if not program_complete():
                prog["trend"] = "WEEK COMPLETE!"
            else:
                prog["trend"] = "PROGRAM COMPLETE!"
        # else: stay on Day7-PM until the target is actually met
    else:
        if slot == "AM":
            prog["next_slot"] = "PM"
        else:
            prog["next_slot"] = "AM"
            prog["next_day"] += 1

    save(prog)
    return entry

# ══════════════════════════════════════════════════════
#  Maths — shoulder flexion (unchanged geometry, body-relative)
# ══════════════════════════════════════════════════════
def shoulder_flexion(elbow_xy, shoulder_xy, hip_xy):
    sh, el, hip = np.array(shoulder_xy, float), np.array(elbow_xy, float), np.array(hip_xy, float)
    torso_down = hip - sh
    arm_vec    = el - sh
    norm_t, norm_a = np.linalg.norm(torso_down), np.linalg.norm(arm_vec)
    if norm_t < 1e-6 or norm_a < 1e-6:
        return 0
    cos_val = np.dot(arm_vec, torso_down) / (norm_t * norm_a)
    raw = float(np.degrees(np.arccos(np.clip(cos_val, -1, 1))))
    return int(np.clip(raw, 0, 180))

class Smoother:
    def __init__(self, n=6):
        self.buf = deque(maxlen=n)
    def __call__(self, v):
        self.buf.append(v)
        return int(np.median(self.buf))

class RepCounter:
    """
    Counts a rep when the arm rises above `up` (a fraction of the week's
    ROM target), then resets once it has dropped back down to roughly half
    of THAT rep's own peak — not an absolute near-zero floor.

    Why: the old version required the arm to fall below a fixed low angle
    (e.g. 8°) before it would arm itself for the next rep. In practice the
    resting arm rarely reads that low (camera angle / landmark jitter), so
    it would count one rep, get stuck in "UP", and never count again.
    Resetting relative to each rep's own peak instead makes it robust to
    wherever the person's real "arm down" position actually measures.
    """
    def __init__(self):
        self.stage = "DOWN"
        self.count = 0
        self.peak  = 0
    def update(self, rom, target_rom):
        up = max(15, target_rom * 0.65)
        if self.stage == "DOWN":
            if rom > up:
                self.stage = "UP"
                self.peak  = rom
                self.count += 1
        else:
            self.peak = max(self.peak, rom)
            if rom < self.peak * 0.55:
                self.stage = "DOWN"
                self.peak  = 0
        return self.count, self.stage

class HoldTracker:
    def __init__(self):
        self.active = False
        self.t0 = None
        self.cur = 0.0
        self.best = 0.0
    def update(self, rom, target_rom):
        min_rom = max(15, target_rom * 0.80)
        now = time.time()
        if rom >= min_rom:
            if not self.active:
                self.active = True
                self.t0 = now
            self.cur = now - self.t0
            self.best = max(self.best, self.cur)
        else:
            self.active = False
            self.t0 = None
            self.cur = 0.0
        return self.cur, self.best

class ArmTracker:
    def __init__(self):
        self.smooth  = Smoother(6)
        self.reps    = RepCounter()
        self.hold    = HoldTracker()
        self.rom     = 0
        self.max_rom = 0
    def update(self, elbow, shoulder, hip, ok, target_rom):
        if not ok:
            return
        raw = shoulder_flexion(elbow, shoulder, hip)
        self.rom = self.smooth(raw)
        self.max_rom = max(self.max_rom, self.rom)
        self.reps.update(self.rom, target_rom)
        self.hold.update(self.rom, target_rom)

tracker = ArmTracker()

VIS_THR = 0.55
def lm_xy(lms, idx):
    lm = lms[idx.value]
    return [lm.x, lm.y], lm.visibility >= VIS_THR

# ══════════════════════════════════════════════════════
#  Palette
# ══════════════════════════════════════════════════════
BG     = (14, 16, 22)
PANEL  = (22, 26, 34)
WHITE  = (240, 240, 240)
CYAN   = (0, 220, 200)
ORANGE = (30, 160, 255)
GREEN  = (60, 210, 100)
GOLD   = (40, 190, 255)
DIM    = (100, 100, 110)
RED    = (60, 80, 240)
ARM_COL = CYAN if SURGERY_ARM == "L" else ORANGE

# ══════════════════════════════════════════════════════
#  Draw utilities
# ══════════════════════════════════════════════════════
def filled_rect(img, x1, y1, x2, y2, col, alpha=0.88):
    ov = img.copy()
    cv2.rectangle(ov, (x1, y1), (x2, y2), col, -1)
    cv2.addWeighted(ov, alpha, img, 1 - alpha, 0, img)

def hbar(img, x, y, w, h, val, mx, col):
    pct = np.clip(val / mx, 0, 1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (40, 43, 52), -1)
    fw = int(w * pct)
    if fw > 2:
        for i in range(fw):
            t = i / max(fw - 1, 1)
            c = tuple(int(col[j] * (0.3 + 0.7 * t)) for j in range(3))
            cv2.line(img, (x + i, y + 1), (x + i, y + h - 1), c, 1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (70, 72, 80), 1)

def arc(img, cx, cy, r, pct, col, thick=5):
    cv2.circle(img, (cx, cy), r, (40, 43, 52), thick)
    if pct > 0.01:
        ea = int(-90 + 360 * min(pct, 1.0))
        cv2.ellipse(img, (cx, cy), (r, r), 0, -90, ea, col, thick)

def txt(img, s, x, y, scale, col, bold=1):
    cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, col, bold, cv2.LINE_AA)

def txt2(img, s, x, y, scale, col, bold=2):
    cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_DUPLEX, scale, col, bold, cv2.LINE_AA)

# ══════════════════════════════════════════════════════
#  Stick-figure — arm angle is mathematically tied to the ROM value
#  passed in (deg), using the SAME 0°=down / 90°=forward / 180°=up
#  convention as the real tracker, so the pose is always accurate.
# ══════════════════════════════════════════════════════
def arm_vec(deg, length):
    r = math.radians(deg)
    return int(length * math.sin(r)), -int(length * math.cos(r))

def draw_stick(img, x, y, w, h, week_idx, deg, col, t):
    hx = x + w // 2
    hy = y + int(h * 0.16)
    hr = max(int(h * 0.09), 8)
    cv2.circle(img, (hx, hy), hr, col, 2, cv2.LINE_AA)

    bx1, by1 = hx, hy + hr
    bx2, by2 = hx, hy + hr + int(h * 0.30)
    cv2.line(img, (bx1, by1), (bx2, by2), col, 2, cv2.LINE_AA)

    # legs
    sway = int(math.sin(t * 2) * 3)
    cv2.line(img, (bx2, by2), (bx2 - 10 + sway, by2 + int(h * 0.26)), col, 2, cv2.LINE_AA)
    cv2.line(img, (bx2, by2), (bx2 + 10 - sway, by2 + int(h * 0.26)), col, 2, cv2.LINE_AA)

    # working arm — raised to the EXACT target angle for this week
    shoulder = (bx1, by1 + int(h * 0.02))
    arm_len  = int(h * 0.30)
    dx, dy   = arm_vec(deg, arm_len)
    hand     = (shoulder[0] + dx, shoulder[1] + dy)
    cv2.line(img, shoulder, hand, col, 3, cv2.LINE_AA)
    cv2.circle(img, hand, 4, col, -1, cv2.LINE_AA)

    # resting arm — stays down for balance
    cv2.line(img, shoulder, (shoulder[0] - 16, shoulder[1] + int(h * 0.20)), col, 2, cv2.LINE_AA)

    # week-specific prop, positioned relative to the hand position
    if week_idx == 0:  # Pendulum swings — weight swaying below the hand
        swing = int(math.sin(t * 3) * 10)
        px, py = hand[0] + swing, hand[1] + int(h * 0.10)
        cv2.line(img, hand, (px, py), col, 1, cv2.LINE_AA)
        cv2.circle(img, (px, py), 4, col, 1, cv2.LINE_AA)

    elif week_idx == 1:  # Table slide — hand slides along a tabletop
        ty = shoulder[1] + int(h * 0.22)
        cv2.line(img, (x + 8, ty), (x + w - 8, ty), col, 2, cv2.LINE_AA)
        cv2.line(img, (x + 8, ty), (x + 8, ty + 10), col, 1, cv2.LINE_AA)
        cv2.line(img, (x + w - 8, ty), (x + w - 8, ty + 10), col, 1, cv2.LINE_AA)

    elif week_idx == 2:  # Wall crawl (low) — vertical wall with finger marks
        wx = hand[0] + 14
        cv2.line(img, (wx, y + 8), (wx, y + h - 8), col, 1, cv2.LINE_AA)
        for m in range(3):
            my = hand[1] + m * 10
            cv2.line(img, (wx - 4, my), (wx + 4, my), col, 1, cv2.LINE_AA)

    elif week_idx == 3:  # Assisted forward reach — a helper hand guiding
        cv2.circle(img, (hand[0] + 14, hand[1]), 4, col, 1, cv2.LINE_AA)
        cv2.line(img, hand, (hand[0] + 14, hand[1]), col, 1, cv2.LINE_AA)

    elif week_idx == 4:  # Shoulder-height reach — shirt / doorway shape
        pts = np.array([[bx1 - 18, by1 + 6], [bx1 + 18, by1 + 6],
                         [bx1 + 22, by2 - 4], [bx1 - 22, by2 - 4]], np.int32)
        cv2.polylines(img, [pts], True, col, 1, cv2.LINE_AA)

    elif week_idx == 5:  # Comb hair / eye-level shelf
        for ci in range(4):
            cx2 = hand[0] - 6 + ci * 4
            cv2.line(img, (cx2, hand[1] - 6), (cx2, hand[1] - 12), col, 1, cv2.LINE_AA)
        shelf_y = hand[1] + 14
        cv2.line(img, (hand[0] - 20, shelf_y), (hand[0] + 20, shelf_y), col, 2, cv2.LINE_AA)

    elif week_idx == 6:  # Overhead cabinet reach
        shelf_y = hand[1] - 6
        cv2.line(img, (hand[0] - 22, shelf_y), (hand[0] + 22, shelf_y), col, 2, cv2.LINE_AA)
        cv2.rectangle(img, (hand[0] - 6, shelf_y - 10), (hand[0] + 8, shelf_y), col, 1, cv2.LINE_AA)

    elif week_idx == 7:  # Full overhead reach / swim
        bar_y = hand[1] - 4
        cv2.line(img, (hand[0] - 26, bar_y), (hand[0] + 26, bar_y), col, 2, cv2.LINE_AA)
        for wi in range(0, w - 20, 10):
            wy = int(by2 + int(h * 0.15) + math.sin((wi + t * 60) * 0.4) * 3)
            cv2.line(img, (x + 10 + wi, wy), (x + 10 + wi + 6, wy), col, 1, cv2.LINE_AA)

# ══════════════════════════════════════════════════════
#  Side panel — single, wider, generously spaced
# ══════════════════════════════════════════════════════
def draw_side_panel(canvas, tracker, target):
    x, y, W, H = CAM_W, 0, PANEL_W, CAM_H
    filled_rect(canvas, x, y, x + W, y + H, PANEL, alpha=1.0)
    cv2.line(canvas, (x, 0), (x, H), (50, 54, 66), 1)
    P = 16

    wk = week_cfg()
    _, __, ms_name, ms_col = get_ms(tracker.rom)
    complete = program_complete()

    # ── header: arm + week/day/slot ─────────────────────────────
    txt2(canvas, f"{'LEFT' if SURGERY_ARM=='L' else 'RIGHT'} ARM", x + P, 30, 0.75, ARM_COL, 2)
    if complete:
        txt(canvas, "PROGRAM COMPLETE", x + P, 52, 0.42, GOLD)
    else:
        txt(canvas, f"Week {prog['week']}/8   Day {prog['next_day']}/7   {prog['next_slot']} session",
            x + P, 52, 0.42, GOLD)
    cv2.line(canvas, (x + P, 62), (x + W - P, 62), (50, 54, 66), 1)

    # ── ROM ──────────────────────────────────────────────────────
    row = 84
    txt(canvas, "ROM", x + P, row, 0.42, DIM)
    rom_col = GREEN if tracker.rom >= target["rom"] else WHITE
    txt2(canvas, f"{tracker.rom} deg", x + P, row + 46, 1.6, rom_col, 3)
    hbar(canvas, x + P, row + 56, W - P * 2, 12, tracker.rom, 180, ms_col)
    tx = x + P + int((W - P * 2) * target["rom"] / 180)
    cv2.line(canvas, (tx, row + 54), (tx, row + 70), (255, 220, 60), 2)
    txt(canvas, f"target {target['rom']} deg", x + P, row + 88, 0.34, GOLD)

    # ── HOLD ─────────────────────────────────────────────────────
    row2 = row + 110
    cv2.line(canvas, (x + P, row2), (x + W - P, row2), (50, 54, 66), 1)
    txt(canvas, "HOLD", x + P, row2 + 20, 0.42, DIM)
    hold_done = tracker.hold.cur >= target["hold"]
    hold_col  = GREEN if hold_done else ms_col
    arc(canvas, x + P + 34, row2 + 68, 30, tracker.hold.cur / max(target["hold"], 0.1), hold_col, 6)
    txt(canvas, f"{tracker.hold.cur:.1f}s", x + P + 14, row2 + 73, 0.42, hold_col)
    txt(canvas, f"target {target['hold']:.0f}s", x + P + 78, row2 + 50, 0.36, GOLD)
    txt(canvas, f"best {tracker.hold.best:.1f}s", x + P + 78, row2 + 70, 0.34, DIM)

    # ── REPS ─────────────────────────────────────────────────────
    row3 = row2 + 110
    cv2.line(canvas, (x + P, row3), (x + W - P, row3), (50, 54, 66), 1)
    txt(canvas, "REPS", x + P, row3 + 20, 0.42, DIM)
    reps_col = GREEN if tracker.reps.count >= target["reps"] else WHITE
    txt2(canvas, f"{tracker.reps.count}", x + P, row3 + 60, 1.5, reps_col, 3)
    txt(canvas, f"target {target['reps']}", x + P + 70, row3 + 40, 0.36, GOLD)
    txt(canvas, tracker.reps.stage, x + P + 70, row3 + 60, 0.36,
        GREEN if tracker.reps.stage == "UP" else DIM)

    # ── SESSION TARGET SUMMARY BOX ──────────────────────────────
    row4 = row3 + 40

    # ── TREND ────────────────────────────────────────────────────
    row5 = row4 + 60
    tr = prog.get("trend", "STEADY")
    tr_col = (GREEN if tr in ("MET TARGET", "WEEK COMPLETE!", "PROGRAM COMPLETE!")
              else RED if tr == "SETBACK" else ORANGE if tr == "ADJUSTING DOWN" else DIM)
    txt(canvas, tr, x + P, row5, 0.40, tr_col, 2)

    # ── Milestone dots ───────────────────────────────────────────
    row6 = row5 + 22
    cv2.line(canvas, (x + P, row6), (x + W - P, row6), (50, 54, 66), 1)
    dot_y = row6 + 20
    for lo, hi, name, col_ in MS[1:]:
        unlocked = tracker.max_rom >= lo
        cur_ms   = tracker.rom >= lo and tracker.rom < hi
        dc = tuple(int(c) for c in col_) if unlocked else (50, 50, 58)
        r  = 5 if cur_ms else 3
        cv2.circle(canvas, (x + P + 5, dot_y), r, dc, -1, cv2.LINE_AA)
        txt(canvas, name, x + P + 16, dot_y + 4, 0.34, dc)
        dot_y += 20

# ══════════════════════════════════════════════════════
#  Bottom bar
# ══════════════════════════════════════════════════════
def draw_bottom(canvas, tracker, target, t):
    y = BOT_Y
    filled_rect(canvas, 0, y, WIN_W, WIN_H, (16, 18, 26), alpha=1.0)
    cv2.line(canvas, (0, y), (WIN_W, y), (50, 54, 66), 1)

    week_idx = min(prog["week"] - 1, len(WEEK_PROG) - 1)
    wk = WEEK_PROG[week_idx]

    # ── left zone: illustration (own vertical divider) ───────────
    ILLUS_W = 210
    txt2(canvas, f"WEEK {prog['week']}", 16, y + 28, 0.55, GOLD, 2)
    txt(canvas, wk["name"], 16, y + 48, 0.38, (180, 180, 190))
    txt(canvas, f"pose target: {wk['rom']} deg", 16, y + 66, 0.34, DIM)

    fig_w, fig_h = 150, BOT_H - 90
    draw_stick(canvas, 24, y + 76, fig_w, fig_h, week_idx, wk["rom"], ARM_COL, t)
    cv2.line(canvas, (ILLUS_W, y + 14), (ILLUS_W, WIN_H - 14), (50, 54, 66), 1)

    # ── right zone: 8-week roadmap, one clean column list ─────────
    gx, gy = ILLUS_W + 30, y + 28
    txt2(canvas, "8-WEEK ROADMAP", gx, gy, 0.55, GOLD, 2)

    col_w  = (WIN_W - gx - 20) // 2
    row_h  = 30
    for i, w in enumerate(WEEK_PROG):
        wk_no  = i + 1
        is_cur = wk_no == prog["week"]
        done   = wk_no < prog["week"]
        col    = GOLD if is_cur else GREEN if done else DIM
        mark   = ">" if is_cur else "DONE" if done else "-"
        label  = f"{mark} W{wk_no}: {w['rom']} deg | {w['hold']}s | x{w['reps']}"
        cx = gx + (i % 2) * col_w
        cy = gy + 30 + (i // 2) * row_h
        txt(canvas, label, cx, cy, 0.40, col, 2 if is_cur else 1)

# ══════════════════════════════════════════════════════
#  Top header bar (over camera top edge only)
# ══════════════════════════════════════════════════════
def draw_header(canvas):
    overlay = canvas.copy()
    cv2.rectangle(overlay, (CAM_X, 0), (CAM_X + CAM_W, 40), (14, 16, 22), -1)
    cv2.addWeighted(overlay, 0.75, canvas, 0.25, 0, canvas)
    txt2(canvas, "REHABVERSE", CAM_X + 10, 28, 0.85, ARM_COL, 2)
    txt(canvas, "Rotator Cuff Recovery Tracker", CAM_X + 170, 20, 0.46, (170, 170, 180))
    if not program_complete():
        txt(canvas, f"Week {prog['week']}  Day {prog['next_day']}  {prog['next_slot']} session",
            CAM_X + 170, 35, 0.40, GOLD)
    else:
        txt(canvas, "8-week program complete - great work!", CAM_X + 170, 35, 0.40, GREEN)
    txt(canvas, "R=reset  ESC=save & quit", CAM_X + CAM_W - 190, 28, 0.35, DIM)

# ══════════════════════════════════════════════════════
#  Main loop
# ══════════════════════════════════════════════════════
t_start = time.time()
# NOTE: the camera frame is mirrored (cv2.flip) before MediaPipe ever sees it,
# so it looks like a natural mirror to the person. That flip also swaps which
# side MediaPipe calls "left" vs "right" relative to the person's real body —
# so we deliberately pick the OPPOSITE MediaPipe landmark set here to end up
# tracking the person's actual, physical surgery arm.
sh_idx, el_idx, hip_idx = (
    (mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.RIGHT_ELBOW, mp_pose.PoseLandmark.RIGHT_HIP)
    if SURGERY_ARM == "L" else
    (mp_pose.PoseLandmark.LEFT_SHOULDER, mp_pose.PoseLandmark.LEFT_ELBOW, mp_pose.PoseLandmark.LEFT_HIP)
)

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        break

    frame = cv2.flip(frame, 1)
    frame = cv2.resize(frame, (CAM_W, CAM_H))
    frame = cv2.convertScaleAbs(frame, alpha=0.80, beta=5)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb)

    target, _ = current_target()

    if results.pose_landmarks:
        lms = results.pose_landmarks.landmark
        sh, sh_v = lm_xy(lms, sh_idx)
        el, el_v = lm_xy(lms, el_idx)
        hp, hp_v = lm_xy(lms, hip_idx)
        tracker.update(el, sh, hp, sh_v and el_v and hp_v, target["rom"])

        mp_drawing.draw_landmarks(
            frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0, 230, 200), thickness=2, circle_radius=4),
            connection_drawing_spec=mp_drawing.DrawingSpec(color=(80, 80, 200), thickness=2),
        )
        if sh_v and el_v:
            px = (int(sh[0] * CAM_W), int(sh[1] * CAM_H))
            ex = (int(el[0] * CAM_W), int(el[1] * CAM_H))
            cv2.line(frame, px, ex, ARM_COL, 3, cv2.LINE_AA)
            cv2.circle(frame, px, 10, ARM_COL, -1, cv2.LINE_AA)
            cv2.circle(frame, ex, 6, WHITE, -1, cv2.LINE_AA)
    else:
        cv2.putText(frame, "No pose - step back or improve lighting",
                    (CAM_W // 2 - 260, CAM_H // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (80, 80, 255), 2, cv2.LINE_AA)

    canvas = np.full((WIN_H, WIN_W, 3), BG, dtype=np.uint8)
    canvas[0:CAM_H, CAM_X:CAM_X + CAM_W] = frame

    draw_side_panel(canvas, tracker, target)
    t_anim = time.time() - t_start
    draw_bottom(canvas, tracker, target, t_anim)
    draw_header(canvas)

    cv2.imshow("RehabVerse — Rotator Cuff Tracker", canvas)

    key = cv2.waitKey(1) & 0xFF
    if key == 27:  # ESC — save & quit
        entry = end_session(tracker.max_rom, tracker.hold.best, tracker.reps.count)
        if entry:
            print(f"\n✓ Session saved | Week {entry['week']} Day {entry['day']} {entry['slot']} | "
                  f"met={entry['met']} | trend={prog['trend']}")
        else:
            print("\nProgram already complete — nothing to save.")
        break

    if key == ord('r'):  # reset current session's live stats (not the program)
        tracker.rom = 0
        tracker.max_rom = 0
        tracker.smooth = Smoother(6)
        tracker.reps = RepCounter()
        tracker.hold = HoldTracker()

cap.release()
cv2.destroyAllWindows()