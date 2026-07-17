"""
RehabVerse – Black Hole Surgeon
================================
Exercise  : Gomukhasana / Back Reach Challenge
Theme     : Two colliding singularities must be merged by the surgeon's hands
Stack     : Python · OpenCV · MediaPipe · NumPy · Pygame
"""

import cv2
import mediapipe as mp
import numpy as np
import pygame
import pyttsx3
import time
import math
import random
import threading
from collections import deque
from enum import Enum, auto
from PIL import Image as PILImage, ImageDraw, ImageFont
from .translations import STRINGS, LANGUAGES, t, fetch_live_translations

# ─────────────────────────────────────────────
# ASSET PATH RESOLUTION
# ─────────────────────────────────────────────
# Loading assets with a bare relative path like "fonts/Orbitron.ttf" only
# works if the process is launched from exactly the right working directory.
# Flask is launched from backend/, so bare relative paths break here even
# though they work fine when this file is run standalone. Resolve every
# asset relative to this file's own location instead.
import os as _os

_MODULE_DIR = _os.path.dirname(_os.path.abspath(__file__))


def _find_asset(*rel_path_parts):
    """Return the first existing path for an asset, checked in a few likely
    locations relative to this script. Falls back to the most likely
    candidate (next to this file) if none exist, so error messages still
    name a sensible path.
    """
    rel_path = _os.path.join(*rel_path_parts)
    candidates = [
        _os.path.join(_MODULE_DIR, rel_path),                       # next to this file
        _os.path.join(_os.path.dirname(_MODULE_DIR), rel_path),     # one level up (e.g. exercises/.. )
    ]
    for c in candidates:
        if _os.path.isfile(c):
            return c
    return candidates[0]

# ─────────────────────────────────────────────
#  CONSTANTS & CONFIGURATION
# ─────────────────────────────────────────────

WIN_W, WIN_H = 1280, 720

# Reach thresholds (wrist-to-wrist distance, normalised by torso height)
REACH_CLOSE_THRESHOLD   = 0.12   # merger imminent
REACH_TARGET_THRESHOLD  = 0.22   # within target zone
REACH_GOOD_THRESHOLD    = 0.38   # decent range
HOLD_MERGE_SECONDS      = 3.0    # hold at closest for full singularity merge
HOLD_GRACE_SECONDS      = 0.35   # tolerate brief noisy spikes without resetting hold progress

AVG_TORSO_CM = 50.0   # assumed average adult torso height for distance estimation

SMOOTHING_WINDOW = 10
TRUNK_LEAN_LIMIT = 0.07

SIDE_LEFT  = "left"
SIDE_RIGHT = "right"
FINGERTIP_EXTENSION_RATIO = 0.35   # approximate hand+finger length as a fraction of forearm length
DIFFICULTY_SETTINGS = {
    "easy":   {"hold_seconds": 5.0, "target_threshold": 0.35, "good_threshold": 0.50},
    "medium": {"hold_seconds": 3.0, "target_threshold": 0.22, "good_threshold": 0.38},
    "hard":   {"hold_seconds": 2.0, "target_threshold": 0.15, "good_threshold": 0.28},
}

# Colors (BGR)
C_WHITE            = (255, 255, 255)
C_BLACK            = (0,   0,   0  )
C_PURPLE           = (200, 100, 255)
C_CYAN             = (255, 220, 100)
C_ORANGE           = (30,  140, 255)
C_RED              = (60,  60,  220)
C_GOLD             = (40,  200, 255)
C_DARK_BG          = (8,   2,   18 )
C_GRID_HOT         = (120, 60,  200)
C_SINGULARITY_A    = (80,  100, 255)   # warm — top arm
C_SINGULARITY_B    = (255, 180, 60 )   # cool — bottom arm


# ─────────────────────────────────────────────
#  GAME PHASES
# ─────────────────────────────────────────────

class Phase(Enum):
    RECORDS      = auto()
    INTRO        = auto()
    CALIBRATION  = auto()
    PLAYING      = auto()
    MERGER       = auto()
    PAUSED       = auto()
    SESSION_END  = auto()


# ─────────────────────────────────────────────
#  STANDALONE SPEAK FUNCTION (reps)
# ─────────────────────────────────────────────

def speak(text, audio_manager=None):
    def _speak():
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.setProperty("volume", 1.0)
            if audio_manager:
                engine.connect('started-utterance',  lambda name: audio_manager._apply_duck(0.12))
                engine.connect('finished-utterance',  lambda name, completed: audio_manager._apply_duck(1.0))
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"[Voice] {e}")
    threading.Thread(target=_speak, daemon=True).start()
# ─────────────────────────────────────────────
#  PARTICLE SYSTEM
# ─────────────────────────────────────────────

class Particle:
    __slots__ = ("x","y","color","vx","vy","life","max_life","size")

    def __init__(self, x, y, color, vx=None, vy=None, life=None, size=None):
        self.x    = float(x)
        self.y    = float(y)
        self.color= color
        self.vx   = vx   if vx   is not None else random.uniform(-3, 3)
        self.vy   = vy   if vy   is not None else random.uniform(-3, 3)
        self.life = life if life is not None else random.uniform(0.4, 1.2)
        self.max_life = self.life
        self.size = size if size is not None else random.uniform(1, 4)

    def update(self, dt):
        self.x  += self.vx
        self.y  += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        self.life -= dt
        return self.life > 0

    def draw(self, frame):
        a = max(0.0, self.life / self.max_life)
        c = tuple(int(ch * a) for ch in self.color)
        s = max(1, int(self.size * a))
        cv2.circle(frame, (int(self.x), int(self.y)), s, c, -1)


class ParticleSystem:
    def __init__(self):
        self.pool: list[Particle] = []

    def emit(self, x, y, color, count=5, **kw):
        for _ in range(count):
            self.pool.append(Particle(x, y, color, **kw))

    def update_draw(self, frame, dt):
        alive = []
        for p in self.pool:
            if p.update(dt):
                p.draw(frame)
                alive.append(p)
        self.pool = alive

    def arc_sparks(self, x1, y1, x2, y2, intensity, ca, cb):
        n = int(intensity * 6)
        for _ in range(n):
            t  = random.random()
            mx = int(x1 + (x2-x1)*t) + random.randint(-25,25)
            my = int(y1 + (y2-y1)*t) + random.randint(-25,25)
            c  = ca if random.random() < 0.5 else cb
            self.emit(mx, my, c, count=1,
                      vx=random.uniform(-5,5), vy=random.uniform(-5,5),
                      life=random.uniform(0.08,0.35), size=random.uniform(1,3))


# ─────────────────────────────────────────────
#  SPACETIME WARP GRID
# ─────────────────────────────────────────────

