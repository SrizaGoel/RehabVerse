"""
RehabVerse — The Forgotten Orchestra  (v3)
==========================================
Added in v3:
  • Daily session log persisted to JSON
  • If next day's max angle < previous day → daily ROM target drops for 2 days (recovery mode)
  • If next day's max angle > previous day → hold target bumps up
  • HUD shows: today's best, yesterday's best, current daily target, trend badge
  • Best session all-time displayed

Install:
    pip install opencv-python mediapipe numpy pygame

Run:
    python forgotten_orchestra_v2.py
"""

import cv2
import numpy as np
import math
import time
import random
import json
import os
from datetime import date, timedelta

import pygame
import pygame.sndarray
import mediapipe as mp

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
W, H        = 1280, 720
SAMPLE_RATE = 44100
CHUNK       = 1024
DATA_FILE   = "orchestra_progress.json"

# ──────────────────────────────────────────────
# PERSISTENCE — daily log + adaptive targets
# ──────────────────────────────────────────────
def load_progress():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {
        "days": [],                # list of {date, max_angle, max_hold, week}
        "hold_target": 3.0,        # adaptive hold target (seconds)
        "rom_penalty_days": 0,     # how many more days the target stays reduced
        "rom_penalty_offset": 0,   # degrees subtracted from week target during penalty
        "trend": "STEADY",         # UP / DROP / STEADY
        "all_time_best_angle": 0,
        "all_time_best_hold": 0.0,
    }

def save_progress(p):
    with open(DATA_FILE, "w") as f:
        json.dump(p, f, indent=2)

prog = load_progress()

def get_today_entry():
    today = str(date.today())
    return next((d for d in prog["days"] if d["date"] == today), None)

def get_yesterday_entry():
    yesterday = str(date.today() - timedelta(days=1))
    return next((d for d in prog["days"] if d["date"] == yesterday), None)

def commit_session(max_angle, max_hold, week_idx):
    """Called on quit — updates daily log and recalculates adaptive targets."""
    today = str(date.today())
    entry = get_today_entry()
    if entry is None:
        entry = {"date": today, "max_angle": 0, "max_hold": 0.0, "week": week_idx}
        prog["days"].append(entry)

    # Only update if better
    entry["max_angle"] = max(entry["max_angle"], int(max_angle))
    entry["max_hold"]  = max(entry["max_hold"],  round(max_hold, 1))
    entry["week"]      = week_idx

    # All-time bests
    prog["all_time_best_angle"] = max(prog["all_time_best_angle"], entry["max_angle"])
    prog["all_time_best_hold"]  = max(prog["all_time_best_hold"],  entry["max_hold"])

    # Adaptive logic vs yesterday
    yesterday = get_yesterday_entry()
    if yesterday:
        prev_angle = yesterday["max_angle"]
        prev_hold  = yesterday["max_hold"]

        if max_angle < prev_angle:
            # Performed worse → reduce daily ROM target for next 2 days
            drop = max(5, int((prev_angle - max_angle) * 0.5))
            prog["rom_penalty_days"]   = 2
            prog["rom_penalty_offset"] = drop
            prog["trend"] = "DROP"
        elif max_angle > prev_angle:
            # Performed better → increase hold target
            boost = 1.0 if max_angle - prev_angle < 10 else 2.0
            prog["hold_target"] = min(prog["hold_target"] + boost, 30.0)
            prog["trend"] = "UP"
            # Also reduce penalty if recovering
            prog["rom_penalty_days"] = max(0, prog["rom_penalty_days"] - 1)
        else:
            prog["trend"] = "STEADY"
            prog["rom_penalty_days"] = max(0, prog["rom_penalty_days"] - 1)
    else:
        prog["trend"] = "STEADY"

    save_progress(prog)

def effective_rom_target(base_target):
    """Return today's ROM target, reduced if in penalty window."""
    if prog["rom_penalty_days"] > 0:
        return max(20, base_target - prog["rom_penalty_offset"])
    return base_target

def tick_penalty_on_new_day():
    """Decrement penalty counter if we're on a new day vs last session."""
    if prog["days"]:
        last_date = prog["days"][-1]["date"]
        if last_date != str(date.today()) and prog["rom_penalty_days"] > 0:
            prog["rom_penalty_days"] = max(0, prog["rom_penalty_days"] - 1)
            save_progress(prog)

tick_penalty_on_new_day()

