"""
RehabVerse — The Forgotten Orchestra  (v4)
==========================================
This version implements the finalized "RehabVerse Final Rehabilitation Flow"
spec on top of the v3 pose/audio/visual engine:

  • Weekly ROM goal is FIXED for the whole week (no more penalty-day drops).
  • Hold Time and Rep Target are the only adaptive parameters. They ramp
    up day over day when the patient performs well, and step back down
    on a missed/poor day. They never affect the ROM goal.
  • Two independent sessions per day: Morning and Evening.
  • Each session shows a live "Today's Objectives" checklist (ROM / Hold /
    Reps / Restore Orchestra) and starts the orchestra at 0% every time.
  • Day 7 is the official Weekly Assessment: both Morning and Evening
    sessions are tested against the week's FINAL hold/rep targets (not
    the daily adaptive ones). The week only clears if BOTH sessions meet
    ROM + Hold + Reps. Otherwise -> "Week Extended" (never "Week Failed").
  • A permanent "Kingdom Orchestra" tracks one restored instrument family
    per completed week, independent of daily session resets.
  • Daily Dashboard HUD shows week/day, targets, session status, today's
    orchestra %, kingdom %, and streak.

Install:
    pip install opencv-python mediapipe numpy pygame

Run:
    python forgotten_orchestra_v4.py

Future : 
    specify arm (l OR r) !IMPORTANT
"""

import cv2
import numpy as np
import math
import time
import random
import json
import os
from datetime import date, datetime

import pygame
import pygame.sndarray
import mediapipe as mp

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
W, H        = 1280, 720
SAMPLE_RATE = 44100
CHUNK       = 1024
DATA_FILE   = "rehabverse_progress.json"

KINGDOM_NAMES = ["Strings", "Woodwinds", "Brass", "Choir", "Percussion", "Full Orchestra"]

# ──────────────────────────────────────────────
# REHAB WEEK DEFINITIONS
#   max_angle          = FIXED weekly ROM goal (never changes mid-week)
#   start_hold/final_hold = adaptive hold time range for the week
#   start_reps/final_reps = adaptive rep target range for the week
#   final_hold/final_reps are also what Day 7 assessment tests against
# ──────────────────────────────────────────────
REHAB_WEEKS = [
    {
        "label": "Week 1", "max_angle": 45,
        "tip": "Gentle pendulum — let gravity do the work.",
        "goal_label": "45° goal",
        "encourage": ["Easy does it!", "Great start!", "Listen to your body."],
        "theme_col": (180, 210, 255), "bg_tint": (10, 8, 22),
        "bar_style": "thin", "tempo": "slow", "timbre": "sparse",
        "start_hold": 5.0, "final_hold": 10.0,
        "start_reps": 5,   "final_reps": 10,
    },
    {
        "label": "Week 2", "max_angle": 70,
        "tip": "Active-assisted range. Use your good arm if needed.",
        "goal_label": "70° goal",
        "encourage": ["Nice progress!", "Smooth and steady.", "You're doing great!"],
        "theme_col": (180, 255, 210), "bg_tint": (8, 18, 14),
        "bar_style": "normal", "tempo": "moderate", "timbre": "duet",
        "start_hold": 10.5, "final_hold": 15.0,
        "start_reps": 7,   "final_reps": 12,
    },
    {
        "label": "Week 3", "max_angle": 90,
        "tip": "Reach shoulder height — no higher than comfortable.",
        "goal_label": "90° goal (shoulder height)",
        "encourage": ["Shoulder height reached!", "Beautiful form!", "Keep it smooth."],
        "theme_col": (255, 200, 140), "bg_tint": (18, 12, 6),
        "bar_style": "normal", "tempo": "moderate", "timbre": "triad",
        "start_hold": 16.0, "final_hold": 20.0,
        "start_reps": 9,   "final_reps": 14,
    },
    {
        "label": "Week 4", "max_angle": 110,
        "tip": "Push gently past shoulder — stop at any pain.",
        "goal_label": "110° goal",
        "encourage": ["Above the shoulder!", "Strong work!", "Steady progress."],
        "theme_col": (255, 140, 180), "bg_tint": (20, 6, 14),
        "bar_style": "wide", "tempo": "lively", "timbre": "power",
        "start_hold": 20.5, "final_hold": 25.0,
        "start_reps": 11,  "final_reps": 16,
    },
    {
        "label": "Week 5", "max_angle": 130,
        "tip": "Approaching overhead. Never force through pain.",
        "goal_label": "130° goal",
        "encourage": ["Almost overhead!", "Excellent control!", "You've come far!"],
        "theme_col": (200, 140, 255), "bg_tint": (14, 6, 22),
        "bar_style": "wide", "tempo": "lively", "timbre": "full",
        "start_hold": 26.0, "final_hold": 40.0,
        "start_reps": 13,  "final_reps": 18,
    },
    {
        "label": "Week 6+", "max_angle": 160,
        "tip": "Full functional range. Quality over height.",
        "goal_label": "160° full range",
        "encourage": ["Full orchestra!", "Peak performance!", "The kingdom sings!"],
        "theme_col": (255, 220, 80), "bg_tint": (18, 14, 4),
        "bar_style": "wide", "tempo": "triumphant", "timbre": "orchestra",
        "start_hold": 41.0, "final_hold": 60.0,
        "start_reps": 15,  "final_reps": 20,
    },
]
LAST_WEEK_IDX = len(REHAB_WEEKS) - 1

