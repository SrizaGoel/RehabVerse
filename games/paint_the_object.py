"""
RehabVerse — Paint the Sky
===========================
Weekly mobility check: paint a picture by raising your arm.
Arm angle controls brush Y position. Hold still to paint.

UNLOCK REQUIREMENTS (tracked in local file rehab_progress.json):
  - Front raise hold: 60s cumulative at >= 90 deg
  - Side raise hold:  60s cumulative at >= 90 deg (toggle with TAB)

Once both are met, the weekly paint challenge unlocks.

Controls:
  TAB  - toggle front / side raise mode
  Q    - quit

Install:
  pip install opencv-python mediapipe numpy pygame
"""

import cv2
import mediapipe as mp
import numpy as np
import math
import time
import json
import os
import random

mp_pose    = None   
mp_drawing = None

W, H = 1280, 720

PROGRESS_FILE = "rehab_progress.json"
REQUIRED_HOLD = 60.0   


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"front_hold": 0.0, "side_hold": 0.0,
            "week": _week_key(), "paint_done": False}


def save_progress(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _week_key():
    import datetime
    today = datetime.date.today()
    return f"{today.year}-W{today.isocalendar()[1]:02d}"


def check_new_week(data):
    wk = _week_key()
    if data.get("week") != wk:
        data["week"]       = wk
        data["paint_done"] = False   
    return data


TEMPLATES = ["sun", "flower", "butterfly"]

def make_template_mask(name, w=500, h=500):
    """Return (outline_img, zone_list).
    outline_img: BGR image with white background and black outline.
    zone_list: list of (region_mask, fill_color_BGR) — the regions to fill.
    """
    img = np.ones((h, w, 3), dtype=np.uint8) * 255
    zones = []

    if name == "sun":
        # Central circle
        cx, cy, r = w//2, h//2, 90
        mask_body = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask_body, (cx, cy), r, 255, -1)
        zones.append((mask_body, (0, 200, 255)))   # orange-yellow

        # Rays
        mask_rays = np.zeros((h, w), dtype=np.uint8)
        for i in range(12):
            angle = math.radians(i * 30)
            x1 = int(cx + (r+5) * math.cos(angle))
            y1 = int(cy + (r+5) * math.sin(angle))
            x2 = int(cx + (r+45) * math.cos(angle))
            y2 = int(cy + (r+45) * math.sin(angle))
            cv2.line(mask_rays, (x1, y1), (x2, y2), 255, 14)
        zones.append((mask_rays, (0, 230, 255)))

        # Draw outline
        cv2.circle(img, (cx, cy), r, (0,0,0), 3)
        for i in range(12):
            angle = math.radians(i * 30)
            x1 = int(cx + (r+5) * math.cos(angle))
            y1 = int(cy + (r+5) * math.sin(angle))
            x2 = int(cx + (r+45) * math.cos(angle))
            y2 = int(cy + (r+45) * math.sin(angle))
            cv2.line(img, (x1, y1), (x2, y2), (0,0,0), 4)

    elif name == "flower":
        cx, cy = w//2, h//2
        # Petals
        petal_colors = [(180,100,255),(100,180,255),(100,255,180),(255,180,100),(255,100,180)]
        for i in range(5):
            angle = math.radians(i * 72 - 90)
            px = int(cx + 80 * math.cos(angle))
            py = int(cy + 80 * math.sin(angle))
            mask_p = np.zeros((h, w), dtype=np.uint8)
            cv2.ellipse(mask_p, (px, py), (55, 38), int(math.degrees(angle)), 0, 360, 255, -1)
            zones.append((mask_p, petal_colors[i]))
            cv2.ellipse(img, (px, py), (55, 38), int(math.degrees(angle)), 0, 360, (0,0,0), 3)
        # Centre
        mask_c = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask_c, (cx, cy), 45, 255, -1)
        zones.append((mask_c, (0, 200, 255)))
        cv2.circle(img, (cx, cy), 45, (0,0,0), 3)
        # Stem
        cv2.line(img, (cx, cy+45), (cx, cy+200), (0,0,0), 6)
        mask_stem = np.zeros((h, w), dtype=np.uint8)
        cv2.line(mask_stem, (cx, cy+45), (cx, cy+200), 255, 12)
        zones.append((mask_stem, (50, 160, 50)))

    elif name == "butterfly":
        cx, cy = w//2, h//2
        # Left wings
        pts_ul = np.array([(cx,cy),(cx-60,cy-120),(cx-160,cy-80),(cx-140,cy+10),(cx-20,cy+20)], np.int32)
        pts_ll = np.array([(cx,cy),(cx-30,cy+20),(cx-120,cy+100),(cx-100,cy+150),(cx-10,cy+80)], np.int32)
        # Right wings
        pts_ur = np.array([(cx,cy),(cx+60,cy-120),(cx+160,cy-80),(cx+140,cy+10),(cx+20,cy+20)], np.int32)
        pts_lr = np.array([(cx,cy),(cx+30,cy+20),(cx+120,cy+100),(cx+100,cy+150),(cx+10,cy+80)], np.int32)

        for pts, col in [(pts_ul,(200,100,255)),(pts_ur,(200,100,255)),
                         (pts_ll,(100,180,255)),(pts_lr,(100,180,255))]:
            mask_w = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask_w, [pts], 255)
            zones.append((mask_w, col))
            cv2.polylines(img, [pts], True, (0,0,0), 3)

        # Body
        mask_b = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(mask_b, (cx, cy), (12, 70), 0, 0, 360, 255, -1)
        zones.append((mask_b, (40, 40, 80)))
        cv2.ellipse(img, (cx, cy), (12, 70), 0, 0, 360, (0,0,0), 3)

    return img, zones