# ──────────────────────────────────────────────
# REHAB WEEK DEFINITIONS
# ──────────────────────────────────────────────
REHAB_WEEKS = [
    {
        "label":      "Week 1",
        "max_angle":  45,
        "tip":        "Gentle pendulum — let gravity do the work.",
        "goal_label": "45° goal",
        "encourage":  ["Easy does it!", "Great start!", "Listen to your body."],
        "theme_col":  (180, 210, 255),
        "bg_tint":    (10,  8,  22),
        "bar_style":  "thin",
        "tempo":      "slow",
        "timbre":     "sparse",
        "unlock_req": {"reps": 5, "hold_s": 2.0, "instruments": 3},
    },
    {
        "label":      "Week 2",
        "max_angle":  70,
        "tip":        "Active-assisted range. Use your good arm if needed.",
        "goal_label": "70° goal",
        "encourage":  ["Nice progress!", "Smooth and steady.", "You're doing great!"],
        "theme_col":  (180, 255, 210),
        "bg_tint":    (8,  18,  14),
        "bar_style":  "normal",
        "tempo":      "moderate",
        "timbre":     "duet",
        "unlock_req": {"reps": 8, "hold_s": 3.0, "instruments": 4},
    },
    {
        "label":      "Week 3",
        "max_angle":  90,
        "tip":        "Reach shoulder height — no higher than comfortable.",
        "goal_label": "90° goal (shoulder height)",
        "encourage":  ["Shoulder height reached!", "Beautiful form!", "Keep it smooth."],
        "theme_col":  (255, 200, 140),
        "bg_tint":    (18,  12,  6),
        "bar_style":  "normal",
        "tempo":      "moderate",
        "timbre":     "triad",
        "unlock_req": {"reps": 10, "hold_s": 4.0, "instruments": 5},
    },
    {
        "label":      "Week 4",
        "max_angle":  110,
        "tip":        "Push gently past shoulder — stop at any pain.",
        "goal_label": "110° goal",
        "encourage":  ["Above the shoulder!", "Strong work!", "Steady progress."],
        "theme_col":  (255, 140, 180),
        "bg_tint":    (20,  6,  14),
        "bar_style":  "wide",
        "tempo":      "lively",
        "timbre":     "power",
        "unlock_req": {"reps": 12, "hold_s": 5.0, "instruments": 6},
    },
    {
        "label":      "Week 5",
        "max_angle":  130,
        "tip":        "Approaching overhead. Never force through pain.",
        "goal_label": "130° goal",
        "encourage":  ["Almost overhead!", "Excellent control!", "You've come far!"],
        "theme_col":  (200, 140, 255),
        "bg_tint":    (14,  6,  22),
        "bar_style":  "wide",
        "tempo":      "lively",
        "timbre":     "full",
        "unlock_req": {"reps": 15, "hold_s": 6.0, "instruments": 6},
    },
    {
        "label":      "Week 6+",
        "max_angle":  160,
        "tip":        "Full functional range. Quality over height.",
        "goal_label": "160° full range",
        "encourage":  ["Full orchestra!", "Peak performance!", "The kingdom sings!"],
        "theme_col":  (255, 220, 80),
        "bg_tint":    (18,  14,  4),
        "bar_style":  "wide",
        "tempo":      "triumphant",
        "timbre":     "orchestra",
        "unlock_req": None,
    },
]

# ──────────────────────────────────────────────
# PERFORMANCE TRACKER (in-session)
# ──────────────────────────────────────────────
class PerfTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.reps        = 0
        self.max_hold    = 0.0
        self.instruments = 0
        self.week_done   = False

    def check_gate(self, week_idx):
        req = REHAB_WEEKS[week_idx].get("unlock_req")
        if req is None:
            return True
        return (self.reps        >= req["reps"] and
                self.max_hold    >= req["hold_s"] and
                self.instruments >= req["instruments"])

# ──────────────────────────────────────────────
# WEEK-SCALED UNLOCK ANGLES + HYSTERESIS
# ──────────────────────────────────────────────
def week_unlock_angles(week_idx):
    max_a  = REHAB_WEEKS[week_idx]["max_angle"]
    ratios = [0.15, 0.30, 0.48, 0.63, 0.78, 0.93]
    return [max(5, int(max_a * r)) for r in ratios]

RELOCK_MARGIN = 8

# ──────────────────────────────────────────────
# AUDIO ENGINE
# ──────────────────────────────────────────────
pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, CHUNK)
pygame.init()

C2,D2,E2,F2,G2,A2,B2 = 65.41,73.42,82.41,87.31,98.00,110.00,123.47
C3,D3,E3,F3,G3,A3,B3 = 130.81,146.83,164.81,174.61,196.00,220.00,246.94
C4,D4,E4,F4,G4,A4,B4 = 261.63,293.66,329.63,349.23,392.00,440.00,493.88
C5,D5,E5,F5,G5,A5,B5 = 523.25,587.33,659.25,698.46,784.00,880.00,987.77

