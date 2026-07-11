

import cv2
import mediapipe as mp
import numpy as np
import math
import time
import random
import json
import os
import pygame
import pygame.sndarray
from collections import deque

W, H = 1280, 720
SAMPLE_RATE = 44100
CHUNK = 1024



POSES = [
    {
        "name": "First Position",
        "description": "Arms rounded in front at chest height.",
        "targets": {
            "l_shoulder": 40.0,
            "r_shoulder": 40.0,
            "l_elbow": 125.0,
            "r_elbow": 125.0
        },
        "draw_offsets": {
            "l_elbow": (-60, 10),
            "l_wrist": (-15, 20),
            "r_elbow": (60, 10),
            "r_wrist": (15, 20)
        },
        "tip": "Form a soft circle. Fingers should almost meet at chest level."
    },
    {
        "name": "Second Position",
        "description": "Arms extended horizontally to the sides.",
        "targets": {
            "l_shoulder": 85.0,
            "r_shoulder": 85.0,
            "l_elbow": 160.0,
            "r_elbow": 160.0
        },
        "draw_offsets": {
            "l_elbow": (-75, -30),
            "l_wrist": (-110, -30),
            "r_elbow": (75, -30),
            "r_wrist": (110, -30)
        },
        "tip": "Keep arms slightly below shoulder level, elbows soft."
    },
    {
        "name": "Third Position",
        "description": "One arm overhead, the other extended laterally.",
        "targets": {
            "l_shoulder": 135.0,
            "r_shoulder": 85.0,
            "l_elbow": 130.0,
            "r_elbow": 160.0
        },
        "draw_offsets": {
            "l_elbow": (-55, -75),
            "l_wrist": (-20, -100),
            "r_elbow": (75, -30),
            "r_wrist": (110, -30)
        },
        "tip": "Reach high with left arm. Stretch right arm straight but relaxed."
    },
    {
        "name": "Belle Pose",
        "description": "Arms raised overhead, forming a curved frame.",
        "targets": {
            "l_shoulder": 135.0,
            "r_shoulder": 135.0,
            "l_elbow": 135.0,
            "r_elbow": 135.0
        },
        "draw_offsets": {
            "l_elbow": (-55, -75),
            "l_wrist": (-20, -100),
            "r_elbow": (55, -75),
            "r_wrist": (20, -100)
        },
        "tip": "Keep shoulders relaxed. Do not force overhead if painful."
    }
]

# ──────────────────────────────────────────────
# SOUND GENERATOR
# ──────────────────────────────────────────────
pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, CHUNK)
pygame.init()

def make_success_chime():
    # Sequence of notes forming a bright major arpeggio
    duration_per_note = 0.12
    freqs = [523.25, 659.25, 784.00, 1046.50]  # C5 -> E5 -> G5 -> C6
    chime_waves = []
    
    for f in freqs:
        n = int(SAMPLE_RATE * duration_per_note)
        t = np.linspace(0, duration_per_note, n, endpoint=False)
        wave = np.sin(2 * np.pi * f * t)
        
        # Apply volume envelope
        env = np.ones(n)
        att = n // 8
        rel = n // 4
        env[:att] = np.linspace(0, 1, att)
        env[-rel:] = np.linspace(1, 0, rel)
        chime_waves.append(wave * env)
        
    full_wave = np.concatenate(chime_waves)
    mono = (full_wave * 0.25 * 32767).astype(np.int16)
    return np.column_stack([mono, mono])

class SoundEngine:
    def __init__(self):
        self._channel = pygame.mixer.Channel(0)
        self._chime = pygame.sndarray.make_sound(make_success_chime())
        
    def play_success(self):
        self._channel.play(self._chime)

# ──────────────────────────────────────────────
# ANGLE & MATH HELPERS
# ──────────────────────────────────────────────
def calculate_angle(a, b, c):
    """Calculate the 2D angle at vertex b between vectors ba and bc."""
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba = a - b
    bc = c - b
    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    cosine = np.clip(cosine, -1.0, 1.0)
    angle = np.degrees(np.arccos(cosine))
    return float(angle)

