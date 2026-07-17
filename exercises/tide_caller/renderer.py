"""Draw coordinator for Tide Caller.

One TideRenderer.render() call per frame; internally dispatches to a screen
method by TideState. Screens that need no camera feed (INTRO, SESSION_
COMPLETE, RECORDS) draw over a plain gradient; gameplay states draw the
live ocean/beach/HUD over the camera frame.

All text is drawn through text.py (Orbitron TTF, anti-aliased) instead of
cv2's blocky Hershey font - see text.draw_text / text.draw_gradient_text.
All colors are BGR (cv2). Owns no game logic - everything it draws is
passed in as plain data.
"""

from __future__ import annotations
import cv2
import os
import numpy as np
import math
import time
from . import config
from . import text as tx
from .game import TideState
from .render.sorcerer import draw_magic_circle, draw_tide_orb, draw_energy_link

_BG_DIR = os.path.join(os.path.dirname(__file__), "assets", "backgrounds")

_PROMPTS = {
    TideState.CALIBRATING: ("FIND YOUR STANCE", config.COL_FOAM),
    TideState.IDLE: ("RAISE YOUR ARMS TO CALL THE TIDE", config.COL_HUD_ACCENT),
    TideState.RISING: ("RISING...", config.COL_FOAM),
    TideState.CHARGING: ("HOLD AT PEAK - CHARGING", config.COL_HUD_ACCENT),
    TideState.CHARGED: ("RELEASE THE TIDE", config.COL_FOAM),
    TideState.LOWERING: ("CRASHING - CONTROL THE LOWER", config.COL_SHORE_SUNSET),
    TideState.WASHING: ("", config.COL_FOAM),
    TideState.WAVE_SCORED: ("", config.COL_FOAM),
    TideState.PAUSED: ("PAUSED  (p to resume)", config.COL_SHORE_SUNSET),
}

_GRADE_MESSAGES = {
    "RIPPLE": "RIPPLE OF HOPE",
    "WAVE": "TIDE AWAKENED",
    "BREAKER": "ANCIENT SURGE",
    "TSUNAMI": "TSUNAMI OF THE DEEP",
}