# ──────────────────────────────────────────────
# PERSISTENCE — week / day / session state machine
# ──────────────────────────────────────────────
def today_str():
    return str(date.today())

def _default_progress():
    w = REHAB_WEEKS[0]
    return {
        "week_idx": 0,
        "day_number": 1,                 # 1..7, day 7 = assessment day
        "last_active_date": None,
        "hold_target": w["start_hold"],  # today's adaptive hold target
        "rep_target": w["start_reps"],   # today's adaptive rep target
        "morning_done": False,
        "evening_done": False,
        "today_morning_record": None,    # {"rom":bool,"hold":bool,"reps":bool}
        "today_evening_record": None,
        "day7_morning": None,
        "day7_evening": None,
        "streak": 0,
        "kingdom": [False] * len(REHAB_WEEKS),
        "last_result": None,             # "WEEK_COMPLETE" / "WEEK_EXTENDED"
    }

def load_progress():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            p = json.load(f)
        # backfill any missing keys (schema upgrades)
        for k, v in _default_progress().items():
            p.setdefault(k, v)
        return p
    return _default_progress()

def save_progress(p):
    with open(DATA_FILE, "w") as f:
        json.dump(p, f, indent=2)

def _reset_week_targets(prog):
    w = REHAB_WEEKS[prog["week_idx"]]
    prog["hold_target"] = w["start_hold"]
    prog["rep_target"] = w["start_reps"]

def _adapt_daily_targets(prog, good_day, poor_day):
    """Only Hold Time and Rep Target ever move. ROM goal is untouched."""
    w = REHAB_WEEKS[prog["week_idx"]]
    if good_day:
        prog["hold_target"] = min(w["final_hold"], round(prog["hold_target"] + 2, 1))
        prog["rep_target"] = min(w["final_reps"], prog["rep_target"] + 1)
    elif poor_day:
        prog["hold_target"] = max(w["start_hold"], round(prog["hold_target"] - 2, 1))
        prog["rep_target"] = max(3, prog["rep_target"] - 2)
    # else steady -> no change