class PaintCanvas:
    PAINT_W, PAINT_H = 500, 500

    def __init__(self, template_name):
        self.name        = template_name
        self.outline, self.zones = make_template_mask(template_name, self.PAINT_W, self.PAINT_H)
        self.canvas      = self.outline.copy()  
        self.filled      = np.zeros((self.PAINT_H, self.PAINT_W), dtype=np.uint8)  # painted pixels
        self.brush_x     = self.PAINT_W // 2
        self.brush_y     = self.PAINT_H // 2
        self.brush_r     = 22   
        self.paint_color = (0, 180, 255)
        self.total_paintable = 0
        self.total_painted   = 0
        self.outside_strokes = 0
        self.total_strokes   = 0
        self.accuracy        = 100.0
        self.complete        = False

        self.valid_mask = np.zeros((self.PAINT_H, self.PAINT_W), dtype=np.uint8)
        for mask, _ in self.zones:
            self.valid_mask = cv2.bitwise_or(self.valid_mask, mask)
        self.total_paintable = int(np.sum(self.valid_mask > 0))

    def move_brush(self, norm_x, norm_y):
        """norm_x, norm_y in [0,1]"""
        self.brush_x = int(np.clip(norm_x * self.PAINT_W, 0, self.PAINT_W-1))
        self.brush_y = int(np.clip(norm_y * self.PAINT_H, 0, self.PAINT_H-1))

    def paint_at_brush(self, holding: bool):
        if not holding:
            return
        bx, by = self.brush_x, self.brush_y
        active_color = None
        for mask, color in self.zones:
            if 0 <= by < self.PAINT_H and 0 <= bx < self.PAINT_W:
                if mask[by, bx] > 0:
                    active_color = color
                    break

        self.total_strokes += 1

        stamp = np.zeros((self.PAINT_H, self.PAINT_W), dtype=np.uint8)
        cv2.circle(stamp, (bx, by), self.brush_r, 255, -1)

        outside = cv2.bitwise_and(stamp, cv2.bitwise_not(self.valid_mask))
        if np.sum(outside) > 0:
            self.outside_strokes += 1

        inside = cv2.bitwise_and(stamp, self.valid_mask)
        new_paint = cv2.bitwise_and(inside, cv2.bitwise_not(self.filled))

        if active_color and np.sum(new_paint) > 0:
            # Paint each zone with its own colour
            for mask, color in self.zones:
                zone_new = cv2.bitwise_and(new_paint, mask)
                coords = np.where(zone_new > 0)
                if len(coords[0]) > 0:
                    b, g, r = color
                    self.canvas[coords[0], coords[1]] = [b, g, r]

            self.filled = cv2.bitwise_or(self.filled, new_paint)
            self.total_painted = int(np.sum(self.filled > 0))

        if self.total_strokes > 0:
            self.accuracy = 100.0 * max(0, self.total_strokes - self.outside_strokes) / self.total_strokes

        if self.total_paintable > 0:
            pct = self.total_painted / self.total_paintable
            if pct >= 0.85:
                self.complete = True

    def completion_pct(self):
        if self.total_paintable == 0:
            return 0.0
        return 100.0 * self.total_painted / self.total_paintable

    def draw_cursor(self, img):
        bx, by = self.brush_x, self.brush_y
        # Show brush circle
        in_valid = self.valid_mask[by, bx] > 0 if 0<=by<self.PAINT_H and 0<=bx<self.PAINT_W else False
        color = (0, 220, 100) if in_valid else (0, 60, 220)
        cv2.circle(img, (bx, by), self.brush_r, color, 2)
        cv2.circle(img, (bx, by), 2, color, -1)

    def get_display(self):
        disp = self.canvas.copy()
        self.draw_cursor(disp)
        return disp