class WarpGrid:
    COLS, ROWS = 22, 13

    def __init__(self, w, h):
        self.bx = np.linspace(0, w, self.COLS+1)
        self.by = np.linspace(0, h, self.ROWS+1)

    @staticmethod
    def _pull(px, py, cx, cy, strength):
        dx, dy = px-cx, py-cy
        d = math.sqrt(dx*dx + dy*dy) + 80
        pull = strength / d
        return px - dx*pull, py - dy*pull

    def draw(self, frame, a_pos, b_pos, gap_norm):
        strength = (1.0 - gap_norm) * 20000
        intensity = int(60 + 140*(1.0-gap_norm))
        color = (intensity//4, intensity//8, intensity)

        def warp(col, row):
            px, py = float(self.bx[col]), float(self.by[row])
            px, py = self._pull(px, py, a_pos[0], a_pos[1], strength)
            px, py = self._pull(px, py, b_pos[0], b_pos[1], strength)
            return int(px), int(py)

        for row in range(self.ROWS+1):
            pts = [warp(c, row) for c in range(self.COLS+1)]
            for i in range(len(pts)-1):
                cv2.line(frame, pts[i], pts[i+1], color, 1, cv2.LINE_AA)
        for col in range(self.COLS+1):
            pts = [warp(col, r) for r in range(self.ROWS+1)]
            for i in range(len(pts)-1):
                cv2.line(frame, pts[i], pts[i+1], color, 1, cv2.LINE_AA)


# ─────────────────────────────────────────────
#  AUDIO MANAGER  (fully synthesised, no files)
# ─────────────────────────────────────────────

class AudioManager:
    def __init__(self):
        self.ok = False
        self.duck_factor = 1.0
        self.base_vols   = {}
        try:
            pygame.mixer.init(44100, -16, 2, 512)
            pygame.mixer.set_num_channels(16)
            self.ok = True
            self._load()
        except Exception as e:
            print(f"[Audio] disabled: {e}")

    def _load(self):
        self.s = {}
        files = {
            "ambient_loop":           _find_asset("sounds", "ambient_loop.wav"),
            "calibration_music":      _find_asset("sounds", "calibration_ready.wav"),
            "calibration_voice":      _find_asset("sounds", "cabiration_ready_word_audio.ogg"),
            "hold_start":             _find_asset("sounds", "hold_start.ogg"),
            "charging_loop":          _find_asset("sounds", "charging_loop.ogg"),
            "merge_event":            _find_asset("sounds", "merge_event.ogg"),
            "warning":                _find_asset("sounds", "warning.ogg"),
            "session_complete":       _find_asset("sounds", "session_complete.ogg"),
            "proximity_close":        _find_asset("sounds", "proximity_close.ogg"),
            "singularity_merged":     _find_asset("sounds", "singularity_merged.ogg"),
        }
        for name, path in files.items():
            try:
                self.s[name] = pygame.mixer.Sound(path)
                print(f"[Audio] loaded: {name}")
            except Exception as e:
                print(f"[Audio] failed to load {name}: {e}")

        # Set base volumes
        self._set_vol("ambient_loop",      0.6)
        self._set_vol("calibration_music", 0.7)
        self._set_vol("calibration_voice", 1.0)
        self._set_vol("hold_start",        0.8)
        self._set_vol("charging_loop",     0.3)
        self._set_vol("merge_event",       0.6)
        self._set_vol("warning",           0.9)
        self._set_vol("session_complete",  1.0)
        self._set_vol("proximity_close",   0.0)  # starts silent, driven by gap
        self._set_vol("singularity_merged", 1.0)
        
        self.base_vols = {"ambient_loop": 0.6, "charging_loop": 0.3, "calibration_music": 0.7}
        # Start proximity loop immediately at zero volume — always ready
        self.play("proximity_close", loops=-1)

    def _set_vol(self, name, vol):
        if name in self.s:
            self.s[name].set_volume(vol)

    def set_proximity_volume(self, gap_norm):
        # gap_norm: 0 = hands touching, 1 = hands far apart
        volume = max(0.0, min(1.0, 1.0 - gap_norm))* self.duck_factor
        self._set_vol("proximity_close", volume)
    
    def _apply_duck(self, factor):
        self.duck_factor = factor
        for name, base in self.base_vols.items():
            self._set_vol(name, base * factor)

    def duck_and_play(self, name, duck_to=0.12):
        if not self.ok or name not in self.s:
            return
        self._apply_duck(duck_to)
        self.play(name)
        duration = self.s[name].get_length()
        threading.Timer(duration + 0.1, lambda: self._apply_duck(1.0)).start()
 
    def play(self, name, loops=0):
        if self.ok and name in self.s:
            self.s[name].play(loops=loops)

    def stop(self, name):
        if self.ok and name in self.s:
            self.s[name].stop()

    def stop_all(self):
        if self.ok:
            pygame.mixer.stop()

# ─────────────────────────────────────────────
#  METRICS
# ─────────────────────────────────────────────

class Metrics:
    def __init__(self):
        self.reps         = 0
        self.mergers      = 0
        self.best_gap     = 1.0
        self.best_hold_s  = 0.0
        self.total_hold_s = 0.0
        self.left_best    = 1.0
        self.right_best   = 1.0
        self.symmetry     = 100.0
        self.smoothness   = 100.0
        self._smooth_buf  = deque(maxlen=30)
        self._start       = time.time()
        self._paused_at   = None
        self._paused_total = 0.0

    def pause_timer(self):
        if self._paused_at is None:
            self._paused_at = time.time()

    def resume_timer(self):
        if self._paused_at is not None:
            self._paused_total += time.time() - self._paused_at
            self._paused_at = None

    def session_time(self):
        paused = self._paused_total
        if self._paused_at is not None:
            paused += time.time() - self._paused_at
        return time.time() - self._start - paused

    def update_symmetry(self):
        if self.left_best < 1.0 and self.right_best < 1.0:
            diff = abs(self.left_best - self.right_best)
            self.symmetry = max(0, 100 - diff * 250)

    def update_smoothness(self, delta):
        self._smooth_buf.append(abs(delta))
        if len(self._smooth_buf) > 5:
            self.smoothness = max(0, 100 - np.mean(self._smooth_buf)*900)


# ─────────────────────────────────────────────
#  POSE ANALYSER
# ─────────────────────────────────────────────

class PoseAnalyser:
    IDX = dict(l_sh=11, r_sh=12, l_el=13, r_el=14, l_wr=15, r_wr=16,
               l_hp=23, r_hp=24)

    def __init__(self):
        self.pose = mp.solutions.pose.Pose(
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6)
        self._buf    = deque(maxlen=SMOOTHING_WINDOW)
        self._prev   = None

    def _pt(self, lm, key, w, h):
        idx = self.IDX[key]
        return np.array([lm[idx].x*w, lm[idx].y*h])

    def process(self, frame):
        h, w = frame.shape[:2]
        res  = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not res.pose_landmarks:
            return None

        lm = res.pose_landmarks.landmark
        l_wr_vis = lm[15].visibility
        r_wr_vis = lm[16].visibility
        if l_wr_vis < 0.35 and r_wr_vis < 0.35 and self._prev is not None:
            return None
        p  = lambda k: self._pt(lm, k, w, h)

        l_sh, r_sh = p("l_sh"), p("r_sh")
        l_hp, r_hp = p("l_hp"), p("r_hp")
        l_wr, r_wr = p("l_wr"), p("r_wr")
        l_el, r_el = p("l_el"), p("r_el")
        # Approximate fingertip position by projecting past the wrist
        # along the forearm direction (elbow -> wrist), since Pose has no hand landmarks
        l_tip = l_wr + (l_wr - l_el) * FINGERTIP_EXTENSION_RATIO
        r_tip = r_wr + (r_wr - r_el) * FINGERTIP_EXTENSION_RATIO

        mid_sh  = (l_sh + r_sh) / 2
        mid_hp  = (l_hp + r_hp) / 2
        torso_h = max(1.0, np.linalg.norm(mid_sh - mid_hp))

        gap_raw  = np.linalg.norm(l_tip - r_tip) / torso_h
        self._buf.append(gap_raw)
        gap = float(np.mean(self._buf))

        delta = (gap - self._prev) if self._prev is not None else 0.0
        self._prev = gap

        # Top arm = whichever elbow is higher on screen (lower y value)
        top_side = SIDE_LEFT if l_el[1] < r_el[1] else SIDE_RIGHT
        top_wrist = l_tip if top_side == SIDE_LEFT else r_tip
        bot_wrist = r_tip if top_side == SIDE_LEFT else l_tip

        trunk_lean = abs((mid_sh[0] - mid_hp[0]) / torso_h)

        return dict(
            gap=gap, delta=delta,
            top_side=top_side,
            top_wrist_px=top_wrist.astype(int),
            bot_wrist_px=bot_wrist.astype(int),
            trunk_lean=trunk_lean,
            landmarks=res.pose_landmarks,
        )


# ─────────────────────────────────────────────
#  DRAW HELPERS
# ─────────────────────────────────────────────
_font_cache = {}  # key: (font_path, font_size, weight)

def draw_text_orbitron(frame, text, pos, font_size, color_bgr, weight="Bold", align="center",
                        stroke_width=0, stroke_color_bgr=None):
    font_path = _find_asset("fonts", "Orbitron.ttf")
    cache_key = (font_path, font_size, weight)
    if cache_key not in _font_cache:
        font = ImageFont.truetype(font_path, font_size)
        try:
            font.set_variation_by_name(weight)
        except Exception:
            pass
        _font_cache[cache_key] = font
    font = _font_cache[cache_key]

    pil_img = PILImage.new("RGBA", (frame.shape[1], frame.shape[0]), (0,0,0,0))
    draw = ImageDraw.Draw(pil_img)
    bbox = draw.textbbox((0,0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    if align == "center":
        x = pos[0] - tw//2
    elif align == "right":
        x = pos[0] - tw
    else:
        x = pos[0]
    y = pos[1] - th//2 - bbox[1]

    color_rgb = (color_bgr[2], color_bgr[1], color_bgr[0], 255)
    stroke_rgb = (stroke_color_bgr[2], stroke_color_bgr[1], stroke_color_bgr[0], 255) if stroke_color_bgr else None

    draw.text((x, y), text, font=font, fill=color_rgb,
              stroke_width=stroke_width, stroke_fill=stroke_rgb)

    text_layer = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2BGR)
    alpha = np.array(pil_img)[:,:,3:4].astype(float)/255.0
    frame[:] = (frame.astype(float)*(1-alpha) + text_layer.astype(float)*alpha).astype(np.uint8)

            
def draw_lang_text(frame, key, lang, pos, font_size, color_bgr,
                    weight="Bold", align="center", **kwargs):
    """
    Draw translated text using the correct font for the selected language.
    Falls back to English + Orbitron if translation missing.
    """
    from .translations import LANGUAGES, t
    text      = t(key, lang, **kwargs)
    font_path = LANGUAGES.get(lang, LANGUAGES["english"])["font"]
    cache_key = (font_path, font_size, weight)
    if cache_key not in _font_cache:
        try:
            font = ImageFont.truetype(font_path, font_size)
            try:
                font.set_variation_by_name(weight)
            except Exception:
                pass
        except Exception:
            # Fallback to Orbitron if font file missing
            font = ImageFont.truetype(_find_asset("fonts", "Orbitron.ttf"), font_size)
        _font_cache[cache_key] = font
    font = _font_cache[cache_key]

    pil_img = PILImage.new("RGBA", (frame.shape[1], frame.shape[0]), (0,0,0,0))
    draw    = ImageDraw.Draw(pil_img)
    bbox    = draw.textbbox((0,0), text, font=font)
    tw, th  = bbox[2]-bbox[0], bbox[3]-bbox[1]
    x = pos[0] - tw//2 if align == "center" else pos[0]
    y = pos[1] - th//2 - bbox[1]

    color_rgb = (color_bgr[2], color_bgr[1], color_bgr[0], 255)
    draw.text((x, y), text, font=font, fill=color_rgb)

    text_layer = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2BGR)
    alpha      = np.array(pil_img)[:,:,3:4].astype(float)/255.0
    frame[:]   = (frame.astype(float)*(1-alpha) + text_layer.astype(float)*alpha).astype(np.uint8)

def rounded_rect(frame, pt1, pt2, color, radius, thickness=-1):
    x1, y1 = pt1
    x2, y2 = pt2
    if thickness < 0:
        cv2.rectangle(frame, (x1+radius, y1), (x2-radius, y2), color, -1)
        cv2.rectangle(frame, (x1, y1+radius), (x2, y2-radius), color, -1)
        cv2.circle(frame, (x1+radius, y1+radius), radius, color, -1)
        cv2.circle(frame, (x2-radius, y1+radius), radius, color, -1)
        cv2.circle(frame, (x1+radius, y2-radius), radius, color, -1)
        cv2.circle(frame, (x2-radius, y2-radius), radius, color, -1)
    else:
        cv2.line(frame, (x1+radius, y1), (x2-radius, y1), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x1+radius, y2), (x2-radius, y2), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x1, y1+radius), (x1, y2-radius), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x2, y1+radius), (x2, y2-radius), color, thickness, cv2.LINE_AA)
        cv2.ellipse(frame, (x1+radius, y1+radius), (radius,radius), 0, 180, 270, color, thickness, cv2.LINE_AA)
        cv2.ellipse(frame, (x2-radius, y1+radius), (radius,radius), 0, 270, 360, color, thickness, cv2.LINE_AA)
        cv2.ellipse(frame, (x2-radius, y2-radius), (radius,radius), 0, 0, 90, color, thickness, cv2.LINE_AA)
        cv2.ellipse(frame, (x1+radius, y2-radius), (radius,radius), 0, 90, 180, color, thickness, cv2.LINE_AA)