def _close_out_day(prog):
    """Roll one elapsed calendar day: handles Day-7 assessment or a normal
    adaptive day, then clears the day's session flags."""
    day_num = prog["day_number"]
    m_done, e_done = prog["morning_done"], prog["evening_done"]

    if day_num == 7:
        m = prog.get("day7_morning")
        e = prog.get("day7_evening")
        m_pass = bool(m) and m["rom"] and m["hold"] and m["reps"]
        e_pass = bool(e) and e["rom"] and e["hold"] and e["reps"]
        if m_pass and e_pass:
            prog["kingdom"][prog["week_idx"]] = True
            prog["last_result"] = "WEEK_COMPLETE"
            if prog["week_idx"] < LAST_WEEK_IDX:
                prog["week_idx"] += 1
        else:
            prog["last_result"] = "WEEK_EXTENDED"
        _reset_week_targets(prog)
        prog["day_number"] = 1
        prog["day7_morning"] = None
        prog["day7_evening"] = None
        prog["streak"] = prog["streak"] + 1 if (m_done or e_done) else 0
    else:
        good_day = poor_day = False
        if not m_done and not e_done:
            poor_day = True
        else:   
            hit_full = False
            hit_none = True
            for rec in (prog.get("today_morning_record"), prog.get("today_evening_record")):
                if rec:
                    if rec["hold"] and rec["reps"]:
                        hit_full = True
                    if rec["hold"] or rec["reps"]:
                        hit_none = False
            good_day = hit_full
            poor_day = hit_none and not hit_full
        _adapt_daily_targets(prog, good_day, poor_day)
        prog["day_number"] = min(7, day_num + 1)
        prog["streak"] = prog["streak"] + 1 if (m_done or e_done) else 0

    prog["morning_done"] = False
    prog["evening_done"] = False
    prog["today_morning_record"] = None
    prog["today_evening_record"] = None

def advance_day_if_needed(prog):
    today = today_str()
    last = prog.get("last_active_date")
    if last is None:
        prog["last_active_date"] = today
        save_progress(prog)
        return
    if last == today:
        return
    try:
        elapsed = (date.fromisoformat(today) - date.fromisoformat(last)).days
    except ValueError:
        elapsed = 1
    for _ in range(max(1, elapsed)):
        _close_out_day(prog)
    prog["last_active_date"] = today
    save_progress(prog)

def finalize_session(prog, slot, rom_met, hold_met, reps_met):
    record = {"rom": bool(rom_met), "hold": bool(hold_met), "reps": bool(reps_met)}
    if slot == "morning":
        prog["morning_done"] = True
        prog["today_morning_record"] = record
        if prog["day_number"] == 7:
            prog["day7_morning"] = record
    else:
        prog["evening_done"] = True
        prog["today_evening_record"] = record
        if prog["day_number"] == 7:
            prog["day7_evening"] = record
    prog["last_active_date"] = today_str()
    save_progress(prog)

def default_session_slot():
    return "morning" if time.localtime().tm_hour < 14 else "evening"