WEEK_CHORD_LIBS = {
    "sparse":    [[[C5]],[[E5]],[[G5]],[[A5]],[[C5]],[[D5]]],
    "duet":      [[[C5,E5]],[[D5,G5]],[[E5,A5]],[[G5,B5]],[[A5,C5]],[[F5,C5]]],
    "triad":     [[[C4,E4,G4]],[[D4,G4,A4]],[[E4,G4,C5]],[[A4,C5,E5]],[[F4,A4,C5]],[[G4,B4,D5]]],
    "power":     [[[C3,G3,C4,G4]],[[G2,G3,D4,G4]],[[C3,E4,G4,C5]],[[A3,E4,A4,E5]],
                  [[F3,C4,F4,A4]],[[G3,D4,G4,B4]]],
    "full":      [[[C3,C4,E4,G4,C5]],[[D3,D4,F4,A4,D5]],[[E3,E4,G4,B4,E5]],
                  [[A3,A4,C5,E5,A5]],[[F3,F4,A4,C5,F5]],[[G3,G4,B4,D5,G5]]],
    "orchestra": [[[C2,C3,G3,C4,E4,G4,C5,E5]],[[G2,G3,D4,G4,B4,D5,G5]],
                  [[C2,C3,E3,G3,C4,E4,G4,C5]],[[A2,A3,E4,A4,C5,E5,A5]],
                  [[F2,F3,C4,F4,A4,C5,F5]],   [[G2,G3,D4,G4,B4,D5,G5,B5]]],
}

WEEK_INTERVALS = {
    "slow":       [1.40,1.30,1.60,1.80,1.50,2.20],
    "moderate":   [0.90,0.85,1.00,1.20,1.05,1.40],
    "lively":     [0.60,0.55,0.70,0.85,0.70,1.00],
    "triumphant": [0.45,0.42,0.52,0.65,0.55,0.80],
}

NOTE_DURATION = 0.85