def draw_metallic_title(frame, text, center_xy, font_size, weight="Bold",
                         box_color_bgr=(190,150,30), box_padding=(28,14), draw_box=True):
    font_path = _find_asset("fonts", "Orbitron.ttf")
    cache_key = (font_path, font_size, weight)
    if cache_key not in _font_cache:
        font = ImageFont.truetype(font_path, font_size)
        try:
            font.set_variation_by_name(weight)
        except Exception:
            pass
        _font_cache[cache_key] = font
    font = _font_cache[cache_key]

    dummy = PILImage.new("L", (1,1))
    bbox = ImageDraw.Draw(dummy).textbbox((0,0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    x = center_xy[0] - tw//2
    y = center_xy[1] - th//2 - bbox[1]

    # True vertical ink extent of the rendered glyphs — fixes the black-bottom bug
    ink_top    = y + bbox[1]
    ink_bottom = y + bbox[3]

    # Translucent rounded box, drawn first — sits behind the text
    pad_x, pad_y = box_padding
    bx0, by0 = x - pad_x, ink_top - pad_y
    bx1, by1 = x + tw + pad_x, ink_bottom + pad_y
    if draw_box:
        ov = frame.copy()
        rounded_rect(ov, (bx0,by0), (bx1,by1), box_color_bgr, radius=24)
        cv2.addWeighted(ov, 0.22, frame, 0.78, 0, frame)
        rounded_rect(frame, (bx0,by0), (bx1,by1), box_color_bgr, radius=24, thickness=1)

    # Metallic gradient text
    mask_img = PILImage.new("L", (frame.shape[1], frame.shape[0]), 0)
    ImageDraw.Draw(mask_img).text((x, y), text, font=font, fill=255)
    mask = np.array(mask_img).astype(float)[:,:,None] / 255.0

    top_c, mid_c, bottom_c = np.array([170,255,255]), np.array([40,200,255]), np.array([10,110,170])
    grad = np.zeros_like(frame, dtype=np.float64)
    grad[:] = mid_c   # safety fallback — never black, worst case plain gold
    row_y0 = max(0, int(ink_top) - 2)
    row_y1 = min(frame.shape[0], int(ink_bottom) + 2)
    span = max(1, row_y1 - row_y0)
    for row in range(row_y0, row_y1):
        t = (row - row_y0) / span
        grad[row,:] = (top_c*(1-t*2)+mid_c*(t*2)) if t<0.5 else (mid_c*(1-(t-0.5)*2)+bottom_c*((t-0.5)*2))

    frame[:] = (frame.astype(float)*(1-mask) + grad*mask).astype(np.uint8)    

def put_text_orbitron(frame, text, pos, font_size, color_bgr,
                       align="left", weight="Medium"):
    """Drop-in replacement for cv2.putText using Orbitron font."""
    draw_text_orbitron(frame, text, pos, font_size, color_bgr,
                        weight=weight, align=align)
    
def draw_singularity(frame, cx, cy, color, radius, intensity):
    t = time.time()
    radius = int(radius * 1.25)  # 25% bigger

    # ── Layer 5 — Outer corona ──
    for i in range(7):
        r = int(radius * (3.0 - i * 0.28))
        alpha = 0.035 * intensity * (1 - i/7)
        ov = frame.copy()
        cv2.circle(ov, (cx,cy), r, color, -1)
        cv2.addWeighted(ov, alpha, frame, 1-alpha, 0, frame)

    # ── Layer 4 — Light smear arcs ──
    for i in range(10):
        arc_angle = t * (0.8 + i * 0.15) * (1 if i%2==0 else -1)
        start_deg = int(math.degrees(arc_angle) % 360)
        r = int(radius * (0.7 + i * 0.12))
        arc_intensity = max(0, intensity - i * 0.07)
        c = tuple(int(ch * arc_intensity * 0.6) for ch in color)
        sweep = random.randint(40, 100)
        cv2.ellipse(frame, (cx,cy), (r, max(1,int(r*0.55))),
                    int(t*20) % 360,
                    start_deg, start_deg + sweep,
                    c, 1, cv2.LINE_AA)

    # ── Layer 2 — Accretion disk ──
    disk_rx = int(radius * 1.3)
    disk_ry = int(radius * 0.38)
    tilt = int(t * 15) % 180

    outer_c = tuple(int(ch * 0.5 * intensity) for ch in color)
    cv2.ellipse(frame, (cx,cy), (disk_rx, disk_ry),
                tilt, 0, 360, outer_c, 3, cv2.LINE_AA)

    mid_rx = int(radius * 1.0)
    mid_ry = int(radius * 0.28)
    mid_c = tuple(min(255, int(ch * 0.85 * intensity)) for ch in color)
    cv2.ellipse(frame, (cx,cy), (mid_rx, mid_ry),
                tilt, 0, 360, mid_c, 2, cv2.LINE_AA)

    inner_rx = int(radius * 0.6)
    inner_ry = int(radius * 0.18)
    white_hot = tuple(min(255, int(ch * intensity + 180)) for ch in color)
    cv2.ellipse(frame, (cx,cy), (inner_rx, inner_ry),
                tilt, 0, 360, white_hot, 2, cv2.LINE_AA)

    # ── Layer 1 — Gravitational void ──
    core_r = max(8, int(radius * 0.32))
    for i in range(6):
        r = core_r + (5 - i) * 4
        alpha = 0.12 + i * 0.13
        ov = frame.copy()
        cv2.circle(ov, (cx,cy), r, (0,0,0), -1)
        cv2.addWeighted(ov, alpha, frame, 1-alpha, 0, frame)
    cv2.circle(frame, (cx,cy), core_r, (0,0,0), -1)
    cv2.circle(frame, (cx,cy), 2,
               tuple(min(255, ch+200) for ch in color), -1, cv2.LINE_AA)    
    
def update_absorption(frame, cx, cy, color, gap_norm, particles, dt):
    """Spawn and spiral particles inward toward singularity core."""
    radius = 80  # spawn ring distance from centre
    # Spawn new particles — more when gap is large (black hole feeding)
    spawn_chance = gap_norm * 0.72
    if random.random() < spawn_chance:
        angle = random.uniform(0, 2 * math.pi)
        dist  = random.uniform(radius * 1.5, radius * 2.34)
        particles.append({
            "angle": angle,
            "dist":  dist,
            "speed": random.uniform(1.0, 2.0),
            "spin":  random.uniform(1.5, 3.5),
            "size":  random.uniform(1.5, 3.5),
            "life":  1.0,
        })

    # Update and draw
    alive = []
    for p in particles:
        # Spiral inward
        p["dist"]  -= p["speed"] * (1 + (1 - p["dist"] / (radius * 3)) * 4)
        p["angle"] += math.radians(p["spin"])
        p["life"]   = min(1.0, p["dist"] / (radius * 1.5))

        if p["dist"] < 6:
            continue  # absorbed — remove

        px = int(cx + math.cos(p["angle"]) * p["dist"])
        py = int(cy + math.sin(p["angle"]) * p["dist"])

        # Colour shifts white-hot as it gets closer
        t_pull = max(0, 1 - p["dist"] / (radius * 3))
        c = tuple(min(255, int(color[j] * p["life"] + 255 * t_pull * 0.6))
                  for j in range(3))
        size = max(1, int(p["size"] * p["life"]))

        # Draw with small tail
        tail_x = int(cx + math.cos(p["angle"] - 0.15) * (p["dist"] + 6))
        tail_y = int(cy + math.sin(p["angle"] - 0.15) * (p["dist"] + 6))
        cv2.line(frame, (tail_x, tail_y), (px, py), c, 1, cv2.LINE_AA)
        cv2.circle(frame, (px, py), size, c, -1, cv2.LINE_AA)

        alive.append(p)

    particles.clear()
    particles.extend(alive)

def draw_lightning(frame, p1, p2, ca, cb, intensity):
    if intensity < 0.06:
        return
    steps = 14
    pts   = [np.array(p1, dtype=float)]
    for i in range(1, steps):
        t   = i/steps
        mid = np.array(p1)*(1-t) + np.array(p2)*t
        perp = np.array([-(p2[1]-p1[1]), p2[0]-p1[0]], dtype=float)
        n    = np.linalg.norm(perp) + 1e-6
        pts.append(mid + (perp/n)*random.uniform(-35,35)*intensity)
    pts.append(np.array(p2, dtype=float))
    for i in range(len(pts)-1):
        f = i/len(pts)
        c = tuple(int(ca[j]*(1-f) + cb[j]*f) for j in range(3))
        b = int(255*intensity)
        c = tuple(min(255, ch + b//5) for ch in c)
        cv2.line(frame, tuple(pts[i].astype(int)), tuple(pts[i+1].astype(int)),
                 c, max(1,int(intensity*3)), cv2.LINE_AA)


def draw_hud(frame, m: Metrics, gap, hold_pct, phase: Phase,
             current_side, trunk_warn, difficulty="medium", streak=0):
    W, H = frame.shape[1], frame.shape[0]

    # Top bar
    ov = frame.copy()
    cv2.rectangle(ov, (0,0),(W,58),(10,4,25),-1)
    cv2.addWeighted(ov, 0.78, frame, 0.22, 0, frame)
    cv2.putText(frame,"BLACK HOLE SURGEON",(16,38),
                cv2.FONT_HERSHEY_DUPLEX, 0.9, C_PURPLE, 1, cv2.LINE_AA)
    mm,ss = divmod(int(m.session_time()),60)
    cv2.putText(frame,f"{mm:02d}:{ss:02d}",(W-110,38),
                cv2.FONT_HERSHEY_SIMPLEX,0.8,C_CYAN,1,cv2.LINE_AA)

    # Left stats panel
    px,py,pw,ph = 14,68,226,340
    ov2 = frame.copy()
    cv2.rectangle(ov2,(px,py),(px+pw,py+ph),(10,4,25),-1)
    cv2.addWeighted(ov2,0.68,frame,0.32,0,frame)
    cv2.rectangle(frame,(px,py),(px+pw,py+ph),C_GRID_HOT,1)

    def stat(lbl, val, yo, col=C_WHITE):
        y = py+yo
        cv2.putText(frame,lbl,(px+10,y),
                    cv2.FONT_HERSHEY_SIMPLEX,0.4,(160,120,200),1,cv2.LINE_AA)
        cv2.putText(frame,str(val),(px+10,y+18),
                    cv2.FONT_HERSHEY_SIMPLEX,0.56,col,1,cv2.LINE_AA)

    stat("MERGERS",         m.mergers,            26, C_GOLD)
    stat("REPS",            m.reps,                74)
    stat("BEST REACH GAP", f"{m.best_gap:.2f}",  122, C_ORANGE)
    stat("BEST HOLD",      f"{m.best_hold_s:.1f}s",170)
    stat("SYMMETRY",       f"{m.symmetry:.0f}%",  218, C_CYAN)
    stat("DIFFICULTY",   difficulty.upper(), 266, C_GOLD)
    stat("DAY STREAK", f"{streak} days in a row", 312, C_GOLD)     

    # Reach meter (right)
    mx,my,mh = W-48,80,290
    fill = int((1-min(gap,1.0))*mh)
    cv2.rectangle(frame,(mx,my),(mx+30,my+mh),C_GRID_HOT,1)
    fc = C_GOLD if gap<REACH_CLOSE_THRESHOLD else \
         C_ORANGE if gap<REACH_TARGET_THRESHOLD else \
         C_CYAN if gap<REACH_GOOD_THRESHOLD else C_PURPLE
    if fill > 0:
        cv2.rectangle(frame,(mx+2,my+mh-fill+2),(mx+28,my+mh-2),fc,-1)
    cv2.putText(frame,"REACH",(mx-4,my-10),
                cv2.FONT_HERSHEY_SIMPLEX,0.38,C_PURPLE,1,cv2.LINE_AA)
    cv2.putText(frame,f"{int((1-min(gap,1))*100)}%",(mx-4,my+mh+18),
                cv2.FONT_HERSHEY_SIMPLEX,0.42,fc,1,cv2.LINE_AA)

    # Hold charge arc
    if hold_pct > 0:
        cx,cy = 150, H-110
        cv2.putText(frame,"HOLD CHARGE",(cx-55,cy-70),
                    cv2.FONT_HERSHEY_SIMPLEX,0.42,C_PURPLE,1,cv2.LINE_AA)
        cv2.ellipse(frame,(cx,cy),(55,55),-90,0,360,C_GRID_HOT,2)
        if hold_pct > 0:
            cv2.ellipse(frame,(cx,cy),(55,55),-90,0,int(hold_pct*360),C_GOLD,3,cv2.LINE_AA)
        cv2.putText(frame,f"{int(hold_pct*100)}%",(cx-18,cy+8),
                    cv2.FONT_HERSHEY_SIMPLEX,0.55,C_GOLD,1,cv2.LINE_AA)

    # Active side
    cv2.putText(frame,f"ACTIVE: {current_side.upper()} ARM OVERHEAD",
                (W//2-120,H-22),cv2.FONT_HERSHEY_SIMPLEX,0.45,C_CYAN,1,cv2.LINE_AA)

    # Trunk warning
    if trunk_warn:
        cv2.putText(frame,"!! GRAVITATIONAL DRIFT - KEEP TRUNK STRAIGHT !!",(W//2-260,38),
                    cv2.FONT_HERSHEY_SIMPLEX,0.55,C_RED,2,cv2.LINE_AA)

    # Pause overlay
    if phase == Phase.PAUSED:
        ov3 = frame.copy()
        cv2.rectangle(ov3,(W//2-260,H//2-55),(W//2+260,H//2+55),(10,4,25),-1)
        cv2.addWeighted(ov3,0.82,frame,0.18,0,frame)
        cv2.putText(frame,"PAUSED",(W//2-70,H//2-8),
                    cv2.FONT_HERSHEY_DUPLEX,1.2,C_CYAN,2,cv2.LINE_AA)
        cv2.putText(frame,"Press R to resume",(W//2-120,H//2+34),
                    cv2.FONT_HERSHEY_SIMPLEX,0.6,C_WHITE,1,cv2.LINE_AA)

    # Calibration overlay
    if phase == Phase.CALIBRATION:
        ov4 = frame.copy()
        cv2.rectangle(ov4,(W//2-320,H//2-65),(W//2+320,H//2+65),(10,4,25),-1)
        cv2.addWeighted(ov4,0.82,frame,0.18,0,frame)
        cv2.putText(frame,"CALIBRATING...",(W//2-130,H//2-12),
                    cv2.FONT_HERSHEY_DUPLEX,1.1,C_PURPLE,2,cv2.LINE_AA)
        cv2.putText(frame,"Stand facing camera - arms at your sides",(W//2-220,H//2+32),
                    cv2.FONT_HERSHEY_SIMPLEX,0.58,C_WHITE,1,cv2.LINE_AA)

def draw_lang_select(frame, selected_lang="english"):
    W, H = frame.shape[1], frame.shape[0]
    ov = frame.copy()
    cv2.rectangle(ov,(0,0),(W,H),(40,18,12),-1)
    cv2.addWeighted(ov,0.93,frame,0.07,0,frame)

    # Title
    draw_text_orbitron(frame, "SELECT LANGUAGE", (W//2, 120), 36, C_GOLD, weight="Bold")
    draw_text_orbitron(frame, "Choose your preferred language", (W//2, 168), 20,
                        C_CYAN, weight="Medium")
    cv2.line(frame, (W//2-300, 192), (W//2+300, 192), C_CYAN, 1, cv2.LINE_AA)

    langs = list(LANGUAGES.keys())
    keys  = ["1","2","3","4","5","6"]

    box_w, box_h = 320, 80
    cols, rows   = 3, 2
    total_w = cols * box_w + (cols-1) * 24
    start_x = W//2 - total_w//2

    for i, (lang_key, key_char) in enumerate(zip(langs, keys)):
        col = i % cols
        row = i // cols
        bx  = start_x + col * (box_w + 24)
        by  = 240 + row * (box_h + 20)

        is_selected = lang_key == selected_lang
        border_col  = C_GOLD if is_selected else C_CYAN
        fill_alpha  = 0.35 if is_selected else 0.15

        ov2 = frame.copy()
        rounded_rect(ov2, (bx,by), (bx+box_w,by+box_h), (110,90,20) if is_selected else (30,40,60), radius=14)
        cv2.addWeighted(ov2, fill_alpha, frame, 1-fill_alpha, 0, frame)
        rounded_rect(frame, (bx,by), (bx+box_w,by+box_h), border_col, radius=14, thickness=2 if is_selected else 1)

        # Key hint
        cv2.putText(frame, f"[{key_char}]", (bx+14, by+26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, border_col, 1, cv2.LINE_AA)

        # Language name — native script
        lang_info = LANGUAGES[lang_key]
        lang_name = lang_info["name"]
        font_path = lang_info["font"]
        cache_key = (font_path, 26, "Bold")
        if cache_key not in _font_cache:
            try:
                f = ImageFont.truetype(font_path, 26)
                try: f.set_variation_by_name("Bold")
                except: pass
            except:
                f = ImageFont.truetype(_find_asset("fonts", "Orbitron.ttf"), 26)
            _font_cache[cache_key] = f
        font = _font_cache[cache_key]

        pil_img = PILImage.new("RGBA", (frame.shape[1], frame.shape[0]), (0,0,0,0))
        draw_pil = ImageDraw.Draw(pil_img)
        bbox = draw_pil.textbbox((0,0), lang_name, font=font)
        tw = bbox[2]-bbox[0]
        tx = bx + box_w//2 - tw//2
        ty = by + box_h//2 - (bbox[3]-bbox[1])//2 - bbox[1] + 8
        color_rgb = (C_GOLD[2], C_GOLD[1], C_GOLD[0], 255) if is_selected else (200, 200, 200, 255)
        draw_pil.text((tx, ty), lang_name, font=font, fill=color_rgb)
        text_layer = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2BGR)
        alpha = np.array(pil_img)[:,:,3:4].astype(float)/255.0
        frame[:] = (frame.astype(float)*(1-alpha) + text_layer.astype(float)*alpha).astype(np.uint8)

    draw_text_orbitron(frame, "Press ENTER to confirm", (W//2, H-60), 22, C_GOLD, weight="Medium")

def draw_intro_screen(frame, blink_on=True, intro_image_right=None, intro_image_left=None,
                       intro_neon_rings_alpha=None, intro_neon_rings_beta=None, intro_bg=None):
    W, H = frame.shape[1], frame.shape[0]

    # Background — nebula texture at very low opacity, then dark tint on top
    if intro_bg is not None :
        cv2.addWeighted(intro_bg, 0.90, frame, 0.1, 0, frame)

    ov = frame.copy()
    cv2.rectangle(ov,(0,0),(W,H),(40,18,12) ,-1)
    cv2.addWeighted(ov,0.32,frame,0.68,0,frame)
    glow_cx, glow_cy = W//2, H//3
    for i in range(8):
        r = 520 - i*55
        alpha = 0.03 + i*0.012
        ov_glow = frame.copy()
        cv2.circle(ov_glow, (glow_cx, glow_cy), r, (140, 70, 25), -1)
        cv2.addWeighted(ov_glow, alpha, frame, 1-alpha, 0, frame)

    def centered(text, y, font, scale, color, thick=1):
        (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
        cv2.putText(frame, text, (W//2 - tw//2, y), font, scale, color, thick, cv2.LINE_AA)

    # ── Title box ──
    title_box_w, title_box_h = 760, 110
    tbx, tby = W//2 - title_box_w//2, 40
    ovt = frame.copy()
    rounded_rect(ovt, (tbx,tby), (tbx+title_box_w,tby+title_box_h), (110,90,20), radius=20)
    cv2.addWeighted(ovt, 0.25, frame, 0.75, 0, frame)
    rounded_rect(frame, (tbx,tby), (tbx+title_box_w,tby+title_box_h), C_CYAN, radius=20, thickness=1)
    draw_metallic_title(frame, "GUARDIANS OF AETHER", (W//2 , tby+58), 44, draw_box=False)
    
    

    # ── Mission panel ──
    box_w, box_h = 720, 380
    bx, by = W//2 - box_w//2, tby + title_box_h + 24
    ov2 = frame.copy()
    rounded_rect(ov2, (bx,by), (bx+box_w,by+box_h), (110,90,20), radius=22)
    cv2.addWeighted(ov2, 0.25, frame, 0.75, 0, frame)
    rounded_rect(frame, (bx,by), (bx+box_w,by+box_h), C_CYAN, radius=22, thickness=1)

    draw_text_orbitron(frame, "GOMUKHASANA  REHABILITATION  PROTOCOL", (W//2, by+38), 22,
                        C_CYAN, weight="Medium")
    cv2.line(frame, (bx+50, by+66), (bx+box_w-50, by+66), C_CYAN, 1, cv2.LINE_AA)

    sec_y = by + 106
    sections = [
        ("MISSION :" ,   "Guide two unstable singularities together .",  C_GOLD, (255,255,255)),
        ("OBJECTIVE :", "Reach <-> Hold <-> Stabilize",                     C_GOLD, (255,255,255)),
        ("WARNING :",   "PRECISION MATTERS MORE THAN SPEED !",           C_GOLD, (0, 50, 255) ),
    ]
    label_w = 165
    for label, body, label_col, body_col in sections:
        draw_text_orbitron(frame, label, (bx+50, sec_y), 18, label_col, weight="Bold", align="left")
        draw_text_orbitron(frame, body, (bx+50+label_w, sec_y), 18, body_col, weight="Medium", align="left")
        
        sec_y += 62

    centered("Mission movements are designed to improve functional shoulder",
              sec_y+12, cv2.FONT_HERSHEY_SIMPLEX, 0.61, (255, 255, 255), 1)
    centered("mobility while restoring controlled range of motion.",
              sec_y+34, cv2.FONT_HERSHEY_SIMPLEX, 0.64, (255, 255, 255), 1)
    box_bottom = by + box_h
    sing_cy = by + 150
    left_cx  = (0 + bx) // 2
    right_cx = ((bx + box_w) + W) // 2

    def blend_image(img, cx, cy):
        img_h, img_w = img.shape[:2]
        x0, y0 = cx - img_w // 2, cy - img_h // 2
        if not (0 <= x0 and x0 + img_w <= W and 0 <= y0 and y0 + img_h <= H):
            return
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 18, 255, cv2.THRESH_BINARY)
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR).astype(float) / 255.0
        roi = frame[y0:y0+img_h, x0:x0+img_w]
        blended = img.astype(float)*mask_3ch + roi.astype(float)*(1-mask_3ch)
        frame[y0:y0+img_h, x0:x0+img_w] = blended.astype(np.uint8)

    
    if intro_neon_rings_alpha is not None:
        blend_image(intro_neon_rings_alpha, left_cx, sing_cy)
    if intro_neon_rings_beta is not None:
        blend_image(intro_neon_rings_beta, right_cx, sing_cy)

    label_y = sing_cy + 130
    draw_text_orbitron(frame, "SINGULARITY ALPHA", (left_cx, label_y), 16, C_SINGULARITY_A, weight="Medium")
    draw_text_orbitron(frame, "SINGULARITY BETA", (right_cx, label_y), 16, C_SINGULARITY_B, weight="Medium")

    if blink_on:
        draw_text_orbitron(frame, "Press -> SPACE to assume command ", (W//2, box_bottom + 60), 26, C_GOLD, weight="Medium")

def draw_session_summary(frame, m: Metrics, streak=0, intro_image_right=None, intro_image_left=None,  summary_bg=None, prev_best_gap=None):

    W, H = frame.shape[1], frame.shape[0]
    if summary_bg is not None:
        cv2.addWeighted(summary_bg, 0.91, frame, 0.09, 0, frame)
    ov = frame.copy()
    cv2.rectangle(ov,(0,0),(W,H),(8,2,18) ,-1)
    cv2.addWeighted(ov,0.15,frame,0.85,0,frame)
    glow_cx, glow_cy = W//2, H//3
    for i in range(8):
        r = 520 - i*55
        alpha = 0.03 + i*0.012
        ov_glow = frame.copy()
        cv2.circle(ov_glow, (glow_cx, glow_cy), r, (140, 70, 25), -1)
        cv2.addWeighted(ov_glow, alpha, frame, 1-alpha, 0, frame)

    def centered(text, y, font, scale, color, thick=1):
        (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
        cv2.putText(frame, text, (W//2 - tw//2, y), font, scale, color, thick, cv2.LINE_AA)
    
    #glow_layer = np.zeros_like(frame)
    #draw_text_orbitron(glow_layer, "MISSION COMPLETE", (W//2, 96), 64, C_GOLD)
    #glow_layer = cv2.GaussianBlur(glow_layer, (0,0), sigmaX=15)
    #frame[:] = cv2.add(frame, glow_layer)

    draw_metallic_title(frame, "MISSION COMPLETE", (W//2, 96), 64)
    draw_text_orbitron(frame, "SESSION SUMMARY", (W//2, 172), 26, C_CYAN, weight="Medium")

    def perf_color(score, good=80, ok=50):
        return C_CYAN if score >= good else C_ORANGE if score >= ok else C_PURPLE

    gap_color = (C_GOLD if m.best_gap < REACH_CLOSE_THRESHOLD else
                 C_ORANGE if m.best_gap < REACH_TARGET_THRESHOLD else
                 C_CYAN if m.best_gap < REACH_GOOD_THRESHOLD else C_PURPLE)

    hold_color = (C_GOLD if m.best_hold_s >= HOLD_MERGE_SECONDS else
                  C_ORANGE if m.best_hold_s >= HOLD_MERGE_SECONDS*0.5 else C_PURPLE)

    box_w = 620
    bx = W//2 - box_w//2

    # Decorative singularities flanking the title — existing in-game render reused
    sing_cy = 110
    draw_singularity(frame, (0+bx)//2, sing_cy, C_SINGULARITY_A, 34, 0.9)
    draw_singularity(frame, ((bx+box_w)+W)//2, sing_cy, C_SINGULARITY_B, 34, 0.9)

    label_y = sing_cy + 65
    for label, cx, col in [("SINGULARITY ALPHA", (0+bx)//2, C_SINGULARITY_A),
                            ("SINGULARITY BETA", ((bx+box_w)+W)//2, C_SINGULARITY_B)]:
        draw_text_orbitron(frame, label, (cx, label_y), 16, col, weight="Medium")

    def section(title, rows, y_start):
        row_h = 54
        box_h = 36 + len(rows)*row_h
        ov2 = frame.copy()
        rounded_rect(ov2, (bx,y_start), (bx+box_w,y_start+box_h), (14,6,28), radius=18)
        cv2.addWeighted(ov2,0.75,frame,0.25,0,frame)
        rounded_rect(frame, (bx,y_start), (bx+box_w,y_start+box_h), C_GRID_HOT, radius=18, thickness=1)
        draw_text_orbitron(frame, title, (bx+24, y_start+26), 20, C_GOLD, weight="SemiBold", align="left")
        for i,(lbl,val,col,note,pct) in enumerate(rows):
            ry = y_start + 56 + i*row_h
            put_text_orbitron(frame, lbl, (bx+24, ry), 14, C_CYAN, align="left")
            put_text_orbitron(frame, val, (bx+box_w-24, ry), 17, col, align="right")
            if note:
                put_text_orbitron(frame, note, (bx+24, ry+20), 11, (200,190,220), align="left")
            if pct is not None:
                bar_y = ry + (32 if note else 18)
                bar_x0, bar_x1 = bx+24, bx+box_w-24
                cv2.rectangle(frame, (bar_x0, bar_y), (bar_x1, bar_y+6), (40,25,55), -1)
                fill_x1 = bar_x0 + int((bar_x1-bar_x0) * max(0.0,min(1.0,pct)))
                if fill_x1 > bar_x0:
                    cv2.rectangle(frame, (bar_x0, bar_y), (fill_x1, bar_y+6), col, -1)
                cv2.rectangle(frame, (bar_x0, bar_y), (bar_x1, bar_y+6), C_GRID_HOT, 1)
        return y_start + box_h

    perf_rows = [
        ("MERGERS ACHIEVED :", str(m.mergers), C_GOLD, None, None),
        ("TOTAL REPS :",       str(m.reps),    C_GOLD, None, None),
        ("BEST REACH GAP :",   f"{m.best_gap:.2f}",C_GOLD, "lower = better", None),
        ("BEST HOLD :",        f"{m.best_hold_s:.1f}s", C_GOLD, None, None),
    ]
    next_y = section("PERFORMANCE", perf_rows, 190)
    
    # ── Closest Approach — left margin circular gauge ──
    best_dist_cm = round(m.best_gap * AVG_TORSO_CM, 1)
    dist_color = (C_GOLD if best_dist_cm < 6 else
                  C_ORANGE if best_dist_cm < 11 else
                  C_CYAN if best_dist_cm < 18 else C_PURPLE)

    gauge_cx = bx // 2
    gauge_cy = 190 + (next_y - 190) // 2 + 120
    gauge_r  = 72

    # Outer ring — full circle, faint
    cv2.circle(frame, (gauge_cx, gauge_cy), gauge_r, (60,40,80), 2, cv2.LINE_AA)

    # Arc fill — how close they got (closer = more arc filled)
    fill_pct = max(0.0, min(1.0, 1.0 - m.best_gap / 0.8))
    if fill_pct > 0:
        sweep = int(fill_pct * 300)
        cv2.ellipse(frame, (gauge_cx, gauge_cy), (gauge_r, gauge_r),
                    -210, 0, sweep, C_CYAN, 3, cv2.LINE_AA)

    # Inner glow circle
    ov_gauge = frame.copy()
    cv2.circle(ov_gauge, (gauge_cx, gauge_cy), gauge_r - 12, C_CYAN, -1)
    cv2.addWeighted(ov_gauge, 0.09, frame, 0.91, 0, frame)

    # Value — large center text
    draw_text_orbitron(frame, f"~{best_dist_cm}", (gauge_cx, gauge_cy - 10), 28,
                        C_CYAN, weight="Bold")
    draw_text_orbitron(frame, "cm", (gauge_cx, gauge_cy + 22), 16,
                        (200,200,200), weight="Medium")

    # Label above
    draw_text_orbitron(frame, "CLOSEST", (gauge_cx, gauge_cy - gauge_r - 32), 16,
                        C_GOLD, weight="Bold")
    draw_text_orbitron(frame, "APPROACH", (gauge_cx, gauge_cy - gauge_r - 10), 16,
                        C_GOLD, weight="Bold")

    # Subtitle below
    put_text_orbitron(frame, "Estimated hand", (gauge_cx, gauge_cy+gauge_r+18), 13, (255,255,255), align="center")
    put_text_orbitron(frame, "distance at best.", (gauge_cx, gauge_cy+gauge_r+34), 13, (255,255,255), align="center")
    
    # Display-only note — reads existing fields, does not change how symmetry is calculated
    symmetry_note = None
    if m.left_best >= 1.0 or m.right_best >= 1.0:
        symmetry_note = "train both sides for an accurate score"

    form_rows = [
        ("SYMMETRY",   f"{m.symmetry:.0f}/100", perf_color(m.symmetry), symmetry_note, m.symmetry/100.0),
        ("SMOOTHNESS", f"{m.smoothness:.0f}/100", perf_color(m.smoothness), None, m.smoothness/100.0),
    ]
    next_y = section("FORM QUALITY", form_rows, next_y + 24)

    mm,ss = divmod(int(m.session_time()),60)
    put_text_orbitron(frame, f"Session time {mm:02d}:{ss:02d}   |   {streak} day streak",
                       (W//2, next_y+36), 15, (170,170,170), align="center")

    # Decorative side images — reused from intro screen, same blending approach
    dia_cy = 190 + (next_y - 190)//2

    # ── ROM Progress — right margin gauge ──
    right_cx = ((bx + box_w) + W) // 2
    gauge_cy_r = gauge_cy +11
    gauge_r_r  = 72

    if prev_best_gap is not None and prev_best_gap < 1.0:
        delta     = prev_best_gap - m.best_gap          # positive = improvement
        pct_delta_raw = (delta / prev_best_gap) * 100.0
        pct_delta = max(-100.0, min(100.0, pct_delta_raw))  # clamp to -100..+100
        improved  = delta >= 0
        arrow_col = C_CYAN if pct_delta >= 5 else C_GOLD if improved else C_RED
        arrow_col_r = C_RED if not improved else arrow_col

        # Outer ring
        cv2.circle(frame, (right_cx, gauge_cy_r), gauge_r_r, (60,40,80), 2, cv2.LINE_AA)

        # Arc fill — magnitude of change
        fill_pct_r = min(1.0, abs(pct_delta) / 30.0)
        if fill_pct_r > 0:
            sweep_r = int(fill_pct_r * 300)
            cv2.ellipse(frame, (right_cx, gauge_cy_r), (gauge_r_r, gauge_r_r),
                        -210, 0, sweep_r, arrow_col_r, 3, cv2.LINE_AA)

        # Inner glow
        ov_gr = frame.copy()
        cv2.circle(ov_gr, (right_cx, gauge_cy_r), gauge_r_r - 12, arrow_col_r, -1)
        cv2.addWeighted(ov_gr, 0.09, frame, 0.91, 0, frame)

        # Arrow symbol
        arrow = "+" if improved else "-"
        draw_text_orbitron(frame, arrow, (right_cx, gauge_cy_r - 8), 34,
                            arrow_col_r, weight="Bold")

        # Percentage
        draw_text_orbitron(frame, f"{min(100.0, abs(pct_delta)):.1f}%", (right_cx, gauge_cy_r + 26), 18,
                            arrow_col_r, weight="Bold")
        # Labels
        label_top = "ROM" 
        label_bot = "IMPROVED" if improved else "REGRESSED"
        draw_text_orbitron(frame, label_top,  (right_cx, gauge_cy_r - gauge_r_r - 32), 16, C_GOLD, weight="Bold")
        draw_text_orbitron(frame, label_bot,  (right_cx, gauge_cy_r - gauge_r_r - 10), 16, C_GOLD, weight="Bold")

        put_text_orbitron(frame, "Comparison of performance", (right_cx, gauge_cy_r+gauge_r_r+18), 13, (255,255,255), align="center")
        put_text_orbitron(frame, "vs last session.", (right_cx, gauge_cy_r+gauge_r_r+34), 13, (255,255,255), align="center")

    else:
        # No prior data — first session
        cv2.circle(frame, (right_cx, gauge_cy_r), gauge_r_r, (60,40,80), 2, cv2.LINE_AA)
        draw_text_orbitron(frame, "ROM", (right_cx, gauge_cy_r - 16), 20, C_GOLD, weight="Bold")
        draw_text_orbitron(frame, "BASELINE", (right_cx, gauge_cy_r + 10), 14, (170,170,170), weight="Medium")
        put_text_orbitron(frame, "First session recorded", (right_cx, gauge_cy_r+gauge_r_r+18), 13, (150,150,150), align="center")

    put_text_orbitron(frame, "R = Play again   |   T = Records   |   Q = Quit",
                       (W//2, H-38), 15, C_CYAN, align="center")

def draw_records_screen(frame, records, confirm_reset=False, summary_bg=None):
    W, H = frame.shape[1], frame.shape[0]
    if summary_bg is not None:
        cv2.addWeighted(summary_bg, 0.91, frame, 0.09, 0, frame)
    ov = frame.copy()
    cv2.rectangle(ov,(0,0),(W,H),(8,2,18),-1)
    cv2.addWeighted(ov,0.15,frame,0.85,0,frame)

    def centered(text, y, font, scale, color, thick=1):
        (tw,_),_ = cv2.getTextSize(text, font, scale, thick)
        cv2.putText(frame, text, (W//2-tw//2, y), font, scale, color, thick, cv2.LINE_AA)

    draw_metallic_title(frame, "RECORDS", (W//2, 72), 52, draw_box=True)
    cv2.line(frame,(W//2-300,112),(W//2+300,112),C_CYAN,1,cv2.LINE_AA)

    if records is None:
        draw_text_orbitron(frame, "No sessions recorded yet.", (W//2, H//2), 24,
                            (170,170,170), weight="Medium")
    else:
        sections = [
            ("TODAY",        records.get("today")),
            ("THIS WEEK",    records.get("weekly")),
            ("ALL TIME",     records.get("alltime")),
        ]

        box_w = 380
        gap   = 24
        total_w = len(sections) * box_w + (len(sections)-1) * gap
        start_x = W//2 - total_w//2
        box_y   = 130
        box_h   = 360

        for i, (title, data) in enumerate(sections):
            bx = start_x + i*(box_w+gap)
            ov2 = frame.copy()
            rounded_rect(ov2,(bx,box_y),(bx+box_w,box_y+box_h),(14,6,28),radius=18)
            cv2.addWeighted(ov2,0.75,frame,0.25,0,frame)
            rounded_rect(frame,(bx,box_y),(bx+box_w,box_y+box_h),C_GRID_HOT,radius=18,thickness=1)

            draw_text_orbitron(frame, title, (bx+box_w//2, box_y+32), 20,
                                C_GOLD, weight="Bold")
            cv2.line(frame,(bx+20,box_y+56),(bx+box_w-20,box_y+56),C_GRID_HOT,1,cv2.LINE_AA)

            if data is None:
                put_text_orbitron(frame, "No data", (bx+box_w//2, box_y+180),
                                   14, (130,130,130), align="center")
            else:
                rows = [
                    ("Best Gap",    f"{data['best_gap']:.2f}",   C_CYAN),
                    ("Best Hold",   f"{data['best_hold']:.1f}s",  C_GOLD),
                    ("Max Mergers", str(data['mergers']),         C_GOLD),
                    ("Max Reps",    str(data['reps']),            C_WHITE),
                    ("Sessions",    str(data['sessions']),        (170,170,170)),
                ]
                row_h = 52
                for j,(lbl,val,col) in enumerate(rows):
                    ry = box_y + 80 + j*row_h
                    put_text_orbitron(frame, lbl, (bx+20, ry), 16, C_CYAN, align="left")
                    put_text_orbitron(frame, val, (bx+box_w-20, ry), 16, col, align="right")
                    if j < len(rows)-1:
                        cv2.line(frame,(bx+20,ry+18),(bx+box_w-20,ry+18),(40,25,55),1,cv2.LINE_AA)
    
    # ── Daily Mergers Line Chart ──
    if records and records.get("heatmap"):
        from datetime import datetime, timedelta
        today = datetime.now().date()

        chart_x0, chart_y0 = 80, box_y + box_h + 24
        chart_w, chart_h   = W - 160, 90

        # Background strip — translucent
        ov_c = frame.copy()
        rounded_rect(ov_c, (chart_x0, chart_y0), (chart_x0+chart_w, chart_y0+chart_h),
                     (14,6,28), radius=12)
        cv2.addWeighted(ov_c, 0.6, frame, 0.4, 0, frame)
        rounded_rect(frame, (chart_x0, chart_y0), (chart_x0+chart_w, chart_y0+chart_h),
                     C_GRID_HOT, radius=12, thickness=1)

        

        # Last 14 days
        days = 14
        heatmap = records["heatmap"]
        values = []
        for d in range(days-1, -1, -1):
            date_key = (today - timedelta(days=d)).strftime("%Y-%m-%d")
            val = heatmap[date_key]["mergers"] if date_key in heatmap else 0
            values.append(val)

        max_val = max(values) if max(values) > 0 else 1
        pad_x, pad_y = 30, 20
        plot_x0 = chart_x0 + pad_x
        plot_y0 = chart_y0 + pad_y
        plot_w  = chart_w - pad_x*2
        plot_h  = chart_h - pad_y*2 - 10

        # Grid line at 0
        cv2.line(frame, (plot_x0, plot_y0+plot_h),
                 (plot_x0+plot_w, plot_y0+plot_h), (60,40,80), 1, cv2.LINE_AA)

        # Points + line
        pts = []
        for i, val in enumerate(values):
            px = plot_x0 + int(i * plot_w / (days-1))
            py = plot_y0 + plot_h - int((val/max_val) * plot_h)
            pts.append((px, py))

        # Glow line
        for i in range(len(pts)-1):
            ov_l = frame.copy()
            cv2.line(ov_l, pts[i], pts[i+1], C_CYAN, 4, cv2.LINE_AA)
            cv2.addWeighted(ov_l, 0.3, frame, 0.7, 0, frame)
            cv2.line(frame, pts[i], pts[i+1], C_CYAN, 1, cv2.LINE_AA)

        # Dots + labels
        for i, (px, py) in enumerate(pts):
            cv2.circle(frame, (px, py), 4, C_GOLD, -1, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 2, (255,255,255), -1, cv2.LINE_AA)

            # Value on top of dot (only if > 0)
            if values[i] > 0:
                put_text_orbitron(frame, str(values[i]), (px, py-10),
                                   10, C_GOLD, align="center")

            # Date below baseline — plain cv2 for visibility
            if i % 2 == 0:
                date_str = (today - timedelta(days=days-1-i)).strftime("%d")
                (tw,_),_ = cv2.getTextSize(date_str, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
                cv2.putText(frame, date_str, (px - tw//2, plot_y0+plot_h+16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200,200,200), 1, cv2.LINE_AA)

    # Chart title — bottom left, metallic, no glow
    if records and records.get("heatmap"):
        draw_metallic_title(frame, "14-DAY SINGULARITY MERGE LOG",
                             (W//2, chart_y0 + chart_h + 22), 22, draw_box=False)
        
                    
    # Bottom controls
    if confirm_reset:
        ov3 = frame.copy()
        cv2.rectangle(ov3,(W//2-280,H-90),(W//2+280,H-20),(60,10,10),-1)
        cv2.addWeighted(ov3,0.85,frame,0.15,0,frame)
        cv2.rectangle(frame,(W//2-280,H-90),(W//2+280,H-20),C_RED,2)
        put_text_orbitron(frame, "!! CONFIRM RESET? Press X again, B to cancel !!",
                           (W//2, H-48), 14, C_RED, align="center")
    else:
        put_text_orbitron(frame, "B = Back   |   X = Reset all records (fresh start)",
                           (W//2, H-38), 15, (170,170,170), align="center")

             
# ─────────────────────────────────────────────
#  MAIN GAME CLASS
# ─────────────────────────────────────────────

class BlackHoleSurgeon:

    def __init__(self, params=None):
        self.params = params or {}

        # ── Per-patient file scoping (mirrors forgotten_orchestra.py's DATA_FILE pattern) ──
        import os, re
        uid = self.params.get("user_id")
        rid = self.params.get("recovery_id")
        if uid and rid:
            uid_clean = re.sub(r'[^a-zA-Z0-9_-]', '', str(uid))
            rid_clean = re.sub(r'[^a-zA-Z0-9_-]', '', str(rid))
            suffix = f"_{uid_clean}_{rid_clean}"
        else:
            suffix = ""

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.session_log_path = os.path.join(base_dir, f"session_log{suffix}.csv")
        self.streak_path      = os.path.join(base_dir, f"streak{suffix}.json")

        #fetch_live_translations({})  # one-time startup translation fetch
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  WIN_W)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)

        self.difficulty     = "medium"
        self._apply_difficulty()

        self.analyser  = PoseAnalyser()
        self.audio     = AudioManager()
        self.particles = ParticleSystem()
        self.grid      = WarpGrid(WIN_W, WIN_H)
        self.metrics   = Metrics()

        self.phase       = Phase.INTRO
        self.calib_n     = 0
        
        _bg_raw = cv2.imread(_find_asset("images", "space.jpg"))
        self.intro_bg = cv2.imread(_find_asset("images", "space.jpg"))
        if self.intro_bg is None:
            print("[Intro] failed to load images/space.jpg")
            self.intro_bg = None
        else:
            self.intro_bg = cv2.resize(_bg_raw, (WIN_W, WIN_H))
            print(f"[Intro BG] loaded and resized to {self.intro_bg.shape[:2]}")
        
        # Singularity screen positions
        self.pos_a = np.array([WIN_W//2 - 140, WIN_H//2], dtype=float)
        self.pos_b = np.array([WIN_W//2 + 140, WIN_H//2], dtype=float)
        self.rad_a = 38.0
        self.rad_b = 38.0

        # Hold tracking
        self.in_hold      = False
        self.hold_t       = 0.0
        self.hold_start   = None
        self.hold_grace_t = 0.0

        self.confirm_reset  = False   # reset confirmation state

        # Merger event
        self.merger_active = False
        self.merger_t      = 0.0
        self.MERGER_DUR    = 2.2

        # Rep FSM
        self.rep_fsm    = "open"
        self.smooth_gap = 1.0

        # Trunk warning timer
        self.tw_timer   = 0.0

        self.current_side = SIDE_LEFT
        self.prev_t       = time.time()

        # STREAK TRACKING
        self.current_streak = self._get_streak_readonly()

        self.absorb_a = []  # particles for singularity A
        self.absorb_b = []  # particles for singularity B
        
        self.prev_best_gap = None

        # Stars
        self.stars = [(random.randint(0, WIN_W), random.randint(0, WIN_H),
                       random.uniform(0.3, 1.0)) for _ in range(200)]
        
        self.intro_image_right = cv2.imread(_find_asset("images", "black_hole_icon.png"))
        self.intro_image_left  = cv2.imread(_find_asset("images", "black_hole_icon_left.png"))   # ← new
        self.intro_neon_rings_alpha = cv2.imread(_find_asset("images", "intro_neon_rings_alpha.png"))
        self.intro_neon_rings_beta  = cv2.imread(_find_asset("images", "intro_neon_rings_beta.png"))
        self.summary_neon_hands = cv2.imread(_find_asset("images", "summary_neon_hands.png"))
        
        _summary_bg_raw = cv2.imread(_find_asset("images", "purple.jpg"))
        if _summary_bg_raw is None:
            print("[Summary] failed to load images/purple.jpg")
            self.summary_bg = None
        else:
            self.summary_bg = cv2.resize(_summary_bg_raw, (WIN_W, WIN_H))

        cv2.namedWindow("Black Hole Surgeon", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("Black Hole Surgeon", cv2.WND_PROP_ASPECT_RATIO, cv2.WINDOW_KEEPRATIO)
        self.audio.play("ambient_loop", loops=-1)

    # ── Background ────────────────────────────

    def _bg(self, frame, raw_camera):
        # Blend dark space tint over the real camera feed
        dark = np.full(frame.shape, C_DARK_BG, dtype=np.uint8)
        cv2.addWeighted(dark,0.45, raw_camera, 0.65, 0, frame)
        t = time.time()
        for sx,sy,b in self.stars:
            tw = 0.45 + 0.45*math.sin(t*1.8 + sx*0.04)
            v  = int(b*tw*180)
            cv2.circle(frame,(sx,sy),1,(v,v,v),-1)
    
    def _get_streak_readonly(self):
            import json
            
            try:
                with open(self.streak_path, "r") as f:
                    data = json.load(f)
                return data.get("streak", 0)
            except:
                return 0
            
    def _load_prev_best_gap(self):
        import csv
        try:
            with open(self.session_log_path, "r") as f:
                rows = list(csv.DictReader(f))
            if len(rows) >= 1:
                return float(rows[-1]["best_gap"])
        except:
            pass
        return None

    # ── Singularity positions ─────────────────

    def _update_positions(self, data):
        tw = data["top_wrist_px"].astype(float)
        bw = data["bot_wrist_px"].astype(float)
        
        # Clamp positions to stay within screen bounds
        tw[0] = np.clip(tw[0], 80, WIN_W - 80)
        tw[1] = np.clip(tw[1], 80, WIN_H - 80)
        bw[0] = np.clip(bw[0], 80, WIN_W - 80)
        bw[1] = np.clip(bw[1], 80, WIN_H - 80)
        
        alpha = 0.22
        self.pos_a += alpha * (tw - self.pos_a)
        self.pos_b += alpha * (bw - self.pos_b)
        gap = data["gap"]
        base = 34 + (1 - min(gap, 1)) * 32
        pulse = math.sin(time.time() * 6) * 5
        self.rad_a = base + pulse
        self.rad_b = base - pulse

    def _rep_fsm(self, gap):
        if self.rep_fsm=="open" and gap < REACH_GOOD_THRESHOLD:
            self.rep_fsm = "closing"
        elif self.rep_fsm=="closing" and gap < REACH_TARGET_THRESHOLD:
            self.rep_fsm = "close"
        elif self.rep_fsm=="close" and gap > REACH_GOOD_THRESHOLD:
            self.rep_fsm = "opening"
            self.metrics.reps += 1
            # Provide audio feedback for every 5 reps, otherwise just announce the count
            count = self.metrics.reps
            if count % 5 == 0:
                speak(f"Great job! {count} reps completed", self.audio)
            else:
                speak(str(count), self.audio)
        elif self.rep_fsm=="opening" and gap > REACH_GOOD_THRESHOLD + 0.06:
            self.rep_fsm = "open"

    # ── Hold ─────────────────────────────────

    def _hold(self, gap, dt):
        if gap < REACH_TARGET_THRESHOLD:
            self.hold_grace_t = 0.0   # back in range — clear any pending grace
            if not self.in_hold:
                self.in_hold    = True
                self.hold_start = time.time()
                self.audio.play("hold_start")
            self.hold_t = time.time() - self.hold_start
            self.metrics.total_hold_s += dt
            if self.hold_t > self.metrics.best_hold_s:
                self.metrics.best_hold_s = self.hold_t
        elif self.in_hold:
            # Brief noisy spike above threshold — tolerate it instead of
            # wiping out real progress from a single jittery frame
            self.hold_grace_t += dt
            if self.hold_grace_t > HOLD_GRACE_SECONDS:
                self.in_hold       = False
                self.hold_start    = None
                self.hold_t        = 0.0
                self.hold_grace_t  = 0.0
        pct = min(1.0, self.hold_t / HOLD_MERGE_SECONDS)
        if self.hold_t > 0.3 and not self.merger_active:
            if not pygame.mixer.get_busy() or "charging_loop" not in str(pygame.mixer.get_busy()):
                self.audio.play("charging_loop", loops=-1)
        if pct >= 1.0 and not self.merger_active:
            self._merge()
        return pct
    
    # ── Merger ───────────────────────────────

    def _merge(self):
        self.audio.stop("charging_loop")
        self.audio.stop("hold_start")
        self.merger_active = True
        self.merger_t      = 0.0
        self.metrics.mergers += 1 
        self.audio.play("merge_event")
        self.audio.duck_and_play("singularity_merged")   # was: self.audio.play("singularity_merged")
        cx = int((self.pos_a[0]+self.pos_b[0])/2)
        cy = int((self.pos_a[1]+self.pos_b[1])/2)
        self.particles.emit(cx,cy,C_GOLD,   count=70, life=1.4, size=4.5)
        self.particles.emit(cx,cy,C_ORANGE, count=50, life=1.0, size=3.0)
        self.particles.emit(cx,cy,C_PURPLE, count=35, life=0.7, size=2.0)

    # ── Reset ────────────────────────────────

    def _reset(self):
        self.metrics       = Metrics()
        self.phase         = Phase.CALIBRATION
        self.calib_n       = 0
        self.smooth_gap    = 1.0
        self.merger_active = False
        self.in_hold       = False
        self.hold_t        = 0.0
        self.hold_grace_t  = 0.0
        self.rep_fsm       = "open"
        self.current_streak = 0
        self.audio.play("ambient_loop", loops=-1)

    # ── Main loop ────────────────────────────

    def run(self):
        while True:
            ret, raw = self.cap.read()
            if not ret:
                break

            raw          = cv2.flip(raw, 1)
            frame        = cv2.resize(raw, (WIN_W, WIN_H))
            camera_feed  = frame.copy()
            
            now = time.time()
            dt  = min(now - self.prev_t, 0.05)
            self.prev_t = now

            key = cv2.waitKey(1) & 0xFF
                
            if key == ord('q') :
                break
            elif key == ord(' ') and self.phase == Phase.INTRO:
                self.phase = Phase.CALIBRATION
            elif key == ord('p') and self.phase == Phase.PLAYING:
                self.phase = Phase.PAUSED
                self.metrics.pause_timer()
                self.audio.stop_all()

            elif key == ord('r') and self.phase == Phase.PAUSED:
                self.phase = Phase.PLAYING
                self.metrics.resume_timer()
                self.audio.play("ambient_loop", loops=-1)

            elif key == ord('e') and self.phase == Phase.PLAYING:
                self.prev_best_gap = self._load_prev_best_gap()  # load BEFORE saving
                self.phase = Phase.SESSION_END
                self.audio.stop_all()
                self.audio.play("session_complete")
                self._save_session_log()

            elif key == ord('r') and self.phase == Phase.SESSION_END:
                self._reset()

            elif key == ord('1'):
                self.difficulty = "easy"
                self._apply_difficulty()
            elif key == ord('2'):
                self.difficulty = "medium"
                self._apply_difficulty()
            elif key == ord('3'):
                self.difficulty = "hard"
                self._apply_difficulty()
            
            elif key == ord('t') and self.phase == Phase.SESSION_END:
                self.phase = Phase.RECORDS
                self.confirm_reset = False

            elif key == ord('b') and self.phase == Phase.RECORDS:
                self.phase = Phase.SESSION_END
                self.confirm_reset = False

            elif key == ord('x') and self.phase == Phase.RECORDS:
                if self.confirm_reset:
                    self._reset_all_records()
                    self.phase = Phase.SESSION_END
                    self.confirm_reset = False
                else:
                    self.confirm_reset = True
                                
            # ── Background ───────────────────
            # Process pose on raw camera frame BEFORE painting background
            data = None
            if self.phase not in (Phase.PAUSED, Phase.SESSION_END, Phase.INTRO, Phase.RECORDS):
                data = self.analyser.process(frame)
            # Now paint the space background over it
            self._bg(frame, camera_feed)
            
           
            # ── INTRO ────────────────────────
            if self.phase == Phase.INTRO:
                blink_on = int(time.time()*2) % 2 == 0
                draw_intro_screen(frame, blink_on=blink_on, intro_image_right=self.intro_image_right,
                                   intro_image_left=self.intro_image_left,
                                   intro_neon_rings_alpha=self.intro_neon_rings_alpha,
                                   intro_neon_rings_beta=self.intro_neon_rings_beta,
                                   intro_bg=self.intro_bg,
                                   )
                cv2.imshow("Black Hole Surgeon", frame)
                continue
            gap       = self.smooth_gap
            hold_pct  = 0.0
            trunk_warn = self.tw_timer > 0

            if data:
                gap             = data["gap"]
                self.smooth_gap = gap
                self.current_side = data["top_side"]

                # Update metric bests
                if gap < self.metrics.best_gap:
                    self.metrics.best_gap = gap
                if self.current_side == SIDE_LEFT:
                    self.metrics.left_best  = min(self.metrics.left_best,  gap)
                else:
                    self.metrics.right_best = min(self.metrics.right_best, gap)
                self.metrics.update_symmetry()
                self.metrics.update_smoothness(data["delta"])

                if data["trunk_lean"] > TRUNK_LEAN_LIMIT:
                    self.tw_timer = 1.8
                    if random.random() < 0.04:
                        self.audio.play("warning")

            if self.tw_timer > 0:
                self.tw_timer -= dt
                trunk_warn = True

            # ── SESSION END ──────────────────
            if self.phase == Phase.SESSION_END:
                _ = self.cap.read()  # keep camera ticking so waitKey stays fast
                draw_session_summary(frame, self.metrics, self.current_streak,
                                      self.intro_image_right, self.intro_image_left, self.summary_bg, prev_best_gap=self.prev_best_gap)
                cv2.imshow("Black Hole Surgeon", frame)
                continue

            # ── RECORDS ──────────────────────
            if self.phase == Phase.RECORDS:
                records = self._get_records()
                draw_records_screen(frame, records, self.confirm_reset, self.summary_bg)
                cv2.imshow("Black Hole Surgeon", frame)
                continue

            # ── CALIBRATION ──────────────────
            if self.phase == Phase.CALIBRATION:
                if data:
                    self.calib_n += 1
                    if self.calib_n >= 40:
                        self.phase = Phase.PLAYING
                        self.audio.play("calibration_music")
                        self.audio.duck_and_play("calibration_voice") # was: self.audio.play("calibration_voice")
                draw_hud(frame, self.metrics, 1.0, 0.0, self.phase,
                         self.current_side, False, self.difficulty, self.current_streak)
                cv2.imshow("Black Hole Surgeon", frame)
                continue

            # ── PAUSED ───────────────────────
            if self.phase == Phase.PAUSED:
                gap_norm = min(self.smooth_gap/0.8, 1.0)
                self.grid.draw(frame,
                               tuple(self.pos_a.astype(int)),
                               tuple(self.pos_b.astype(int)), gap_norm)
                draw_singularity(frame,
                                 int(self.pos_a[0]), int(self.pos_a[1]),
                                 C_SINGULARITY_A, int(self.rad_a), 0.7)
                draw_singularity(frame,
                                 int(self.pos_b[0]), int(self.pos_b[1]),
                                 C_SINGULARITY_B, int(self.rad_b), 0.7)
                draw_hud(frame, self.metrics, gap, 0.0, self.phase,
                         self.current_side, False, self.difficulty, self.current_streak)
                cv2.imshow("Black Hole Surgeon", frame)
                continue

            # ── PLAYING ──────────────────────
            if data:
                self._update_positions(data)
                self._rep_fsm(gap)

            gap_norm = min(gap / 0.8, 1.0)
            self.audio.set_proximity_volume(gap_norm)

            # Grid
            self.grid.draw(frame,
                           tuple(self.pos_a.astype(int)),
                           tuple(self.pos_b.astype(int)), gap_norm)

            # Hold + merger
            hold_pct = self._hold(gap, dt)

            # Arc lightning
            arc_int = max(0.0, 1.0 - gap/REACH_GOOD_THRESHOLD)
            if arc_int > 0.08:
                pa = tuple(self.pos_a.astype(int))
                pb = tuple(self.pos_b.astype(int))
                draw_lightning(frame, pa, pb, C_SINGULARITY_A, C_SINGULARITY_B, arc_int)
                if random.random() < arc_int * 0.7:
                    self.particles.arc_sparks(pa[0],pa[1],pb[0],pb[1],
                                              arc_int,C_SINGULARITY_A,C_SINGULARITY_B)
                if random.random() < 0.04*arc_int:
                    self.audio.play("proximity")

            # Singularities
            # Singularities
            draw_singularity(frame,
                            int(self.pos_a[0]),int(self.pos_a[1]),
                            C_SINGULARITY_A, int(self.rad_a), 1.0-gap_norm*0.4)
            update_absorption(frame,
                            int(self.pos_a[0]),int(self.pos_a[1]),
                            C_SINGULARITY_A, gap_norm, self.absorb_a, dt)

            draw_singularity(frame,
                            int(self.pos_b[0]),int(self.pos_b[1]),
                            C_SINGULARITY_B, int(self.rad_b), 1.0-gap_norm*0.4)
            update_absorption(frame,
                            int(self.pos_b[0]),int(self.pos_b[1]),
                            C_SINGULARITY_B, gap_norm, self.absorb_b, dt)
            
            # Particles
            self.particles.update_draw(frame, dt)

            # Merger flash
            if self.merger_active:
                self.merger_t += dt
                prog = self.merger_t / self.MERGER_DUR
                if prog > 0.4:
                    W,H2 = frame.shape[1],frame.shape[0]
                    ov = frame.copy()
                    cv2.rectangle(ov,(0,0),(W,H2),(255,255,255),-1)
                    cv2.addWeighted(ov, min(0.55,(prog-0.4)*1.5),
                                    frame,1-min(0.55,(prog-0.4)*1.5),0,frame)
                    cv2.putText(frame,"SINGULARITY MERGED!",(W//2-220,H2//2),
                                cv2.FONT_HERSHEY_DUPLEX,1.5,C_GOLD,3,cv2.LINE_AA)
                    cv2.putText(frame,f"+1  MERGER",(W//2-90,H2//2+55),
                                cv2.FONT_HERSHEY_SIMPLEX,1.0,C_ORANGE,2,cv2.LINE_AA)
                if self.merger_t >= self.MERGER_DUR:
                    self.merger_active = False
                    self.in_hold       = False
                    self.hold_t        = 0.0
                    self.hold_grace_t  = 0.0

            # Skeleton
            if data and data.get("landmarks"):
                BODY_CONNECTIONS = [
                    (11,12), (11,13), (13,15), (12,14), (14,16),
                    (11,23), (12,24), (23,24),
                ]
                KEY_JOINTS = [11, 12, 13, 14, 15, 16]  # shoulders, elbows, wrists only

                lms = data["landmarks"].landmark
                h, w = frame.shape[:2]
                t = time.time()

                GLOW_OUTER  = (200, 210, 60)   # faint outer glow — teal
                GLOW_MID    = (230, 225, 100)  # mid glow
                GLOW_CORE   = (255, 245, 160)  # bright core — near white cyan

                # Pass 1 — thick faint outer glow
                for a, b in BODY_CONNECTIONS:
                    ax,ay = int(lms[a].x*w), int(lms[a].y*h)
                    bx,by = int(lms[b].x*w), int(lms[b].y*h)
                    ov = frame.copy()
                    cv2.line(ov, (ax,ay), (bx,by), GLOW_OUTER, 8, cv2.LINE_AA)
                    cv2.addWeighted(ov, 0.12, frame, 0.88, 0, frame)

                # Pass 2 — medium mid glow
                for a, b in BODY_CONNECTIONS:
                    ax,ay = int(lms[a].x*w), int(lms[a].y*h)
                    bx,by = int(lms[b].x*w), int(lms[b].y*h)
                    ov = frame.copy()
                    cv2.line(ov, (ax,ay), (bx,by), GLOW_MID, 4, cv2.LINE_AA)
                    cv2.addWeighted(ov, 0.22, frame, 0.78, 0, frame)

                # Pass 3 — sharp bright core line
                for a, b in BODY_CONNECTIONS:
                    ax,ay = int(lms[a].x*w), int(lms[a].y*h)
                    bx,by = int(lms[b].x*w), int(lms[b].y*h)
                    cv2.line(frame, (ax,ay), (bx,by), GLOW_CORE, 1, cv2.LINE_AA)

                # Pulsing dots on key joints only
                pulse = 0.6 + 0.4 * math.sin(t * 5)
                for idx in KEY_JOINTS:
                    x = int(lms[idx].x * w)
                    y = int(lms[idx].y * h)

                    # Outer pulse ring
                    ring_r = int(10 + 4 * pulse)
                    ov = frame.copy()
                    cv2.circle(ov, (x,y), ring_r, GLOW_OUTER, 2, cv2.LINE_AA)
                    cv2.addWeighted(ov, 0.35 * pulse, frame, 1 - 0.35 * pulse, 0, frame)

                    # Bright filled centre dot
                    cv2.circle(frame, (x,y), 7, GLOW_CORE, -1, cv2.LINE_AA)

                    # Tiny white hot centre
                    cv2.circle(frame, (x,y), 3, (255,255,255), -1, cv2.LINE_AA)

            # HUD
            draw_hud(frame, self.metrics, gap, hold_pct, self.phase,
                     self.current_side, trunk_warn, self.difficulty, self.current_streak)

            # Status label
            if gap < REACH_CLOSE_THRESHOLD:
                lbl,col = "MERGER IMMINENT - HOLD!",C_GOLD
            elif gap < REACH_TARGET_THRESHOLD:
                lbl,col = "TARGET REACHED - HOLD!",C_ORANGE
            elif gap < REACH_GOOD_THRESHOLD:
                lbl,col = "GOOD REACH - GO FURTHER",C_CYAN
            else:
                lbl,col = "REACH FURTHER BACK",C_PURPLE

            W2 = frame.shape[1]
            cv2.putText(frame,lbl,(W2//2-160,frame.shape[0]-48),
                        cv2.FONT_HERSHEY_DUPLEX,0.8,col,2,cv2.LINE_AA)
            cv2.rectangle(frame, (0, WIN_H-28), (WIN_W-790, WIN_H), (10,4,25), -1)
            cv2.putText(frame,"P=pause  R=resume  E=end session  1=Easy  2=Medium  3=Hard  Q=quit",
                        (10,WIN_H-10),cv2.FONT_HERSHEY_SIMPLEX,
                        0.36,(200,200,200),1,cv2.LINE_AA)

            cv2.imshow("Black Hole Surgeon", frame)

        self.audio.stop_all()
        self.cap.release()
        cv2.destroyAllWindows()
        pygame.quit()

        m = self.metrics
        completed = self.phase == Phase.SESSION_END

        session_result = {
            "session": {
                "name": "aether_guardian",
                "completed": completed,
                "slot": self.params.get("session_type", "morning"),
                "week": self.params.get("current_week", 1)
            },
            "metrics": {
                "mergers": m.mergers,
                "reps": m.reps,
                "best_gap": round(m.best_gap, 3),
                "best_hold_s": round(m.best_hold_s, 1),
                "symmetry": round(m.symmetry, 1),
                "smoothness": round(m.smoothness, 1),
                "difficulty": self.difficulty
            },
            "objectives": {
                "completed": completed
            }
        }
        return session_result

    def _save_session_log(self):
        import csv
        import os
        from datetime import datetime

        filepath = self.session_log_path
        file_exists = os.path.isfile(filepath)

        row = {
            "date":              datetime.now().strftime("%Y-%m-%d"),
            "time":              datetime.now().strftime("%H:%M:%S"),
            "duration_s":        round(self.metrics.session_time(), 1),
            "mergers":           self.metrics.mergers,
            "reps":              self.metrics.reps,
            "best_gap":          round(self.metrics.best_gap, 3),
            "closest_approach_cm": round(self.metrics.best_gap * AVG_TORSO_CM, 1),
            "best_hold_s":       round(self.metrics.best_hold_s, 1),
            "symmetry":          round(self.metrics.symmetry, 1),
            "smoothness":        round(self.metrics.smoothness, 1),
            "difficulty":        self.difficulty,
        }

        with open(filepath, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    
        print(f"[Log] Session saved to {filepath}")
        self.current_streak = self._get_streak()
        print(f"[Streak] Current streak: {self.current_streak} days")
    
    def _get_records(self):
        import csv
        import os
        from datetime import datetime, timedelta

        filepath = self.session_log_path
        if not os.path.isfile(filepath):
            return None

        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        all_rows = []
        today_rows = []
        week_rows = []

        try:
            with open(filepath, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        row_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
                        best_gap = float(row["best_gap"])
                        best_hold = float(row["best_hold_s"])
                        mergers = int(row["mergers"])
                        reps = int(row["reps"])

                        all_rows.append((row_date, best_gap, best_hold, mergers, reps))
                        if row_date == today:
                            today_rows.append((row_date, best_gap, best_hold, mergers, reps))
                        if row_date >= week_ago:
                            week_rows.append((row_date, best_gap, best_hold, mergers, reps))
                    except:
                        continue
        except:
            return None

        if not all_rows:
            return None

        def best_of(rows):
            if not rows:
                return None
            return {
                "best_gap":   min(r[1] for r in rows),
                "best_hold":  max(r[2] for r in rows),
                "mergers":    max(r[3] for r in rows),
                "reps":       max(r[4] for r in rows),
                "sessions":   len(rows),
            }

        # Last 30 days heatmap data
        heatmap = {}
        for row_date, best_gap, best_hold, mergers, reps in all_rows:
            if row_date >= today - timedelta(days=30):
                key = row_date.strftime("%Y-%m-%d")
                if key not in heatmap or mergers > heatmap[key]["mergers"]:
                    heatmap[key] = {"best_gap": best_gap, "mergers": mergers}

        return {
            "alltime": best_of(all_rows),
            "today":   best_of(today_rows),
            "weekly":  best_of(week_rows),
            "heatmap": heatmap,
        }
    
    def _reset_all_records(self):
        import os
        for f in [self.session_log_path, self.streak_path]:
            if os.path.isfile(f):
                os.remove(f)
                print(f"[Reset] Deleted {f}")
        self.current_streak = 0
        print("[Reset] All records cleared.")

    def _get_streak(self):
        import json
        from datetime import datetime, timedelta

        filepath = self.streak_path
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except:
            data = {"streak": 0, "last_date": ""}

        last  = data.get("last_date", "")
        streak = data.get("streak", 0)

        if last == today:
            # Already played today, streak unchanged
            pass
        elif last == (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"):
            # Played yesterday, increment streak
            streak += 1
            data = {"streak": streak, "last_date": today}
            with open(filepath, "w") as f:
                json.dump(data, f)
        else:
            # Missed a day or first time, reset
            streak = 1
            data = {"streak": streak, "last_date": today}
            with open(filepath, "w") as f:
                json.dump(data, f)

        return streak
    
    def _apply_difficulty(self):
        s = DIFFICULTY_SETTINGS[self.difficulty]
        global HOLD_MERGE_SECONDS, REACH_TARGET_THRESHOLD, REACH_GOOD_THRESHOLD
        HOLD_MERGE_SECONDS       = s["hold_seconds"]
        REACH_TARGET_THRESHOLD   = s["target_threshold"]
        REACH_GOOD_THRESHOLD     = s["good_threshold"]

# ─────────────────────────────────────────────

def main(params=None):
    game = BlackHoleSurgeon(params=params)
    result = game.run()
    return result

if __name__ == "__main__":
    main()