def get_current_angles(landmarks):
    lm = landmarks
    Pose = mp.solutions.pose.PoseLandmark
    
    # Left Arm
    l_hip      = [lm[Pose.LEFT_HIP.value].x,      lm[Pose.LEFT_HIP.value].y]
    l_shoulder = [lm[Pose.LEFT_SHOULDER.value].x,  lm[Pose.LEFT_SHOULDER.value].y]
    l_elbow    = [lm[Pose.LEFT_ELBOW.value].x,     lm[Pose.LEFT_ELBOW.value].y]
    l_wrist    = [lm[Pose.LEFT_WRIST.value].x,     lm[Pose.LEFT_WRIST.value].y]
    
    # Right Arm
    r_hip      = [lm[Pose.RIGHT_HIP.value].x,     lm[Pose.RIGHT_HIP.value].y]
    r_shoulder = [lm[Pose.RIGHT_SHOULDER.value].x, lm[Pose.RIGHT_SHOULDER.value].y]
    r_elbow    = [lm[Pose.RIGHT_ELBOW.value].x,    lm[Pose.RIGHT_ELBOW.value].y]
    r_wrist    = [lm[Pose.RIGHT_WRIST.value].x,    lm[Pose.RIGHT_WRIST.value].y]
    
    return {
        "l_shoulder": calculate_angle(l_hip, l_shoulder, l_elbow),
        "r_shoulder": calculate_angle(r_hip, r_shoulder, r_elbow),
        "l_elbow":    calculate_angle(l_shoulder, l_elbow, l_wrist),
        "r_elbow":    calculate_angle(r_shoulder, r_elbow, r_wrist)
    }

