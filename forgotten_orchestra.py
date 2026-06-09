"""
RehabVerse — The Forgotten Orchestra
=====================================
Arm abduction tracked via MediaPipe Pose.
Audio synthesized in real-time using pygame + numpy.

Install:
    pip install opencv-python mediapipe numpy pygame

If mediapipe install fails on Python 3.11:
    pip install mediapipe==0.10.9

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

# ── MediaPipe imported ONCE here, used only inside functions ──
import mediapipe as mp

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
W, H        = 1280, 720
SAMPLE_RATE = 44100
CHUNK       = 1024

# ──────────────────────────────────────────────
# AUDIO ENGINE
# ──────────────────────────────────────────────
pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, CHUNK)  # 2 channels = stereo
pygame.init()

# Note frequencies (Hz)
C3, G3 = 130.81, 196.00
C4, D4, E4, G4, A4, B4 = 261.63, 293.66, 329.63, 392.00, 440.00, 493.88
C5, D5, E5, G5, A5     = 523.25, 587.33, 659.25, 784.00, 880.00

INSTRUMENT_CHORDS = [
    # Triangle  – sparkly high singles
    [[C5], [E5], [G5], [A5]],
    # Flute     – high intervals
    [[C5, E5], [D5, G5], [E5, A5], [G5, C5]],
    # Violin    – mid three-note
    [[C4, E4, G4], [D4, G4, A4], [E4, G4, C5], [A4, C5, E5]],
    # Cello     – low sustained
    [[C3, G3, C4], [G3, C4, E4], [C3, E4, G4], [G3, D4, G4]],
    # Choir     – warm full
    [[C4, E4, G4, C5], [D4, G4, A4, D5], [E4, G4, C5, E5], [A4, C5, E5, A5]],
    # Orchestra – grand
    [[C3, C4, E4, G4, C5, E5], [G3, D4, G4, B4, D5, G5],
     [C3, E4, G4, C5, E5, G5], [C3, G3, C4, E4, G4, C5]],
]

INSTRUMENT_INTERVAL = [0.60, 0.55, 0.70, 0.90, 0.75, 1.10]  # seconds between notes
NOTE_DURATION       = 0.85


def make_chord_wave(freqs, duration=NOTE_DURATION, amp=0.20):
    n    = int(SAMPLE_RATE * duration)
    t    = np.linspace(0, duration, n, endpoint=False)
    wave = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
    env  = np.ones(n)
    att  = min(int(SAMPLE_RATE * 0.05), n // 4)
    rel  = min(int(SAMPLE_RATE * 0.10), n // 4)
    env[:att]  = np.linspace(0, 1, att)
    env[-rel:] = np.linspace(1, 0, rel)
    mono = (wave * env * amp * 32767).astype(np.int16)
    return np.column_stack([mono, mono])  # stereo: shape (n, 2)


class InstrumentPlayer:
    def __init__(self, idx):
        self.idx         = idx
        self.interval    = INSTRUMENT_INTERVAL[idx]
        self.chord_idx   = 0
        self.active      = False
        self.volume      = 0.0
        self.last_played = 0.0
        self._channel    = pygame.mixer.Channel(idx)
        self._sounds     = [
            pygame.sndarray.make_sound(make_chord_wave(freqs))
            for freqs in INSTRUMENT_CHORDS[idx]
        ]

    def update(self, active: bool, volume: float, t: float):
        self.active = active
        self.volume = max(0.0, min(1.0, volume))
        self._channel.set_volume(self.volume)
        if not active:
            self._channel.fadeout(300)
            return
        if t - self.last_played >= self.interval:
            self._channel.play(self._sounds[self.chord_idx % len(self._sounds)])
            self.chord_idx  = (self.chord_idx + 1) % len(self._sounds)
            self.last_played = t

    def stop(self):
        self._channel.stop()


class AudioEngine:
    def __init__(self):
        pygame.mixer.set_num_channels(max(8, len(INSTRUMENT_CHORDS)))
        self.players = [InstrumentPlayer(i) for i in range(len(INSTRUMENT_CHORDS))]

    def update(self, unlocked: list, volumes: list, t: float):
        for i, player in enumerate(self.players):
            player.update(unlocked[i], volumes[i], t)

    def stop(self):
        pygame.mixer.stop()


# ──────────────────────────────────────────────
# INSTRUMENT VISUAL DEFINITIONS
# ──────────────────────────────────────────────
INSTRUMENTS = [
    {"name": "Triangle",  "unlock": 20,  "color": (200, 220, 255), "bar_col": (180, 200, 255)},
    {"name": "Flute",     "unlock": 40,  "color": (180, 255, 200), "bar_col": (140, 220, 160)},
    {"name": "Violin",    "unlock": 65,  "color": (255, 200, 160), "bar_col": (220, 160, 100)},
    {"name": "Cello",     "unlock": 90,  "color": (255, 160, 180), "bar_col": (200, 100, 120)},
    {"name": "Choir",     "unlock": 120, "color": (220, 160, 255), "bar_col": (180, 100, 220)},
    {"name": "Orchestra", "unlock": 150, "color": (255, 220, 100), "bar_col": (220, 180,  60)},
]


class SoundBar:
    def __init__(self, x, color):
        self.x         = x
        self.color     = color
        self.h_min     = 4
        self.h_max     = int(40 + 60 * (0.4 + 0.6 * abs(math.sin(x * 0.8))))
        self.current_h = float(self.h_min)
        self.phase     = random.uniform(0, 2 * math.pi)
        self.speed     = random.uniform(2.0, 5.0)
        self.width     = 8

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
                          (min(255, b+40), min(255, g+40), min(255, r+40)), 1)


class InstrumentSection:
    def __init__(self, cx, cy, instrument, n_bars=12):
        self.cx, self.cy = cx, cy
        self.instrument  = instrument
        self.unlocked    = False
        self.unlock_anim = 0.0
        self.unlock_time = None
        r, g, b = instrument["color"]
        spacing = 14
        start_x = cx - (n_bars * spacing) // 2
        self.bars = [SoundBar(start_x + i * spacing, (r, g, b)) for i in range(n_bars)]
        self.volume = self.target_volume = 0.0
        self.particles = []

    def try_unlock(self, t):
        if not self.unlocked:
            self.unlocked    = True
            self.unlock_time = t
            for _ in range(20):
                a = random.uniform(0, 2 * math.pi)
                s = random.uniform(2, 6)
                self.particles.append({
                    "x": self.cx, "y": self.cy,
                    "vx": math.cos(a) * s, "vy": math.sin(a) * s,
                    "life": 1.0, "size": random.uniform(2, 5),
                })

    def update(self, t, global_angle):
        threshold = self.instrument["unlock"]
        if global_angle >= threshold:
            self.try_unlock(t)
        self.target_volume = min(1.0, (global_angle - threshold + 20) / 50.0) if self.unlocked else 0.0
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
            cv2.putText(frame, f"? {self.instrument['name']}",
                        (self.cx - 45, self.cy - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (70, 70, 80), 1)
            cv2.putText(frame, f">{int(self.instrument['unlock'])} deg",
                        (self.cx - 20, self.cy - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (70, 70, 80), 1)
        else:
            r, g, b = self.instrument["color"]
            a   = min(1.0, self.unlock_anim * 2)
            col = (int(b * a), int(g * a), int(r * a))
            cv2.putText(frame, self.instrument["name"],
                        (self.cx - 30, self.cy - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
            vol_w = int(60 * self.volume)
            cv2.rectangle(frame, (self.cx-30, self.cy-25), (self.cx+30, self.cy-18), (40,40,50), -1)
            r2, g2, b2 = self.instrument["bar_col"]
            cv2.rectangle(frame, (self.cx-30, self.cy-25),
                          (self.cx-30+vol_w, self.cy-18), (b2, g2, r2), -1)
        for bar in self.bars:
            bar.draw(frame, base_y, self.unlocked)
        for p in self.particles:
            r, g, b = self.instrument["color"]
            al   = p["life"]
            size = max(1, int(p["size"] * al))
            px, py = int(p["x"]), int(p["y"])
            if 0 <= px < W and 0 <= py < H:
                cv2.circle(frame, (px, py), size, (int(b*al), int(g*al), int(r*al)), -1)
        if self.unlocked and self.unlock_anim < 1.0:
            r, g, b = self.instrument["color"]
            al = 1.0 - self.unlock_anim
            cv2.circle(frame, (self.cx, self.cy), int(50 * self.unlock_anim),
                       (int(b*al), int(g*al), int(r*al)), 2)


class OrchestraStage:
    def __init__(self):
        positions = [
            (W//2 - 420, H//2 - 20), (W//2 - 240, H//2 - 60),
            (W//2 -  60, H//2 - 80), (W//2 + 120, H//2 - 60),
            (W//2 + 280, H//2 - 20), (W//2 + 420, H//2 + 10),
        ]
        self.sections       = [InstrumentSection(cx, cy, INSTRUMENTS[i])
                                for i, (cx, cy) in enumerate(positions)]
        self.total_unlocked = 0
        self.music_progress = 0.0
        self.reps           = 0
        self.was_raised     = False
        self.hold_start     = None
        self.hold_time      = 0.0

    def update(self, angle, t):
        self.total_unlocked = sum(s.unlocked for s in self.sections)
        self.music_progress = min(100.0, self.music_progress + (angle / 160.0) * 0.05)
        for s in self.sections:
            s.update(t, angle)
        if angle > 60:
            if not self.was_raised:
                self.was_raised = True
                self.hold_start = t
            self.hold_time = t - self.hold_start
        else:
            if self.was_raised:
                self.reps += 1
            self.was_raised = False
            self.hold_start = None
            self.hold_time  = 0.0

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
# POSE HELPERS  (mp_pose used only here)
# ──────────────────────────────────────────────
def calc_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    angle   = abs(math.degrees(
        math.atan2(c[1]-b[1], c[0]-b[0]) - math.atan2(a[1]-b[1], a[0]-b[0])))
    return 360 - angle if angle > 180 else angle


def get_abduction_angle(landmarks):
    """Use LEFT arm: hip -> shoulder -> elbow angle."""
    lm = landmarks
    Pose = mp.solutions.pose.PoseLandmark
    hip      = [lm[Pose.LEFT_HIP.value].x,      lm[Pose.LEFT_HIP.value].y]
    shoulder = [lm[Pose.LEFT_SHOULDER.value].x,  lm[Pose.LEFT_SHOULDER.value].y]
    elbow    = [lm[Pose.LEFT_ELBOW.value].x,     lm[Pose.LEFT_ELBOW.value].y]
    return calc_angle(hip, shoulder, elbow)


def draw_conductor_arc(frame, angle, cx, cy):
    sweep = min(angle, 160)
    color = (100, 200, 255) if angle > 90 else (100, 150, 200)
    cv2.ellipse(frame, (cx, cy), (70, 70), -90, -sweep/2, sweep/2, (60, 60, 70), 1)
    cv2.ellipse(frame, (cx, cy), (70, 70), -90, -sweep/2, sweep/2, color, 2)
    rad = math.radians(-90 + sweep / 2)
    cv2.circle(frame, (int(cx + 70*math.cos(rad)), int(cy + 70*math.sin(rad))), 5, color, -1)


def draw_hud(frame, angle, stage, t):
    panel = frame.copy()
    cv2.rectangle(panel, (10, 10), (320, 215), (10, 8, 18), -1)
    cv2.addWeighted(panel, 0.78, frame, 0.22, 0, frame)
    cv2.rectangle(frame, (10, 10), (320, 215), (60, 55, 80), 1)

    cv2.putText(frame, "THE FORGOTTEN ORCHESTRA",
                (20, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 160, 255), 1)

    # Abduction bar
    cv2.putText(frame, f"Abduction: {int(angle)} deg",
                (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 170, 200), 1)
    cv2.rectangle(frame, (20, 55), (220, 65), (35, 30, 50), -1)
    fill = int(200 * min(angle, 160) / 160)
    cv2.rectangle(frame, (20, 55), (20+fill, 65),
                  (60, 220, 120) if angle > 90 else (80, 130, 255), -1)

    # Music progress
    cv2.putText(frame, f"Music restored: {int(stage.music_progress)}%",
                (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 170, 200), 1)
    cv2.rectangle(frame, (20, 85), (220, 95), (35, 30, 50), -1)
    cv2.rectangle(frame, (20, 85), (20 + int(200 * stage.music_progress/100), 95), (180, 100, 220), -1)

    cv2.putText(frame, f"Instruments: {stage.total_unlocked}/6",
                (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 150, 180), 1)
    cv2.putText(frame, f"Reps: {stage.reps}   Hold: {stage.hold_time:.1f}s",
                (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 150, 180), 1)

    # Instrument dots
    cv2.putText(frame, "Awakened:",
                (20, 163), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 110, 140), 1)
    for i, (inst, sec) in enumerate(zip(INSTRUMENTS, stage.sections)):
        col = (int(inst["color"][2]*0.7), int(inst["color"][1]*0.7),
               int(inst["color"][0]*0.7)) if sec.unlocked else (40, 40, 50)
        cv2.circle(frame, (90 + i*22, 160), 6, col, -1)

    n = stage.total_unlocked
    cv2.putText(frame, f"Audio: {n} instrument{'s' if n!=1 else ''} playing",
                (20, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                (80, 200, 120) if n > 0 else (100, 100, 120), 1)

    # Bottom message
    msgs = [
        (30,  "Raise your arms to begin!",        (100, 100, 120)),
        (60,  "Raise higher — conduct!",           (100, 160, 255)),
        (100, "The orchestra stirs...",             (140, 200, 140)),
        (130, "Beautiful! Keep going",              (180, 220, 100)),
        (999, "The kingdom fills with music!",      (200, 150, 255)),
    ]
    for threshold, msg, col in msgs:
        if angle < threshold:
            cv2.putText(frame, msg, (W//2 - 190, H-30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, 2)
            break


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    print("RehabVerse — The Forgotten Orchestra")
    print("Raise your LEFT arm to unlock instruments and hear them play.")
    print("Press Q to quit.\n")

    # MediaPipe objects created INSIDE main to avoid module-level init errors
    mp_pose    = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)

    stage          = OrchestraStage()
    audio_engine   = AudioEngine()
    smoothed_angle = 0.0

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
                lm            = results.pose_landmarks.landmark
                raw           = get_abduction_angle(lm)
                smoothed_angle = 0.82 * smoothed_angle + 0.18 * raw
                angle         = smoothed_angle

                ls = lm[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
                draw_conductor_arc(frame, angle, int(ls.x * W), int(ls.y * H))
                mp_drawing.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(80,70,100), thickness=1, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(70,60,90),  thickness=1))

            # Cinematic dark overlay
            dark = np.zeros_like(frame, dtype=np.uint8)
            dark[:] = (15, 10, 25)
            cv2.addWeighted(dark, 0.45, frame, 0.55, 0, frame)

            stage.update(angle, t)
            stage.draw(frame, t)

            unlocked, volumes = stage.audio_state()
            audio_engine.update(unlocked, volumes, t)

            draw_hud(frame, angle, stage, t)
            cv2.putText(frame, "Q to quit", (W-120, H-15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (70,65,85), 1)
            cv2.imshow("RehabVerse — The Forgotten Orchestra", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    audio_engine.stop()
    cap.release()
    cv2.destroyAllWindows()
    pygame.quit()

    print(f"\nSession complete!")
    print(f"  Reps:               {stage.reps}")
    print(f"  Instruments awoken: {stage.total_unlocked}/6")
    print(f"  Music restored:     {int(stage.music_progress)}%")


if __name__ == "__main__":
    main()