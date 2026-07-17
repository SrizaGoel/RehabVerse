"""RehabVerse — Leg Raise (SLR) entry point.

Straight-leg-raise rehab game with a "rocket launch" visual metaphor.

Controls:
    p    pause
    r    resume
    Esc  quit and save session

Params (matches the payload sent by ExerciseModal's launchGame()):
    user_id        - Supabase user id
    recovery_id    - Supabase recovery/plan id
    side           - "L" or "R" (which leg to track). Defaults to "L".
    session_type   - "morning" | "evening" (informational, echoed back)
    current_week   - int, informational, echoed back

Progress persistence:
    Session history / day_number / streak are stored in a per-user JSON
    file (rehab_progress_{uid}_{rid}.json, next to this script), and
    day_number/streak only advance once per elapsed calendar date - the
    same "advance once per day, not once per session" pattern used by
    forgotten_orchestra.py's advance_day_if_needed(). Playing twice in one
    day logs two sessions in history but doesn't double-advance the day
    count.

Returns:
    A JSON-serializable session_result dict on normal completion, matching
    the shape the other games return, so the Flask layer / onComplete()
    can hand it to Supabase.
"""
import cv2
import mediapipe as mp
import numpy as np
import random
import time
import json
import os
import re
from datetime import date, datetime
import pygame

pygame.mixer.init()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
SOUNDS_DIR = os.path.join(PROJECT_ROOT, "sounds")

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)


def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    ba = a - b
    bc = c - b
    cosine = np.dot(ba, bc) / (
        np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8
    )
    cosine = np.clip(cosine, -1.0, 1.0)
    angle = np.degrees(np.arccos(cosine))
    return int(angle)


# --- sounds (loaded once at import time, shared across sessions) ---
pygame.mixer.music.load(os.path.join(SOUNDS_DIR, "main_universal.mp3"))
pygame.mixer.music.set_volume(0.12)
pygame.mixer.music.play(-1)

success_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "success.mp3"))
ignition_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "ignition.ogg"))
liftoff_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "lift off.ogg"))
atmosphere_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "atmospherereached.ogg"))
orbit_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "orbitachieved.ogg"))
mission_complete_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "missioncomplete.ogg"))
rocket_launch_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "rocket_lauch.mp3"))
pause_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "missionpaused.ogg"))
resume_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "missionresumed.ogg"))


def _progress_path(user_id, recovery_id):
    if user_id and recovery_id:
        uid = re.sub(r'[^a-zA-Z0-9_-]', '', str(user_id))
        rid = re.sub(r'[^a-zA-Z0-9_-]', '', str(recovery_id))
        return os.path.join(BASE_DIR, f"rehab_progress_{uid}_{rid}.json")
    return os.path.join(BASE_DIR, "rehab_progress_leg_raise.json")


def _load_progress(path):
    if os.path.exists(path):
        with open(path) as f:
            p = json.load(f)
        p.setdefault("day_number", 1)
        p.setdefault("streak", 0)
        p.setdefault("last_active_date", None)
        p.setdefault("history", [])
        return p
    return {"day_number": 1, "streak": 0, "last_active_date": None, "history": []}


def _save_progress(path, progress):
    with open(path, "w") as f:
        json.dump(progress, f, indent=2)


def _record_session(progress, session_record):
    """Log this session, and advance day_number/streak at most once per
    calendar day - mirrors forgotten_orchestra.py's advance_day_if_needed()."""
    today = str(date.today())
    hist = progress.get("history", [])
    hist.append(session_record)
    progress["history"] = hist[-100:]

    if progress.get("last_active_date") != today:
        progress["day_number"] = progress.get("day_number", 1) + 1
        progress["streak"] = progress.get("streak", 0) + 1
        progress["last_active_date"] = today
    # else: same calendar day as last session - it's logged above, but
    # day_number/streak don't move again until a new date is seen.

    return progress


