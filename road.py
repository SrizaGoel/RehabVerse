"""
RehabVerse — Road to Recovery
==============================
Wrist rehabilitation game: third-person bike racing controlled entirely
by hand gestures detected via MediaPipe.

CONTROLS:
  Steer        — Tilt palm left / right (radial/ulnar deviation)
  Accelerate   — Open palm (fingers spread)
  Brake        — Close fist (fingers curl)

CLINICAL TARGET:
  Radial/ulnar deviation, grip open/close (post wrist surgery)

PROGRESSION:
  Week 1 — Straight road, gentle curves, wide steering tolerance
  Week 2 — Moderate curves, cones introduced, grip mechanic active
  Week 3 — S-bends, moving obstacles, tighter steering window
  Week 4 — Winding road, ghost rider, full time trial

Install:
  pip install opencv-python mediapipe numpy pygame

Run:
  python road_to_recovery.py
"""

import cv2
import mediapipe as mp
import numpy as np
import math
import time
import json
import os
import random
import pygame
import pygame.sndarray
from datetime import date, timedelta
from collections import deque

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
W, H        = 1280, 720
SAMPLE_RATE = 44100
DATA_FILE   = "road_recovery_progress.json"

# Road rendering constants
HORIZON_Y   = H // 2 - 40
ROAD_W_FAR  = 180      # road width at horizon
ROAD_W_NEAR = 520      # road width at bottom
BIKE_Y      = H - 160  # bike vertical position

# Steering
MAX_DEVIATION_DEG = 25.0   # wrist tilt that = full steer
STEER_SMOOTHING   = 0.75

# Speed
BASE_SPEED      = 4.0
MAX_SPEED       = 9.0
ACCEL_RATE      = 0.12
BRAKE_RATE      = 0.25
PASSIVE_DECEL   = 0.04

# ──────────────────────────────────────────────
# WEEK DEFINITIONS
# ──────────────────────────────────────────────
REHAB_WEEKS = [
    {
        "label":        "Week 1",
        "track_length": 800,
        "curve_strength": 0.3,
        "obstacle_count": 0,
        "steer_tolerance": 30,   # degrees — wide tolerance
        "grip_required":  False,
        "tip":          "Focus on tilting your wrist side to side — gentle and controlled.",
        "theme":        (60, 120, 200),
        "road_col":     (60, 65, 75),
        "unlock_req":   {"completions": 1, "max_deviation": 10},
    },
    {
        "label":        "Week 2",
        "track_length": 1000,
        "curve_strength": 0.55,
        "obstacle_count": 5,
        "steer_tolerance": 22,
        "grip_required":  True,
        "tip":          "Open your palm to go faster. Close fist to brake around cones.",
        "theme":        (60, 180, 120),
        "road_col":     (55, 65, 60),
        "unlock_req":   {"completions": 2, "max_deviation": 15},
    },
    {
        "label":        "Week 3",
        "track_length": 1200,
        "curve_strength": 0.85,
        "obstacle_count": 10,
        "steer_tolerance": 16,
        "grip_required":  True,
        "tip":          "S-bends ahead. Controlled wrist deviation — don't force range.",
        "theme":        (200, 140, 60),
        "road_col":     (65, 60, 50),
        "unlock_req":   {"completions": 3, "max_deviation": 20},
    },
    {
        "label":        "Week 4",
        "track_length": 1500,
        "curve_strength": 1.2,
        "obstacle_count": 15,
        "steer_tolerance": 12,
        "grip_required":  True,
        "tip":          "Full range needed. Ghost shows your last run — can you beat it?",
        "theme":        (180, 80, 220),
        "road_col":     (50, 45, 65),
        "unlock_req":   None,
    },
]

# ──────────────────────────────────────────────
# SOUND ENGINE
# ──────────────────────────────────────────────
pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 1024)
pygame.init()

def _make_tone(freq, duration, volume=0.3, wave="sine"):
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    if wave == "sine":
        w = np.sin(2 * np.pi * freq * t)
    elif wave == "square":
        w = np.sign(np.sin(2 * np.pi * freq * t))
    else:
        w = np.sin(2 * np.pi * freq * t)
    env = np.ones(n)
    rel = n // 5
    env[-rel:] = np.linspace(1, 0, rel)
    mono = (w * env * volume * 32767).astype(np.int16)
    return np.column_stack([mono, mono])

def _make_engine_loop(speed_ratio):
    """Generate engine hum — pitch scales with speed."""
    base_freq = 80 + speed_ratio * 160
    duration  = 0.25
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    fundamental = np.sin(2 * np.pi * base_freq * t)
    harmonic2   = 0.4 * np.sin(2 * np.pi * base_freq * 2 * t)
    harmonic3   = 0.2 * np.sin(2 * np.pi * base_freq * 3 * t)
    wave = fundamental + harmonic2 + harmonic3
    wave /= wave.max() + 1e-8
    mono = (wave * 0.18 * 32767).astype(np.int16)
    return np.column_stack([mono, mono])

