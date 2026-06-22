"""
RehabVerse — The Forgotten Orchestra  (v2)
==========================================
Changes from v1:
  • Instruments RE-LOCK when arm drops below threshold  (hysteresis band)
  • Next week unlocks only after meeting performance targets in the current week
  • Each week has a distinct audio/visual identity — tempo, timbre, colour theme, bar style

Install:
    pip install opencv-python mediapipe numpy pygame

Run:
    python forgotten_orchestra.py
"""

import cv2
import numpy as np
import math
import time
import random

import pygame
import pygame.sndarray

import mediapipe as mp

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
W, H        = 1280, 720
SAMPLE_RATE = 44100
CHUNK       = 1024

# ──────────────────────────────────────────────
# REHAB WEEK DEFINITIONS
# Each week has its own identity: colour palette, tempo feel, sound character
# ──────────────────────────────────────────────
REHAB_WEEKS = [
    {
        "label":      "Week 1",
        "max_angle":  45,
        "tip":        "Gentle pendulum — let gravity do the work.",
        "goal_label": "45° goal",
        "encourage":  ["Easy does it!", "Great start!", "Listen to your body."],
        # Visual identity
        "theme_col":  (180, 210, 255),   # icy blue — calm, minimal
        "bg_tint":    (10,  8,  22),
        "bar_style":  "thin",            # narrow quiet bars
        # Audio identity
        "tempo":      "slow",            # long intervals between notes
        "timbre":     "sparse",          # single notes only, soft
        # Performance gate to unlock Week 2
        "unlock_req": {"reps": 5, "hold_s": 2.0, "instruments": 3},
    },
    {
        "label":      "Week 2",
        "max_angle":  70,
        "tip":        "Active-assisted range. Use your good arm if needed.",
        "goal_label": "70° goal",
        "encourage":  ["Nice progress!", "Smooth and steady.", "You're doing great!"],
        "theme_col":  (180, 255, 210),   # soft mint — gentle growth
        "bg_tint":    (8,  18,  14),
        "bar_style":  "normal",
        "tempo":      "moderate",
        "timbre":     "duet",            # pairs of notes
        "unlock_req": {"reps": 8, "hold_s": 3.0, "instruments": 4},
    },
    {
        "label":      "Week 3",
        "max_angle":  90,
        "tip":        "Reach shoulder height — no higher than comfortable.",
        "goal_label": "90° goal (shoulder height)",
        "encourage":  ["Shoulder height reached!", "Beautiful form!", "Keep it smooth."],
        "theme_col":  (255, 200, 140),   # warm amber — building warmth
        "bg_tint":    (18,  12,  6),
        "bar_style":  "normal",
        "tempo":      "moderate",
        "timbre":     "triad",           # three-note chords
        "unlock_req": {"reps": 10, "hold_s": 4.0, "instruments": 5},
    },
    {
        "label":      "Week 4",
        "max_angle":  110,
        "tip":        "Push gently past shoulder — stop at any pain.",
        "goal_label": "110° goal",
        "encourage":  ["Above the shoulder!", "Strong work!", "Steady progress."],
        "theme_col":  (255, 140, 180),   # rose — energy rising
        "bg_tint":    (20,  6,  14),
        "bar_style":  "wide",
        "tempo":      "lively",
        "timbre":     "power",           # bass + chord
        "unlock_req": {"reps": 12, "hold_s": 5.0, "instruments": 6},
    },
    {
        "label":      "Week 5",
        "max_angle":  130,
        "tip":        "Approaching overhead. Never force through pain.",
        "goal_label": "130° goal",
        "encourage":  ["Almost overhead!", "Excellent control!", "You've come far!"],
        "theme_col":  (200, 140, 255),   # violet — near the peak
        "bg_tint":    (14,  6,  22),
        "bar_style":  "wide",
        "tempo":      "lively",
        "timbre":     "full",            # rich chords
        "unlock_req": {"reps": 15, "hold_s": 6.0, "instruments": 6},
    },
    {
        "label":      "Week 6+",
        "max_angle":  160,
        "tip":        "Full functional range. Quality over height.",
        "goal_label": "160° full range",
        "encourage":  ["Full orchestra!", "Peak performance!", "The kingdom sings!"],
        "theme_col":  (255, 220, 80),    # gold — triumphant
        "bg_tint":    (18,  14,  4),
        "bar_style":  "wide",
        "tempo":      "triumphant",
        "timbre":     "orchestra",       # full multi-octave chords
        "unlock_req": None,              # final week, no further unlock
    },
]