def main(params=None):
    params = params or {}
    user_id = params.get("user_id")
    recovery_id = params.get("recovery_id")
    side = params.get("side", "L")
    session_type = params.get("session_type", "morning")
    current_week = params.get("current_week", 1)

    progress_path = _progress_path(user_id, recovery_id)
    progress = _load_progress(progress_path)

    hip_lm = mp_pose.PoseLandmark.RIGHT_HIP if side == "R" else mp_pose.PoseLandmark.LEFT_HIP
    shoulder_lm = mp_pose.PoseLandmark.RIGHT_SHOULDER if side == "R" else mp_pose.PoseLandmark.LEFT_SHOULDER
    knee_lm = mp_pose.PoseLandmark.RIGHT_KNEE if side == "R" else mp_pose.PoseLandmark.LEFT_KNEE

    # ------------------------
    # Rep Counter / session state
    # ------------------------
    reps = 0
    stage = "DOWN"
    max_rom = 0
    rom_history = []
    progress_pct = 0
    display_progress = 0
    display_rocket_y = 550
    current_mission = ""
    mission_alert_timer = 0
    is_paused = False
    pause_start_time = 0
    total_pause_time = 0
    session_started = False
    hold_progress = 0
    hold_start_time = None
    hold_seconds = 0
    hold_complete = False
    max_hold = 0
    flame_phase = 0
    hold_banner_timer = 0
    session_start_time = time.time()
    elapsed_seconds = 0
    rom = 0

    # ------------------------
    # Camera
    # ------------------------
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return None

    cv2.namedWindow("RehabVerse SLR Engine", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("RehabVerse SLR Engine", 1280, 720)

    stars = []
    for i in range(40):
        stars.append([
            random.randint(350, 1250),
            random.randint(20, 400),
            random.randint(1, 3)
        ])

    particles = []
    rgb = None

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        if not session_started:
            session_start_time = time.time()
            session_started = True

        frame = cv2.resize(frame, (1280, 720))
        frame = cv2.flip(frame, 1)

        # =====================
        # TWINKLING STARS
        # =====================
        if not is_paused:
            for star in stars:
                brightness = random.randint(180, 255)
                cv2.circle(frame, (star[0], star[1]), star[2], (brightness, brightness, brightness), -1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if is_paused:
            progress_pct = display_progress

        results = pose.process(rgb) if rgb is not None else None

        if results and results.pose_landmarks and not is_paused:
            landmarks = results.pose_landmarks.landmark

            shoulder = landmarks[shoulder_lm.value]
            hip = landmarks[hip_lm.value]
            knee = landmarks[knee_lm.value]

            shoulder_xy = [shoulder.x, shoulder.y]
            hip_xy = [hip.x, hip.y]
            knee_xy = [knee.x, knee.y]

            rom = calculate_angle(shoulder_xy, hip_xy, knee_xy)

            rom_history.append(rom)
            if len(rom_history) > 10:
                rom_history.pop(0)

            rom = int(sum(rom_history) / len(rom_history))
            if rom < 145:
                if hold_start_time is None:
                    hold_start_time = time.time()
                hold_seconds = int(time.time() - hold_start_time)
                max_hold = max(max_hold, hold_seconds)
            else:
                hold_start_time = None
                hold_seconds = 0
                hold_complete = False

            if hold_seconds >= 3 and not hold_complete:
                hold_complete = True
                hold_banner_timer = 60
                success_sound.play()

            hold_progress = int(np.interp(hold_seconds, [0, 5], [0, 100]))
            max_rom = max(max_rom, rom)

            # ------------------------
            # Rep Counting
            # ------------------------
            if rom > 160:
                stage = "DOWN"
            if rom < 145 and stage == "DOWN":
                stage = "UP"
                reps += 1

            mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        if not is_paused:
            progress_pct = int(np.interp(rom, [100, 180], [100, 0]))
        display_progress = int(0.9 * display_progress + 0.1 * progress_pct)

        # Elapsed Time
        if is_paused:
            elapsed_seconds = int(pause_start_time - session_start_time - total_pause_time)
        else:
            elapsed_seconds = int(time.time() - session_start_time - total_pause_time)

        minutes = elapsed_seconds // 60
        seconds = elapsed_seconds % 60

        # ------------------------
        # Mission Logic
        # ------------------------
        if display_progress < 20:
            mission = "LAUNCH PAD"
        elif display_progress < 40:
            mission = "IGNITION"
        elif display_progress < 60:
            mission = "LIFT OFF"
        elif display_progress < 80:
            mission = "ATMOSPHERE"
        else:
            mission = "ORBIT"

        if mission != current_mission:
            current_mission = mission
            mission_alert_timer = 60
            if mission == "IGNITION":
                ignition_sound.play()
            elif mission == "LIFT OFF":
                liftoff_sound.play()
            elif mission == "ATMOSPHERE":
                atmosphere_sound.play()
            elif mission == "ORBIT":
                orbit_sound.play()

        # ------------------------
        # Dashboard
        # ------------------------
        cv2.rectangle(frame, (10, 10), (310, 310), (12, 12, 18), -1)
        cv2.rectangle(frame, (10, 10), (310, 310), (80, 220, 255), 2)
        cv2.putText(frame, "MISSION CONTROL", (20, 40), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 255, 255), 2)
        cv2.putText(frame, "TELEMETRY ->", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.putText(frame, f"ROM: {rom}", (20, 90), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, "PERFORMANCE ->", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.putText(frame, f"REPS: {reps}", (20, 145), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)

        stage_color = (0, 255, 0) if stage == "UP" else (0, 0, 255)
        cv2.putText(frame, f"STAGE: {stage}", (20, 165), cv2.FONT_HERSHEY_DUPLEX, 0.5, stage_color, 1)
        cv2.putText(frame, f"MAX ROM: {max_rom}", (20, 185), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, f"PROGRESS: {display_progress}%", (20, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, f"HOLD: {hold_seconds}s", (20, 225), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, f"BEST HOLD: {max_hold}s", (150, 225), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)

        cv2.putText(frame, "HOLD CHARGE: ", (20, 247), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 220, 120), 1)
        cv2.rectangle(frame, (150, 235), (300 - 10, 250), (60, 60, 60), -1)
        cv2.rectangle(frame, (150, 235), (150 + int(1.5 * hold_progress), 250), (255, 220, 120), -1)

        cv2.putText(frame, "MISSION STATUS ->", (20, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        cv2.putText(frame, f" {mission} ", (160, 275), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(frame, f"SESSION TIME: {minutes:02}:{seconds:02}", (20, 305), cv2.FONT_HERSHEY_DUPLEX, 0.65, (0, 255, 255), 2)

        # =========================
        # SCI-FI HEX LAUNCH PAD
        # =========================
        center_x = 1100
        center_y = 630
        radius = 65
        height3d = 30
        top = []
        for i in range(6):
            angle = np.deg2rad(60 * i - 30)
            x = int(center_x + radius * np.cos(angle))
            y = int(center_y + radius * np.sin(angle))
            top.append([x, y])
        top = np.array(top, dtype=np.int32)
        bottom = top + np.array([0, height3d])

        for i in range(6):
            j = (i + 1) % 6
            face = np.array([top[i], top[j], bottom[j], bottom[i]])
            cv2.fillPoly(frame, [face], (25, 25, 25))

        cv2.polylines(frame, [bottom], True, (255, 220, 120), 1)
        for i in [2, 3, 4]:
            cv2.line(frame, tuple(top[i]), tuple(bottom[i]), (255, 220, 120), 1)

        cv2.fillPoly(frame, [top], (55, 55, 55))
        cv2.polylines(frame, [top], True, (255, 220, 120), 2)

        inner_radius = 40
        inner = []
        for i in range(6):
            angle = np.deg2rad(60 * i - 30)
            x = int(center_x + inner_radius * np.cos(angle))
            y = int(center_y + inner_radius * np.sin(angle))
            inner.append([x, y])
        inner = np.array(inner, dtype=np.int32)
        cv2.polylines(frame, [inner], True, (120, 90, 65), 1)
        cv2.circle(frame, (center_x, center_y), 10, (0, 255, 255), -1)
        cv2.circle(frame, (center_x, center_y), 20, (0, 180, 255), 2)

        overlay = frame.copy()
        cv2.polylines(overlay, [top], True, (255, 220, 120), 6)
        cv2.addWeighted(overlay, 0.10, frame, 0.90, 0, frame)

        # ------------------------
        # Rocket Position
        # ------------------------
        target_rocket_y = np.interp(display_progress, [0, 100], [550, 100])
        display_rocket_y = (0.92 * display_rocket_y + 0.08 * target_rocket_y)
        rocket_y = int(display_rocket_y)

        cx = 1100
        cy = rocket_y + 85

        BODY = (140, 90, 45)
        SHADOW = (80, 45, 20)
        HIGHLIGHT = (200, 150, 90)
        FIN = (255, 220, 120)
        WINDOW_COLOR = (255, 240, 180)
        NOZZLE = (45, 45, 55)

        overlay = frame.copy()
        cv2.circle(overlay, (cx, cy + 15), 30, (0, 140, 255), -1)
        cv2.addWeighted(overlay, 0.12, frame, 0.88, 0, frame)

        cv2.rectangle(frame, (cx - 18, cy - 90), (cx + 18, cy), BODY, -1)
        cv2.rectangle(frame, (cx + 5, cy - 90), (cx + 18, cy), SHADOW, -1)
        cv2.rectangle(frame, (cx - 18, cy - 90), (cx - 8, cy), HIGHLIGHT, -1)

        nose = np.array([[cx, cy - 125], [cx - 18, cy - 90], [cx + 18, cy - 90]])
        cv2.fillPoly(frame, [nose], BODY)

        left_fin = np.array([[cx - 18, cy - 25], [cx - 35, cy + 10], [cx - 18, cy]])
        cv2.fillPoly(frame, [left_fin], FIN)

        right_fin = np.array([[cx + 18, cy - 25], [cx + 35, cy + 10], [cx + 18, cy]])
        cv2.fillPoly(frame, [right_fin], FIN)

        cv2.circle(frame, (cx, cy - 55), 7, WINDOW_COLOR, -1)
        cv2.circle(frame, (cx, cy - 25), 5, WINDOW_COLOR, -1)

        engine = np.array([[cx - 10, cy], [cx + 10, cy], [cx + 6, cy + 12], [cx - 6, cy + 12]])
        cv2.fillPoly(frame, [engine], NOZZLE)

        # =====================
        # ENGINE PARTICLES
        # =====================
        if not is_paused:
            particle_count = 7
            for i in range(particle_count):
                particle_color = random.choice([(255, 255, 255), (255, 220, 0), (0, 180, 255)])
                particles.append([cx + random.randint(-10, 10), cy + 20, random.randint(2, 4), particle_color])

            new_particles = []
            for particle in particles:
                x, y, size, color = particle
                y += random.randint(5, 10)
                x += random.randint(-2, 2)
                size -= 0.20
                if size > 0:
                    overlay = frame.copy()
                    cv2.circle(overlay, (int(x), int(y)), int(size * 1.8), color, -1)
                    cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
                    cv2.circle(frame, (int(x), int(y)), int(size), color, -1)
                    new_particles.append([x, y, size, color])
            particles = new_particles

        # -----------------
        # FLAME
        # -----------------
        outer_color = (0, 140, 255)
        mid_color = (0, 220, 255)
        inner_color = (255, 255, 255)

        flame_length = random.randint(45, 70)
        flame_length += int(5 * np.sin(flame_phase) * 10)
        if not is_paused:
            flame_phase += 0.2  # NOTE: previously only ran once at import time

        outer_flame = np.array([[cx, cy + flame_length], [cx - 16, cy + 10], [cx + 16, cy + 10]])
        cv2.fillPoly(frame, [outer_flame], outer_color)

        mid_flame = np.array([[cx, cy + flame_length - 15], [cx - 10, cy + 10], [cx + 10, cy + 10]])
        cv2.fillPoly(frame, [mid_flame], mid_color)

        inner_flame = np.array([[cx, cy + flame_length - 30], [cx - 5, cy + 10], [cx + 5, cy + 10]])
        cv2.fillPoly(frame, [inner_flame], inner_color)

        # Altitude Meter
        cv2.rectangle(frame, (1180, 100), (1205, 500), (225, 225, 225), 2)
        cv2.putText(frame, "ORBIT", (1215, 120), cv2.FONT_HERSHEY_DUPLEX, 0.5, (225, 225, 225), 1)
        cv2.putText(frame, "ATMOS", (1215, 220), cv2.FONT_HERSHEY_DUPLEX, 0.5, (225, 225, 225), 1)
        cv2.putText(frame, "LIFT OFF", (1215, 320), cv2.FONT_HERSHEY_DUPLEX, 0.5, (225, 225, 225), 1)
        cv2.putText(frame, "IGNITION", (1215, 420), cv2.FONT_HERSHEY_DUPLEX, 0.5, (225, 225, 225), 1)
        cv2.putText(frame, "GROUND", (1215, 520), cv2.FONT_HERSHEY_DUPLEX, 0.5, (225, 225, 225), 1)

        bar_height = int(np.interp(display_progress, [0, 100], [0, 400]))
        cv2.rectangle(frame, (1180, 500 - bar_height), (1205, 500), (0, 255, 0), -1)

        if hold_complete:
            cv2.rectangle(frame, (470, 120), (810, 180), (0, 40, 0), -1)
            cv2.rectangle(frame, (470, 120), (810, 180), (0, 255, 0), 3)
            cv2.putText(frame, "STABLE HOLD", (540, 160), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 255, 0), 2)

        if mission_alert_timer > 0:
            cv2.rectangle(frame, (520, 40), (720, 90), (0, 0, 0), -1)
            cv2.rectangle(frame, (520, 40), (720, 90), (0, 255, 255), 3)
            cv2.putText(frame, current_mission, (530, 75), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 255, 255), 2)
            mission_alert_timer -= 1

        if is_paused:
            cv2.putText(frame, "SESSION PAUSED", (480, 650), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 0, 255), 2)

        cv2.imshow("RehabVerse SLR Engine", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('p'):
            if not is_paused:
                is_paused = True
                pause_start_time = time.time()
                pause_sound.play()

        if key == ord('r'):
            if is_paused:
                resume_sound.play()
                is_paused = False
                total_pause_time += (time.time() - pause_start_time)

        if key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

    session_record = {
        "date": datetime.now().isoformat(),
        "session_type": session_type,
        "side": side,
        "reps": reps,
        "max_rom": max_rom,
        "max_hold": max_hold,
        "elapsed_seconds": elapsed_seconds,
    }
    progress = _record_session(progress, session_record)
    _save_progress(progress_path, progress)

    session_result = {
        "game": "leg_raise",
        "session": {
            "user_id": user_id,
            "recovery_id": recovery_id,
            "side": side,
            "session_type": session_type,
            "current_week": current_week,
            "day_number": progress["day_number"],
            "streak": progress["streak"],
        },
        "metrics": {
            "repetitions": reps,
            "max_rom": max_rom,
            "max_hold": max_hold,
            "elapsed_seconds": elapsed_seconds,
        },
        "timestamp": datetime.now().isoformat(),
    }
    print(f"Session saved. Reps: {reps}, Max ROM: {max_rom} deg, Best hold: {max_hold}s "
          f"(Day {progress['day_number']}, Streak {progress['streak']})")
    return session_result


if __name__ == "__main__":
    result = main()
    print("\nReturned Result:")
    print(result)