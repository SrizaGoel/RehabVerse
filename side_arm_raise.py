import cv2
import mediapipe as mp
import numpy as np
from collections import deque

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

pose = mp_pose.Pose(
    model_complexity=1,           
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6,
    smooth_landmarks=True         
)


cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)


def calculate_angle(a, b, c):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    c = np.array(c, dtype=float)
    ba = a - b
    bc = c - b
    cosine = np.dot(ba, bc) / (
        np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8
    )
    cosine = np.clip(cosine, -1.0, 1.0)
    angle = np.degrees(np.arccos(cosine))
    return angle


def shoulder_flexion_rom(elbow, shoulder, hip):

    raw_angle = calculate_angle(elbow, shoulder, hip)
    rom = abs(180 - raw_angle)
    return int(np.clip(rom, 0, 180))


class ROMSmoother:
    def __init__(self, window=8):
        self.buf = deque(maxlen=window)

    def update(self, value):
        self.buf.append(value)
        return int(np.median(self.buf))   


class RepCounter:
    def __init__(self, up_thresh=80, down_thresh=25):
        self.up_thresh = up_thresh      
        self.down_thresh = down_thresh  
        self.stage = "DOWN"
        self.count = 0

    def update(self, rom):
        if rom < self.down_thresh:
            self.stage = "DOWN"
        if rom > self.up_thresh and self.stage == "DOWN":
            self.stage = "UP"
            self.count += 1
        return self.count, self.stage


MILESTONES = [
    (0,   30,  "START",      "Begin Recovery",          (160, 160, 160)),
    (30,  60,  "BASE CAMP",  "Reach Table Height",      (100, 200, 255)),
    (60,  90,  "FOREST",     "Wear Shirt Easily",       (80,  200, 120)),
    (90,  120, "HIGH CAMP",  "Comb Your Hair",          (255, 200, 60)),
    (120, 180, "SUMMIT",     "Reach Overhead Shelf",    (255, 80,  80)),
]

def get_milestone(rom):
    for lo, hi, name, ability, color in MILESTONES:
        if rom < hi:
            return name, ability, color
    return MILESTONES[-1][2], MILESTONES[-1][3], MILESTONES[-1][4]


class ArmTracker:
    def __init__(self, label):
        self.label = label         
        self.smoother = ROMSmoother(window=8)
        self.rep_counter = RepCounter(up_thresh=80, down_thresh=25)
        self.rom = 0
        self.max_rom = 0           

    def update(self, elbow, shoulder, hip, visibility_ok):
        if not visibility_ok:
            return
        raw_rom = calculate_angle(elbow, shoulder, hip)
        self.rom = int(raw_rom)
        # self.rom = self.smoother.update(raw_rom)
        self.max_rom = max(self.max_rom, self.rom)
        self.rep_counter.update(self.rom)

    @property
    def reps(self):
        return self.rep_counter.count

    @property
    def stage(self):
        return self.rep_counter.stage


left_arm  = ArmTracker("LEFT")
right_arm = ArmTracker("RIGHT")


VISIBILITY_THRESHOLD = 0.6

def get_landmark_xy(landmarks, landmark_enum):
    lm = landmarks[landmark_enum.value]
    return [lm.x, lm.y], lm.visibility >= VISIBILITY_THRESHOLD


DARK_BG   = (15,  15,  20)
PANEL_BG  = (25,  28,  35)
WHITE     = (240, 240, 240)
CYAN      = (0,   220, 200)
ORANGE    = (30,  160, 255)
GREEN     = (60,  210, 100)
YELLOW    = (40,  220, 200)
RED       = (60,  80,  255)

def draw_rounded_rect(img, pt1, pt2, color, radius=12, thickness=-1, alpha=0.85):
    """Draw a filled semi-transparent rounded rectangle."""
    overlay = img.copy()
    x1, y1 = pt1
    x2, y2 = pt2
    r = radius
    cv2.rectangle(overlay, (x1+r, y1), (x2-r, y2), color, thickness)
    cv2.rectangle(overlay, (x1, y1+r), (x2, y2-r), color, thickness)
    cv2.circle(overlay, (x1+r, y1+r), r, color, thickness)
    cv2.circle(overlay, (x2-r, y1+r), r, color, thickness)
    cv2.circle(overlay, (x1+r, y2-r), r, color, thickness)
    cv2.circle(overlay, (x2-r, y2-r), r, color, thickness)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)