# ── Performance tracker (persists across the session) ──
class PerfTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.reps        = 0
        self.max_hold    = 0.0
        self.instruments = 0
        self.week_done   = False   # True once this week's gate is cleared

    def check_gate(self, week_idx):
        req = REHAB_WEEKS[week_idx].get("unlock_req")
        if req is None:
            return True   # final week
        return (self.reps        >= req["reps"] and
                self.max_hold    >= req["hold_s"] and
                self.instruments >= req["instruments"])


# ──────────────────────────────────────────────
# WEEK-SCALED UNLOCK ANGLES (6 instruments)
# ──────────────────────────────────────────────
def week_unlock_angles(week_idx):
    max_a  = REHAB_WEEKS[week_idx]["max_angle"]
    ratios = [0.15, 0.30, 0.48, 0.63, 0.78, 0.93]
    return [max(5, int(max_a * r)) for r in ratios]


# ──────────────────────────────────────────────
# HYSTERESIS: re-lock margin (degrees below unlock threshold)
# ──────────────────────────────────────────────
RELOCK_MARGIN = 8   # arm must drop 8° below unlock angle to re-lock


# ──────────────────────────────────────────────
# AUDIO ENGINE — week-aware timbre + tempo
# ──────────────────────────────────────────────
pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, CHUNK)
pygame.init()

# Note frequencies
C2, D2, E2, F2, G2, A2, B2 = 65.41, 73.42, 82.41, 87.31, 98.00, 110.00, 123.47
C3, D3, E3, F3, G3, A3, B3 = 130.81, 146.83, 164.81, 174.61, 196.00, 220.00, 246.94
C4, D4, E4, F4, G4, A4, B4 = 261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88
C5, D5, E5, F5, G5, A5, B5 = 523.25, 587.33, 659.25, 698.46, 784.00, 880.00, 987.77

# Per-week chord libraries (timbre identity)
#   sparse  = single note + silence
#   duet    = two-note intervals
#   triad   = three-note chords
#   power   = bass + chord stacks
#   full    = rich 4-note chords
#   orchestra = 5-6 note spread chords
WEEK_CHORD_LIBS = {
    "sparse":    [[[C5]], [[E5]], [[G5]], [[A5]], [[C5]], [[D5]]],
    "duet":      [[[C5,E5]], [[D5,G5]], [[E5,A5]], [[G5,B5]], [[A5,C5]], [[F5,C5]]],
    "triad":     [[[C4,E4,G4]], [[D4,G4,A4]], [[E4,G4,C5]], [[A4,C5,E5]],
                  [[F4,A4,C5]], [[G4,B4,D5]]],
    "power":     [[[C3,G3,C4,G4]], [[G2,G3,D4,G4]], [[C3,E4,G4,C5]], [[A3,E4,A4,E5]],
                  [[F3,C4,F4,A4]], [[G3,D4,G4,B4]]],
    "full":      [[[C3,C4,E4,G4,C5]], [[D3,D4,F4,A4,D5]], [[E3,E4,G4,B4,E5]],
                  [[A3,A4,C5,E5,A5]], [[F3,F4,A4,C5,F5]], [[G3,G4,B4,D5,G5]]],
    "orchestra": [[[C2,C3,G3,C4,E4,G4,C5,E5]], [[G2,G3,D4,G4,B4,D5,G5]],
                  [[C2,C3,E3,G3,C4,E4,G4,C5]], [[A2,A3,E4,A4,C5,E5,A5]],
                  [[F2,F3,C4,F4,A4,C5,F5]],    [[G2,G3,D4,G4,B4,D5,G5,B5]]],
}

# Per-week play intervals (seconds between note triggers per instrument)
WEEK_INTERVALS = {
    "slow":       [1.40, 1.30, 1.60, 1.80, 1.50, 2.20],
    "moderate":   [0.90, 0.85, 1.00, 1.20, 1.05, 1.40],
    "lively":     [0.60, 0.55, 0.70, 0.85, 0.70, 1.00],
    "triumphant": [0.45, 0.42, 0.52, 0.65, 0.55, 0.80],
}

NOTE_DURATION = 0.85