def calc_angle(a, b, c):
    a, b, c = np.array(a), np.array(b), np.array(c)
    angle   = abs(math.degrees(
        math.atan2(c[1]-b[1], c[0]-b[0]) - math.atan2(a[1]-b[1], a[0]-b[0])))
    return 360 - angle if angle > 180 else angle


def get_arm_angle(landmarks, mode="front"):
    """
    front: shoulder FLEXION - arm raised forward.
           hip->shoulder->elbow angle. Good for front raise.
    side:  shoulder ABDUCTION - arm raised out to the side.
           right_shoulder->left_shoulder->left_elbow angle.
           Lifting left arm laterally produces a growing angle.
    Both ~0 at rest, growing toward ~180 at full raise. Uses LEFT arm.
    """
    lm   = landmarks
    Pose = mp.solutions.pose.PoseLandmark

    l_shoulder = [lm[Pose.LEFT_SHOULDER.value].x,  lm[Pose.LEFT_SHOULDER.value].y]
    l_elbow    = [lm[Pose.LEFT_ELBOW.value].x,     lm[Pose.LEFT_ELBOW.value].y]

    if mode == "front":
        hip = [lm[Pose.LEFT_HIP.value].x, lm[Pose.LEFT_HIP.value].y]
        return calc_angle(hip, l_shoulder, l_elbow)
    else:
        r_shoulder = [lm[Pose.RIGHT_SHOULDER.value].x, lm[Pose.RIGHT_SHOULDER.value].y]
        return calc_angle(r_shoulder, l_shoulder, l_elbow)


def get_wrist_normalized(landmarks):
    """Return (x, y) of left wrist, normalised 0-1.
    Note: MediaPipe y=0 is TOP of frame, y=1 is BOTTOM.
    We flip Y so y=0 means bottom of canvas (arm low) and y=1 means top.
    """
    lm   = landmarks
    Pose = mp.solutions.pose.PoseLandmark
    w    = lm[Pose.LEFT_WRIST.value]
    raw_x = float(w.x)
    raw_y = float(w.y)
    flipped_y = 1.0 - raw_y
    return raw_x, flipped_y