def draw_progress_bar(img, x, y, w, h, value, max_val=180, color=(0, 220, 200)):
    pct = np.clip(value / max_val, 0, 1)
    cv2.rectangle(img, (x, y), (x+w, y+h), (50, 50, 60), -1)
    cv2.rectangle(img, (x, y), (x+w, y+h), (80, 80, 90),  1)
    fill_w = int(w * pct)
    if fill_w > 2:
        for i in range(fill_w):
            t = i / max(fill_w - 1, 1)
            c = tuple(int(color[j] * (0.4 + 0.6 * t)) for j in range(3))
            cv2.line(img, (x+i, y+1), (x+i, y+h-1), c, 1)
    for lo, hi, *_ in MILESTONES[1:]:
        tx = x + int(w * lo / max_val)
        cv2.line(img, (tx, y), (tx, y+h), (100, 100, 110), 1)


def draw_arm_panel(img, tracker, x, y, w, panel_h):

    milestone, ability, m_color = get_milestone(tracker.rom)
    mc = tuple(int(c) for c in m_color)
    label_color = CYAN if tracker.label == "LEFT" else ORANGE
    stage_color = GREEN if tracker.stage == "UP" else (140, 140, 140)
    PAD = 14          
    mid = x + w // 2  

    draw_rounded_rect(img, (x, y), (x+w, y+panel_h), PANEL_BG, radius=14, alpha=0.90)

    cv2.putText(img, f"{tracker.label} ARM",
                (x+PAD, y+28), cv2.FONT_HERSHEY_DUPLEX, 0.72, label_color, 2)

    cv2.line(img, (x+PAD, y+36), (x+w-PAD, y+36), (55, 58, 70), 1)

    cv2.putText(img, "ROM",
                (x+PAD, y+52), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (130, 130, 140), 1)
    cv2.putText(img, "REPS",
                (mid+8, y+52), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (130, 130, 140), 1)

    cv2.putText(img, f"{tracker.rom:3d}",
                (x+PAD, y+100), cv2.FONT_HERSHEY_DUPLEX, 2.0, WHITE, 3)
    cv2.putText(img, f"{tracker.reps:2d}",
                (mid+8, y+100), cv2.FONT_HERSHEY_DUPLEX, 2.0, WHITE, 3)

    cv2.putText(img, "deg",
                (x+PAD, y+118), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (130, 130, 140), 1)
    cv2.putText(img, tracker.stage,
                (mid+8, y+118), cv2.FONT_HERSHEY_SIMPLEX, 0.55, stage_color, 2)

    draw_progress_bar(img, x+PAD, y+130, w-PAD*2, 13, tracker.rom, color=m_color)

    cv2.putText(img, f"Best: {tracker.max_rom} deg",
                (x+PAD, y+154), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (150, 150, 160), 1)

    cv2.line(img, (x+PAD, y+162), (x+w-PAD, y+162), (55, 58, 70), 1)

    cv2.putText(img, milestone,
                (x+PAD, y+182), cv2.FONT_HERSHEY_DUPLEX, 0.65, mc, 2)

    cv2.putText(img, ability,
                (x+PAD, y+200), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (190, 190, 200), 1)

    cv2.line(img, (x+PAD, y+208), (x+w-PAD, y+208), (55, 58, 70), 1)

    dot_y = y + 226
    for lo, _, name, _, dcolor in MILESTONES[1:]:
        unlocked = tracker.rom >= lo
        dc = tuple(int(c) for c in dcolor) if unlocked else (55, 55, 65)
        cv2.circle(img, (x+PAD+7, dot_y), 6, dc, -1)
        cv2.putText(img, name,
                    (x+PAD+20, dot_y+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.43, dc, 1)
        dot_y += 26


def draw_header(img, w):
    """Top banner."""
    cv2.rectangle(img, (0, 0), (w, 48), (18, 20, 28), -1)
    cv2.putText(img, "REHABVERSE",
                (16, 34), cv2.FONT_HERSHEY_DUPLEX, 1.1, CYAN, 2)
    cv2.putText(img, "Rotator Cuff Recovery Tracker",
                (210, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
    cv2.putText(img, "Press ESC to quit",
                (w - 200, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1)
    cv2.line(img, (0, 48), (w, 48), (50, 50, 60), 1)


def draw_no_pose(img, h, w):
    cv2.putText(img, "No pose detected — step back or improve lighting",
                (w//2 - 340, h//2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 255), 2)


while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    h, w = frame.shape[:2]

    frame = cv2.convertScaleAbs(frame, alpha=0.75, beta=0)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb)

    pose_detected = results.pose_landmarks is not None

    if pose_detected:
        landmarks = results.pose_landmarks.landmark

        l_shoulder, l_sh_vis = get_landmark_xy(landmarks, mp_pose.PoseLandmark.LEFT_SHOULDER)
        l_elbow,    l_el_vis = get_landmark_xy(landmarks, mp_pose.PoseLandmark.LEFT_ELBOW)
        l_hip,      l_hp_vis = get_landmark_xy(landmarks, mp_pose.PoseLandmark.LEFT_HIP)
        left_arm.update(l_elbow, l_shoulder, l_hip,
                        l_sh_vis and l_el_vis and l_hp_vis)

        r_shoulder, r_sh_vis = get_landmark_xy(landmarks, mp_pose.PoseLandmark.RIGHT_SHOULDER)
        r_elbow,    r_el_vis = get_landmark_xy(landmarks, mp_pose.PoseLandmark.RIGHT_ELBOW)
        r_hip,      r_hp_vis = get_landmark_xy(landmarks, mp_pose.PoseLandmark.RIGHT_HIP)
        right_arm.update(r_elbow, r_shoulder, r_hip,
                         r_sh_vis and r_el_vis and r_hp_vis)

        mp_drawing.draw_landmarks(
            frame,
            results.pose_landmarks,
            mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_drawing.DrawingSpec(
                color=(0, 230, 200), thickness=2, circle_radius=3),
            connection_drawing_spec=mp_drawing.DrawingSpec(
                color=(80, 80, 200), thickness=2)
        )

        for (sh, el, hp, color, vis) in [
            (l_shoulder, l_elbow, l_hip, (0, 220, 200), l_sh_vis and l_el_vis),
            (r_shoulder, r_elbow, r_hip, (30, 160, 255), r_sh_vis and r_el_vis),
        ]:
            if vis:
                px = int(sh[0] * w), int(sh[1] * h)
                ex = int(el[0] * w), int(el[1] * h)
                cv2.line(frame, px, ex, color, 3)
                cv2.circle(frame, px, 10, color, -1)
                cv2.circle(frame, ex,  6, (255, 255, 255), -1)

    else:
        draw_no_pose(frame, h, w)

    draw_header(frame, w)

    panel_w  = 290
    panel_h  = 340   
    margin   = 10
    top      = 56

    draw_arm_panel(frame, left_arm,  margin, top, panel_w, panel_h)

    draw_arm_panel(frame, right_arm, w - panel_w - margin, top, panel_w, panel_h)

    cv2.imshow("RehabVerse - Rotator Cuff Rehab", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == 27:   
        break
    if key == ord('r'):
        left_arm.rom = 0
        left_arm.max_rom = 0
        left_arm.smoother = ROMSmoother(window=8)
        left_arm.rep_counter = RepCounter(up_thresh=80, down_thresh=25)
        right_arm.rom = 0
        right_arm.max_rom = 0
        right_arm.smoother = ROMSmoother(window=8)
        right_arm.rep_counter = RepCounter(up_thresh=80, down_thresh=25)

cap.release()
cv2.destroyAllWindows()