def make_chord_wave(freqs, duration=NOTE_DURATION, amp=0.18):
    n    = int(SAMPLE_RATE * duration)
    t    = np.linspace(0, duration, n, endpoint=False)
    wave = sum(np.sin(2 * np.pi * f * t) for f in freqs) / max(len(freqs), 1)
    env  = np.ones(n)
    att  = min(int(SAMPLE_RATE * 0.05), n // 4)
    rel  = min(int(SAMPLE_RATE * 0.12), n // 4)
    env[:att]  = np.linspace(0, 1, att)
    env[-rel:] = np.linspace(1, 0, rel)
    mono = (wave * env * amp * 32767).astype(np.int16)
    return np.column_stack([mono, mono])


class InstrumentPlayer:
    def __init__(self, idx, week_idx=0):
        self.idx         = idx
        self.chord_idx   = 0
        self.active      = False
        self.volume      = 0.0
        self.last_played = 0.0
        self._channel    = pygame.mixer.Channel(idx)
        self._load_week(week_idx)

    def _load_week(self, week_idx):
        timbre      = REHAB_WEEKS[week_idx]["timbre"]
        tempo       = REHAB_WEEKS[week_idx]["tempo"]
        chord_lib   = WEEK_CHORD_LIBS[timbre]
        self.interval = WEEK_INTERVALS[tempo][self.idx]
        # Each instrument picks a rotating subset of the chord lib
        chords = chord_lib[self.idx % len(chord_lib)]
        self._sounds = [pygame.sndarray.make_sound(make_chord_wave(f)) for f in chords]
        self.chord_idx = 0

    def set_week(self, week_idx):
        self._channel.stop()
        self._load_week(week_idx)

    def update(self, active, volume, t):
        self.active = active
        self.volume = max(0.0, min(1.0, volume))
        self._channel.set_volume(self.volume)
        if not active:
            self._channel.fadeout(400)
            return
        if t - self.last_played >= self.interval:
            self._channel.play(self._sounds[self.chord_idx % len(self._sounds)])
            self.chord_idx   = (self.chord_idx + 1) % len(self._sounds)
            self.last_played = t

    def stop(self):
        self._channel.stop()


class AudioEngine:
    def __init__(self, week_idx=0):
        pygame.mixer.set_num_channels(12)
        self.players = [InstrumentPlayer(i, week_idx) for i in range(6)]

    def set_week(self, week_idx):
        for p in self.players:
            p.set_week(week_idx)

    def update(self, unlocked, volumes, t):
        for i, player in enumerate(self.players):
            player.update(unlocked[i], volumes[i], t)

    def stop(self):
        pygame.mixer.stop()


# ──────────────────────────────────────────────
# INSTRUMENT VISUAL DEFINITIONS (base colours; tinted per week)
# ──────────────────────────────────────────────
INSTRUMENT_NAMES = ["Triangle", "Flute", "Violin", "Cello", "Choir", "Orchestra"]

def instrument_colors(week_idx):
    """Generate per-instrument colours tinted toward the week's theme."""
    theme = REHAB_WEEKS[week_idx]["theme_col"]
    tr, tg, tb = theme
    base = [
        (200, 220, 255), (180, 255, 200), (255, 200, 160),
        (255, 160, 180), (220, 160, 255), (255, 220, 100),
    ]
    result = []
    for br, bg, bb in base:
        r = int(br * 0.6 + tr * 0.4)
        g = int(bg * 0.6 + tg * 0.4)
        b = int(bb * 0.6 + tb * 0.4)
        result.append({"color": (r, g, b), "bar_col": (int(r*0.75), int(g*0.75), int(b*0.75))})
    return result


# ──────────────────────────────────────────────
# SOUND BAR — style varies per week
# ──────────────────────────────────────────────
class SoundBar:
    def __init__(self, x, color, style="normal"):
        self.x         = x
        self.color     = color
        self.phase     = random.uniform(0, 2 * math.pi)
        self.speed     = random.uniform(2.0, 5.0)
        self.current_h = 4.0

        if style == "thin":
            self.width = 5;  self.h_min = 3;  self.h_max = int(25 + 30 * abs(math.sin(x*0.8)))
        elif style == "wide":
            self.width = 12; self.h_min = 5;  self.h_max = int(55 + 80 * abs(math.sin(x*0.8)))
        else:
            self.width = 8;  self.h_min = 4;  self.h_max = int(40 + 60 * abs(math.sin(x*0.8)))

    def update(self, t, active, volume):
        if active:
            target = self.h_min + (self.h_max - self.h_min) * volume * (
                0.6 + 0.4 * abs(math.sin(t * self.speed + self.phase)))
        else:
            target = self.h_min + 2
        self.current_h += (target - self.current_h) * 0.25

    def draw(self, frame, base_y, unlocked):
        r, g, b = self.color if unlocked else (50, 50, 60)
        h  = max(2, int(self.current_h))
        x1, x2 = self.x - self.width // 2, self.x + self.width // 2
        cv2.rectangle(frame, (x1, base_y - h), (x2, base_y), (b, g, r), -1)
        if unlocked:
            cv2.rectangle(frame, (x1, base_y - h), (x2, base_y),
                          (min(255,b+40), min(255,g+40), min(255,r+40)), 1)


# ──────────────────────────────────────────────
# INSTRUMENT SECTION  — with RE-LOCKING
# ──────────────────────────────────────────────
class InstrumentSection:
    def __init__(self, cx, cy, inst_info, unlock_angle, style="normal"):
        self.cx, self.cy  = cx, cy
        self.inst_info    = inst_info
        self.unlock_angle = unlock_angle
        self.relock_angle = unlock_angle - RELOCK_MARGIN   # drop below this → lock again
        self.unlocked     = False
        self.unlock_anim  = 0.0
        self.unlock_time  = None
        r, g, b = inst_info["color"]
        spacing = 14
        n_bars  = 12
        start_x = cx - (n_bars * spacing) // 2
        self.bars      = [SoundBar(start_x + i * spacing, (r, g, b), style) for i in range(n_bars)]
        self.volume    = self.target_volume = 0.0
        self.particles = []

    def reset_lock(self, new_unlock_angle, new_inst_info, style):
        self.unlock_angle = new_unlock_angle
        self.relock_angle = new_unlock_angle - RELOCK_MARGIN
        self.inst_info    = new_inst_info
        self.unlocked     = False
        self.unlock_anim  = 0.0
        self.unlock_time  = None
        self.volume = self.target_volume = 0.0
        self.particles = []
        # Rebuild bars with new style/colour
        r, g, b = new_inst_info["color"]
        spacing = 14
        n_bars  = 12
        start_x = self.cx - (n_bars * spacing) // 2
        self.bars = [SoundBar(start_x + i * spacing, (r, g, b), style) for i in range(n_bars)]

    def try_unlock(self, t):
        if not self.unlocked:
            self.unlocked    = True
            self.unlock_time = t
            for _ in range(20):
                a = random.uniform(0, 2 * math.pi)
                s = random.uniform(2, 6)
                self.particles.append({
                    "x": self.cx, "y": self.cy,
                    "vx": math.cos(a)*s, "vy": math.sin(a)*s,
                    "life": 1.0, "size": random.uniform(2, 5),
                })

    def try_relock(self):
        if self.unlocked:
            self.unlocked    = False
            self.unlock_anim = 0.0
            self.unlock_time = None
            self.volume = self.target_volume = 0.0
            self.particles = []

    def update(self, t, global_angle):
        # Unlock / re-lock with hysteresis
        if not self.unlocked and global_angle >= self.unlock_angle:
            self.try_unlock(t)
        elif self.unlocked and global_angle < self.relock_angle:
            self.try_relock()

        window = max(10, self.unlock_angle * 0.3)
        self.target_volume = (
            min(1.0, (global_angle - self.unlock_angle + window * 0.4) / window)
            if self.unlocked else 0.0
        )
        self.volume += (self.target_volume - self.volume) * 0.1

        if self.unlock_time is not None:
            self.unlock_anim = min(1.0, (t - self.unlock_time) / 0.8)

        for bar in self.bars:
            bar.update(t, self.unlocked, self.volume)

        for p in self.particles:
            p["x"] += p["vx"]; p["y"] += p["vy"]
            p["vy"] += 0.15;   p["life"] -= 0.03
        self.particles = [p for p in self.particles if p["life"] > 0]

    def draw(self, frame, t):
        base_y = self.cy + 30
        if not self.unlocked:
            cv2.putText(frame, f"? {INSTRUMENT_NAMES[0]}",   # placeholder, overridden below
                        (self.cx - 45, self.cy - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (70,70,80), 1)
            cv2.putText(frame, f">{int(self.unlock_angle)}\xb0",
                        (self.cx - 15, self.cy - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (70,70,80), 1)
        else:
            r, g, b = self.inst_info["color"]
            a   = min(1.0, self.unlock_anim * 2)
            col = (int(b*a), int(g*a), int(r*a))
            cv2.putText(frame, self.inst_info.get("name","?"),
                        (self.cx - 30, self.cy - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
            vol_w = int(60 * self.volume)
            cv2.rectangle(frame, (self.cx-30, self.cy-25), (self.cx+30, self.cy-18), (40,40,50), -1)
            r2, g2, b2 = self.inst_info["bar_col"]
            cv2.rectangle(frame, (self.cx-30, self.cy-25),
                          (self.cx-30+vol_w, self.cy-18), (b2, g2, r2), -1)

        for bar in self.bars:
            bar.draw(frame, base_y, self.unlocked)

        for p in self.particles:
            r, g, b = self.inst_info["color"]
            al   = p["life"]
            size = max(1, int(p["size"]*al))
            px, py = int(p["x"]), int(p["y"])
            if 0 <= px < W and 0 <= py < H:
                cv2.circle(frame, (px, py), size, (int(b*al), int(g*al), int(r*al)), -1)

        if self.unlocked and self.unlock_anim < 1.0:
            r, g, b = self.inst_info["color"]
            al = 1.0 - self.unlock_anim
            cv2.circle(frame, (self.cx, self.cy), int(50*self.unlock_anim),
                       (int(b*al), int(g*al), int(r*al)), 2)


# ──────────────────────────────────────────────
# ORCHESTRA STAGE
# ──────────────────────────────────────────────
class OrchestraStage:
    POSITIONS = [
        (W//2 - 420, H//2 - 20), (W//2 - 240, H//2 - 60),
        (W//2 -  60, H//2 - 80), (W//2 + 120, H//2 - 60),
        (W//2 + 280, H//2 - 20), (W//2 + 420, H//2 + 10),
    ]

    def __init__(self, week_idx=0):
        self.week_idx       = week_idx
        self.perf           = PerfTracker()
        self.music_progress = 0.0
        self.was_raised     = False
        self.hold_start     = None
        self.hold_time      = 0.0
        self._build_sections(week_idx)

    def _build_sections(self, week_idx):
        angles    = week_unlock_angles(week_idx)
        colors    = instrument_colors(week_idx)
        style     = REHAB_WEEKS[week_idx]["bar_style"]
        for i, info in enumerate(colors):
            info["name"] = INSTRUMENT_NAMES[i]
        self.sections = [
            InstrumentSection(cx, cy, colors[i], angles[i], style)
            for i, (cx, cy) in enumerate(self.POSITIONS)
        ]

    def set_week(self, week_idx):
        self.week_idx = week_idx
        angles  = week_unlock_angles(week_idx)
        colors  = instrument_colors(week_idx)
        style   = REHAB_WEEKS[week_idx]["bar_style"]
        for i, info in enumerate(colors):
            info["name"] = INSTRUMENT_NAMES[i]
        for i, section in enumerate(self.sections):
            section.reset_lock(angles[i], colors[i], style)
        self.music_progress = 0.0
        self.perf.reset()

    @property
    def week_max(self):
        return REHAB_WEEKS[self.week_idx]["max_angle"]

    @property
    def total_unlocked(self):
        return sum(s.unlocked for s in self.sections)

    def update(self, angle, t):
        self.music_progress = min(100.0,
            self.music_progress + (angle / self.week_max) * 0.05)

        for s in self.sections:
            s.update(t, angle)

        raise_threshold = self.week_max * 0.4
        if angle > raise_threshold:
            if not self.was_raised:
                self.was_raised = True
                self.hold_start = t
            self.hold_time = t - self.hold_start
            # Track max hold for perf gate
            if self.hold_time > self.perf.max_hold:
                self.perf.max_hold = self.hold_time
        else:
            if self.was_raised:
                self.perf.reps += 1
            self.was_raised = False
            self.hold_start = None
            self.hold_time  = 0.0

        # Update instruments count for perf gate
        self.perf.instruments = self.total_unlocked

        # Check if this week's gate is cleared
        if not self.perf.week_done:
            self.perf.week_done = self.perf.check_gate(self.week_idx)

    def audio_state(self):
        return ([s.unlocked for s in self.sections],
                [s.volume   for s in self.sections])

    def draw(self, frame, t):
        stage_y = H - 60
        cv2.line(frame, (80, stage_y), (W-80, stage_y), (60, 55, 70), 1)
        for i in range(10):
            x = 80 + i * ((W-160)//9)
            cv2.line(frame, (x, stage_y), (x, stage_y+15), (50, 45, 60), 1)
        for s in self.sections:
            cv2.line(frame, (s.cx, stage_y), (s.cx, s.cy+35), (45, 40, 55), 1)
            s.draw(frame, t)


# ──────────────────────────────────────────────
# WEEK SELECTOR OVERLAY
# ──────────────────────────────────────────────
def draw_week_selector(frame, selected_idx, unlocked_weeks):
    overlay = frame.copy()
    cv2.rectangle(overlay, (W//2-340, H//2-250), (W//2+340, H//2+260), (12, 8, 22), -1)
    cv2.addWeighted(overlay, 0.92, frame, 0.08, 0, frame)
    cv2.rectangle(frame, (W//2-340, H//2-250), (W//2+340, H//2+260), (80, 60, 110), 2)

    cv2.putText(frame, "RECOVERY WEEK",
                (W//2-120, H//2-215), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (200,160,255), 2)
    cv2.putText(frame, "Complete week goals to unlock the next",
                (W//2-190, H//2-188), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140,130,160), 1)

    for i, week in enumerate(REHAB_WEEKS):
        y      = H//2 - 155 + i * 56
        is_sel = (i == selected_idx)
        avail  = i in unlocked_weeks

        bg_col = (40, 28, 60) if is_sel else (18, 14, 30)
        cv2.rectangle(frame, (W//2-325, y-24), (W//2+325, y+28), bg_col, -1)
        border = (160,100,255) if is_sel else ((60,50,80) if avail else (35,30,45))
        cv2.rectangle(frame, (W//2-325, y-24), (W//2+325, y+28), border, 1 if not is_sel else 2)

        # Lock icon for unavailable weeks
        if not avail:
            cv2.putText(frame, "\U0001F512" if False else "[locked]",
                        (W//2+235, y+6), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (80,70,90), 1)

        label_col = (210,170,255) if is_sel else ((120,110,140) if avail else (60,55,70))
        cv2.putText(frame, f"{i+1}  {week['label']}  (up to {week['max_angle']}\xb0)",
                    (W//2-310, y+6), cv2.FONT_HERSHEY_SIMPLEX, 0.42, label_col, 1)

        tip_col = (160,200,160) if is_sel else ((70,80,70) if avail else (45,45,50))
        cv2.putText(frame, week["tip"],
                    (W//2-310, y+22), cv2.FONT_HERSHEY_SIMPLEX, 0.30, tip_col, 1)

        # Show unlock requirement for locked weeks
        req = week.get("unlock_req")
        if not avail and req:
            req_text = f"Need: {req['reps']}reps  {req['hold_s']:.0f}s hold  {req['instruments']} instruments"
            cv2.putText(frame, req_text,
                        (W//2-310, y+35), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (90,70,100), 1)

        # Mini arc
        arc_cx = W//2 + 295
        sweep  = int(week["max_angle"] * 0.75)
        arc_col = (160,100,255) if is_sel else (60,50,80)
        cv2.ellipse(frame, (arc_cx, y+2), (18,18), -90, -sweep//2, sweep//2, arc_col, 2)

    cv2.putText(frame, "1-6 select  |  ENTER confirm  |  locked weeks require performance goals",
                (W//2-270, H//2+240), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (90,85,110), 1)


# ──────────────────────────────────────────────
# POSE HELPERS
# ──────────────────────────────────────────────
def calc_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    angle   = abs(math.degrees(
        math.atan2(c[1]-b[1], c[0]-b[0]) - math.atan2(a[1]-b[1], a[0]-b[0])))
    return 360 - angle if angle > 180 else angle

def get_abduction_angle(landmarks):
    lm   = landmarks
    Pose = mp.solutions.pose.PoseLandmark
    hip      = [lm[Pose.LEFT_HIP.value].x,      lm[Pose.LEFT_HIP.value].y]
    shoulder = [lm[Pose.LEFT_SHOULDER.value].x,  lm[Pose.LEFT_SHOULDER.value].y]
    elbow    = [lm[Pose.LEFT_ELBOW.value].x,     lm[Pose.LEFT_ELBOW.value].y]
    return calc_angle(hip, shoulder, elbow)

def draw_conductor_arc(frame, angle, cx, cy, week_max, theme_col):
    sweep    = min(angle, week_max)
    progress = sweep / week_max
    tr, tg, tb = theme_col
    color    = (int(tb*0.8), int(tg*0.8), int(tr*0.8)) if progress < 0.5 \
               else (int(tb), int(tg), int(tr))
    cv2.ellipse(frame, (cx,cy), (70,70), -90,
                -int(week_max*0.5), int(week_max*0.5), (55,50,65), 1)
    cv2.ellipse(frame, (cx,cy), (70,70), -90,
                -int(sweep*0.5), int(sweep*0.5), color, 2)
    rad = math.radians(-90 + sweep/2)
    cv2.circle(frame, (int(cx+70*math.cos(rad)), int(cy+70*math.sin(rad))), 5, color, -1)
    tick_rad = math.radians(-90 + week_max/2)
    tx, ty   = int(cx+70*math.cos(tick_rad)), int(cy+70*math.sin(tick_rad))
    cv2.circle(frame, (tx,ty), 3, (180,100,255), -1)


# ──────────────────────────────────────────────
# HUD
# ──────────────────────────────────────────────
def draw_hud(frame, angle, stage, t, next_week_ready):
    week      = REHAB_WEEKS[stage.week_idx]
    week_max  = stage.week_max
    perf      = stage.perf
    req       = week.get("unlock_req")
    theme     = week["theme_col"]
    tr, tg, tb = theme

    panel = frame.copy()
    cv2.rectangle(panel, (10,10), (360,310), (10,8,18), -1)
    cv2.addWeighted(panel, 0.78, frame, 0.22, 0, frame)
    cv2.rectangle(frame, (10,10), (360,310), (int(tb*0.3),int(tg*0.3),int(tr*0.3)), 1)

    cv2.putText(frame, "THE FORGOTTEN ORCHESTRA",
                (20,36), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (int(tb),int(tg),int(tr)), 1)
    cv2.putText(frame, f"{week['label']}  |  {week['goal_label']}",
                (20,56), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160,100,255), 1)

    # Abduction bar
    cv2.putText(frame, f"Abduction: {int(angle)}\xb0  /  {week_max}\xb0 goal",
                (20,76), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180,170,200), 1)
    cv2.rectangle(frame, (20,81), (220,91), (35,30,50), -1)
    fill = int(200 * min(angle, week_max) / week_max)
    bar_col = (int(tb*0.3), int(tg*0.8), int(tr*0.3)) if angle >= week_max*0.8 else (80,130,255)
    cv2.rectangle(frame, (20,81), (20+fill,91), bar_col, -1)

    # Re-lock indicator: show lock margin visually
    relock_fill = int(200 * max(0, (angle - RELOCK_MARGIN)) / week_max)
    cv2.rectangle(frame, (20,92), (20+relock_fill, 95), (100,80,120), -1)

    cv2.putText(frame, week["tip"],
                (20,110), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (120,180,140), 1)

    # Music progress
    cv2.putText(frame, f"Music restored: {int(stage.music_progress)}%",
                (20,126), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180,170,200), 1)
    cv2.rectangle(frame, (20,131), (220,141), (35,30,50), -1)
    cv2.rectangle(frame, (20,131),
                  (20+int(200*stage.music_progress/100),141), (int(tb*0.7),int(tg*0.4),int(tr*0.7)), -1)

    cv2.putText(frame, f"Instruments: {stage.total_unlocked}/6",
                (20,160), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160,150,180), 1)
    cv2.putText(frame, f"Reps: {perf.reps}   Hold: {stage.hold_time:.1f}s  (best: {perf.max_hold:.1f}s)",
                (20,176), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (160,150,180), 1)

    # Instrument dots
    cv2.putText(frame, "Awakened:",
                (20,199), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (120,110,140), 1)
    colors = instrument_colors(stage.week_idx)
    for i, (info, sec) in enumerate(zip(colors, stage.sections)):
        r, g, b = info["color"]
        col = (int(b*0.7), int(g*0.7), int(r*0.7)) if sec.unlocked else (40,40,50)
        cv2.circle(frame, (95+i*22, 196), 6, col, -1)

    # ── Performance gate display ──
    if req:
        cv2.putText(frame, "Week goals to unlock next week:",
                    (20,220), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (120,100,150), 1)

        def gate_col(done):
            return (60,200,80) if done else (120,100,140)

        r_done = perf.reps >= req["reps"]
        h_done = perf.max_hold >= req["hold_s"]
        i_done = perf.instruments >= req["instruments"]

        cv2.putText(frame, f"  Reps {perf.reps}/{req['reps']}",
                    (20,235), cv2.FONT_HERSHEY_SIMPLEX, 0.30, gate_col(r_done), 1)
        cv2.putText(frame, f"  Hold {perf.max_hold:.1f}/{req['hold_s']:.0f}s",
                    (110,235), cv2.FONT_HERSHEY_SIMPLEX, 0.30, gate_col(h_done), 1)
        cv2.putText(frame, f"  Inst {perf.instruments}/{req['instruments']}",
                    (210,235), cv2.FONT_HERSHEY_SIMPLEX, 0.30, gate_col(i_done), 1)

    if next_week_ready and stage.week_idx < len(REHAB_WEEKS)-1:
        cv2.putText(frame, ">> Week goal met! Press W to advance <<",
                    (20,255), cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                    (int(tb), int(tg), int(tr)), 1)

    cv2.putText(frame, "W = change week",
                (20,278), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (70,65,85), 1)

    # ── Dynamic encouragement ──
    progress_pct = angle / week_max if week_max > 0 else 0
    encourage    = week["encourage"]
    if angle < 5:
        msg, col = "Raise your arm gently to begin!", (100,100,120)
    elif progress_pct < 0.35:
        msg, col = encourage[0], (100,160,255)
    elif progress_pct < 0.65:
        msg, col = (encourage[1] if len(encourage)>1 else encourage[0]), (140,200,140)
    elif progress_pct < 0.90:
        msg, col = encourage[-1], (180,220,100)
    else:
        msg, col = f"{week['goal_label']} reached! Wonderful!", (int(tb),int(tg),int(tr))
    cv2.putText(frame, msg, (W//2 - len(msg)*5, H-30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, col, 2)


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("RehabVerse — The Forgotten Orchestra  (v2)")
    print("  LEFT arm abduction tracked.")
    print("  Instruments LOCK again when arm lowers.")
    print("  Next week unlocks after meeting performance targets.\n")

    mp_pose    = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)

    # unlocked_weeks starts with only Week 1 available
    unlocked_weeks = {0}

    # ── Startup week selector ──
    selected_week = 0
    in_selector   = True
    ret, bg_frame = cap.read()
    if ret:
        bg_frame = cv2.flip(bg_frame, 1)
    else:
        bg_frame = np.zeros((H, W, 3), dtype=np.uint8)

    while in_selector:
        frame = bg_frame.copy()
        dark  = np.zeros_like(frame, dtype=np.uint8); dark[:] = (15,10,25)
        cv2.addWeighted(dark, 0.6, frame, 0.4, 0, frame)
        draw_week_selector(frame, selected_week, unlocked_weeks)
        cv2.imshow("RehabVerse — The Forgotten Orchestra", frame)
        key = cv2.waitKey(30) & 0xFF
        if key in [ord(str(i)) for i in range(1,7)]:
            candidate = key - ord('1')
            if candidate in unlocked_weeks:
                selected_week = candidate
        elif key in [13, ord('\r'), ord(' ')]:
            in_selector = False
        elif key == ord('q'):
            cap.release(); cv2.destroyAllWindows(); pygame.quit(); return

    stage        = OrchestraStage(week_idx=selected_week)
    audio_engine = AudioEngine(week_idx=selected_week)
    smoothed_angle = 0.0
    show_selector  = False

    with mp_pose.Pose(min_detection_confidence=0.6,
                      min_tracking_confidence=0.6) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame   = cv2.flip(frame, 1)
            rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)
            t       = time.time()

            angle = smoothed_angle
            if results.pose_landmarks:
                lm             = results.pose_landmarks.landmark
                raw            = get_abduction_angle(lm)
                smoothed_angle = 0.82 * smoothed_angle + 0.18 * raw
                angle          = smoothed_angle

                ls = lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
                draw_conductor_arc(frame, angle,
                                   int(ls.x*W), int(ls.y*H),
                                   stage.week_max,
                                   REHAB_WEEKS[stage.week_idx]["theme_col"])
                mp_drawing.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(80,70,100), thickness=1, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(70,60,90),  thickness=1))

            # Background tint per week
            bg_col = REHAB_WEEKS[stage.week_idx]["bg_tint"]
            dark   = np.zeros_like(frame, dtype=np.uint8); dark[:] = bg_col
            cv2.addWeighted(dark, 0.45, frame, 0.55, 0, frame)

            stage.update(angle, t)
            stage.draw(frame, t)

            # Unlock next week in the registry if gate cleared
            if stage.perf.week_done and stage.week_idx + 1 < len(REHAB_WEEKS):
                unlocked_weeks.add(stage.week_idx + 1)

            unlocked, volumes = stage.audio_state()
            audio_engine.update(unlocked, volumes, t)

            next_week_ready = stage.perf.week_done and stage.week_idx < len(REHAB_WEEKS)-1
            draw_hud(frame, angle, stage, t, next_week_ready)
            cv2.putText(frame, "Q quit  |  W change week",
                        (W-230, H-15), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (70,65,85), 1)

            if show_selector:
                draw_week_selector(frame, stage.week_idx, unlocked_weeks)

            cv2.imshow("RehabVerse — The Forgotten Orchestra", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break
            elif key in (ord('w'), ord('W')):
                show_selector = not show_selector
            elif show_selector:
                if key in [ord(str(i)) for i in range(1,7)]:
                    candidate = key - ord('1')
                    if candidate in unlocked_weeks:
                        stage.set_week(candidate)
                        audio_engine.set_week(candidate)
                elif key in [13, ord('\r'), ord(' ')]:
                    show_selector = False

    audio_engine.stop()
    cap.release()
    cv2.destroyAllWindows()
    pygame.quit()

    week = REHAB_WEEKS[stage.week_idx]
    perf = stage.perf
    req  = week.get("unlock_req")
    print(f"\nSession complete  ({week['label']})")
    print(f"  Reps:               {perf.reps}")
    print(f"  Best hold:          {perf.max_hold:.1f}s")
    print(f"  Instruments awoken: {perf.instruments}/6")
    print(f"  Music restored:     {int(stage.music_progress)}%")
    if req:
        gate_met = perf.check_gate(stage.week_idx)
        print(f"  Week gate:          {'CLEARED ✓' if gate_met else 'not yet met'}")
        if not gate_met:
            print(f"    Need — reps:{req['reps']}  hold:{req['hold_s']}s  instruments:{req['instruments']}")

if __name__ == "__main__":
    main()