# ──────────────────────────────────────────────
# AUDIO ENGINE  (unchanged musical building blocks from v3)
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
#   Unlocking is now driven by SESSION OBJECTIVE milestones, not raw angle:
#     ROM objective met   -> instruments 0,1 awaken
#     Hold objective met  -> instruments 2,3 awaken
#     Reps objective met  -> instruments 4,5 awaken (100% restored)
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
    """A single instrument's visual/audio slot. Unlock state is now set
    directly by the OrchestraStage based on session-objective milestones."""
    def __init__(self, cx, cy, inst_info, style="normal"):
        self.cx,self.cy   = cx,cy
        self.inst_info    = inst_info
        self.unlocked     = False
        self.unlock_anim  = 0.0
        self.unlock_time  = None
        self.volume    = self.target_volume = 0.0
        self.particles = []
        self._build_bars(style)

    def _build_bars(self, style):
        r,g,b = self.inst_info["color"]
        spacing=14; n_bars=12
        start_x = self.cx-(n_bars*spacing)//2
        self.bars = [SoundBar(start_x+i*spacing,(r,g,b),style) for i in range(n_bars)]

    def reset_session(self, new_inst_info, style):
        """Called at the start of every session — orchestra restarts at 0%."""
        self.inst_info    = new_inst_info
        self.unlocked     = False
        self.unlock_anim  = 0.0
        self.unlock_time  = None
        self.volume = self.target_volume = 0.0
        self.particles = []
        self._build_bars(style)

    def set_unlocked(self, unlocked, t):
        if unlocked and not self.unlocked:
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
        elif not unlocked and self.unlocked:
            self.unlocked    = False
            self.unlock_anim = 0.0
            self.unlock_time = None
            self.volume = self.target_volume = 0.0
            self.particles = []

    def update(self, t):
        self.target_volume = (0.55 + 0.45*abs(math.sin(t*1.4 + self.cx))) if self.unlocked else 0.0
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
            cv2.putText(frame, "locked",
                        (self.cx-22,self.cy-25),cv2.FONT_HERSHEY_SIMPLEX,0.32,(70,70,80),1)
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
# SESSION OBJECTIVES + ORCHESTRA STAGE
# ──────────────────────────────────────────────
class SessionObjectives:
    """Tracks the 4 checklist items for the CURRENT session only."""
    def __init__(self, rom_target, hold_target, rep_target):
        self.rom_target  = rom_target
        self.hold_target = hold_target
        self.rep_target  = rep_target
        self.reps          = 0
        self.session_max_angle = 0.0
        self.session_max_hold  = 0.0

    @property
    def rom_met(self):
        return self.session_max_angle >= self.rom_target

    @property
    def hold_met(self):
        return self.session_max_hold >= self.hold_target

    @property
    def reps_met(self):
        return self.reps >= self.rep_target

    @property
    def orchestra_restored(self):
        return self.rom_met and self.hold_met and self.reps_met