# ──────────────────────────────────────────────
# GRAPHICAL UI HELPERS
# ──────────────────────────────────────────────
def draw_glass_panel(img, pt1, pt2, color=(16, 12, 28), border_color=(70, 55, 90), alpha=0.82):
    """Draw a styled glassmorphic overlay panel with border."""
    overlay = img.copy()
    cv2.rectangle(overlay, pt1, pt2, color, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.rectangle(img, pt1, pt2, border_color, 1)

def draw_radial_gauge(img, center, radius, value, max_value=100, label="SIM", color=(100, 220, 255)):
    """Draw a clean, circular gauge for scores."""
    cx, cy = center
    # Background ring
    cv2.circle(img, (cx, cy), radius, (35, 30, 45), 4)
    
    # Progress arc
    val_norm = np.clip(value / max_value, 0.0, 1.0)
    angle_sweep = int(val_norm * 360)
    cv2.ellipse(img, (cx, cy), (radius, radius), -90, 0, angle_sweep, color, 4)
    
    # Label inside
    cv2.putText(img, f"{int(value)}%", (cx - 18, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (240, 240, 245), 1)
    cv2.putText(img, label, (cx - 15, cy + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (140, 130, 155), 1)

def draw_target_stick_figure(img, center_x, center_y, offsets, active_pose_name):
    """Draw the skeletal target schematic for the active pose."""
    cx, cy = center_x, center_y
    head_cy = cy - 60
    neck_cy = cy - 30
    hip_cy  = cy + 60
    
    # Hip and spine
    cv2.line(img, (cx - 20, hip_cy), (cx + 20, hip_cy), (60, 50, 75), 2)
    cv2.line(img, (cx, hip_cy), (cx, neck_cy), (60, 50, 75), 2)
    
    # Shoulders
    l_sh = (cx - 35, neck_cy)
    r_sh = (cx + 35, neck_cy)
    cv2.line(img, l_sh, r_sh, (80, 65, 100), 2)
    
    # Head
    cv2.circle(img, (cx, head_cy), 14, (120, 100, 145), 2)
    
    # Target joints mapped from offsets relative to center
    l_el = (cx + offsets["l_elbow"][0], cy + offsets["l_elbow"][1])
    l_wr = (cx + offsets["l_wrist"][0], cy + offsets["l_wrist"][1])
    
    r_el = (cx + offsets["r_elbow"][0], cy + offsets["r_elbow"][1])
    r_wr = (cx + offsets["r_wrist"][0], cy + offsets["r_wrist"][1])
    
    # Draw left arm (Target)
    cv2.line(img, l_sh, l_el, (0, 200, 255), 2)
    cv2.line(img, l_el, l_wr, (0, 200, 255), 2)
    cv2.circle(img, l_el, 3, (0, 240, 255), -1)
    cv2.circle(img, l_wr, 3, (0, 240, 255), -1)
    
    # Draw right arm (Target)
    cv2.line(img, r_sh, r_el, (0, 200, 255), 2)
    cv2.line(img, r_el, r_wr, (0, 200, 255), 2)
    cv2.circle(img, r_el, 3, (0, 240, 255), -1)
    cv2.circle(img, r_wr, 3, (0, 240, 255), -1)
    
    cv2.putText(img, "Target Schematic", (cx - 50, cy - 80), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (140, 130, 155), 1)

# ──────────────────────────────────────────────
# MAIN EXECUTION LOOP
# ──────────────────────────────────────────────
def main(params=None):
    print("RehabVerse — Belle Pose Starting...")
    
    import copy
    POSES_local = copy.deepcopy(POSES)
    side = params.get("side", "L") if params else "L"
    if side == "R":
        for pose in POSES_local:
            if pose["name"] == "Third Position":
                targets = pose["targets"]
                targets["l_shoulder"], targets["r_shoulder"] = targets.get("r_shoulder", 85.0), targets.get("l_shoulder", 135.0)
                targets["l_elbow"], targets["r_elbow"] = targets.get("r_elbow", 160.0), targets.get("l_elbow", 130.0)
                pose["targets"] = targets
    POSES = POSES_local

    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    
    sound_engine = SoundEngine()
    
    # State tracking
    current_pose_idx = 0
    hold_duration = 0.0
    pose_completed = False
    completion_banner_time = None
    
    # Session tracking (scores per pose)
    session_scores = {}       # {pose_name: {similarity, stability}}
    poses_completed_set = set()
    session_complete = False
    session_complete_time = None
    peak_similarity = 0.0    # best similarity seen for current pose
    peak_stability  = 0.0
    
    # Rolling history queues for stability checks
    history_len = 15
    angle_history = {
        "l_shoulder": deque(maxlen=history_len),
        "r_shoulder": deque(maxlen=history_len),
        "l_elbow":    deque(maxlen=history_len),
        "r_elbow":    deque(maxlen=history_len)
    }
    
    # Particle burst lists
    particles = []
    
    last_frame_time = time.time()
    
    with mp_pose.Pose(min_detection_confidence=0.6, min_tracking_confidence=0.6) as pose:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
            
            curr_time = time.time()
            dt = curr_time - last_frame_time
            last_frame_time = curr_time
            
            frame = cv2.flip(frame, 1)
            
            # Dim the camera background for UI readability
            dark = np.zeros_like(frame, dtype=np.uint8)
            dark[:] = (12, 10, 20)
            cv2.addWeighted(dark, 0.48, frame, 0.52, 0, frame)
            
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)
            
            # Extract active pose configurations
            active_pose = POSES[current_pose_idx]
            targets = active_pose["targets"]
            
            # Default metrics
            similarity = 0.0
            stability = 0.0
            angles = {"l_shoulder": 0.0, "r_shoulder": 0.0, "l_elbow": 0.0, "r_elbow": 0.0}
            pose_detected = False
            
            if results.pose_landmarks:
                pose_detected = True
                lm = results.pose_landmarks.landmark
                angles = get_current_angles(lm)
                
                # Append to history queues
                for joint in angles:
                    angle_history[joint].append(angles[joint])
                
                # 1. Evaluate Similarity
                # Calculates error compared to template targets (forgiving window: max score at 0, 0% at 55 deg)
                joint_scores = []
                for joint in targets:
                    diff = abs(angles[joint] - targets[joint])
                    joint_scores.append(max(0.0, 100.0 - (diff * 1.8)))
                similarity = float(np.mean(joint_scores))
                
                # 2. Evaluate Stability
                # Variance check: small standard deviation indicates stable pose
                std_devs = []
                for joint in angle_history:
                    if len(angle_history[joint]) >= history_len:
                        std_devs.append(np.std(angle_history[joint]))
                if std_devs:
                    avg_std = np.mean(std_devs)
                    # 0 std -> 100% stability, 3.0 std -> 64% stability, 8.3 std -> 0%
                    stability = float(max(0.0, 100.0 - (avg_std * 12.0)))
                else:
                    stability = 100.0
                
                # Draw MediaPipe skeleton landmarks overlay
                mp_drawing.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(80, 60, 110), thickness=1, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(60, 45, 90), thickness=1)
                )
                
                # Colorize key joints on screen based on local match
                for joint, lm_index in [
                    ("l_shoulder", mp_pose.PoseLandmark.LEFT_SHOULDER),
                    ("r_shoulder", mp_pose.PoseLandmark.RIGHT_SHOULDER),
                    ("l_elbow",    mp_pose.PoseLandmark.LEFT_ELBOW),
                    ("r_elbow",    mp_pose.PoseLandmark.RIGHT_ELBOW)
                ]:
                    pos = (int(lm[lm_index.value].x * W), int(lm[lm_index.value].y * H))
                    diff = abs(angles[joint] - targets[joint])
                    color = (100, 220, 100) if diff <= 15 else ((80, 220, 255) if diff <= 28 else (80, 80, 240))
                    cv2.circle(frame, pos, 6, color, -1)
            
            # 3. Evaluate Hold Duration
            # Relaxed criteria: similarity >= 72.0% and stability >= 65.0%
            is_matching = similarity >= 72.0 and stability >= 65.0 and pose_detected
            
            # Track peak scores for current pose
            if pose_detected:
                peak_similarity = max(peak_similarity, similarity)
                peak_stability  = max(peak_stability, stability)
            
            if is_matching and not pose_completed and not session_complete:
                hold_duration = min(3.0, hold_duration + dt)
                
                if hold_duration >= 3.0:
                    pose_completed = True
                    completion_banner_time = curr_time
                    # Record this pose score
                    pname = active_pose["name"]
                    session_scores[pname] = {
                        "similarity": round(peak_similarity, 1),
                        "stability":  round(peak_stability, 1)
                    }
                    poses_completed_set.add(pname)
                    sound_engine.play_success()
                    # Trigger fireworks / particle blast
                    for _ in range(60):
                        a = random.uniform(0, 2 * math.pi)
                        s = random.uniform(3, 12)
                        particles.append({
                            "x": W // 2, "y": H // 2 - 50,
                            "vx": math.cos(a) * s, "vy": math.sin(a) * s - 2,
                            "life": 1.0, "size": random.uniform(3, 8),
                            "color": random.choice([(100, 240, 255), (180, 120, 255), (255, 200, 100), (100, 255, 180)])
                        })
            else:
                if not pose_completed and not session_complete:
                    # Decay hold progress slowly instead of resetting instantly to 0.0
                    hold_duration = max(0.0, hold_duration - dt * 1.2)
            
            # Post-completion delay before moving to next pose
            if pose_completed and curr_time - completion_banner_time >= 2.5 and not session_complete:
                next_idx = current_pose_idx + 1
                if next_idx >= len(POSES):
                    # All poses done — session complete!
                    session_complete = True
                    session_complete_time = curr_time
                    if params and params.get("user_id") and params.get("recovery_id"):
                        import re
                        uid = re.sub(r'[^a-zA-Z0-9_-]', '', str(params["user_id"]))
                        rid = re.sub(r'[^a-zA-Z0-9_-]', '', str(params["recovery_id"]))
                        progress_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"rehab_progress_{uid}_{rid}.json")
                    else:
                        progress_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rehab_progress.json")
                    try:
                        with open(progress_path, "r") as f:
                            progress = json.load(f)
                    except (FileNotFoundError, json.JSONDecodeError):
                        progress = {}
                    progress.setdefault("belle_pose_sessions", [])
                    progress["belle_pose_sessions"].append({
                        "date": time.strftime("%Y-%m-%d %H:%M"),
                        "scores": session_scores
                    })
                    with open(progress_path, "w") as f:
                        json.dump(progress, f, indent=2)
                    print(f"Session scores saved to {os.path.basename(progress_path)}")
                else:
                    # Advance to next pose
                    current_pose_idx = next_idx
                    peak_similarity = 0.0
                    peak_stability  = 0.0
                hold_duration = 0.0
                pose_completed = False
                completion_banner_time = None
                for joint in angle_history:
                    angle_history[joint].clear()
            
            # ──────────────────────────────────────────────
            # RENDER HUD & INTERACTIVE PANELS
            # ──────────────────────────────────────────────
            # Left Panel (Pose Goal & Instructions)
            draw_glass_panel(frame, (10, 10), (330, 710))
            cv2.putText(frame, "REHABVERSE", (25, 40), cv2.FONT_HERSHEY_DUPLEX, 0.72, (200, 160, 255), 2)
            cv2.line(frame, (25, 50), (315, 50), (60, 50, 75), 1)
            
            cv2.putText(frame, "ACTIVE GOAL", (25, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (140, 130, 155), 1)
            cv2.putText(frame, active_pose["name"], (25, 105), cv2.FONT_HERSHEY_DUPLEX, 0.75, (255, 240, 255), 2)
            
            # Draws target stick schematic
            draw_target_stick_figure(frame, 170, 240, active_pose["draw_offsets"], active_pose["name"])
            
            # Description text wrapper
            desc_lines = [active_pose["description"][i:i+32] for i in range(0, len(active_pose["description"]), 32)]
            y_offset = 350
            for dl in desc_lines:
                cv2.putText(frame, dl, (25, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 175, 195), 1)
                y_offset += 20
                
            cv2.line(frame, (25, 390), (315, 390), (60, 50, 75), 1)
            cv2.putText(frame, "CLINICIAN TIP", (25, 415), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140, 130, 155), 1)
            tip_lines = [active_pose["tip"][i:i+32] for i in range(0, len(active_pose["tip"]), 32)]
            y_offset = 440
            for tl in tip_lines:
                cv2.putText(frame, tl, (25, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (150, 185, 160), 1)
                y_offset += 18
            
            # Bottom shortcut guides
            cv2.putText(frame, "SPACE - Skip Pose", (25, 630), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (110, 100, 125), 1)
            cv2.putText(frame, "R     - Reset Hold", (25, 650), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (110, 100, 125), 1)
            cv2.putText(frame, "Q/ESC - Quit Session", (25, 670), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (110, 100, 125), 1)
            
            # Right Panel (AI Evaluation Metrics)
            draw_glass_panel(frame, (950, 10), (1270, 710))
            cv2.putText(frame, "AI EVALUATION", (965, 40), cv2.FONT_HERSHEY_DUPLEX, 0.65, (200, 160, 255), 1)
            cv2.line(frame, (965, 50), (1255, 50), (60, 50, 75), 1)
            
            # Draw Radial Score Gauges
            draw_radial_gauge(frame, (1030, 110), 45, similarity, label="MATCH", color=(100, 220, 255))
            draw_radial_gauge(frame, (1190, 110), 45, stability, label="STABLE", color=(180, 120, 255))
            
            cv2.line(frame, (965, 180), (1255, 180), (60, 50, 75), 1)
            cv2.putText(frame, "ALIGNMENT BREAKDOWN", (965, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (140, 130, 155), 1)
            
            # Angle list with alignment corrections
            y_offset = 245
            for label, joint, display_name in [
                ("L. Shoulder", "l_shoulder", "L. Shoulder"),
                ("R. Shoulder", "r_shoulder", "R. Shoulder"),
                ("L. Elbow",    "l_elbow",    "L. Elbow"),
                ("R. Elbow",    "r_elbow",    "R. Elbow")
            ]:
                curr_a = angles[joint]
                targ_a = targets[joint]
                diff = abs(curr_a - targ_a)
                
                # Check status
                if diff <= 15:
                    status_str = "MATCH"
                    status_col = (100, 220, 100)
                elif diff <= 28:
                    status_str = "CLOSE"
                    status_col = (100, 200, 240)
                else:
                    status_str = "ADJUST"
                    status_col = (100, 100, 240)
                    
                # Alignment instructions
                guide_str = "OK"
                if status_str != "MATCH":
                    if "shoulder" in joint:
                        guide_str = "RAISE" if curr_a < targ_a else "LOWER"
                    else:  # elbow
                        guide_str = "STRAIGHTEN" if curr_a < targ_a else "BEND"
                
                # Render joint labels
                cv2.putText(frame, display_name, (965, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (215, 210, 230), 1)
                cv2.putText(frame, f"{int(curr_a)}/{int(targ_a)} deg", (965, y_offset+18), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (140, 135, 155), 1)
                cv2.putText(frame, status_str, (1135, y_offset+5), cv2.FONT_HERSHEY_SIMPLEX, 0.36, status_col, 1)
                cv2.putText(frame, guide_str, (1135, y_offset+18), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (180, 180, 200) if guide_str != "OK" else (100, 200, 100), 1)
                
                cv2.line(frame, (965, y_offset+30), (1255, y_offset+30), (35, 30, 45), 1)
                y_offset += 48
            
            # Pose Progress Dots (bottom of right panel)
            dot_y = 660
            cv2.putText(frame, "PROGRESS", (965, dot_y - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (140, 130, 155), 1)
            dot_x_start = 975
            for i, p in enumerate(POSES):
                dot_cx = dot_x_start + i * 72
                is_done = p["name"] in poses_completed_set
                is_active = (i == current_pose_idx and not session_complete)
                dot_color = (100, 220, 120) if is_done else ((200, 160, 255) if is_active else (50, 45, 65))
                cv2.circle(frame, (dot_cx, dot_y), 10, dot_color, -1 if is_done or is_active else 1)
                if is_active:
                    cv2.circle(frame, (dot_cx, dot_y), 13, (200, 160, 255), 1)
                short_name = p["name"].split()[0][:5]
                cv2.putText(frame, short_name, (dot_cx - 14, dot_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.26, (160, 155, 175), 1)
            
            # Central Warning overlays
            if not pose_detected and not session_complete:
                cv2.putText(frame, "Stand back, place entire body in camera frame", (W//2 - 200, H//2 - 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (100, 100, 240), 1)
            
            # ──────────────────────────────────────────────
            # CENTRAL TIMERS & SUCCESS EFFECTS
            # ──────────────────────────────────────────────
            # Render Hold progress circle/banner in center top
            if pose_detected and not pose_completed:
                gauge_color = (100, 220, 100) if is_matching else (120, 115, 135)
                progress_pct = min(1.0, hold_duration / 3.0)
                
                # Transparent center panel
                draw_glass_panel(frame, (W//2 - 160, 20), (W//2 + 160, 75), alpha=0.5)
                cv2.putText(frame, f"HOLD TARGET: {hold_duration:.1f}s / 3.0s", (W//2 - 110, 42),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (250, 250, 255), 1)
                
                # Visual slider border
                cv2.rectangle(frame, (W//2 - 130, 55), (W//2 + 130, 62), (40, 35, 50), -1)
                # Fill indicator
                cv2.rectangle(frame, (W//2 - 130, 55), (W//2 - 130 + int(260 * progress_pct), 62), gauge_color, -1)
            
            # Render Completion overlay banner
            if pose_completed and not session_complete:
                # Darken center screen
                overlay = frame.copy()
                cv2.rectangle(overlay, (W//2 - 260, H//2 - 70), (W//2 + 260, H//2 + 25), (10, 6, 20), -1)
                cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)
                cv2.rectangle(frame, (W//2 - 260, H//2 - 70), (W//2 + 260, H//2 + 25), (0, 220, 100), 2)
                
                cv2.putText(frame, "POSE COMPLETED!", (W//2 - 140, H//2 - 20),
                            cv2.FONT_HERSHEY_DUPLEX, 0.82, (100, 240, 100), 2)
                cv2.putText(frame, "Loading next pose...", (W//2 - 90, H//2 + 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.40, (160, 175, 170), 1)
            
            # ── SESSION COMPLETE OVERLAY ──────────────────────────────
            if session_complete:
                # Full-screen dark overlay
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (W, H), (8, 5, 18), -1)
                cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)
                
                # Title banner
                cv2.rectangle(frame, (W//2 - 300, 80), (W//2 + 300, 155), (20, 15, 40), -1)
                cv2.rectangle(frame, (W//2 - 300, 80), (W//2 + 300, 155), (140, 100, 220), 2)
                cv2.putText(frame, "SESSION COMPLETE!", (W//2 - 185, 130),
                            cv2.FONT_HERSHEY_DUPLEX, 1.10, (200, 160, 255), 2)
                cv2.putText(frame, "Belle Pose — All 4 Poses Cleared", (W//2 - 175, 152),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.44, (160, 155, 180), 1)
                
                # Score table
                table_x = W//2 - 260
                table_y = 195
                cv2.rectangle(frame, (table_x - 10, table_y - 10), (table_x + 530, table_y + len(session_scores) * 58 + 20), (14, 10, 28), -1)
                cv2.rectangle(frame, (table_x - 10, table_y - 10), (table_x + 530, table_y + len(session_scores) * 58 + 20), (60, 50, 80), 1)
                
                cv2.putText(frame, "Pose", (table_x, table_y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (140, 130, 155), 1)
                cv2.putText(frame, "Match", (table_x + 290, table_y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (140, 130, 155), 1)
                cv2.putText(frame, "Stability", (table_x + 410, table_y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (140, 130, 155), 1)
                cv2.line(frame, (table_x - 5, table_y + 18), (table_x + 525, table_y + 18), (50, 42, 68), 1)
                
                row_y = table_y + 42
                total_sim = 0.0
                total_sta = 0.0
                for pname, sc in session_scores.items():
                    sim_v = sc["similarity"]
                    sta_v = sc["stability"]
                    total_sim += sim_v
                    total_sta += sta_v
                    
                    sim_col = (100, 220, 100) if sim_v >= 85 else ((80, 200, 240) if sim_v >= 70 else (200, 140, 255))
                    sta_col = (100, 220, 100) if sta_v >= 80 else ((80, 200, 240) if sta_v >= 65 else (200, 140, 255))
                    
                    cv2.putText(frame, pname, (table_x, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (230, 220, 245), 1)
                    cv2.putText(frame, f"{sim_v:.0f}%", (table_x + 300, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, sim_col, 1)
                    cv2.putText(frame, f"{sta_v:.0f}%", (table_x + 420, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, sta_col, 1)
                    
                    # Mini gauge bars
                    bar_w = 80
                    cv2.rectangle(frame, (table_x + 290, row_y + 6), (table_x + 290 + bar_w, row_y + 14), (35, 30, 48), -1)
                    cv2.rectangle(frame, (table_x + 290, row_y + 6), (table_x + 290 + int(bar_w * sim_v / 100), row_y + 14), sim_col, -1)
                    cv2.rectangle(frame, (table_x + 410, row_y + 6), (table_x + 410 + bar_w, row_y + 14), (35, 30, 48), -1)
                    cv2.rectangle(frame, (table_x + 410, row_y + 6), (table_x + 410 + int(bar_w * sta_v / 100), row_y + 14), sta_col, -1)
                    
                    row_y += 58
                
                # Average score
                n = max(1, len(session_scores))
                avg_sim = total_sim / n
                avg_sta = total_sta / n
                overall = (avg_sim + avg_sta) / 2
                
                cv2.line(frame, (table_x - 5, row_y - 10), (table_x + 525, row_y - 10), (50, 42, 68), 1)
                cv2.putText(frame, f"Average Match: {avg_sim:.0f}%  |  Average Stability: {avg_sta:.0f}%  |  Overall: {overall:.0f}%",
                            (table_x, row_y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200, 190, 215), 1)
                
                # Motivational badge
                if overall >= 85:
                    badge_text, badge_col = "EXCELLENT!", (100, 240, 180)
                elif overall >= 70:
                    badge_text, badge_col = "GREAT JOB!", (100, 200, 255)
                elif overall >= 55:
                    badge_text, badge_col = "KEEP GOING!", (200, 160, 255)
                else:
                    badge_text, badge_col = "PRACTICE MAKES PERFECT", (180, 180, 210)
                
                cv2.putText(frame, badge_text, (W//2 - len(badge_text) * 8, H - 130),
                            cv2.FONT_HERSHEY_DUPLEX, 0.78, badge_col, 2)
                cv2.putText(frame, "Progress saved to rehab_progress.json",
                            (W//2 - 170, H - 95), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 95, 120), 1)
                cv2.putText(frame, "Press Q or ESC to exit session",
                            (W//2 - 120, H - 65), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (120, 115, 135), 1)
            
            # Particle operations
            for p in particles:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["vy"] += 0.22      # gravity simulation
                p["life"] -= 0.02    # fading out
                
                size = max(1, int(p["size"] * p["life"]))
                alpha = p["life"]
                b, g, r = p["color"]
                col = (int(b * alpha), int(g * alpha), int(r * alpha))
                
                px, py = int(p["x"]), int(p["y"])
                if 0 <= px < W and 0 <= py < H:
                    cv2.circle(frame, (px, py), size, col, -1)
            
            # Prune dead particles
            particles = [p for p in particles if p["life"] > 0]
            
            cv2.imshow("RehabVerse — Belle Pose", frame)
            
            # Keyboard event parsing
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:   # Q or ESC key
                break
            elif key == ord('r') or key == ord('R'):
                if not session_complete:
                    hold_duration = 0.0
                    pose_completed = False
                    peak_similarity = 0.0
                    peak_stability  = 0.0
            elif key == 32:   # SPACE bar — skip current pose
                if not session_complete:
                    next_idx = current_pose_idx + 1
                    if next_idx >= len(POSES):
                        session_complete = True
                        session_complete_time = curr_time
                    else:
                        current_pose_idx = next_idx
                    hold_duration = 0.0
                    pose_completed = False
                    peak_similarity = 0.0
                    peak_stability  = 0.0
                    completion_banner_time = None
                    for joint in angle_history:
                        angle_history[joint].clear()
                    
    cap.release()
    cv2.destroyAllWindows()
    pygame.quit()
    print("Session ended.")

    # Build structured session result
    total_sim = sum(v.get("similarity", 0) for v in session_scores.values())
    total_sta = sum(v.get("stability", 0) for v in session_scores.values())
    n = max(1, len(session_scores))
    avg_sim = round(total_sim / n, 1)
    avg_sta = round(total_sta / n, 1)
    overall = round((avg_sim + avg_sta) / 2, 1)

    session_result = {
        "session": {
            "name": "belle_pose",
            "completed": session_complete,
            "slot": params.get("session_type", "morning") if params else "morning",
            "week": params.get("current_week", 1) if params else 1
        },
        "metrics": {
            "avg_similarity": avg_sim,
            "avg_stability": avg_sta,
            "overall_score": overall,
            "poses_completed": len(session_scores),
            "total_poses": len(POSES)
        },
        "objectives": {
            "completed": session_complete,
            "all_poses_done": session_complete
        },
        "pose_scores": session_scores
    }
    return session_result

if __name__ == "__main__":
    main()