def make_chord_wave(freqs, duration=NOTE_DURATION, amp=0.18):
    n    = int(SAMPLE_RATE * duration)
    t    = np.linspace(0, duration, n, endpoint=False)
    wave = sum(np.sin(2*np.pi*f*t) for f in freqs) / max(len(freqs),1)
    env  = np.ones(n)
    att  = min(int(SAMPLE_RATE*0.05), n//4)
    rel  = min(int(SAMPLE_RATE*0.12), n//4)
    env[:att]  = np.linspace(0,1,att)
    env[-rel:] = np.linspace(1,0,rel)
    mono = (wave*env*amp*32767).astype(np.int16)
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
        timbre         = REHAB_WEEKS[week_idx]["timbre"]
        tempo          = REHAB_WEEKS[week_idx]["tempo"]
        chord_lib      = WEEK_CHORD_LIBS[timbre]
        self.interval  = WEEK_INTERVALS[tempo][self.idx]
        chords         = chord_lib[self.idx % len(chord_lib)]
        self._sounds   = [pygame.sndarray.make_sound(make_chord_wave(f)) for f in chords]
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
# INSTRUMENT VISUALS
# ──────────────────────────────────────────────
INSTRUMENT_NAMES = ["Triangle","Flute","Violin","Cello","Choir","Orchestra"]

def instrument_colors(week_idx):
    theme  = REHAB_WEEKS[week_idx]["theme_col"]
    tr,tg,tb = theme
    base = [
        (200,220,255),(180,255,200),(255,200,160),
        (255,160,180),(220,160,255),(255,220,100),
    ]
    result = []
    for br,bg,bb in base:
        r = int(br*0.6+tr*0.4); g = int(bg*0.6+tg*0.4); b = int(bb*0.6+tb*0.4)
        result.append({"color":(r,g,b),"bar_col":(int(r*0.75),int(g*0.75),int(b*0.75))})
    return result

class SoundBar:
    def __init__(self, x, color, style="normal"):
        self.x         = x
        self.color     = color
        self.phase     = random.uniform(0, 2*math.pi)
        self.speed     = random.uniform(2.0, 5.0)
        self.current_h = 4.0
        if style == "thin":
            self.width=5;  self.h_min=3;  self.h_max=int(25+30*abs(math.sin(x*0.8)))
        elif style == "wide":
            self.width=12; self.h_min=5;  self.h_max=int(55+80*abs(math.sin(x*0.8)))
        else:
            self.width=8;  self.h_min=4;  self.h_max=int(40+60*abs(math.sin(x*0.8)))

    def update(self, t, active, volume):
        if active:
            target = self.h_min+(self.h_max-self.h_min)*volume*(
                0.6+0.4*abs(math.sin(t*self.speed+self.phase)))
        else:
            target = self.h_min+2
        self.current_h += (target-self.current_h)*0.25

    def draw(self, frame, base_y, unlocked):
        r,g,b = self.color if unlocked else (50,50,60)
        h  = max(2, int(self.current_h))
        x1,x2 = self.x-self.width//2, self.x+self.width//2
        cv2.rectangle(frame,(x1,base_y-h),(x2,base_y),(b,g,r),-1)
        if unlocked:
            cv2.rectangle(frame,(x1,base_y-h),(x2,base_y),
                          (min(255,b+40),min(255,g+40),min(255,r+40)),1)

class InstrumentSection:
    def __init__(self, cx, cy, inst_info, unlock_angle, style="normal"):
        self.cx,self.cy   = cx,cy
        self.inst_info    = inst_info
        self.unlock_angle = unlock_angle
        self.relock_angle = unlock_angle - RELOCK_MARGIN
        self.unlocked     = False
        self.unlock_anim  = 0.0
        self.unlock_time  = None
        r,g,b = inst_info["color"]
        spacing=14; n_bars=12
        start_x = cx-(n_bars*spacing)//2
        self.bars      = [SoundBar(start_x+i*spacing,(r,g,b),style) for i in range(n_bars)]
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
        r,g,b = new_inst_info["color"]
        spacing=14; n_bars=12
        start_x = self.cx-(n_bars*spacing)//2
        self.bars = [SoundBar(start_x+i*spacing,(r,g,b),style) for i in range(n_bars)]

    def try_unlock(self, t):
        if not self.unlocked:
            self.unlocked    = True
            self.unlock_time = t
            for _ in range(20):
                a = random.uniform(0, 2*math.pi)
                s = random.uniform(2, 6)
                self.particles.append({
                    "x":self.cx,"y":self.cy,
                    "vx":math.cos(a)*s,"vy":math.sin(a)*s,
                    "life":1.0,"size":random.uniform(2,5),
                })

    def try_relock(self):
        if self.unlocked:
            self.unlocked    = False
            self.unlock_anim = 0.0
            self.unlock_time = None
            self.volume = self.target_volume = 0.0
            self.particles = []

    def update(self, t, global_angle):
        if not self.unlocked and global_angle >= self.unlock_angle:
            self.try_unlock(t)
        elif self.unlocked and global_angle < self.relock_angle:
            self.try_relock()
        window = max(10, self.unlock_angle*0.3)
        self.target_volume = (
            min(1.0,(global_angle-self.unlock_angle+window*0.4)/window)
            if self.unlocked else 0.0
        )
        self.volume += (self.target_volume-self.volume)*0.1
        if self.unlock_time is not None:
            self.unlock_anim = min(1.0,(t-self.unlock_time)/0.8)
        for bar in self.bars:
            bar.update(t, self.unlocked, self.volume)
        for p in self.particles:
            p["x"]+=p["vx"]; p["y"]+=p["vy"]
            p["vy"]+=0.15;   p["life"]-=0.03
        self.particles = [p for p in self.particles if p["life"]>0]

    def draw(self, frame, t):
        base_y = self.cy+30
        if not self.unlocked:
            cv2.putText(frame, f">{int(self.unlock_angle)}\xb0",
                        (self.cx-15,self.cy-25),cv2.FONT_HERSHEY_SIMPLEX,0.35,(70,70,80),1)
        else:
            r,g,b = self.inst_info["color"]
            a     = min(1.0, self.unlock_anim*2)
            col   = (int(b*a),int(g*a),int(r*a))
            cv2.putText(frame, self.inst_info.get("name","?"),
                        (self.cx-30,self.cy-40),cv2.FONT_HERSHEY_SIMPLEX,0.45,col,1)
            vol_w = int(60*self.volume)
            cv2.rectangle(frame,(self.cx-30,self.cy-25),(self.cx+30,self.cy-18),(40,40,50),-1)
            r2,g2,b2 = self.inst_info["bar_col"]
            cv2.rectangle(frame,(self.cx-30,self.cy-25),
                          (self.cx-30+vol_w,self.cy-18),(b2,g2,r2),-1)
        for bar in self.bars:
            bar.draw(frame, base_y, self.unlocked)
        for p in self.particles:
            r,g,b = self.inst_info["color"]
            al   = p["life"]; size = max(1,int(p["size"]*al))
            px,py = int(p["x"]),int(p["y"])
            if 0<=px<W and 0<=py<H:
                cv2.circle(frame,(px,py),size,(int(b*al),int(g*al),int(r*al)),-1)
        if self.unlocked and self.unlock_anim < 1.0:
            r,g,b = self.inst_info["color"]
            al = 1.0-self.unlock_anim
            cv2.circle(frame,(self.cx,self.cy),int(50*self.unlock_anim),
                       (int(b*al),int(g*al),int(r*al)),2)

# ──────────────────────────────────────────────
# ORCHESTRA STAGE
# ──────────────────────────────────────────────
class OrchestraStage:
    POSITIONS = [
        (W//2-420, H//2-20),(W//2-240, H//2-60),
        (W//2-60,  H//2-80),(W//2+120, H//2-60),
        (W//2+280, H//2-20),(W//2+420, H//2+10),
    ]

    def __init__(self, week_idx=0):
        self.week_idx       = week_idx
        self.perf           = PerfTracker()
        self.music_progress = 0.0
        self.was_raised     = False
        self.hold_start     = None
        self.hold_time      = 0.0
        self.session_best_angle = 0.0   # NEW: track this session's best
        self.session_best_hold  = 0.0
        self._build_sections(week_idx)

    def _build_sections(self, week_idx):
        angles = week_unlock_angles(week_idx)
        colors = instrument_colors(week_idx)
        style  = REHAB_WEEKS[week_idx]["bar_style"]
        for i,info in enumerate(colors): info["name"] = INSTRUMENT_NAMES[i]
        self.sections = [
            InstrumentSection(cx,cy,colors[i],angles[i],style)
            for i,(cx,cy) in enumerate(self.POSITIONS)
        ]

    def set_week(self, week_idx):
        self.week_idx = week_idx
        angles = week_unlock_angles(week_idx)
        colors = instrument_colors(week_idx)
        style  = REHAB_WEEKS[week_idx]["bar_style"]
        for i,info in enumerate(colors): info["name"] = INSTRUMENT_NAMES[i]
        for i,section in enumerate(self.sections):
            section.reset_lock(angles[i],colors[i],style)
        self.music_progress = 0.0
        self.perf.reset()

    @property
    def week_max(self):
        return REHAB_WEEKS[self.week_idx]["max_angle"]

    @property
    def total_unlocked(self):
        return sum(s.unlocked for s in self.sections)

    def update(self, angle, t):
        # Track session best
        if angle > self.session_best_angle:
            self.session_best_angle = angle

        self.music_progress = min(100.0, self.music_progress+(angle/self.week_max)*0.05)

        for s in self.sections:
            s.update(t, angle)

        raise_threshold = self.week_max * 0.4
        if angle > raise_threshold:
            if not self.was_raised:
                self.was_raised = True
                self.hold_start = t
            self.hold_time = t - self.hold_start
            if self.hold_time > self.perf.max_hold:
                self.perf.max_hold = self.hold_time
            if self.hold_time > self.session_best_hold:
                self.session_best_hold = self.hold_time
        else:
            if self.was_raised:
                self.perf.reps += 1
            self.was_raised = False
            self.hold_start = None
            self.hold_time  = 0.0

        self.perf.instruments = self.total_unlocked
        if not self.perf.week_done:
            self.perf.week_done = self.perf.check_gate(self.week_idx)

    def audio_state(self):
        return ([s.unlocked for s in self.sections],
                [s.volume   for s in self.sections])

    def draw(self, frame, t):
        stage_y = H-60
        cv2.line(frame,(80,stage_y),(W-80,stage_y),(60,55,70),1)
        for i in range(10):
            x = 80+i*((W-160)//9)
            cv2.line(frame,(x,stage_y),(x,stage_y+15),(50,45,60),1)
        for s in self.sections:
            cv2.line(frame,(s.cx,stage_y),(s.cx,s.cy+35),(45,40,55),1)
            s.draw(frame, t)

# ──────────────────────────────────────────────
# WEEK SELECTOR OVERLAY
# ──────────────────────────────────────────────
def draw_week_selector(frame, selected_idx, unlocked_weeks):
    overlay = frame.copy()
    cv2.rectangle(overlay,(W//2-340,H//2-250),(W//2+340,H//2+260),(12,8,22),-1)
    cv2.addWeighted(overlay,0.92,frame,0.08,0,frame)
    cv2.rectangle(frame,(W//2-340,H//2-250),(W//2+340,H//2+260),(80,60,110),2)
    cv2.putText(frame,"RECOVERY WEEK",
                (W//2-120,H//2-215),cv2.FONT_HERSHEY_SIMPLEX,0.75,(200,160,255),2)
    cv2.putText(frame,"Complete week goals to unlock the next",
                (W//2-190,H//2-188),cv2.FONT_HERSHEY_SIMPLEX,0.38,(140,130,160),1)
    for i,week in enumerate(REHAB_WEEKS):
        y      = H//2-155+i*56
        is_sel = (i==selected_idx)
        avail  = i in unlocked_weeks
        bg_col = (40,28,60) if is_sel else (18,14,30)
        cv2.rectangle(frame,(W//2-325,y-24),(W//2+325,y+28),bg_col,-1)
        border = (160,100,255) if is_sel else ((60,50,80) if avail else (35,30,45))
        cv2.rectangle(frame,(W//2-325,y-24),(W//2+325,y+28),border,1 if not is_sel else 2)
        label_col = (210,170,255) if is_sel else ((120,110,140) if avail else (60,55,70))
        cv2.putText(frame,f"{i+1}  {week['label']}  (up to {week['max_angle']}\xb0)",
                    (W//2-310,y+6),cv2.FONT_HERSHEY_SIMPLEX,0.42,label_col,1)
        tip_col = (160,200,160) if is_sel else ((70,80,70) if avail else (45,45,50))
        cv2.putText(frame,week["tip"],
                    (W//2-310,y+22),cv2.FONT_HERSHEY_SIMPLEX,0.30,tip_col,1)
        req = week.get("unlock_req")
        if not avail and req:
            cv2.putText(frame,
                        f"Need: {req['reps']}reps  {req['hold_s']:.0f}s hold  {req['instruments']} instruments",
                        (W//2-310,y+35),cv2.FONT_HERSHEY_SIMPLEX,0.28,(90,70,100),1)
        arc_cx = W//2+295
        sweep  = int(week["max_angle"]*0.75)
        arc_col = (160,100,255) if is_sel else (60,50,80)
        cv2.ellipse(frame,(arc_cx,y+2),(18,18),-90,-sweep//2,sweep//2,arc_col,2)
    cv2.putText(frame,"1-6 select  |  ENTER confirm  |  locked weeks require performance goals",
                (W//2-270,H//2+240),cv2.FONT_HERSHEY_SIMPLEX,0.30,(90,85,110),1)

# ──────────────────────────────────────────────
# POSE HELPERS
# ──────────────────────────────────────────────
def calc_angle(a, b, c):
    a,b,c = np.array(a),np.array(b),np.array(c)
    angle = abs(math.degrees(
        math.atan2(c[1]-b[1],c[0]-b[0]) - math.atan2(a[1]-b[1],a[0]-b[0])))
    return 360-angle if angle>180 else angle

def get_abduction_angle(landmarks):
    lm   = landmarks
    Pose = mp.solutions.pose.PoseLandmark
    hip      = [lm[Pose.LEFT_HIP.value].x,      lm[Pose.LEFT_HIP.value].y]
    shoulder = [lm[Pose.LEFT_SHOULDER.value].x,  lm[Pose.LEFT_SHOULDER.value].y]
    elbow    = [lm[Pose.LEFT_ELBOW.value].x,     lm[Pose.LEFT_ELBOW.value].y]
    return calc_angle(hip, shoulder, elbow)

def draw_conductor_arc(frame, angle, cx, cy, week_max, theme_col):
    sweep    = min(angle, week_max)
    progress = sweep/week_max
    tr,tg,tb = theme_col
    color    = (int(tb*0.8),int(tg*0.8),int(tr*0.8)) if progress<0.5 \
               else (int(tb),int(tg),int(tr))
    cv2.ellipse(frame,(cx,cy),(70,70),-90,-int(week_max*0.5),int(week_max*0.5),(55,50,65),1)
    cv2.ellipse(frame,(cx,cy),(70,70),-90,-int(sweep*0.5),int(sweep*0.5),color,2)
    rad = math.radians(-90+sweep/2)
    cv2.circle(frame,(int(cx+70*math.cos(rad)),int(cy+70*math.sin(rad))),5,color,-1)
    tick_rad = math.radians(-90+week_max/2)
    tx,ty = int(cx+70*math.cos(tick_rad)),int(cy+70*math.sin(tick_rad))
    cv2.circle(frame,(tx,ty),3,(180,100,255),-1)

# ──────────────────────────────────────────────
# HUD  ← main changes here
# ──────────────────────────────────────────────
def draw_hud(frame, angle, stage, t, next_week_ready):
    week     = REHAB_WEEKS[stage.week_idx]
    week_max = stage.week_max
    perf     = stage.perf
    req      = week.get("unlock_req")
    theme    = week["theme_col"]
    tr,tg,tb = theme

    # Adaptive target for today
    today_target = effective_rom_target(week_max)
    hold_target  = prog["hold_target"]

    # Pull history
    yesterday   = get_yesterday_entry()
    today_entry = get_today_entry()
    atb_angle   = prog["all_time_best_angle"]
    atb_hold    = prog["all_time_best_hold"]
    trend       = prog["trend"]
    penalty_days= prog["rom_penalty_days"]

    panel = frame.copy()
    cv2.rectangle(panel,(10,10),(400,360),(10,8,18),-1)
    cv2.addWeighted(panel,0.80,frame,0.20,0,frame)
    cv2.rectangle(frame,(10,10),(400,360),(int(tb*0.3),int(tg*0.3),int(tr*0.3)),1)

    cv2.putText(frame,"THE FORGOTTEN ORCHESTRA",
                (20,36),cv2.FONT_HERSHEY_SIMPLEX,0.48,(int(tb),int(tg),int(tr)),1)
    cv2.putText(frame,f"{week['label']}  |  {week['goal_label']}",
                (20,56),cv2.FONT_HERSHEY_SIMPLEX,0.38,(160,100,255),1)

    # ── Adaptive ROM target bar ──
    target_col = (80,80,200) if penalty_days>0 else (int(tb*0.3),int(tg*0.8),int(tr*0.3))
    target_label = f"Today target: {today_target}\xb0" + (f"  [{penalty_days}d reduced]" if penalty_days>0 else "")
    cv2.putText(frame,target_label,
                (20,76),cv2.FONT_HERSHEY_SIMPLEX,0.36,(180,170,200),1)
    cv2.rectangle(frame,(20,81),(220,91),(35,30,50),-1)
    fill = int(200*min(angle,today_target)/today_target)
    cv2.rectangle(frame,(20,81),(20+fill,91),target_col,-1)
    # Also show where the real week_max is
    tick_x = 20+int(200*week_max/today_target) if today_target>0 else 220
    if today_target < week_max and tick_x <= 220:
        cv2.line(frame,(tick_x,79),(tick_x,93),(100,80,140),1)

    cv2.putText(frame,week["tip"],
                (20,110),cv2.FONT_HERSHEY_SIMPLEX,0.30,(120,180,140),1)

    # ── Hold target ──
    hold_col = (60,200,80) if stage.hold_time>=hold_target else (int(tb*0.5),int(tg*0.5),int(tr))
    cv2.putText(frame,f"Hold target: {hold_target:.1f}s   Current: {stage.hold_time:.1f}s",
                (20,126),cv2.FONT_HERSHEY_SIMPLEX,0.36,hold_col,1)
    cv2.rectangle(frame,(20,131),(220,141),(35,30,50),-1)
    hold_fill = int(200*min(stage.hold_time/max(hold_target,0.1),1.0))
    cv2.rectangle(frame,(20,131),(20+hold_fill,141),hold_col,-1)

    # ── Music progress ──
    cv2.putText(frame,f"Music restored: {int(stage.music_progress)}%",
                (20,158),cv2.FONT_HERSHEY_SIMPLEX,0.36,(180,170,200),1)
    cv2.rectangle(frame,(20,163),(220,173),(35,30,50),-1)
    cv2.rectangle(frame,(20,163),(20+int(200*stage.music_progress/100),173),
                  (int(tb*0.7),int(tg*0.4),int(tr*0.7)),-1)

    cv2.putText(frame,f"Instruments: {stage.total_unlocked}/6",
                (20,190),cv2.FONT_HERSHEY_SIMPLEX,0.36,(160,150,180),1)
    cv2.putText(frame,f"Reps: {perf.reps}   Best hold: {perf.max_hold:.1f}s",
                (20,206),cv2.FONT_HERSHEY_SIMPLEX,0.34,(160,150,180),1)

    colors = instrument_colors(stage.week_idx)
    cv2.putText(frame,"Awakened:",(20,222),cv2.FONT_HERSHEY_SIMPLEX,0.30,(120,110,140),1)
    for i,(info,sec) in enumerate(zip(colors,stage.sections)):
        r,g,b = info["color"]
        col   = (int(b*0.7),int(g*0.7),int(r*0.7)) if sec.unlocked else (40,40,50)
        cv2.circle(frame,(95+i*22,219),6,col,-1)

    # ── Daily comparison panel ──
    cv2.line(frame,(15,232),(395,232),(50,45,65),1)

    # Session best (this run)
    sb = int(stage.session_best_angle)
    sb_col = (60,200,80) if sb>=today_target else (int(tb),int(tg),int(tr))
    cv2.putText(frame,f"This session: {sb}\xb0  hold: {stage.session_best_hold:.1f}s",
                (20,248),cv2.FONT_HERSHEY_SIMPLEX,0.36,sb_col,1)

    # Yesterday
    if yesterday:
        yd_col = (100,160,100) if yesterday["max_angle"]<=sb else (140,100,100)
        cv2.putText(frame,f"Yesterday:    {yesterday['max_angle']}\xb0  hold: {yesterday['max_hold']:.1f}s",
                    (20,264),cv2.FONT_HERSHEY_SIMPLEX,0.34,yd_col,1)
    else:
        cv2.putText(frame,"Yesterday:    --  (first session!)",
                    (20,264),cv2.FONT_HERSHEY_SIMPLEX,0.34,(80,80,100),1)

    # All-time best
    atb_col = (255,200,60) if atb_angle>0 else (70,70,90)
    cv2.putText(frame,f"All-time best: {atb_angle}\xb0  hold: {atb_hold:.1f}s",
                (20,280),cv2.FONT_HERSHEY_SIMPLEX,0.34,atb_col,1)

    # Trend badge
    trend_sym  = "▲ IMPROVING — hold +boosted"  if trend=="UP"   else \
                 f"▼ DROPPED — target -reduced ({penalty_days}d)" if trend=="DROP" else \
                 "● STEADY"
    trend_col  = (60,200,80) if trend=="UP" else (60,80,200) if trend=="DROP" else (100,100,120)
    cv2.putText(frame,trend_sym,
                (20,296),cv2.FONT_HERSHEY_SIMPLEX,0.34,trend_col,1)

    # ── Performance gate ──
    if req:
        cv2.line(frame,(15,306),(395,306),(50,45,65),1)
        def gc(done): return (60,200,80) if done else (120,100,140)
        r_done=perf.reps>=req["reps"]
        h_done=perf.max_hold>=req["hold_s"]
        i_done=perf.instruments>=req["instruments"]
        cv2.putText(frame,f"Gate — Reps {perf.reps}/{req['reps']}",
                    (20,320),cv2.FONT_HERSHEY_SIMPLEX,0.30,gc(r_done),1)
        cv2.putText(frame,f"Hold {perf.max_hold:.1f}/{req['hold_s']:.0f}s",
                    (160,320),cv2.FONT_HERSHEY_SIMPLEX,0.30,gc(h_done),1)
        cv2.putText(frame,f"Inst {perf.instruments}/{req['instruments']}",
                    (280,320),cv2.FONT_HERSHEY_SIMPLEX,0.30,gc(i_done),1)

    if next_week_ready and stage.week_idx < len(REHAB_WEEKS)-1:
        cv2.putText(frame,">> Week goal met! Press W to advance <<",
                    (20,340),cv2.FONT_HERSHEY_SIMPLEX,0.38,(int(tb),int(tg),int(tr)),1)

    # ── Encouragement ──
    progress_pct = angle/week_max if week_max>0 else 0
    encourage    = week["encourage"]
    if angle < 5:
        msg,col = "Raise your arm gently to begin!",(100,100,120)
    elif progress_pct < 0.35:
        msg,col = encourage[0],(100,160,255)
    elif progress_pct < 0.65:
        msg,col = (encourage[1] if len(encourage)>1 else encourage[0]),(140,200,140)
    elif progress_pct < 0.90:
        msg,col = encourage[-1],(180,220,100)
    else:
        msg,col = f"{week['goal_label']} reached! Wonderful!",(int(tb),int(tg),int(tr))
    cv2.putText(frame,msg,(W//2-len(msg)*5,H-30),cv2.FONT_HERSHEY_SIMPLEX,0.62,col,2)

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("RehabVerse — The Forgotten Orchestra  (v3)")
    print("  Daily adaptive targets + session history\n")

    mp_pose_    = mp.solutions.pose
    mp_drawing_ = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)

    unlocked_weeks = {0}
    selected_week  = 0
    in_selector    = True
    ret, bg_frame  = cap.read()
    if ret: bg_frame = cv2.flip(bg_frame,1)
    else:   bg_frame = np.zeros((H,W,3),dtype=np.uint8)

    while in_selector:
        frame = bg_frame.copy()
        dark  = np.zeros_like(frame,dtype=np.uint8); dark[:] = (15,10,25)
        cv2.addWeighted(dark,0.6,frame,0.4,0,frame)
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

    with mp_pose_.Pose(min_detection_confidence=0.6,
                       min_tracking_confidence=0.6) as pose:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            frame   = cv2.flip(frame,1)
            rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)
            t       = time.time()

            angle = smoothed_angle
            if results.pose_landmarks:
                lm             = results.pose_landmarks.landmark
                raw            = get_abduction_angle(lm)
                smoothed_angle = 0.82*smoothed_angle + 0.18*raw
                angle          = smoothed_angle

                ls = lm[mp_pose_.PoseLandmark.LEFT_SHOULDER.value]
                draw_conductor_arc(frame, angle,
                                   int(ls.x*W), int(ls.y*H),
                                   stage.week_max,
                                   REHAB_WEEKS[stage.week_idx]["theme_col"])
                mp_drawing_.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose_.POSE_CONNECTIONS,
                    mp_drawing_.DrawingSpec(color=(80,70,100),thickness=1,circle_radius=2),
                    mp_drawing_.DrawingSpec(color=(70,60,90), thickness=1))

            bg_col = REHAB_WEEKS[stage.week_idx]["bg_tint"]
            dark   = np.zeros_like(frame,dtype=np.uint8); dark[:] = bg_col
            cv2.addWeighted(dark,0.45,frame,0.55,0,frame)

            stage.update(angle, t)
            stage.draw(frame, t)

            if stage.perf.week_done and stage.week_idx+1 < len(REHAB_WEEKS):
                unlocked_weeks.add(stage.week_idx+1)

            unlocked, volumes = stage.audio_state()
            audio_engine.update(unlocked, volumes, t)

            next_week_ready = stage.perf.week_done and stage.week_idx < len(REHAB_WEEKS)-1
            draw_hud(frame, angle, stage, t, next_week_ready)
            cv2.putText(frame,"Q quit & save  |  W change week",
                        (W-250,H-15),cv2.FONT_HERSHEY_SIMPLEX,0.38,(70,65,85),1)

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

    # ── Save session on quit ──
    commit_session(stage.session_best_angle, stage.session_best_hold, stage.week_idx)
    audio_engine.stop()
    cap.release()
    cv2.destroyAllWindows()
    pygame.quit()

    week = REHAB_WEEKS[stage.week_idx]
    perf = stage.perf
    req  = week.get("unlock_req")
    print(f"\nSession saved  ({week['label']})")
    print(f"  Session best angle:  {int(stage.session_best_angle)}\xb0")
    print(f"  Session best hold:   {stage.session_best_hold:.1f}s")
    print(f"  All-time best angle: {prog['all_time_best_angle']}\xb0")
    print(f"  Hold target now:     {prog['hold_target']:.1f}s")
    print(f"  Trend:               {prog['trend']}")
    if prog['rom_penalty_days'] > 0:
        print(f"  ROM reduced for:     {prog['rom_penalty_days']} more day(s)")
    if req:
        gate_met = perf.check_gate(stage.week_idx)
        print(f"  Week gate:           {'CLEARED' if gate_met else 'not yet'}")

if __name__ == "__main__":
    main()