class OrchestraStage:
    POSITIONS = [
        (W//2-420, H//2-20),(W//2-240, H//2-60),
        (W//2-60,  H//2-80),(W//2+120, H//2-60),
        (W//2+280, H//2-20),(W//2+420, H//2+10),
    ]

    def __init__(self, week_idx, objectives):
        self.week_idx   = week_idx
        self.objectives = objectives
        self.music_progress = 0.0
        self.was_raised = False
        self.hold_start = None
        self.hold_time  = 0.0
        self._build_sections(week_idx)

    def _build_sections(self, week_idx):
        colors = instrument_colors(week_idx)
        style  = REHAB_WEEKS[week_idx]["bar_style"]
        for i,info in enumerate(colors): info["name"] = INSTRUMENT_NAMES[i]
        self.sections = [
            InstrumentSection(cx,cy,colors[i],style)
            for i,(cx,cy) in enumerate(self.POSITIONS)
        ]

    def restart_session(self, week_idx, objectives):
        """Reset the orchestra to 0% — called at the start of every session."""
        self.week_idx   = week_idx
        self.objectives = objectives
        self.music_progress = 0.0
        self.was_raised = False
        self.hold_start = None
        self.hold_time  = 0.0
        colors = instrument_colors(week_idx)
        style  = REHAB_WEEKS[week_idx]["bar_style"]
        for i,info in enumerate(colors): info["name"] = INSTRUMENT_NAMES[i]
        for i,section in enumerate(self.sections):
            section.reset_session(colors[i], style)

    @property
    def rom_target(self):
        return self.objectives.rom_target

    @property
    def total_unlocked(self):
        return sum(s.unlocked for s in self.sections)

    def update(self, angle, t):
        obj = self.objectives
        if angle > obj.session_max_angle:
            obj.session_max_angle = angle

        # rep / hold counting: "raised" once past 40% of the week's ROM goal
        raise_threshold = self.rom_target * 0.4
        if angle > raise_threshold:
            if not self.was_raised:
                self.was_raised = True
                self.hold_start = t
            self.hold_time = t - self.hold_start
            if self.hold_time > obj.session_max_hold:
                obj.session_max_hold = self.hold_time
        else:
            if self.was_raised:
                obj.reps += 1
            self.was_raised = False
            self.hold_start = None
            self.hold_time  = 0.0

        # milestone-driven instrument unlocking (0-1 ROM, 2-3 Hold, 4-5 Reps)
        want_unlocked = [obj.rom_met, obj.rom_met, obj.hold_met, obj.hold_met,
                          obj.reps_met, obj.reps_met]
        for sec, want in zip(self.sections, want_unlocked):
            sec.set_unlocked(want, t)
            sec.update(t)

        self.music_progress = (self.total_unlocked / 6.0) * 100.0

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
# DAY BRIEFING OVERLAY  (pre-session screen)
# ──────────────────────────────────────────────
def draw_day_briefing(frame, prog, chosen_slot):
    week = REHAB_WEEKS[prog["week_idx"]]
    is_day7 = prog["day_number"] == 7
    kingdom_pct = int(100 * sum(prog["kingdom"]) / len(prog["kingdom"]))

    overlay = frame.copy()
    cv2.rectangle(overlay,(W//2-360,H//2-260),(W//2+360,H//2+270),(12,8,22),-1)
    cv2.addWeighted(overlay,0.92,frame,0.08,0,frame)
    cv2.rectangle(frame,(W//2-360,H//2-260),(W//2+360,H//2+270),(80,60,110),2)

    cv2.putText(frame,"RehabVerse — Daily Briefing",
                (W//2-190,H//2-220),cv2.FONT_HERSHEY_SIMPLEX,0.72,(200,160,255),2)

    if prog["last_result"] == "WEEK_COMPLETE":
        cv2.putText(frame,"Week Complete! New week unlocked.",
                    (W//2-190,H//2-188),cv2.FONT_HERSHEY_SIMPLEX,0.42,(80,220,120),1)
    elif prog["last_result"] == "WEEK_EXTENDED":
        cv2.putText(frame,"Week Extended — let's give it another pass.",
                    (W//2-210,H//2-188),cv2.FONT_HERSHEY_SIMPLEX,0.42,(220,160,80),1)
    else:
        cv2.putText(frame,f"{week['label']}  |  {week['goal_label']}",
                    (W//2-150,H//2-188),cv2.FONT_HERSHEY_SIMPLEX,0.42,(160,150,190),1)

    y = H//2-140
    lines = [
        (f"Week: {prog['week_idx']+1}   Day: {prog['day_number']}/7"
         + ("   *** ASSESSMENT DAY ***" if is_day7 else ""), (255,220,120) if is_day7 else (200,200,210)),
        (f"Weekly ROM Goal (fixed): {week['max_angle']}\xb0", (int(week['theme_col'][2]),int(week['theme_col'][1]),int(week['theme_col'][0]))),
    ]
    if is_day7:
        lines.append((f"Assessment targets — Hold: {week['final_hold']:.1f}s   Reps: {week['final_reps']}", (255,220,120)))
    else:
        lines.append((f"Today's Hold Target: {prog['hold_target']:.1f}s   Today's Rep Target: {prog['rep_target']}", (200,200,210)))
    lines.append((f"Morning Session: {'DONE' if prog['morning_done'] else 'pending'}", (80,220,120) if prog['morning_done'] else (150,140,170)))
    lines.append((f"Evening Session: {'DONE' if prog['evening_done'] else 'pending'}", (80,220,120) if prog['evening_done'] else (150,140,170)))
    lines.append((f"Kingdom Restoration: {kingdom_pct}%  ({sum(prog['kingdom'])}/{len(prog['kingdom'])} families)", (255,200,60)))
    lines.append((f"Current Streak: {prog['streak']} day(s)", (150,180,255)))

    for text,col in lines:
        cv2.putText(frame,text,(W//2-320,y),cv2.FONT_HERSHEY_SIMPLEX,0.42,col,1)
        y += 34

    y += 10
    m_col = (255,255,255) if chosen_slot=="morning" else (140,130,160)
    e_col = (255,255,255) if chosen_slot=="evening" else (140,130,160)
    cv2.putText(frame,"[M] Morning Session", (W//2-320,y), cv2.FONT_HERSHEY_SIMPLEX,0.46,m_col,2 if chosen_slot=="morning" else 1)
    cv2.putText(frame,"[E] Evening Session", (W//2+30,y), cv2.FONT_HERSHEY_SIMPLEX,0.46,e_col,2 if chosen_slot=="evening" else 1)
    y += 40
    cv2.putText(frame,"Press ENTER/SPACE to begin the highlighted session, or Q to quit.",
                (W//2-320,y),cv2.FONT_HERSHEY_SIMPLEX,0.34,(120,115,140),1)

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
# IN-SESSION HUD  — Objectives checklist + Daily Dashboard
# ──────────────────────────────────────────────
def draw_hud(frame, angle, stage, prog, slot, is_day7):
    week     = REHAB_WEEKS[stage.week_idx]
    obj      = stage.objectives
    theme    = week["theme_col"]
    tr,tg,tb = theme

    panel = frame.copy()
    cv2.rectangle(panel,(10,10),(410,400),(10,8,18),-1)
    cv2.addWeighted(panel,0.80,frame,0.20,0,frame)
    cv2.rectangle(frame,(10,10),(410,400),(int(tb*0.3),int(tg*0.3),int(tr*0.3)),1)

    cv2.putText(frame,"THE FORGOTTEN ORCHESTRA",
                (20,34),cv2.FONT_HERSHEY_SIMPLEX,0.46,(int(tb),int(tg),int(tr)),1)
    session_label = f"{slot.capitalize()} Session" + ("  (ASSESSMENT)" if is_day7 else "")
    cv2.putText(frame,f"{week['label']}  |  Day {prog['day_number']}/7  |  {session_label}",
                (20,54),cv2.FONT_HERSHEY_SIMPLEX,0.36,(160,100,255),1)

    # ── Today's Objectives checklist ──
    cv2.putText(frame,"Today's Objectives", (20,78), cv2.FONT_HERSHEY_SIMPLEX,0.40,(220,215,230),1)
    def box(y, done, label):
        mark = "\u2611" if done else "\u2610"
        col  = (60,200,80) if done else (150,145,165)
        cv2.putText(frame, f"{mark} {label}", (26,y), cv2.FONT_HERSHEY_SIMPLEX,0.36,col,1)

    box(100, obj.rom_met,  f"Reach {week['max_angle']}\xb0  (now {int(angle)}\xb0)")
    box(120, obj.hold_met, f"Hold {obj.hold_target:.1f}s  (best {obj.session_max_hold:.1f}s)")
    box(140, obj.reps_met, f"Complete {obj.rep_target} reps  (done {obj.reps})")
    box(160, obj.orchestra_restored, "Restore Orchestra")

    cv2.line(frame,(15,172),(405,172),(50,45,65),1)

    # ── ROM progress bar (fixed goal) ──
    rom_col = (60,200,80) if obj.rom_met else (int(tb*0.3),int(tg*0.8),int(tr*0.3))
    cv2.putText(frame,f"Weekly ROM (fixed): {week['max_angle']}\xb0",
                (20,190),cv2.FONT_HERSHEY_SIMPLEX,0.34,(180,170,200),1)
    cv2.rectangle(frame,(20,195),(220,205),(35,30,50),-1)
    fill = int(200*min(angle,week['max_angle'])/week['max_angle'])
    cv2.rectangle(frame,(20,195),(20+fill,205),rom_col,-1)

    # ── Hold bar ──
    hold_col = (60,200,80) if obj.hold_met else (int(tb*0.5),int(tg*0.5),int(tr))
    cv2.putText(frame,f"Hold target: {obj.hold_target:.1f}s   Current: {stage.hold_time:.1f}s",
                (20,222),cv2.FONT_HERSHEY_SIMPLEX,0.34,hold_col,1)
    cv2.rectangle(frame,(20,227),(220,237),(35,30,50),-1)
    hold_fill = int(200*min(stage.hold_time/max(obj.hold_target,0.1),1.0))
    cv2.rectangle(frame,(20,227),(20+hold_fill,237),hold_col,-1)

    # ── Music / orchestra progress ──
    cv2.putText(frame,f"Today's Orchestra: {int(stage.music_progress)}%",
                (20,258),cv2.FONT_HERSHEY_SIMPLEX,0.36,(180,170,200),1)
    cv2.rectangle(frame,(20,263),(220,273),(35,30,50),-1)
    cv2.rectangle(frame,(20,263),(20+int(200*stage.music_progress/100),273),
                  (int(tb*0.7),int(tg*0.4),int(tr*0.7)),-1)
    cv2.putText(frame,f"Instruments: {stage.total_unlocked}/6",
                (20,290),cv2.FONT_HERSHEY_SIMPLEX,0.34,(160,150,180),1)

    colors = instrument_colors(stage.week_idx)
    for i,(info,sec) in enumerate(zip(colors,stage.sections)):
        r,g,b = info["color"]
        col   = (int(b*0.7),int(g*0.7),int(r*0.7)) if sec.unlocked else (40,40,50)
        cv2.circle(frame,(35+i*22,306),6,col,-1)

    cv2.line(frame,(15,320),(405,320),(50,45,65),1)

    # ── Daily dashboard (long-term) ──
    kingdom_pct = int(100 * sum(prog["kingdom"]) / len(prog["kingdom"]))
    cv2.putText(frame,f"Kingdom Restoration: {kingdom_pct}%  |  Streak: {prog['streak']}d",
                (20,338),cv2.FONT_HERSHEY_SIMPLEX,0.34,(255,200,60),1)
    m_txt = "DONE" if prog["morning_done"] or slot=="morning" else "pending"
    e_txt = "DONE" if prog["evening_done"] or slot=="evening" else "pending"
    cv2.putText(frame,f"Morning: {m_txt}   Evening: {e_txt}",
                (20,356),cv2.FONT_HERSHEY_SIMPLEX,0.34,(160,150,180),1)

    # ── Encouragement ──
    progress_pct = angle/week['max_angle'] if week['max_angle']>0 else 0
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

    if obj.orchestra_restored:
        cv2.putText(frame,"Orchestra Fully Restored! Press Q to save & finish.",
                    (W//2-260,60),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,220,80),2)

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("RehabVerse — The Forgotten Orchestra  (v4)")
    print("  Fixed weekly ROM + adaptive hold/reps + two sessions/day + Day 7 assessment\n")

    prog = load_progress()
    advance_day_if_needed(prog)

    mp_pose_    = mp.solutions.pose
    mp_drawing_ = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)

    ret, bg_frame = cap.read()
    if ret: bg_frame = cv2.flip(bg_frame,1)
    else:   bg_frame = np.zeros((H,W,3),dtype=np.uint8)

    # ── Day briefing screen ──
    chosen_slot = default_session_slot()
    in_briefing = True
    while in_briefing:
        frame = bg_frame.copy()
        dark  = np.zeros_like(frame,dtype=np.uint8); dark[:] = (15,10,25)
        cv2.addWeighted(dark,0.6,frame,0.4,0,frame)
        draw_day_briefing(frame, prog, chosen_slot)
        cv2.imshow("RehabVerse — The Forgotten Orchestra", frame)
        key = cv2.waitKey(30) & 0xFF
        if key in (ord('m'), ord('M')):
            chosen_slot = "morning"
        elif key in (ord('e'), ord('E')):
            chosen_slot = "evening"
        elif key in (13, ord('\r'), ord(' ')):
            in_briefing = False
        elif key == ord('q'):
            cap.release(); cv2.destroyAllWindows(); pygame.quit(); return

    week_idx = prog["week_idx"]
    week     = REHAB_WEEKS[week_idx]
    is_day7  = prog["day_number"] == 7
    hold_target = week["final_hold"] if is_day7 else prog["hold_target"]
    rep_target  = week["final_reps"] if is_day7 else prog["rep_target"]

    objectives   = SessionObjectives(week["max_angle"], hold_target, rep_target)
    stage        = OrchestraStage(week_idx, objectives)
    audio_engine = AudioEngine(week_idx=week_idx)
    smoothed_angle = 0.0

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
                                   week["max_angle"],
                                   week["theme_col"])
                mp_drawing_.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose_.POSE_CONNECTIONS,
                    mp_drawing_.DrawingSpec(color=(80,70,100),thickness=1,circle_radius=2),
                    mp_drawing_.DrawingSpec(color=(70,60,90), thickness=1))

            bg_col = week["bg_tint"]
            dark   = np.zeros_like(frame,dtype=np.uint8); dark[:] = bg_col
            cv2.addWeighted(dark,0.45,frame,0.55,0,frame)

            stage.update(angle, t)
            stage.draw(frame, t)

            unlocked, volumes = stage.audio_state()
            audio_engine.update(unlocked, volumes, t)

            draw_hud(frame, angle, stage, prog, chosen_slot, is_day7)
            cv2.putText(frame,"Q quit & save session",
                        (W-230,H-15),cv2.FONT_HERSHEY_SIMPLEX,0.38,(70,65,85),1)

            cv2.imshow("RehabVerse — The Forgotten Orchestra", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

    # ── Save session on quit ──
    obj = stage.objectives
    finalize_session(prog, chosen_slot, obj.rom_met, obj.hold_met, obj.reps_met)

    audio_engine.stop()
    cap.release()
    cv2.destroyAllWindows()
    pygame.quit()
    session_result = {
        "game": "forgotten_orchestra",
        "completed": (
            obj.rom_met and
            obj.hold_met and
            obj.reps_met
        ),

        "session": {
            "week": prog["week_idx"] + 1,
            "day": prog["day_number"],
            "slot": chosen_slot,
            "assessment_day": is_day7
        },

        "metrics": {
            "rom_goal": week["max_angle"],
            "max_angle": obj.session_max_angle,

            "hold_target": obj.hold_target,
            "hold_time": obj.session_max_hold,

            "rep_target": obj.rep_target,
            "repetitions": obj.reps,

            "orchestra_progress": stage.music_progress
        },

        "objectives": {
            "rom_met": obj.rom_met,
            "hold_met": obj.hold_met,
            "reps_met": obj.reps_met
        },
        "timestamp": datetime.now().isoformat(),
    }
    print("\n========== SESSION RESULT ==========")
    print(session_result)
    print(f"\nSession saved  ({week['label']}, Day {prog['day_number']}, {chosen_slot})")
    print(f"  ROM reached:   {'YES' if obj.rom_met else 'no'}  (best {int(obj.session_max_angle)}\xb0 / goal {week['max_angle']}\xb0)")
    print(f"  Hold met:      {'YES' if obj.hold_met else 'no'}  (best {obj.session_max_hold:.1f}s / target {obj.hold_target:.1f}s)")
    print(f"  Reps met:      {'YES' if obj.reps_met else 'no'}  ({obj.reps} / {obj.rep_target})")
    print(f"  Orchestra:     {'FULLY RESTORED' if obj.orchestra_restored else f'{int(stage.music_progress)}%'}")
    if is_day7:
        print("  This was a Day 7 ASSESSMENT session — week outcome is decided once "
              "both Morning and Evening assessments are recorded.")
    return session_result

if __name__ == "__main__":
    result = main()

    print("\nReturned Result:")
    print(result)
    