def _make_checkpoint_chime():
    freqs = [523, 659, 784, 1047]
    waves = []
    for f in freqs:
        n = int(SAMPLE_RATE * 0.1)
        t = np.linspace(0, 0.1, n, endpoint=False)
        w = np.sin(2 * np.pi * f * t)
        env = np.ones(n); 
        env[-(n//4):] = np.linspace(1, 0, n//4)
        waves.append(w * env)
    full = np.concatenate(waves)
    mono = (full * 0.25 * 32767).astype(np.int16)
    return np.column_stack([mono, mono])

def _make_bump_sound():
    n = int(SAMPLE_RATE * 0.15)
    t = np.linspace(0, 0.15, n, endpoint=False)
    w = np.sin(2 * np.pi * 120 * t) * np.exp(-t * 30)
    mono = (w * 0.3 * 32767).astype(np.int16)
    return np.column_stack([mono, mono])

class SoundEngine:
    def __init__(self):
        self._ch_engine     = pygame.mixer.Channel(0)
        self._ch_fx         = pygame.mixer.Channel(1)
        self._engine_sounds = {}
        self._chime         = pygame.sndarray.make_sound(_make_checkpoint_chime())
        self._bump          = pygame.sndarray.make_sound(_make_bump_sound())
        self._last_speed    = -1

    def update_engine(self, speed, max_speed):
        ratio = speed / max_speed
        bucket = int(ratio * 5)
        if bucket == self._last_speed:
            return
        self._last_speed = bucket
        if bucket not in self._engine_sounds:
            self._engine_sounds[bucket] = pygame.sndarray.make_sound(
                _make_engine_loop(ratio))
        snd = self._engine_sounds[bucket]
        snd.set_volume(0.4 + ratio * 0.3)
        self._ch_engine.play(snd, loops=-1)

    def play_chime(self):
        self._ch_fx.play(self._chime)

    def play_bump(self):
        self._ch_fx.play(self._bump)

    def stop(self):
        self._ch_engine.stop()
        self._ch_fx.stop()

# ──────────────────────────────────────────────
# PERSISTENCE
# ──────────────────────────────────────────────
def load_progress():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {
        "days":              [],
        "unlocked_weeks":    [0],
        "all_time_best":     {},   # week_idx -> best_time_seconds
        "total_completions": 0,
        "max_deviation_achieved": {},  # week_idx -> degrees
    }

def save_progress(p):
    with open(DATA_FILE, "w") as f:
        json.dump(p, f, indent=2)

def load_ghost(week_idx):
    """Load ghost frame data for a week if it exists."""
    fname = f"ghost_w{week_idx}.json"
    if os.path.exists(fname):
        with open(fname) as f:
            return json.load(f)
    return None

def save_ghost(week_idx, frames):
    fname = f"ghost_w{week_idx}.json"
    with open(fname, "w") as f:
        json.dump(frames, f)

# ──────────────────────────────────────────────
# MEDIAPIPE HAND DETECTION
# ──────────────────────────────────────────────
def get_wrist_tilt(hand_landmarks):
    """
    Measure wrist tilt left/right from palm-facing-camera position.
    Uses wrist (0), index MCP (5), pinky MCP (17) to compute roll angle.
    Returns degrees: negative = tilted left, positive = tilted right.
    """
    lm = hand_landmarks.landmark
    wrist     = np.array([lm[0].x, lm[0].y])
    index_mcp = np.array([lm[5].x, lm[5].y])
    pinky_mcp = np.array([lm[17].x, lm[17].y])

    # Vector across knuckles
    knuckle_vec = pinky_mcp - index_mcp
    # Angle of knuckle line relative to horizontal
    angle = math.degrees(math.atan2(knuckle_vec[1], knuckle_vec[0]))
    # Neutral is ~0 (horizontal). Tilt right = positive, left = negative
    return angle

def get_finger_spread(hand_landmarks):
    """
    Measure how open the hand is.
    Computes average distance from fingertips to wrist, normalized.
    Returns 0.0 (fist) to 1.0 (fully open).
    """
    lm = hand_landmarks.landmark
    wrist = np.array([lm[0].x, lm[0].y])
    tips  = [4, 8, 12, 16, 20]  # thumb + fingertips
    dists = [np.linalg.norm(np.array([lm[t].x, lm[t].y]) - wrist) for t in tips]
    avg   = np.mean(dists)
    # Typical open ~0.35, closed ~0.15 — normalize
    spread = np.clip((avg - 0.12) / (0.32 - 0.12), 0.0, 1.0)
    return float(spread)

# ──────────────────────────────────────────────
# TRACK GENERATOR
# ──────────────────────────────────────────────
class Track:
    SEGMENT_LEN = 30   # pixels of scroll per segment

    def __init__(self, week_idx):
        week = REHAB_WEEKS[week_idx]
        self.total_segments = week["track_length"]
        self.curve_strength = week["curve_strength"]
        self.obstacle_count = week["obstacle_count"]
        self._generate()

    def _generate(self):
        """Pre-generate curvature for every segment + obstacle positions."""
        segs = self.total_segments
        cs   = self.curve_strength

        # Curvature: smooth random walk
        self.curvature = [0.0] * segs
        cur = 0.0
        for i in range(segs):
            if i % 40 == 0:
                target = random.uniform(-cs, cs)
            cur += (target - cur) * 0.05
            self.curvature[i] = cur

        # Obstacles: random segment positions (avoid first 50 and last 50)
        self.obstacles = set()
        if self.obstacle_count > 0:
            candidates = list(range(80, segs - 60))
            random.shuffle(candidates)
            self.obstacles = set(candidates[:self.obstacle_count])

    def curve_at(self, seg_idx):
        idx = min(int(seg_idx), len(self.curvature) - 1)
        return self.curvature[idx]

    def has_obstacle(self, seg_idx):
        return int(seg_idx) in self.obstacles

# ──────────────────────────────────────────────
# ROAD RENDERER
# ──────────────────────────────────────────────
def draw_road(frame, camera_x_offset, week_idx, track, scroll_pos):
    """
    Draw a perspective road. camera_x_offset shifts the vanishing point
    to simulate steering.
    """
    week     = REHAB_WEEKS[week_idx]
    road_col = week["road_col"]
    theme    = week["theme"]

    h_y = HORIZON_Y
    vp_x = W // 2 + int(camera_x_offset)  # vanishing point x

    # Sky gradient
    for y in range(0, h_y):
        t    = y / h_y
        r    = int(15 + t * 25)
        g    = int(12 + t * 20)
        b    = int(30 + t * 40)
        cv2.line(frame, (0, y), (W, y), (b, g, r), 1)

    # Ground
    cv2.rectangle(frame, (0, h_y), (W, H), (35, 38, 32), -1)

    # Road trapezoid
    road_pts = np.array([
        [vp_x - ROAD_W_FAR // 2, h_y],
        [vp_x + ROAD_W_FAR // 2, h_y],
        [W // 2 + ROAD_W_NEAR // 2, H],
        [W // 2 - ROAD_W_NEAR // 2, H],
    ], dtype=np.int32)
    cv2.fillPoly(frame, [road_pts], road_col)

    # Road markings — dashed centre line
    num_dashes = 8
    for i in range(num_dashes):
        t0 = i / num_dashes
        t1 = (i + 0.5) / num_dashes
        # perspective interpolation
        for t, is_start in [(t0, True), (t1, False)]:
            screen_y = int(h_y + t * (H - h_y))
            road_w   = int(ROAD_W_FAR + t * (ROAD_W_NEAR - ROAD_W_FAR))
            cx_t     = int(vp_x + t * (W // 2 - vp_x))
            if is_start:
                p0 = (cx_t, screen_y)
            else:
                p1 = (cx_t, screen_y)
        # Animate scroll
        dash_offset = int(scroll_pos * 2) % (H // num_dashes)
        mid_y = (p0[1] + p1[1]) // 2
        if (mid_y + dash_offset) % (H // num_dashes) < H // (num_dashes * 2):
            cv2.line(frame, p0, p1, (200, 195, 180), 2)

    # Road edges
    cv2.line(frame, (vp_x - ROAD_W_FAR // 2, h_y),
             (W // 2 - ROAD_W_NEAR // 2, H), (220, 220, 200), 2)
    cv2.line(frame, (vp_x + ROAD_W_FAR // 2, h_y),
             (W // 2 + ROAD_W_NEAR // 2, H), (220, 220, 200), 2)

    # Horizon line
    cv2.line(frame, (0, h_y), (W, h_y), (50, 48, 60), 1)

    # Distance markers on sides
    for i in range(3):
        t = 0.2 + i * 0.25
        screen_y = int(h_y + t * (H - h_y))
        left_x   = int(vp_x - ROAD_W_FAR // 2 + t * (W // 2 - ROAD_W_NEAR // 2 - (vp_x - ROAD_W_FAR // 2)))
        right_x  = int(vp_x + ROAD_W_FAR // 2 + t * (W // 2 + ROAD_W_NEAR // 2 - (vp_x + ROAD_W_FAR // 2)))
        post_h   = int(8 + t * 20)
        col      = tuple(int(c * (0.4 + t * 0.6)) for c in theme)
        cv2.rectangle(frame, (left_x - 3, screen_y - post_h), (left_x + 3, screen_y), col, -1)
        cv2.rectangle(frame, (right_x - 3, screen_y - post_h), (right_x + 3, screen_y), col, -1)

def draw_obstacle(frame, screen_x, screen_y, size):
    """Draw a traffic cone."""
    # Cone body
    pts = np.array([
        [screen_x, screen_y - size],
        [screen_x - size // 2, screen_y],
        [screen_x + size // 2, screen_y],
    ], dtype=np.int32)
    cv2.fillPoly(frame, [pts], (0, 100, 255))
    cv2.polylines(frame, [pts], True, (0, 60, 180), 2)
    # White stripe
    stripe_y = screen_y - size // 3
    cv2.line(frame, (screen_x - size // 4, stripe_y),
             (screen_x + size // 4, stripe_y), (255, 255, 255), 2)
    # Base
    cv2.ellipse(frame, (screen_x, screen_y),
                (size // 2, size // 6), 0, 0, 360, (0, 80, 200), -1)

def draw_bike(frame, bike_x, speed, max_speed, theme):
    """Draw a simple top-view-ish bike sprite."""
    bx, by = int(bike_x), BIKE_Y
    speed_ratio = speed / max_speed

    # Shadow
    cv2.ellipse(frame, (bx, by + 30), (28, 8), 0, 0, 360, (20, 20, 20), -1)

    # Rear wheel
    cv2.ellipse(frame, (bx, by + 18), (14, 8), 0, 0, 360, (40, 40, 50), -1)
    cv2.ellipse(frame, (bx, by + 18), (10, 6), 0, 0, 360, (60, 60, 70), -1)

    # Front wheel
    cv2.ellipse(frame, (bx, by - 32), (12, 7), 0, 0, 360, (40, 40, 50), -1)
    cv2.ellipse(frame, (bx, by - 32), (8, 5), 0, 0, 360, (60, 60, 70), -1)

    # Frame body
    cv2.line(frame, (bx, by + 10), (bx, by - 25), theme, 5)
    cv2.line(frame, (bx - 8, by + 5), (bx + 8, by + 5), theme, 4)

    # Rider body
    rider_col = (200, 190, 210)
    cv2.ellipse(frame, (bx, by - 18), (10, 14), 0, 0, 360, rider_col, -1)  # torso
    cv2.circle(frame, (bx, by - 36), 9, (180, 160, 180), -1)               # head
    # Helmet
    cv2.ellipse(frame, (bx, by - 38), (9, 7), 0, 180, 360, theme, -1)

    # Exhaust particles at speed
    if speed_ratio > 0.4:
        for _ in range(int(speed_ratio * 3)):
            px = bx + random.randint(-6, 6)
            py = by + 22 + random.randint(0, 12)
            r  = random.randint(2, 5)
            alpha_col = tuple(int(c * random.uniform(0.3, 0.7)) for c in theme)
            cv2.circle(frame, (px, py), r, alpha_col, -1)

def draw_ghost_bike(frame, ghost_x):
    """Draw a translucent ghost of the previous run."""
    bx, by = int(ghost_x), BIKE_Y
    ghost_col = (120, 100, 160)
    overlay = frame.copy()
    cv2.ellipse(overlay, (bx, by + 18), (14, 8), 0, 0, 360, ghost_col, 1)
    cv2.ellipse(overlay, (bx, by - 32), (12, 7), 0, 0, 360, ghost_col, 1)
    cv2.line(overlay, (bx, by + 10), (bx, by - 25), ghost_col, 2)
    cv2.ellipse(overlay, (bx, by - 18), (10, 14), 0, 0, 360, ghost_col, 1)
    cv2.circle(overlay, (bx, by - 36), 9, ghost_col, 1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

# ──────────────────────────────────────────────
# GLASS PANEL HELPER (matching your style)
# ──────────────────────────────────────────────
def draw_glass_panel(img, pt1, pt2, color=(16, 12, 28), border_color=(70, 55, 90), alpha=0.82):
    overlay = img.copy()
    cv2.rectangle(overlay, pt1, pt2, color, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.rectangle(img, pt1, pt2, border_color, 1)

# ──────────────────────────────────────────────
# HUD
# ──────────────────────────────────────────────
def draw_hud(frame, week_idx, speed, max_speed, tilt_deg, spread,
             progress_pct, session_time, best_time, obstacles_hit,
             grip_required, daily_life_msg):
    week  = REHAB_WEEKS[week_idx]
    theme = week["theme"]
    tr, tg, tb = theme[2], theme[1], theme[0]

    # ── Left panel ──
    draw_glass_panel(frame, (10, 10), (310, 320))

    cv2.putText(frame, "ROAD TO RECOVERY", (20, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, theme, 1)
    cv2.putText(frame, week["label"], (20, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 155, 175), 1)
    cv2.line(frame, (15, 65), (305, 65), (50, 45, 65), 1)

    # Speed gauge
    cv2.putText(frame, f"Speed", (20, 85),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (120, 115, 135), 1)
    speed_ratio = speed / max_speed
    bar_col = (int(tb * (1 - speed_ratio) + 60 * speed_ratio),
               int(tg * speed_ratio),
               int(tr * speed_ratio))
    cv2.rectangle(frame, (20, 90), (290, 104), (35, 30, 48), -1)
    cv2.rectangle(frame, (20, 90), (20 + int(270 * speed_ratio), 104), bar_col, -1)
    cv2.putText(frame, f"{speed:.1f} km/h", (225, 102),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 175, 195), 1)

    # Wrist tilt
    cv2.putText(frame, f"Wrist tilt", (20, 122),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (120, 115, 135), 1)
    tilt_norm = np.clip((tilt_deg + MAX_DEVIATION_DEG) / (2 * MAX_DEVIATION_DEG), 0, 1)
    mid_x = 155
    bar_fill = int(270 * tilt_norm)
    cv2.rectangle(frame, (20, 127), (290, 141), (35, 30, 48), -1)
    cv2.rectangle(frame, (20, 127), (20 + bar_fill, 141), theme, -1)
    # Centre marker
    cv2.line(frame, (mid_x, 125), (mid_x, 143), (200, 195, 215), 2)
    direction = "RIGHT" if tilt_deg > 3 else ("LEFT" if tilt_deg < -3 else "CENTRE")
    dir_col = (80, 200, 80) if direction == "CENTRE" else (200, 160, 80)
    cv2.putText(frame, direction, (225, 140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, dir_col, 1)
    cv2.putText(frame, f"{tilt_deg:+.1f}°", (20, 155),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (160, 155, 175), 1)

    # Grip
    if grip_required:
        cv2.line(frame, (15, 162), (305, 162), (40, 35, 55), 1)
        cv2.putText(frame, f"Grip (open=accel / fist=brake)", (20, 178),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (120, 115, 135), 1)
        grip_col = (80, 220, 80) if spread > 0.6 else ((80, 160, 220) if spread < 0.35 else (180, 180, 100))
        grip_label = "OPEN — ACCELERATING" if spread > 0.6 else ("FIST — BRAKING" if spread < 0.35 else "PARTIAL")
        cv2.putText(frame, grip_label, (20, 196),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.36, grip_col, 1)
        cv2.rectangle(frame, (20, 200), (290, 212), (35, 30, 48), -1)
        cv2.rectangle(frame, (20, 200), (20 + int(270 * spread), 212), grip_col, -1)

    # Track progress
    cv2.line(frame, (15, 220), (305, 220), (40, 35, 55), 1)
    cv2.putText(frame, f"Track progress", (20, 236),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (120, 115, 135), 1)
    cv2.rectangle(frame, (20, 241), (290, 255), (35, 30, 48), -1)
    prog_col = (80, 220, 80) if progress_pct > 0.8 else theme
    cv2.rectangle(frame, (20, 241), (20 + int(270 * progress_pct), 255), prog_col, -1)
    cv2.putText(frame, f"{progress_pct*100:.0f}%", (250, 254),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 175, 195), 1)

    # Time
    cv2.putText(frame, f"Time: {session_time:.1f}s", (20, 275),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 175, 200), 1)
    if best_time:
        bt_col = (80, 220, 80) if session_time < best_time else (200, 140, 100)
        cv2.putText(frame, f"Best: {best_time:.1f}s", (155, 275),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, bt_col, 1)

    cv2.putText(frame, f"Hits: {obstacles_hit}", (20, 295),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                (80, 80, 200) if obstacles_hit > 0 else (100, 100, 120), 1)

    # Daily life milestone
    if daily_life_msg:
        draw_glass_panel(frame, (10, H - 60), (W - 10, H - 15),
                         color=(10, 8, 20), border_color=theme, alpha=0.75)
        cv2.putText(frame, daily_life_msg, (W // 2 - len(daily_life_msg) * 5, H - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, theme, 1)

    # Controls reminder
    cv2.putText(frame, "Q quit   W change week", (W - 230, H - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, (70, 65, 85), 1)

    # Rehab tip
    draw_glass_panel(frame, (W - 380, 10), (W - 10, 75))
    cv2.putText(frame, "TIP", (W - 370, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36, theme, 1)
    tip = week["tip"]
    # Word wrap at ~40 chars
    words = tip.split()
    line, lines = "", []
    for w_ in words:
        if len(line) + len(w_) + 1 > 42:
            lines.append(line); line = w_
        else:
            line = (line + " " + w_).strip()
    if line: lines.append(line)
    for i, l in enumerate(lines[:2]):
        cv2.putText(frame, l, (W - 370, 48 + i * 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, (160, 155, 175), 1)

# ──────────────────────────────────────────────
# WEEK SELECTOR SCREEN
# ──────────────────────────────────────────────
def draw_week_selector(frame, selected, unlocked, progress):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (W, H), (8, 5, 18), -1)
    cv2.addWeighted(overlay, 0.80, frame, 0.20, 0, frame)

    cv2.putText(frame, "ROAD TO RECOVERY", (W // 2 - 200, 80),
                cv2.FONT_HERSHEY_DUPLEX, 1.1, (200, 160, 255), 2)
    cv2.putText(frame, "Select your rehab week", (W // 2 - 140, 110),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (120, 115, 140), 1)

    for i, week in enumerate(REHAB_WEEKS):
        locked  = i not in unlocked
        active  = (i == selected)
        theme   = week["theme"] if not locked else (60, 55, 75)
        box_x   = W // 2 - 280 + i * 148
        box_y   = 160
        box_w, box_h = 130, 180

        bdr = theme if active else (50, 45, 65)
        draw_glass_panel(frame, (box_x, box_y), (box_x + box_w, box_y + box_h),
                         color=(14, 10, 28) if active else (10, 8, 20),
                         border_color=bdr, alpha=0.85)

        if active:
            cv2.rectangle(frame, (box_x, box_y), (box_x + box_w, box_y + box_h), theme, 2)

        label_col = theme if not locked else (70, 65, 85)
        cv2.putText(frame, week["label"], (box_x + 12, box_y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, label_col, 1)

        if locked:
            cv2.putText(frame, "LOCKED", (box_x + 22, box_y + 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.44, (80, 75, 95), 1)
            req = REHAB_WEEKS[i - 1]["unlock_req"] if i > 0 else None
            if req:
                cv2.putText(frame, f"Complete W{i}", (box_x + 10, box_y + 112),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.30, (70, 65, 85), 1)
                cv2.putText(frame, f"Reach {req['max_deviation']}° tilt", (box_x + 10, box_y + 128),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.30, (70, 65, 85), 1)
        else:
            best = progress["all_time_best"].get(str(i))
            if best:
                cv2.putText(frame, f"Best: {best:.1f}s", (box_x + 12, box_y + 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.36, (100, 220, 100), 1)
            else:
                cv2.putText(frame, "Not run yet", (box_x + 12, box_y + 90),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.30, (90, 85, 105), 1)
            cv2.putText(frame, f"Dist: {week['track_length']}m", (box_x + 12, box_y + 112),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.30, (120, 115, 135), 1)
            cv2.putText(frame, "Grip req" if week["grip_required"] else "Steer only",
                        (box_x + 12, box_y + 130), cv2.FONT_HERSHEY_SIMPLEX, 0.28,
                        (140, 130, 155), 1)

        cv2.putText(frame, f"[{i+1}]", (box_x + box_w - 30, box_y + box_h - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, label_col, 1)

    cv2.putText(frame, "1-4 to select   ENTER/SPACE to start   Q to quit",
                (W // 2 - 230, H - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (100, 95, 120), 1)

# ──────────────────────────────────────────────
# FINISH SCREEN
# ──────────────────────────────────────────────
def draw_finish_screen(frame, week_idx, session_time, best_time, is_new_best,
                       max_deviation, obstacles_hit, progress):
    week  = REHAB_WEEKS[week_idx]
    theme = week["theme"]

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (W, H), (8, 5, 18), -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    # Title
    cv2.rectangle(frame, (W // 2 - 320, 70), (W // 2 + 320, 145), (18, 12, 35), -1)
    cv2.rectangle(frame, (W // 2 - 320, 70), (W // 2 + 320, 145), theme, 2)
    cv2.putText(frame, "TRACK COMPLETE!", (W // 2 - 190, 118),
                cv2.FONT_HERSHEY_DUPLEX, 1.1, theme, 2)

    # Stats panel
    sx, sy = W // 2 - 280, 170
    draw_glass_panel(frame, (sx, sy), (sx + 560, sy + 280))

    rows = [
        ("Finish time",     f"{session_time:.2f}s",
         (80, 220, 80) if is_new_best else (200, 160, 255)),
        ("Previous best",   f"{best_time:.2f}s" if best_time else "First run!",
         (120, 115, 140)),
        ("Max wrist tilt",  f"{max_deviation:.1f}°",
         (80, 200, 255)),
        ("Obstacles hit",   str(obstacles_hit),
         (80, 80, 200) if obstacles_hit > 0 else (80, 200, 80)),
        ("Week",            week["label"], theme),
    ]

    if is_new_best and best_time:
        diff = best_time - session_time
        rows.insert(1, ("Time saved", f"-{diff:.2f}s ⚡", (80, 255, 160)))

    for i, (label, val, col) in enumerate(rows):
        ry = sy + 35 + i * 46
        cv2.putText(frame, label, (sx + 20, ry),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (140, 135, 155), 1)
        cv2.putText(frame, val, (sx + 300, ry),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 1)
        cv2.line(frame, (sx + 10, ry + 8), (sx + 545, ry + 8), (40, 35, 55), 1)

    # Daily life milestone
    milestones = [
        (1,  "Wrist movement enough to steer a shopping cart"),
        (15, "Enough side movement to signal a turn while driving"),
        (20, "Functional wrist control — enough to use a computer mouse"),
        (25, "Full daily wrist range — cooking, typing, driving restored"),
    ]
    msg = ""
    for threshold, text in milestones:
        if max_deviation >= threshold:
            msg = text
    if msg:
        my = sy + 310
        draw_glass_panel(frame, (sx, my), (sx + 560, my + 40),
                         border_color=theme, alpha=0.75)
        cv2.putText(frame, f"✓ {msg}", (sx + 15, my + 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, theme, 1)

    # New best badge
    if is_new_best:
        cv2.putText(frame, "NEW BEST TIME!", (W // 2 - 120, H - 110),
                    cv2.FONT_HERSHEY_DUPLEX, 0.9, (80, 255, 160), 2)

    cv2.putText(frame, "SPACE — run again   W — change week   Q — quit",
                (W // 2 - 230, H - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (100, 95, 120), 1)
    cv2.putText(frame, "Progress saved to road_recovery_progress.json",
                (W // 2 - 200, H - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (80, 75, 95), 1)

# ──────────────────────────────────────────────
# MAIN GAME SESSION
# ──────────────────────────────────────────────
def run_session(cap, week_idx, progress, mp_hands, mp_drawing_utils):
    week          = REHAB_WEEKS[week_idx]
    track         = Track(week_idx)
    sound         = SoundEngine()
    ghost_data    = load_ghost(week_idx)

    # Session state
    scroll_pos    = 0.0           # how far along the track we are (0 → track.total_segments)
    speed         = BASE_SPEED
    bike_x        = float(W // 2) # screen x of bike
    camera_offset = 0.0           # vanishing point shift
    steer_smooth  = 0.0
    obstacles_hit = 0
    max_deviation = 0.0
    session_start = time.time()
    finished      = False
    finish_time   = None

    # Ghost state
    ghost_frames   = []            # record [(scroll, bike_x)] for saving
    ghost_frame_idx = 0

    # Obstacle screen tracking: {seg_idx: screen_y_progress}
    active_obs    = {}

    # Hit cooldown per obstacle
    hit_cooldown  = {}

    # Daily life message (shown briefly on milestone)
    daily_msg     = ""
    daily_msg_until = 0.0

    prev_time     = time.time()

    best_time_str = progress["all_time_best"].get(str(week_idx))
    best_time     = float(best_time_str) if best_time_str else None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        t     = time.time()
        dt    = min(t - prev_time, 0.05)
        prev_time = t

        # ── Hand detection ──
        rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = mp_hands.process(rgb)

        tilt_deg = 0.0
        spread   = 0.5   # neutral

        if results.multi_hand_landmarks:
            hand = results.multi_hand_landmarks[0]
            tilt_deg = get_wrist_tilt(hand)
            spread   = get_finger_spread(hand)
            mp_drawing_utils.draw_landmarks(
                frame, hand,
                mp.solutions.hands.HAND_CONNECTIONS,
                mp_drawing_utils.DrawingSpec(color=(80, 70, 100), thickness=1, circle_radius=2),
                mp_drawing_utils.DrawingSpec(color=(70, 60, 90), thickness=1))

        # ── Clamp tilt ──
        tilt_clamped = np.clip(tilt_deg, -MAX_DEVIATION_DEG, MAX_DEVIATION_DEG)
        max_deviation = max(max_deviation, abs(tilt_clamped))

        # ── Speed control ──
        if not finished:
            if week["grip_required"]:
                if spread > 0.62:
                    speed = min(MAX_SPEED, speed + ACCEL_RATE * dt * 60)
                elif spread < 0.35:
                    speed = max(1.5, speed - BRAKE_RATE * dt * 60)
                else:
                    speed = max(BASE_SPEED, speed - PASSIVE_DECEL * dt * 60)
            else:
                speed = BASE_SPEED + 1.0  # auto speed in early weeks

        # ── Steering ──
        steer_input  = tilt_clamped / MAX_DEVIATION_DEG   # -1 to +1
        steer_smooth = STEER_SMOOTHING * steer_smooth + (1 - STEER_SMOOTHING) * steer_input

        if not finished:
            # Shift bike within road bounds
            road_left  = W // 2 - ROAD_W_NEAR // 2 + 40
            road_right = W // 2 + ROAD_W_NEAR // 2 - 40
            bike_x    += steer_smooth * speed * 1.8
            bike_x     = np.clip(bike_x, road_left, road_right)

            # Camera follows road curvature
            curve        = track.curve_at(scroll_pos)
            camera_offset = camera_offset * 0.92 + curve * 120 * 0.08

            scroll_pos += speed * dt * 3
            sound.update_engine(speed, MAX_SPEED)

        # ── Ghost recording ──
        ghost_frames.append({"scroll": scroll_pos, "bike_x": bike_x})

        # ── Ghost playback ──
        ghost_x = None
        if ghost_data and not finished:
            while (ghost_frame_idx < len(ghost_data) - 1 and
                   ghost_data[ghost_frame_idx]["scroll"] < scroll_pos):
                ghost_frame_idx += 1
            if ghost_frame_idx < len(ghost_data):
                ghost_x = ghost_data[ghost_frame_idx]["bike_x"]

        # ── Check finish ──
        progress_pct = min(1.0, scroll_pos / track.total_segments)
        if progress_pct >= 1.0 and not finished:
            finished    = True
            finish_time = t - session_start
            sound.play_chime()

        # ── Obstacle collision ──
        if not finished:
            for seg in list(track.obstacles):
                dist = seg - scroll_pos
                if 0 < dist < 25:
                    # Map to screen position
                    t_screen = 1.0 - dist / 25
                    screen_y = int(HORIZON_Y + t_screen * (BIKE_Y - HORIZON_Y))
                    road_w_at = int(ROAD_W_FAR + t_screen * (ROAD_W_NEAR - ROAD_W_FAR))
                    cx = int(W // 2 + camera_offset * (1 - t_screen))
                    obs_x = cx + random.randint(-road_w_at // 3, road_w_at // 3) \
                            if seg not in active_obs else active_obs[seg][0]
                    active_obs[seg] = (obs_x, screen_y)
                    cone_size = int(8 + t_screen * 24)
                    draw_obstacle(frame, obs_x, screen_y, cone_size)

                    # Collision check (only near bottom)
                    if t_screen > 0.85:
                        if (abs(obs_x - bike_x) < 35 and
                                seg not in hit_cooldown):
                            obstacles_hit += 1
                            hit_cooldown[seg] = t + 2.0
                            speed = max(1.5, speed * 0.6)
                            sound.play_bump()
                elif seg in active_obs:
                    del active_obs[seg]

            # Clear expired cooldowns
            hit_cooldown = {k: v for k, v in hit_cooldown.items() if v > t}

        # ── Render ──
        render_frame = np.zeros((H, W, 3), dtype=np.uint8)
        draw_road(render_frame, camera_offset, week_idx, track, scroll_pos)

        if ghost_x is not None:
            draw_ghost_bike(render_frame, ghost_x)

        # Blend webcam feed subtly into background
        cv2.addWeighted(frame, 0.15, render_frame, 0.85, 0, render_frame)

        draw_bike(render_frame, bike_x, speed, MAX_SPEED, week["theme"])

        session_time = (finish_time if finished else t - session_start)
        draw_hud(render_frame, week_idx, speed, MAX_SPEED, tilt_clamped,
                 spread, progress_pct, session_time, best_time, obstacles_hit,
                 week["grip_required"],
                 daily_msg if t < daily_msg_until else "")

        # Finish overlay
        if finished:
            is_new_best = (best_time is None or finish_time < best_time)
            draw_finish_screen(render_frame, week_idx, finish_time, best_time,
                               is_new_best, max_deviation, obstacles_hit, progress)

        cv2.imshow("RehabVerse — Road to Recovery", render_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            sound.stop()
            return "quit", finish_time, max_deviation

        if finished:
            if key == 32:   # SPACE — replay
                sound.stop()
                return "replay", finish_time, max_deviation
            elif key in (ord('w'), ord('W')):
                sound.stop()
                return "select", finish_time, max_deviation

    sound.stop()
    return "quit", finish_time, max_deviation

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("RehabVerse — Road to Recovery")
    print("  Palm facing camera. Tilt wrist L/R to steer.")
    print("  Open palm = accelerate   |   Fist = brake\n")

    progress = load_progress()

    mp_hands_mod    = mp.solutions.hands
    mp_drawing_utils = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)

    unlocked    = set(progress.get("unlocked_weeks", [0]))
    selected    = 0
    in_selector = True

    ret, bg = cap.read()
    if ret: bg = cv2.flip(bg, 1)
    else:   bg = np.zeros((H, W, 3), dtype=np.uint8)

    with mp_hands_mod.Hands(
        max_num_hands=1,
        min_detection_confidence=0.65,
        min_tracking_confidence=0.65
    ) as mp_hands:

        # ── Week selector loop ──
        while in_selector:
            ret, frame = cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                bg = frame.copy()
            sel_frame = bg.copy()
            draw_week_selector(sel_frame, selected, unlocked, progress)
            cv2.imshow("RehabVerse — Road to Recovery", sel_frame)

            key = cv2.waitKey(30) & 0xFF
            for i in range(4):
                if key == ord(str(i + 1)) and i in unlocked:
                    selected = i
            if key in (13, 32):    # ENTER or SPACE
                in_selector = False
            elif key in (ord('q'), 27):
                cap.release()
                cv2.destroyAllWindows()
                return

        # ── Game loop ──
        while True:
            result, finish_time, max_deviation = run_session(
                cap, selected, progress, mp_hands, mp_drawing_utils)

            # Save results
            if finish_time is not None:
                key_str = str(selected)
                prev_best = progress["all_time_best"].get(key_str)
                if prev_best is None or finish_time < float(prev_best):
                    progress["all_time_best"][key_str] = round(finish_time, 2)
                    # Save ghost
                    # (ghost recorded in run_session — reload via save_ghost)

                prev_dev = progress["max_deviation_achieved"].get(key_str, 0)
                progress["max_deviation_achieved"][key_str] = round(
                    max(prev_dev, max_deviation), 1)

                progress["total_completions"] = progress.get("total_completions", 0) + 1

                # Check week unlock
                week    = REHAB_WEEKS[selected]
                req     = week["unlock_req"]
                next_wk = selected + 1
                if req and next_wk < len(REHAB_WEEKS):
                    comps     = progress["total_completions"]
                    max_dev   = progress["max_deviation_achieved"].get(key_str, 0)
                    if (comps >= req["completions"] and
                            max_dev >= req["max_deviation"]):
                        unlocked.add(next_wk)
                        progress["unlocked_weeks"] = list(unlocked)
                        print(f"  ✓ {REHAB_WEEKS[next_wk]['label']} unlocked!")

                progress["days"].append({
                    "date":          str(date.today()),
                    "week":          selected,
                    "time":          round(finish_time, 2),
                    "max_deviation": round(max_deviation, 1),
                    "hits":          0,
                })
                save_progress(progress)

            if result == "quit":
                break
            elif result == "replay":
                continue   # re-run same week
            elif result == "select":
                # Show selector again
                ret, bg = cap.read()
                if ret: bg = cv2.flip(bg, 1)
                in_selector = True
                while in_selector:
                    ret, frame = cap.read()
                    if ret:
                        frame = cv2.flip(frame, 1)
                        bg = frame.copy()
                    sel_frame = bg.copy()
                    draw_week_selector(sel_frame, selected, unlocked, progress)
                    cv2.imshow("RehabVerse — Road to Recovery", sel_frame)
                    key = cv2.waitKey(30) & 0xFF
                    for i in range(4):
                        if key == ord(str(i + 1)) and i in unlocked:
                            selected = i
                    if key in (13, 32):
                        in_selector = False
                    elif key in (ord('q'), 27):
                        cap.release()
                        cv2.destroyAllWindows()
                        return

    cap.release()
    cv2.destroyAllWindows()
    pygame.quit()
    print("\nSession ended. Progress saved.")
    best = progress["all_time_best"]
    if best:
        print("  Best times:")
        for wk, t in best.items():
            print(f"    Week {int(wk)+1}: {t}s")

if __name__ == "__main__":
    main()