class TideRenderer:
    def __init__(self) -> None:
        self.w = config.FRAME_WIDTH
        self.h = config.FRAME_HEIGHT
        self._tide_display = 0.0
        self._sea_top_min = int(self.h * 0.45)
        self._beach_top = int(self.h * 0.78)
        self._crash_flash = 0.0
        self._shore_burst = 0.0
        self._foam_wave = 0.0
        self._bg_intro = self._load_bg("intro_bg.jpg")
        self._bg_splash = self._load_bg("splash_bg.jpg")
        self._bg_summary = self._load_bg("summary_bg.jpg")
        self._bg_records = self._load_bg("records_bg.jpg")
        self._bg_intro_video = self._load_bg_video("intro_bg.mp4")

    def _load_bg_video(self, filename: str):
        """Open a looping background video. None on any failure (missing
        file, bad codec, etc.) - callers fall back to the static image."""
        path = os.path.join(_BG_DIR, filename)
        try:
            cap = cv2.VideoCapture(path)
            return cap if cap.isOpened() else None
        except Exception:
            return None

    def _next_video_frame(self, cap):
        """Read the next frame, looping back to the start at end-of-clip.
        Returns None (caller falls back to static bg) on any read failure."""
        if cap is None:
            return None
        try:
            ok, frame = cap.read()
            if not ok:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
            if not ok:
                return None
            return cv2.resize(frame, (self.w, self.h))
        except Exception:
            return None

    def _load_bg(self, filename: str):
        """Load a background photo, resized to the window. None on any failure
        (missing file, unreadable image, etc.) - callers fall back to a
        gradient, so a missing asset never crashes the game."""
        path = os.path.join(_BG_DIR, filename)
        try:
            img = cv2.imread(path)
            if img is None:
                return None
            return cv2.resize(img, (self.w, self.h))
        except Exception:
            return None

    # ------------------------------------------------------------------
    def render(self, frame, *, state, avg_angle, left_angle, right_angle,
               left_wrist, right_wrist, symmetry_pct, session, campaign,
               last_score, charge_fraction, records_data=None):
        """Draw the full scene onto frame and return it."""
        if state == TideState.SPLASH:
            self._draw_splash(frame)
            return frame
        if state == TideState.INTRO:
            self._draw_intro(frame, campaign, session)
            return frame
        if state == TideState.SESSION_COMPLETE:
            self._draw_summary(frame, session, campaign)
            return frame
        if state == TideState.RECORDS:
            self._draw_records(frame, records_data)
            return frame

        chapter = campaign.current_chapter
        self._draw_ocean(frame, avg_angle, charge_fraction, state, chapter)
        if state == TideState.WASHING:
            self._crash_flash = 1.0
            self._shore_burst = 1.0
            self._foam_wave = 1.0
        self._draw_crash_flash(frame)
        self._draw_shore_burst(frame)
        self._draw_foam_wave(frame)
        self._draw_beach(frame, session, chapter)
        self._draw_hud(frame, avg_angle, left_angle, right_angle,
                        symmetry_pct, session, last_score, chapter)
        self._draw_timer(frame, session)
        self._draw_prompt(frame, state, last_score)
        self._draw_player_vfx(frame, left_wrist, right_wrist, charge_fraction)
        return frame

    # ------------------------------------------------------------------
    # SPLASH (static title/lore art, shown before the functional intro)
    # ------------------------------------------------------------------
    def _draw_splash(self, frame):
        if self._bg_splash is not None:
            frame[:] = self._bg_splash
        else:
            self._fill_gradient(frame, config.COL_DARKNESS, config.COL_DEEP_SEA)

        # thin readable scrim bar at the very bottom - the art is busy right
        # up to the edge, so the blinking prompt needs its own contrast strip
        bar_h = 46
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, self.h - bar_h), (self.w, self.h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        self._blink(frame, "Press SPACE to continue", self.h - 16, config.COL_FOAM)

    # ------------------------------------------------------------------
    # INTRO
    # ------------------------------------------------------------------
    def _draw_intro(self, frame, campaign, session):
        chapter = campaign.current_chapter
        self._draw_screen_bg(frame, self._bg_intro, config.COL_DARKNESS, chapter.col_deep,
                              video_cap=self._bg_intro_video, dim=0.28)

        # ---- title badge ----
        tbx0, tby0, tbx1, tby1 = 260, 20, self.w - 260, 108
        self._glass_panel(frame, (tbx0, tby0), (tbx1, tby1), radius=18, fill_alpha=0.65)
        tx.draw_gradient_text(frame, "RECLAIM THE TIDE", (self.w // 2, 38), size=46,
                               weight="Black", align="center", stroke_width=5,
                               top_color_bgr=(255, 253, 245), bottom_color_bgr=(20, 130, 235),
                               glow=True, glow_strength=1.3, glow_color_bgr=(60, 170, 255))
        self._draw_wave_flourish(frame, tbx0 - 70, (tby0 + tby1) // 2, flip=False)
        self._draw_wave_flourish(frame, tbx1 + 70, (tby0 + tby1) // 2, flip=True)

        # ---- story panel (narrower + centered - chapter text never needs
        # full width, so a wide panel just left a wasted empty right half) ----
        panel_w = 640
        px0, py0, px1, py1 = (self.w - panel_w) // 2, 130 + 90, \
                              (self.w + panel_w) // 2, 130 + 90 + 210
        self._glass_panel(frame, (px0, py0), (px1, py1))

        tx.draw_text(frame, f"CHAPTER {campaign.chapter_index + 1}: {chapter.name.upper()}",
                     (px0 + 28, py0 + 20), size=24, color_bgr=config.COL_HUD_ACCENT, weight="Bold",
                     glow=True, glow_strength=0.9)
        tx.draw_text(frame, chapter.story, (px0 + 28, py0 + 65), size=19,
                     color_bgr=config.COL_TEXT, weight="Regular")
        tx.draw_text(frame, "Raise both arms to call the tide and hold at the peak",
                     (px0 + 28, py0 + 118), size=16, color_bgr=config.COL_NEON_BLUE, weight="Medium")
        tx.draw_text(frame, "to charge each wave.", (px0 + 28, py0 + 148), size=16,
                     color_bgr=config.COL_NEON_BLUE, weight="Medium")

        # ---- today's prescription panel (full width - genuinely needs the
        # space for 4 spread-out stat columns) ----
        qx0, qy0, qx1, qy1 = 100, py1 + 20, self.w - 100, py1 + 20 + 200
        self._glass_panel(frame, (qx0, qy0), (qx1, qy1))

        tx.draw_text(frame, f"DAY {campaign.day_number}", (qx0 + 28, qy0 + 18),
                     size=30, color_bgr=config.COL_HUD_ACCENT, weight="Black",
                     glow=True, glow_strength=0.9)
        streak_txt = f"Streak: {campaign.streak} day{'s' if campaign.streak != 1 else ''}"
        tx.draw_text(frame, streak_txt, (qx1 - 28, qy0 + 26), size=18,
                     color_bgr=config.COL_HUD_ACCENT, weight="Medium", align="right")

        cv2.line(frame, (qx0 + 24, qy0 + 66), (qx1 - 24, qy0 + 66), config.COL_NEON_BLUE, 1)

        col_w = (qx1 - qx0) // 4
        stats = [
            ("TARGET ROM", f"{int(session.target_rom)}\u00b0"),
            ("HOLD TIME", f"{campaign.prescription.hold_seconds:.1f}s"),
            ("WAVES", f"{session.wave_target}"),
            ("TIME LIMIT", f"{int(session.time_limit // 60)} min"),
        ]
        for i, (label, value) in enumerate(stats):
            cx = qx0 + col_w * i + col_w // 2
            tx.draw_text(frame, label, (cx, qy0 + 88), size=14,
                         color_bgr=config.COL_TEXT, weight="Regular", align="center")
            tx.draw_text(frame, value, (cx, qy0 + 116), size=32,
                         color_bgr=config.COL_FOAM, weight="Bold", align="center")

        note = "This is a soft time guide - you can keep going past it, or press E to end anytime."
        tx.draw_text(frame, note, (self.w // 2, qy1 - 34), size=14,
                     color_bgr=config.COL_TEXT, weight="Regular", align="center")

        self._blink(frame, "Press SPACE to call the tide", qy1 + 45, config.COL_FOAM)

    # ------------------------------------------------------------------
    # SESSION SUMMARY
    # ------------------------------------------------------------------
    def _draw_summary(self, frame, session, campaign):
        chapter = campaign.current_chapter
        self._draw_screen_bg(frame, self._bg_summary, config.COL_DARKNESS, config.COL_SHORE_SUNSET, dim=0.32)

        completed = session.waves_done >= session.wave_target
        hero_title = "THE COAST IS RESTORED" if completed else "GREAT EFFORT TODAY"

        # ---- title badge ----
        bx0, by0, bx1, by1 = 300, 16, self.w - 300, 104
        self._glass_panel(frame, (bx0, by0), (bx1, by1), radius=18, fill_alpha=0.68)
        tx.draw_gradient_text(frame, hero_title, (self.w // 2, 30), size=34,
                               weight="Black", align="center", stroke_width=4)
        tx.draw_text(frame, "SESSION SUMMARY", (self.w // 2, 78), size=20,
                     color_bgr=config.COL_NEON_BLUE, weight="Medium", align="center")

        scores = session.scores
        n = max(1, len(scores))
        avg_symmetry = sum(s.symmetry for s in scores) / n
        avg_eccentric = sum(s.eccentric for s in scores) / n
        avg_concentric = sum(s.concentric for s in scores) / n
        score_frac = max(0.0, min(1.0, session.best_score / 100.0))

        # ---- mirrored hero gauges: symmetry (left) / best score (right) ----
        self._draw_radial_gauge(frame, (150, 300), 78, avg_symmetry,
                                 f"{int(avg_symmetry * 100)}%", "SYMMETRY",
                                 self._quality_color(avg_symmetry))
        self._draw_radial_gauge(frame, (self.w - 150, 300), 78, score_frac,
                                 str(session.best_score), "BEST SCORE",
                                 config.COL_HUD_ACCENT)

        px0, px1 = 260, self.w - 260

        # ---- PERFORMANCE panel ----
        py0, py1 = 140, 370
        self._glass_panel(frame, (px0, py0), (px1, py1))
        tx.draw_text(frame, "PERFORMANCE", (px0 + 24, py0 + 14), size=22,
                     color_bgr=config.COL_HUD_ACCENT, weight="Bold")

        def row(label, value, y, color=config.COL_TEXT):
            tx.draw_text(frame, label, (px0 + 24, y), size=17,
                         color_bgr=config.COL_TEXT, weight="Regular")
            tx.draw_text(frame, value, (px1 - 24, y - 2), size=19,
                         color_bgr=color, weight="Bold", align="right")

        row("Waves cleared", f"{session.waves_done} / {session.wave_target}", py0 + 54)
        row("Clean clears", str(session.clean_clears), py0 + 78, config.COL_SEA_GREEN)
        row("Murky clears (ripples)", str(session.murky_clears), py0 + 102)
        row("Artifacts discovered", str(len(session.artifact_by_patch)),
            py0 + 126, config.COL_HUD_ACCENT)
        row("Best wave score", str(session.best_score), py0 + 150, config.COL_HUD_ACCENT)
        row("Peak ROM this session", f"{int(session.session_max_rom)} deg", py0 + 174)
        mins, secs = divmod(int(session.elapsed()), 60)
        row("Duration", f"{mins}m {secs}s", py0 + 198)

        # ---- FORM QUALITY panel ----
        fy0, fy1 = 388, 568
        self._glass_panel(frame, (px0, fy0), (px1, fy1))
        tx.draw_text(frame, "FORM QUALITY", (px0 + 24, fy0 + 14), size=22,
                     color_bgr=config.COL_HUD_ACCENT, weight="Bold")

        def bar(label, value, y):
            color = self._quality_color(value)
            tx.draw_text(frame, label, (px0 + 24, y), size=17,
                         color_bgr=config.COL_TEXT, weight="Regular")
            tx.draw_text(frame, f"{int(value * 100)}%", (px1 - 24, y - 2), size=19,
                         color_bgr=color, weight="Bold", align="right")
            bx0_, bx1_, by_ = px0 + 24, px1 - 24, y + 24
            self._rounded_rect(frame, (bx0_, by_), (bx1_, by_ + 14), (55, 50, 45), radius=7)
            fill = int((bx1_ - bx0_) * max(0.0, min(1.0, value)))
            if fill > 6:
                self._rounded_rect(frame, (bx0_, by_), (bx0_ + fill, by_ + 14), color, radius=7)

        bar("Concentric smoothness (lift)", avg_concentric, fy0 + 56)
        bar("Eccentric smoothness (lower)", avg_eccentric, fy0 + 126)

        # ---- chapter progress ----
        needed = chapter.waves_to_clear
        frac = 0.0 if needed <= 0 else min(1.0, campaign.total_clears / needed)
        cy = 585
        ctxt = (f"CHAPTER {campaign.chapter_index + 1}: {chapter.name.upper()}"
                f"  ({campaign.total_clears}/{needed} waves)")
        tx.draw_text(frame, ctxt, (px0, cy), size=16, color_bgr=config.COL_TEXT, weight="Regular")
        self._rounded_rect(frame, (px0, cy + 22), (px1, cy + 38), (55, 50, 45), radius=8)
        fill = int((px1 - px0) * frac)
        if fill > 6:
            self._rounded_rect(frame, (px0, cy + 22), (px0 + fill, cy + 38),
                                config.COL_HUD_ACCENT, radius=8)

        # ---- quiet meta line ----
        meta_txt = (f"Day {campaign.day_number} complete   |   "
                    f"{campaign.streak} day streak   |   "
                    f"Sessions today: {campaign.sessions_today}")
        tx.draw_text(frame, meta_txt, (self.w // 2, 645), size=15,
                     color_bgr=config.COL_TEXT, weight="Regular", align="center")

        self._blink(frame, "R: Play Again   T: Records   Esc: Quit", 682, config.COL_NEON_BLUE)

    # ------------------------------------------------------------------
    # RECORDS
    # ------------------------------------------------------------------
    def _draw_records(self, frame, records_data):
        self._draw_screen_bg(frame, self._bg_records, config.COL_DARKNESS, (90, 50, 15))

        bx0, by0, bx1, by1 = 440, 16, self.w - 440, 96
        self._glass_panel(frame, (bx0, by0), (bx1, by1), radius=18, fill_alpha=0.68)
        tx.draw_gradient_text(frame, "RECORDS", (self.w // 2, 28), size=38,
                               weight="Black", align="center", stroke_width=4)

        if not records_data:
            tx.draw_text(frame, "No sessions logged yet.", (self.w // 2, self.h // 2),
                         size=22, color_bgr=config.COL_TEXT, weight="Regular", align="center")
            return

        panels = [("TODAY", records_data["today"]),
                  ("THIS WEEK", records_data["this_week"]),
                  ("ALL TIME", records_data["all_time"])]
        gap = 30
        panel_w = (self.w - gap * 4) // 3
        py0, py1 = 116, 340

        for i, (label, stats) in enumerate(panels):
            x0 = gap + i * (panel_w + gap)
            x1 = x0 + panel_w
            self._glass_panel(frame, (x0, py0), (x1, py1))

            tx.draw_text(frame, label, (x0 + 20, py0 + 14), size=22,
                         color_bgr=config.COL_NEON_BLUE, weight="Bold")

            def row(lbl, value, y, color=config.COL_TEXT, _x0=x0, _x1=x1):
                tx.draw_text(frame, lbl, (_x0 + 20, y), size=15,
                             color_bgr=config.COL_TEXT, weight="Regular")
                tx.draw_text(frame, str(value), (_x1 - 20, y - 2), size=18,
                             color_bgr=color, weight="Bold", align="right")

            row("Best score", stats['best_score'], py0 + 62, config.COL_HUD_ACCENT)
            row("Max waves", stats['max_waves'], py0 + 96, config.COL_HUD_ACCENT)
            row("Max clean clears", stats['max_clean_clears'], py0 + 130, config.COL_SEA_GREEN)
            row("Sessions", stats['sessions'], py0 + 164)

        cx0, cy0, cx1, cy1 = 60, 360, self.w - 60, 570
        self._glass_panel(frame, (cx0, cy0), (cx1, cy1))
        tx.draw_text(frame, "14-DAY WAVE LOG", (cx0 + 20, cy0 + 14), size=20,
                     color_bgr=config.COL_NEON_BLUE, weight="Bold")

        series = records_data["daily_waves"]
        max_val = max((v for _, v in series), default=0) or 1
        plot_x0, plot_x1 = cx0 + 34, cx1 - 34
        plot_y0, plot_y1 = cy0 + 60, cy1 - 46
        n = max(1, len(series) - 1)
        pts = []
        for i, (_, val) in enumerate(series):
            x = int(plot_x0 + (plot_x1 - plot_x0) * i / n)
            y = int(plot_y1 - (plot_y1 - plot_y0) * (val / max_val))
            pts.append((x, y))
        if len(pts) >= 2:
            cv2.polylines(frame, [np.array(pts, np.int32)], False, config.COL_NEON_BLUE, 3)
        for x, y in pts:
            cv2.circle(frame, (x, y), 5, config.COL_HUD_ACCENT, -1)
            cv2.circle(frame, (x, y), 5, (255, 255, 255), 1)
        for i, (date_str, _) in enumerate(series):
            if i % 2 == 0:
                label = date_str[5:]
                tx.draw_text(frame, label, (pts[i][0], cy1 - 30), size=13,
                             color_bgr=config.COL_TEXT, weight="Regular", align="center")

        self._blink(frame, "B: Back      Esc: Quit", self.h - 30, config.COL_NEON_BLUE)

    # ------------------------------------------------------------------
    # OCEAN
    # ------------------------------------------------------------------
    def _draw_ocean(self, frame, avg_angle, charge_fraction, state, chapter):
        target = np.interp(avg_angle, [config.REST_ANGLE, config.TSUNAMI_ANGLE], [0.0, 1.0])
        target = float(np.clip(target, 0.0, 1.0))
        self._tide_display = (config.TIDE_SMOOTHING_PREV * self._tide_display
                               + config.TIDE_SMOOTHING_TARGET * target)
        sea_top = int(np.interp(self._tide_display, [0.0, 1.0],
                                 [self._beach_top, self._sea_top_min]))

        if charge_fraction > 0:
            glow = frame.copy()
            cv2.circle(glow, (self.w // 2, sea_top), int(120 + charge_fraction * 180),
                       (255, 220, 120), -1)
            cv2.addWeighted(glow, 0.08 * charge_fraction, frame,
                             1 - 0.08 * charge_fraction, 0, frame)

        deep = np.array(chapter.col_deep, dtype=float)
        shallow = np.array(chapter.col_shallow, dtype=float)
        band = max(1, self.h - sea_top)
        for i in range(0, band, 4):
            t = i / band
            color = tuple(int(c) for c in (deep * (1 - t) + shallow * t))
            cv2.line(frame, (0, sea_top + i), (self.w, sea_top + i), color, 4)

        foam_th = 3 + int(4 * charge_fraction) if state in (
            TideState.CHARGING, TideState.CHARGED) else 2
        t = time.time()
        wave_points = []
        for x in range(0, self.w, 9):
            wave_height = 8 + charge_fraction * 12
            distance = abs(x - self.w // 2)
            swell_strength = max(0, 1 - distance / 180)
            swell = charge_fraction * 120 * swell_strength
            wave_y = int(sea_top - swell
                         + wave_height * math.sin((x * 0.02) + t * 2)
                         + 4 * math.sin((x * 0.04) + t * 3))
            wave_points.append([x, wave_y])
        cv2.polylines(frame, [np.array(wave_points, np.int32)], False, config.COL_FOAM, foam_th)

        secondary = []
        for x in range(0, self.w, 8):
            distance = abs(x - self.w // 2)
            swell_strength = max(0, 1 - distance / 250)
            wave_y = int(sea_top + 10 - charge_fraction * 35 * swell_strength
                         + 5 * math.sin((x * 0.03) + t * 1.5))
            secondary.append([x, wave_y])
        cv2.polylines(frame, [np.array(secondary, np.int32)], False, (220, 220, 220), 1)

    # ------------------------------------------------------------------
    # BEACH
    # ------------------------------------------------------------------
    def _draw_beach(self, frame, session, chapter):
        cv2.rectangle(frame, (0, self._beach_top), (self.w, self.h), chapter.col_sand, -1)
        cv2.line(frame, (0, self._beach_top), (self.w, self._beach_top),
                 config.COL_SHORE_SUNSET, 2)

        total = max(1, session.wave_target)
        cleared = session.patches_cleared
        gap = 14
        pw = (self.w - gap * (total + 1)) // total
        py = self._beach_top + 22
        ph = self.h - py - 20

        for i in range(total):
            x = gap + i * (pw + gap)
            pulse = 0.5 + 0.5 * math.sin(time.time() * 2 + i)
            dark_col = tuple(int(c * (0.7 + pulse * 0.3)) for c in config.COL_DARKNESS)

            if i < cleared:
                cv2.rectangle(frame, (x, py), (x + pw, py + ph), chapter.col_sand, -1)
                cx, cy = x + pw // 2, py + ph // 2
                radius = min(pw, ph) // 4
                self._draw_artifact_gem(frame, cx, cy, radius, i)

                name = session.artifact_by_patch.get(i)
                if name:
                    fitted = self._fit_label(name, pw - 6)
                    tx.draw_text(frame, fitted, (x + pw // 2, py + ph - 18), size=12,
                                 color_bgr=config.COL_HUD_BG, weight="Medium", align="center")
            else:
                cv2.ellipse(frame, (x + pw // 2, py + ph // 2), (pw // 2, ph // 2),
                            0, 0, 360, dark_col, -1)
                cv2.rectangle(frame, (x, py), (x + pw, py + ph), config.COL_DARKNESS_MURKY, 1)

    _GEM_PALETTE = [
        (255, 150, 50),   # sapphire blue
        (200, 80, 160),   # amethyst purple
        (120, 200, 80),   # emerald green
        (60, 60, 220),    # ruby red
        (40, 200, 255),   # gold
    ]

    def _draw_artifact_gem(self, frame, cx, cy, radius, index):
        """Glowing faceted gem icon for a discovered artifact - cycles
        through jewel tones so a cleared beach reads as a little collection
        rather than repeated identical marks."""
        color = self._GEM_PALETTE[index % len(self._GEM_PALETTE)]
        pulse = 0.5 + 0.5 * math.sin(time.time() * 2.5 + index)

        glow = frame.copy()
        cv2.circle(glow, (cx, cy), int(radius * 2.0), color, -1)
        alpha = 0.10 + 0.06 * pulse
        cv2.addWeighted(glow, alpha, frame, 1 - alpha, 0, frame)

        r = radius
        pts = np.array([
            [cx, cy - r], [cx + int(r * 0.6), cy - int(r * 0.25)],
            [cx + int(r * 0.4), cy + int(r * 0.7)],
            [cx - int(r * 0.4), cy + int(r * 0.7)],
            [cx - int(r * 0.6), cy - int(r * 0.25)],
        ], np.int32)
        cv2.fillConvexPoly(frame, pts, color)

        highlight = tuple(min(255, int(c * 1.5)) for c in color)
        hi_pts = np.array([[cx, cy - r], [cx - int(r * 0.6), cy - int(r * 0.25)],
                            [cx, cy]], np.int32)
        cv2.fillConvexPoly(frame, hi_pts, highlight)
        cv2.polylines(frame, [pts], True, (255, 255, 255), 1)

        if pulse > 0.75:
            cv2.circle(frame, (cx + r, cy - r), 2, (255, 255, 255), -1)

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------
    def _draw_hud(self, frame, avg_angle, left_angle, right_angle,
                  symmetry_pct, session, last_score, chapter):
        x0, y0, x1, y1 = 10, 10, 320, 296
        self._glass_panel(frame, (x0, y0), (x1, y1))

        def txt(s, y, color=config.COL_TEXT, size=15, weight="Regular"):
            tx.draw_text(frame, s, (22, y), size=size, color_bgr=color, weight=weight)

        txt(chapter.name.upper(), 18, config.COL_NEON_BLUE, 24, "Bold")
        txt(f"ROM (avg): {int(avg_angle)}", 54)
        txt(f"L: {int(left_angle)}   R: {int(right_angle)}", 76)
        txt(f"SYMMETRY: {int(symmetry_pct)}%", 98, self._quality_color(symmetry_pct / 100))
        txt(f"WAVES: {session.waves_done} / {session.wave_target}", 124, config.COL_HUD_ACCENT)
        txt(f"BEST: {session.best_score}", 146, config.COL_HUD_ACCENT)
        txt(f"ARTIFACTS: {len(session.artifact_by_patch)}", 168, config.COL_HUD_ACCENT)
        if last_score is not None:
            txt(f"LAST: {last_score.total}  {last_score.grade}", 190, last_score.color)

        bx0, bx1, by = 22, x1 - 12, 268
        self._rounded_rect(frame, (bx0, by), (bx1, by + 12), (60, 60, 60), radius=6)
        fill = int((bx1 - bx0) * session.progress_fraction)
        if fill > 4:
            self._rounded_rect(frame, (bx0, by), (bx0 + fill, by + 12), config.COL_SEA_GREEN, radius=6)

    # ------------------------------------------------------------------
    # TIMER (soft countdown - never forces anything, just informs)
    # ------------------------------------------------------------------
    def _draw_timer(self, frame, session):
        remaining = session.remaining()
        overtime = session.is_overtime()
        box_w, box_h = 190, 56
        x0, y0 = self.w - box_w - 10, 10
        x1, y1 = x0 + box_w, y0 + box_h
        edge_color = config.COL_SHORE_SUNSET if overtime else config.COL_NEON_BLUE
        self._glass_panel(frame, (x0, y0), (x1, y1), radius=12, border_color=edge_color)

        if overtime:
            over_by = -remaining
            mins, secs = divmod(int(over_by), 60)
            label = "TIME (OVER)"
            value = f"+{mins}:{secs:02d}"
            value_color = config.COL_SHORE_SUNSET
        else:
            mins, secs = divmod(max(0, int(remaining)), 60)
            label = "TIME LEFT"
            value = f"{mins}:{secs:02d}"
            value_color = config.COL_FOAM

        tx.draw_text(frame, label, (x0 + 14, y0 + 8), size=13,
                     color_bgr=config.COL_TEXT, weight="Regular")
        tx.draw_text(frame, value, (x0 + 14, y0 + 26), size=22,
                     color_bgr=value_color, weight="Bold")

    # ------------------------------------------------------------------
    # PROMPT
    # ------------------------------------------------------------------
    def _draw_prompt(self, frame, state, last_score):
        if state == TideState.WAVE_SCORED and last_score is not None:
            msg = _GRADE_MESSAGES.get(last_score.grade, "")
            color = last_score.color
        else:
            msg, color = _PROMPTS.get(state, ("", config.COL_TEXT))
        if not msg:
            return
        y = self._sea_top_min - 55
        tx.draw_text(frame, msg, (self.w // 2, y), size=40, color_bgr=color,
                     weight="Black", align="center", stroke_width=3,
                     stroke_color_bgr=(20, 20, 20))

    # ------------------------------------------------------------------
    # PLAYER VFX (magic circles + tide orb on wrists)
    # ------------------------------------------------------------------
    def _draw_player_vfx(self, frame, left_wrist, right_wrist, charge_fraction):
        magic_radius = 30 + int(charge_fraction * 25)
        if left_wrist is not None:
            draw_magic_circle(frame, left_wrist, radius=magic_radius)
        if right_wrist is not None:
            draw_magic_circle(frame, right_wrist, radius=magic_radius)
        if left_wrist is not None and right_wrist is not None:
            draw_tide_orb(frame, left_wrist, right_wrist, charge_fraction)
            draw_energy_link(frame, left_wrist, right_wrist)

        if left_wrist is not None and right_wrist is not None and charge_fraction > 0.15:
            orb_x = (left_wrist[0] + right_wrist[0]) // 2
            orb_y = (left_wrist[1] + right_wrist[1]) // 2
            sea_target = (self.w // 2, self._sea_top_min + 50)
            overlay = frame.copy()
            cv2.line(overlay, (orb_x, orb_y), sea_target, (255, 220, 180),
                     max(4, int(charge_fraction * 12)))
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

    # ------------------------------------------------------------------
    # TRANSIENT FX (crash flash / shore burst / foam wave)
    # ------------------------------------------------------------------
    def _draw_crash_flash(self, frame):
        if self._crash_flash <= 0:
            return
        overlay = frame.copy()
        alpha = 0.20 * self._crash_flash
        cv2.rectangle(overlay, (0, 0), (self.w, self.h), (255, 255, 255), -1)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        self._crash_flash *= 0.88

    def _draw_shore_burst(self, frame):
        if self._shore_burst <= 0:
            return
        burst_radius = int(40 + (1.0 - self._shore_burst) * 250)
        overlay = frame.copy()
        cv2.circle(overlay, (self.w // 2, self._beach_top), burst_radius, (255, 255, 255), -1)
        cv2.addWeighted(overlay, 0.15 * self._shore_burst, frame,
                         1 - 0.15 * self._shore_burst, 0, frame)
        self._shore_burst *= 0.90

    def _draw_foam_wave(self, frame):
        if self._foam_wave <= 0:
            return
        progress = 1.0 - self._foam_wave
        y = int(self._sea_top_min + progress * (self._beach_top - self._sea_top_min))
        for x in range(0, self.w, 30):
            offset = int(10 * math.sin((x * 0.03) + time.time() * 4))
            cv2.circle(frame, (x, y + offset), 6, (255, 255, 255), -1)
        self._foam_wave *= 0.93

    # ------------------------------------------------------------------
    # SMALL DRAW HELPERS
    # ------------------------------------------------------------------
    def _draw_wave_flourish(self, frame, cx, cy, flip=False):
        """Small decorative ripple-ring flourish flanking the title badge -
        mirrors Black Hole Surgeon's flanking singularity icons, themed as
        concentric tide ripples instead."""
        color = config.COL_HUD_ACCENT if flip else config.COL_NEON_BLUE
        for r, alpha in ((30, 0.10), (22, 0.16), (14, 0.24)):
            overlay = frame.copy()
            cv2.circle(overlay, (cx, cy), r, color, 3)
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        cv2.circle(frame, (cx, cy), 14, color, 2)
        cv2.circle(frame, (cx, cy), 4, color, -1)

    def _quality_color(self, value: float):
        """Semantic color by quality: sea green (good) / gold (okay) /
        sunset (needs work). Keeps cyan reserved for interface chrome only."""
        if value >= 0.8:
            return config.COL_SEA_GREEN
        if value >= 0.5:
            return config.COL_HUD_ACCENT
        return config.COL_SHORE_SUNSET

    def _draw_radial_gauge(self, frame, center, radius, frac, value_text, label, color):
        """Circular progress dial with a centered value and a label below -
        mirrors Black Hole Surgeon's hero-stat gauges."""
        cx, cy = center
        cv2.circle(frame, (cx, cy), radius, (55, 50, 45), 8)
        frac = max(0.0, min(1.0, frac))
        if frac > 0.003:
            cv2.ellipse(frame, (cx, cy), (radius, radius), -90, 0, int(360 * frac), color, 8)
        tx.draw_text(frame, value_text, (cx, cy - 14), size=26, color_bgr=color,
                     weight="Black", align="center")
        tx.draw_text(frame, label, (cx, cy + radius + 16), size=14,
                     color_bgr=config.COL_TEXT, weight="Medium", align="center")

    def _rounded_rect(self, frame, pt1, pt2, color, radius=14, thickness=-1):
        """Rounded rectangle - filled (thickness=-1) or outlined."""
        x0, y0 = pt1
        x1, y1 = pt2
        r = min(radius, (x1 - x0) // 2, (y1 - y0) // 2)
        if thickness < 0:
            cv2.rectangle(frame, (x0 + r, y0), (x1 - r, y1), color, -1)
            cv2.rectangle(frame, (x0, y0 + r), (x1, y1 - r), color, -1)
            for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r),
                           (x0 + r, y1 - r), (x1 - r, y1 - r)):
                cv2.circle(frame, (cx, cy), r, color, -1)
        else:
            cv2.ellipse(frame, (x0 + r, y0 + r), (r, r), 180, 0, 90, color, thickness)
            cv2.ellipse(frame, (x1 - r, y0 + r), (r, r), 270, 0, 90, color, thickness)
            cv2.ellipse(frame, (x0 + r, y1 - r), (r, r), 90, 0, 90, color, thickness)
            cv2.ellipse(frame, (x1 - r, y1 - r), (r, r), 0, 0, 90, color, thickness)
            cv2.line(frame, (x0 + r, y0), (x1 - r, y0), color, thickness)
            cv2.line(frame, (x0 + r, y1), (x1 - r, y1), color, thickness)
            cv2.line(frame, (x0, y0 + r), (x0, y1 - r), color, thickness)
            cv2.line(frame, (x1, y0 + r), (x1, y1 - r), color, thickness)

    def _glass_panel(self, frame, pt1, pt2, radius=14, fill_alpha=0.72,
                      fill_color=None, border_color=None, glow=True):
        """Translucent rounded panel with a true neon-tube border: a thin
        bright core line surrounded by a soft multi-layer bloom that fades
        outward, instead of one flat thick stroke. border_color defaults to
        neon blue (the interface-chrome semantic color)."""
        fill_color = fill_color or config.COL_PANEL_FILL
        border_color = border_color or config.COL_NEON_BLUE
        overlay = frame.copy()
        self._rounded_rect(overlay, pt1, pt2, fill_color, radius, -1)
        cv2.addWeighted(overlay, fill_alpha, frame, 1 - fill_alpha, 0, frame)

        if glow:
            for width, alpha in ((11, 0.05), (7, 0.09), (4, 0.15)):
                glow_layer = frame.copy()
                self._rounded_rect(glow_layer, pt1, pt2, border_color, radius, width)
                cv2.addWeighted(glow_layer, alpha, frame, 1 - alpha, 0, frame)

        self._rounded_rect(frame, pt1, pt2, border_color, radius, 2)

    def _fill_gradient(self, frame, top_color, bottom_color, mix: float = 1.0):
        top = np.array(top_color, dtype=float)
        bottom = np.array(bottom_color, dtype=float)
        for y in range(0, self.h, 4):
            t = (y / self.h) * mix
            color = tuple(int(c) for c in (top * (1 - t) + bottom * t))
            cv2.line(frame, (0, y), (self.w, y), color, 4)

    def _draw_screen_bg(self, frame, bg_image, fallback_top, fallback_bottom,
                         dim=0.30, video_cap=None):
        """Video (looping) > static photo > flat gradient, in that priority
        order, each one a defensive fallback for the last - a missing video
        or image asset never crashes the game or leaves a screen blank."""
        chosen = self._next_video_frame(video_cap) if video_cap is not None else None
        if chosen is None:
            chosen = bg_image
        if chosen is not None:
            frame[:] = chosen
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (self.w, self.h), (0, 0, 0), -1)
            cv2.addWeighted(overlay, dim, frame, 1 - dim, 0, frame)
        else:
            self._fill_gradient(frame, fallback_top, fallback_bottom)

    def _fit_label(self, text: str, max_width: int, size: int = 12) -> str:
        """Truncate text with an ellipsis so it fits max_width pixels."""
        w, _ = tx.measure_text(text, size=size, weight="Medium")
        if w <= max_width:
            return text
        for cut in range(len(text) - 1, 0, -1):
            candidate = text[:cut].rstrip() + "..."
            cw, _ = tx.measure_text(candidate, size=size, weight="Medium")
            if cw <= max_width:
                return candidate
        return text[:1] + "..."

    def _blink(self, frame, text_str, y, color):
        if int(time.time() * 2) % 2 != 0:
            return
        tx.draw_text(frame, text_str, (self.w // 2, y), size=20, color_bgr=color,
                     weight="Medium", align="center")