def draw_lock_screen(frame, progress):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0,0), (W,H), (5,5,15), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    cv2.putText(frame, "WEEKLY PAINT CHALLENGE", (W//2-230, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180,140,255), 2)
    cv2.putText(frame, "LOCKED", (W//2-70, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 1.1, (80,80,200), 2)

    cv2.putText(frame, "Complete these mobility milestones to unlock:", (W//2-270, 190),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160,160,180), 1)

    fh  = min(progress["front_hold"], REQUIRED_HOLD)
    pct = fh / REQUIRED_HOLD
    done = pct >= 1.0
    label = "Front raise: hold 90+ deg for 60 sec"
    col   = (80,220,80) if done else (100,160,255)
    cv2.putText(frame, label, (W//2-270, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
    cv2.rectangle(frame, (W//2-270, 250), (W//2+130, 265), (40,40,60), -1)
    cv2.rectangle(frame, (W//2-270, 250), (W//2-270+int(400*pct), 265), col, -1)
    cv2.putText(frame, f"{fh:.0f}s / 60s", (W//2+140, 263), cv2.FONT_HERSHEY_SIMPLEX, 0.42, col, 1)

    sh   = min(progress["side_hold"], REQUIRED_HOLD)
    pct2 = sh / REQUIRED_HOLD
    done2 = pct2 >= 1.0
    label2 = "Side raise: hold 90+ deg for 60 sec"
    col2   = (80,220,80) if done2 else (100,200,255)
    cv2.putText(frame, label2, (W//2-270, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col2, 1)
    cv2.rectangle(frame, (W//2-270, 320), (W//2+130, 335), (40,40,60), -1)
    cv2.rectangle(frame, (W//2-270, 320), (W//2-270+int(400*pct2), 335), col2, -1)
    cv2.putText(frame, f"{sh:.0f}s / 60s", (W//2+140, 333), cv2.FONT_HERSHEY_SIMPLEX, 0.42, col2, 1)

    cv2.putText(frame, "TAB = toggle front/side mode    Q = quit",
                (W//2-220, H-30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100,100,120), 1)


def draw_paint_hud(frame, canvas: PaintCanvas, mode, angle, is_holding, progress):
    panel = frame.copy()
    cv2.rectangle(panel, (10,10), (340,220), (8,8,18), -1)
    cv2.addWeighted(panel, 0.75, frame, 0.25, 0, frame)
    cv2.rectangle(frame, (10,10), (340,220), (80,60,100), 1)

    cv2.putText(frame, "PAINT THE SKY", (20,38), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180,140,255), 1)

    mode_str = "FRONT RAISE" if mode=="front" else "SIDE RAISE"
    mode_col = (100,200,255) if mode=="front" else (100,255,200)
    cv2.putText(frame, f"Mode: {mode_str}", (20,60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, mode_col, 1)

    cv2.putText(frame, f"Arm angle: {int(angle)} deg", (20,82), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180,170,200), 1)
    cv2.rectangle(frame, (20,88), (220,98), (35,30,50), -1)
    fill = int(200 * min(angle,180) / 180)
    cv2.rectangle(frame, (20,88), (20+fill,98), (60,220,120) if angle>90 else (80,130,255), -1)

    comp = canvas.completion_pct()
    cv2.putText(frame, f"Painted: {comp:.0f}%", (20,120), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180,170,200), 1)
    cv2.rectangle(frame, (20,126), (220,136), (35,30,50), -1)
    cv2.rectangle(frame, (20,126), (20+int(200*comp/100),136), (180,100,220), -1)

    acc = canvas.accuracy
    acc_col = (80,220,80) if acc>85 else (60,160,255) if acc>60 else (60,60,220)
    cv2.putText(frame, f"Accuracy: {acc:.0f}%", (20,158), cv2.FONT_HERSHEY_SIMPLEX, 0.42, acc_col, 1)

    hold_col = (80,220,80) if is_holding else (80,80,100)
    cv2.putText(frame, "PAINTING" if is_holding else "Hold still to paint",
                (20,178), cv2.FONT_HERSHEY_SIMPLEX, 0.42, hold_col, 1)

    fh = min(progress["front_hold"], REQUIRED_HOLD)
    sh = min(progress["side_hold"],  REQUIRED_HOLD)
    cv2.putText(frame, f"Front hold: {fh:.0f}s/60s   Side hold: {sh:.0f}s/60s",
                (20,200), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (120,110,140), 1)

    if canvas.complete:
        cv2.putText(frame, "Painting complete! Well done!", (W//2-200, H-30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (80,255,150), 2)
    elif comp > 50:
        cv2.putText(frame, "Great work — keep filling it in!", (W//2-200, H-30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180,220,100), 2)
    else:
        cv2.putText(frame, "Raise arm to move brush — hold still to paint", (W//2-260, H-30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (100,160,255), 1)

    cv2.putText(frame, "TAB=toggle mode   Q=quit", (W-280, H-15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (70,65,85), 1)


def main():
    import mediapipe as mp
    global mp_pose, mp_drawing
    mp_pose    = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    print("RehabVerse — Paint the Sky")
    print("TAB to toggle front/side raise mode.  Q to quit.")

    progress = load_progress()
    progress = check_new_week(progress)
    save_progress(progress)

    def is_unlocked():
        return (progress["front_hold"] >= REQUIRED_HOLD and
                progress["side_hold"]  >= REQUIRED_HOLD)

    template_name = random.choice(TEMPLATES)
    paint_canvas  = PaintCanvas(template_name)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)

    mode           = "front"    
    smoothed_angle = 0.0
    hold_start     = None
    is_holding     = False
    HOLD_THRESHOLD = 85         
    prev_angle     = 0.0
    prev_time      = time.time()

    smooth_wrist_x = 0.5
    smooth_wrist_y = 0.5

    milestone_hold_start = None

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
            dt      = max(t - prev_time, 1e-6)

            angle      = smoothed_angle
            wrist_norm = (0.5, 0.5)

            if results.pose_landmarks:
                lm         = results.pose_landmarks.landmark
                raw        = get_arm_angle(lm, mode)
                smoothed_angle = 0.82 * smoothed_angle + 0.18 * raw
                angle      = smoothed_angle
                wrist_norm = get_wrist_normalized(lm)

                mp_drawing.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(80,70,100), thickness=1, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(70,60,90),  thickness=1))

            if angle >= HOLD_THRESHOLD:
                if milestone_hold_start is None:
                    milestone_hold_start = t
                elapsed = t - milestone_hold_start
                key = "front_hold" if mode == "front" else "side_hold"
                progress[key] = min(REQUIRED_HOLD, progress.get(key, 0.0) + dt)
                save_progress(progress)
            else:
                milestone_hold_start = None

            SMOOTH = 0.80   
            smooth_wrist_x = SMOOTH * smooth_wrist_x + (1-SMOOTH) * wrist_norm[0]
            smooth_wrist_y = SMOOTH * smooth_wrist_y + (1-SMOOTH) * wrist_norm[1]


            X_LO, X_HI = 0.25, 0.75  
            Y_LO, Y_HI = 0.10, 0.70   
            brush_x_norm = np.clip((smooth_wrist_x - X_LO) / (X_HI - X_LO), 0.0, 1.0)
            brush_y_norm = np.clip((smooth_wrist_y - Y_LO) / (Y_HI - Y_LO), 0.0, 1.0)
            brush_y_norm = 1.0 - brush_y_norm

            is_holding = (angle >= HOLD_THRESHOLD)

            if is_unlocked():
                paint_canvas.move_brush(brush_x_norm, brush_y_norm)
                paint_canvas.paint_at_brush(is_holding)

            prev_angle = angle
            prev_time  = t

            bg = np.zeros((H, W, 3), dtype=np.uint8)
            bg[:] = (18, 12, 28)
            cv2.addWeighted(bg, 0.5, frame, 0.5, 0, frame)

            if not is_unlocked():
                draw_lock_screen(frame, progress)
            else:
                cw, ch = PaintCanvas.PAINT_W, PaintCanvas.PAINT_H
                px = (W - cw) // 2 + 120
                py = (H - ch) // 2
                canvas_display = paint_canvas.get_display()
                frame[py:py+ch, px:px+cw] = canvas_display

                col = (80,220,80) if paint_canvas.complete else (100,80,140)
                cv2.rectangle(frame, (px-2, py-2), (px+cw+2, py+ch+2), col, 2)
                cv2.putText(frame, paint_canvas.name.upper(),
                            (px, py-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160,140,200), 1)

                draw_paint_hud(frame, paint_canvas, mode, angle, is_holding, progress)

            cv2.imshow("RehabVerse — Paint the Sky", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == 9:   # TAB
                mode = "side" if mode == "front" else "front"
                milestone_hold_start = None
                print(f"Switched to {mode} raise mode")

    cap.release()
    cv2.destroyAllWindows()
    save_progress(progress)

    print("\nSession complete!")
    print(f"  Front hold total: {progress['front_hold']:.0f}s / {REQUIRED_HOLD:.0f}s")
    print(f"  Side hold total:  {progress['side_hold']:.0f}s / {REQUIRED_HOLD:.0f}s")
    if is_unlocked():
        print(f"  Painting: {paint_canvas.completion_pct():.0f}% complete, {paint_canvas.accuracy:.0f}% accuracy")
    else:
        print("  Paint challenge not yet unlocked.")


def is_unlocked_check():
    p = load_progress()
    return p.get("front_hold",0) >= REQUIRED_HOLD and p.get("side_hold",0) >= REQUIRED_HOLD


if __name__ == "__main__":
    main()