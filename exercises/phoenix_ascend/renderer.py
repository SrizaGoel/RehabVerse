"""
Rendering: HUD overlays + a simple vector-art phoenix whose wings mirror
the player's tracked shoulder angles in real time.
"""
import time
import math
import cv2
import numpy as np

COLOR_MAP = {
    "green": (80, 220, 100),
    "yellow": (50, 210, 235),
    "red": (60, 60, 230),
}

PALETTE = {
    "glow_aura":   (200, 60, 150),
    "body_outer":  (90, 30, 60),
    "body_inner":  (150, 60, 110),
    "wing_mid":    (130, 35, 90),
    "wing_outer":  (35, 110, 235),
    "wing_tip":    (15, 55, 255),
    "tail_base":   (120, 35, 95),
    "tail_tip":    (20, 60, 255),
    "eye":         (40, 170, 255),
    "beak":        (30, 120, 235),
    "outline":     (35, 12, 30),
}

WING_OFFSETS = [-26, -13, 0, 13, 26]
WING_LENGTH_FACTORS = [0.80, 0.93, 1.0, 0.93, 0.80]
WING_COLOR_KEYS = ["wing_tip", "wing_outer", "wing_mid", "wing_outer", "wing_tip"]
WING_WIDTH_FACTORS = [0.15, 0.19, 0.21, 0.19, 0.15]

PANEL_BG = (30, 30, 30)

# Minimal set of bone connections for the calibration overlay, using the
# classic MediaPipe pose landmark indices (stable across API versions).
SKELETON_CONNECTIONS = [
    (11, 12),  # shoulder to shoulder
    (11, 13), (13, 15),   # left shoulder -> elbow -> wrist
    (12, 14), (14, 16),   # right shoulder -> elbow -> wrist
    (11, 23), (12, 24),   # shoulders to hips
    (23, 24),              # hip to hip
]


def draw_skeleton(frame, landmarks, color=(90, 90, 90)):
    """
    Faint calibration overlay so the player can see they're correctly
    framed. `landmarks` is the flat list returned by PoseTracker.process()
    (normalized x/y in [0, 1]), or None.
    """
    if not landmarks:
        return
    h, w = frame.shape[:2]
    points = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

    for a, b in SKELETON_CONNECTIONS:
        if a < len(points) and b < len(points):
            cv2.line(frame, points[a], points[b], color, 1, cv2.LINE_AA)
    for idx in (11, 12, 13, 14, 15, 16, 23, 24):
        if idx < len(points):
            cv2.circle(frame, points[idx], 3, color, -1, cv2.LINE_AA)


def draw_text(frame, text, pos, scale=0.7, color=(255, 255, 255), thickness=2):
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def draw_translucent_panel(frame, x, y, w, h, alpha=0.55):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), PANEL_BG, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def _dir_vec(angle_deg, side_sign):
    rad = math.radians(angle_deg)
    return (side_sign * math.sin(rad), math.cos(rad))


def _draw_feather(frame, base, angle_deg, side_sign, length, width, color):
    dx, dy = _dir_vec(angle_deg, side_sign)
    tip = (base[0] + dx * length, base[1] + dy * length)
    mid = ((base[0] + tip[0]) / 2, (base[1] + tip[1]) / 2)
    rot = math.degrees(math.atan2(dy, dx))
    axes = (max(int(length / 2), 1), max(int(width / 2), 1))
    cv2.ellipse(frame, (int(mid[0]), int(mid[1])), axes, rot, 0, 360, color, -1, cv2.LINE_AA)


def _draw_wing(frame, shoulder, angle_deg, side_sign, span):
    # Wings look tucked/folded near 0deg and progressively fan out as the
    # player abducts further - both length AND spread scale with angle.
    openness = max(0.0, min(1.0, angle_deg / 150))
    length_scale = 0.32 + 0.68 * openness
    spread_scale = 0.35 + 0.65 * openness
    for offset, length_f, color_key, width_f in zip(
        WING_OFFSETS, WING_LENGTH_FACTORS, WING_COLOR_KEYS, WING_WIDTH_FACTORS
    ):
        _draw_feather(
            frame, shoulder, angle_deg + offset * spread_scale, side_sign,
            span * length_f * length_scale, span * width_f, PALETTE[color_key],
        )


def draw_phoenix(frame, center_x, center_y, left_angle, right_angle, glow_color):
    span = 120
    glow = COLOR_MAP.get(glow_color, (200, 200, 200))
    cx, cy = center_x, center_y

    # soft layered halo
    overlay = frame.copy()
    cv2.circle(overlay, (cx, cy), 100, PALETTE["glow_aura"], -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.12, frame, 0.88, 0, frame)
    overlay = frame.copy()
    cv2.circle(overlay, (cx, cy), 65, glow, -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.10, frame, 0.90, 0, frame)

    # wings (drawn first so the body overlaps their base)
    _draw_wing(frame, (cx, cy), left_angle, -1, span)
    _draw_wing(frame, (cx, cy), right_angle, 1, span)

    # tail (3 flame strands, flickering)
    flick = 6 * math.sin(time.time() * 6)
    tail_specs = [(-16, "tail_tip", 0.8), (0, "tail_base", 1.0), (16, "tail_tip", 0.8)]
    for offset, color_key, length_f in tail_specs:
        _draw_feather(frame, (cx, cy + 28), 180 + offset, 1,
                      (55 + flick) * length_f, 14, PALETTE[color_key])

    # body (outline -> base -> highlight, layered for depth)
    cv2.ellipse(frame, (cx, cy), (26, 38), 0, 0, 360, PALETTE["outline"], -1, cv2.LINE_AA)
    cv2.ellipse(frame, (cx, cy), (22, 34), 0, 0, 360, PALETTE["body_outer"], -1, cv2.LINE_AA)
    cv2.ellipse(frame, (cx - 5, cy - 6), (10, 16), 0, 0, 360, PALETTE["body_inner"], -1, cv2.LINE_AA)

    # head + crest + beak + eye
    head_c = (cx, cy - 40)
    cv2.circle(frame, head_c, 16, PALETTE["outline"], -1, cv2.LINE_AA)
    cv2.circle(frame, head_c, 13, PALETTE["body_outer"], -1, cv2.LINE_AA)
    for crest_angle in (-30, 0, 30):
        _draw_feather(frame, head_c, 180 + crest_angle, 1, 22, 6, PALETTE["wing_tip"])
    cv2.fillPoly(frame, [np.array([
        [head_c[0], head_c[1] - 4],
        [head_c[0] + 20, head_c[1]],
        [head_c[0], head_c[1] + 6],
    ], dtype=np.int32)], PALETTE["beak"], lineType=cv2.LINE_AA)
    cv2.circle(frame, (head_c[0] - 3, head_c[1] - 3), 3, PALETTE["eye"], -1, cv2.LINE_AA)
    cv2.circle(frame, (head_c[0] - 4, head_c[1] - 4), 1, (255, 255, 255), -1, cv2.LINE_AA)


ARM_LANDMARKS = [
    (11, 13, 15, -1),  # left: shoulder, elbow, wrist, side_sign
    (12, 14, 16, 1),   # right: shoulder, elbow, wrist, side_sign
]

ARM_FAN_OFFSETS = [-30, -15, 0, 15, 30]
ARM_FAN_LENGTH_FACTORS = [0.74, 0.88, 1.0, 0.88, 0.74]
ARM_FAN_COLOR_KEYS = ["wing_tip", "wing_outer", "wing_mid", "wing_outer", "wing_tip"]
ARM_FAN_WIDTH_FACTORS = [0.16, 0.20, 0.23, 0.20, 0.16]


def draw_arm_wings(frame, landmarks, frame_w, frame_h):
    """Translucent feathered ghost-wing overlay that hugs each actual arm."""
    if not landmarks:
        return
    for shoulder_idx, elbow_idx, wrist_idx, side_sign in ARM_LANDMARKS:
        shoulder, elbow, wrist = landmarks[shoulder_idx], landmarks[elbow_idx], landmarks[wrist_idx]
        if min(shoulder.visibility, elbow.visibility, wrist.visibility) < 0.5:
            continue
        s_px = (shoulder.x * frame_w, shoulder.y * frame_h)
        e_px = (elbow.x * frame_w, elbow.y * frame_h)
        w_px = (wrist.x * frame_w, wrist.y * frame_h)
        _draw_wing_ribbon(frame, s_px, e_px, w_px, side_sign)


def _dir(p_from, p_to):
    dx, dy = p_to[0] - p_from[0], p_to[1] - p_from[1]
    length = math.hypot(dx, dy) or 1
    return dx / length, dy / length


def _draw_feather_deg(frame, base, angle_deg, length, width, color, alpha=0.6):
    rad = math.radians(angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    tip = (base[0] + dx * length, base[1] + dy * length)
    mid = ((base[0] + tip[0]) / 2, (base[1] + tip[1]) / 2)
    axes = (max(int(length / 2), 1), max(int(width / 2), 1))
    overlay = frame.copy()
    cv2.ellipse(overlay, (int(mid[0]), int(mid[1])), axes, angle_deg, 0, 360, color, -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def _membrane_ribbon(frame, shoulder, elbow, wrist, base_w=44, tip_w=36, alpha=0.42):
    pts = [shoulder, elbow, wrist]
    normals = []
    for i, p in enumerate(pts):
        prev_p = pts[i - 1] if i > 0 else pts[i]
        next_p = pts[i + 1] if i < len(pts) - 1 else pts[i]
        d = _dir(prev_p, next_p)
        normals.append((-d[1], d[0]))
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        t = i / (len(pts) - 1)
        w = base_w * (1 - t) + tip_w * t
        nx, ny = normals[i]
        left.append((x + nx * w / 2, y + ny * w / 2))
        right.append((x - nx * w / 2, y - ny * w / 2))
    poly = np.array(left + right[::-1], dtype=np.int32)
    overlay = frame.copy()
    cv2.fillPoly(overlay, [poly], PALETTE["wing_mid"], lineType=cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def _draw_wing_ribbon(frame, shoulder, elbow, wrist, side_sign, span=130):
    # membrane covering the whole arm (covert-feather area)
    _membrane_ribbon(frame, shoulder, elbow, wrist)

    forearm_dir = _dir(elbow, wrist)
    base_angle = math.degrees(math.atan2(forearm_dir[1], forearm_dir[0]))
    # fan center sweeps outward/back from the wrist, like a real wingtip
    fan_center = base_angle + side_sign * 78

    # long primary feathers fanning from the wrist
    for offset, length_f, color_key, width_f in zip(
        ARM_FAN_OFFSETS, ARM_FAN_LENGTH_FACTORS, ARM_FAN_COLOR_KEYS, ARM_FAN_WIDTH_FACTORS
    ):
        _draw_feather_deg(
            frame, wrist, fan_center + offset * side_sign,
            span * length_f, span * width_f, PALETTE[color_key], alpha=0.62
        )

    # shorter secondary feathers along the forearm, bridging membrane -> wingtip fan
    for t, length_f in [(0.35, 0.55), (0.62, 0.68), (0.85, 0.8)]:
        base = (elbow[0] + (wrist[0] - elbow[0]) * t, elbow[1] + (wrist[1] - elbow[1]) * t)
        sweep = 0.5 + 0.3 * t
        sec_angle = base_angle * (1 - sweep) + fan_center * sweep
        color_key = "wing_outer" if t < 0.7 else "wing_tip"
        _draw_feather_deg(frame, base, sec_angle, span * length_f, span * 0.14, PALETTE[color_key], alpha=0.5)


def draw_hud(frame, snapshot):
    h, w = frame.shape[:2]
    draw_translucent_panel(frame, 10, 10, 330, 150)

    draw_text(frame, f"Level {snapshot['level_id']}: {snapshot['level_name']}", (24, 38), 0.6)
    draw_text(frame, f"Score: {snapshot['score']}", (24, 66), 0.65, (255, 230, 120))
    draw_text(frame, f"Feathers: {snapshot['feathers']}", (24, 92), 0.6, (255, 255, 255))
    draw_text(frame, f"Reps: {snapshot['reps_this_level']}/{snapshot['reps_to_advance']}", (24, 118), 0.55)
    draw_text(frame, f"Combo: {snapshot['combo']} (best {snapshot['best_combo']})", (24, 144), 0.55, (180, 230, 255))

    draw_translucent_panel(frame, w - 300, 10, 290, 120)
    target = snapshot["target"]
    draw_text(frame, f"Target: {target['name']}", (w - 288, 36), 0.55)
    draw_text(frame, f"Goal angle: {target['angle']} deg", (w - 288, 62), 0.55)
    draw_text(frame, f"Phase: {snapshot['phase'].title()}", (w - 288, 88), 0.55)

    if snapshot["phase"] == "stability":
        bar_w = 260
        progress = snapshot["stability_progress"]
        cv2.rectangle(frame, (w - 288, 100), (w - 288 + bar_w, 112), (90, 90, 90), -1)
        cv2.rectangle(frame, (w - 288, 100), (w - 288 + int(bar_w * progress), 112), (80, 220, 100), -1)

    color = COLOR_MAP.get(snapshot["feedback_color"], (200, 200, 200))
    draw_translucent_panel(frame, 0, h - 60, w, 60, alpha=0.5)
    cv2.circle(frame, (30, h - 30), 12, color, -1)
    draw_text(frame, snapshot["feedback_text"], (55, h - 22), 0.65, (255, 255, 255))

    if snapshot["last_event"] and time.time() - snapshot["last_event_time"] < 2.0:
        draw_text(frame, snapshot["last_event"], (w // 2 - 150, 40), 0.75, (255, 255, 120), 2)

def draw_start_screen(frame, ready):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (10, 5, 10), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    draw_text(frame, "PHOENIX ASCEND", (w // 2 - 260, h // 2 - 160), 1.3, PALETTE["wing_tip"], 3)
    draw_text(frame, "Shoulder Rehabilitation Through Flight", (w // 2 - 230, h // 2 - 115), 0.6, (200, 200, 200))
    draw_text(frame, "Stand back so your shoulders, elbows and hips are visible", (w // 2 - 300, h // 2 - 30), 0.55)
    draw_text(frame, "Raise and lower your arm to control the phoenix", (w // 2 - 260, h // 2 + 5), 0.55)

    if ready:
        draw_text(frame, "Position detected - press SPACE to begin", (w // 2 - 250, h // 2 + 70), 0.7, (80, 220, 100), 2)
    else:
        draw_text(frame, "Move into frame to begin calibration...", (w // 2 - 240, h // 2 + 70), 0.7, (60, 60, 230), 2)

    draw_text(frame, "Controls:  SPACE = start    Q = quit", (w // 2 - 190, h - 40), 0.55, (180, 180, 180))


def draw_end_screen(frame, snapshot, max_rom_angle):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (10, 5, 10), -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    card_w, card_h = 480, 340
    cx, cy = w // 2 - card_w // 2, h // 2 - card_h // 2
    draw_translucent_panel(frame, cx, cy, card_w, card_h, radius=20, glow_strength=0.6)

    draw_text(frame, "SESSION COMPLETE", (cx + 55, cy + 55), 0.9, PALETTE["wing_tip"], 2)
    draw_text(frame, f"Level reached: {snapshot['level_name']}", (cx + 40, cy + 105), 0.6)
    draw_text(frame, f"Final score: {snapshot['score']}", (cx + 40, cy + 145), 0.65, (255, 230, 120))
    draw_text(frame, f"Total reps: {snapshot['total_reps']}", (cx + 40, cy + 180), 0.6)
    draw_text(frame, f"Best combo: {snapshot['best_combo']}", (cx + 40, cy + 215), 0.6)
    draw_text(frame, f"Max range of motion: {max_rom_angle:.0f} deg", (cx + 40, cy + 250), 0.6)
    draw_text(frame, "Press any key to exit", (cx + 130, cy + 305), 0.5, (180, 180, 180))

def altitude_to_y(angle_deg, frame_h, base=0.68, scale=0.5, max_angle=130):
    """
    Maps an abduction angle to a vertical screen position - shared by the
    phoenix mascot and the target orb so 'flying up to meet it' reads as
    one consistent altitude scale instead of two unrelated formulas.
    """
    t = max(0.0, min(1.0, angle_deg / max_angle))
    return int(frame_h * base - t * frame_h * scale)


def draw_target_orb(frame, target, phase, stability_progress, frame_w, frame_h):
    """Renders the current target as a glowing ember orb hovering at its
    altitude. Hidden during the banking phase (player is flying back down)."""
    if phase == "banking":
        return

    x = int(frame_w * 0.90)
    y = altitude_to_y(target["angle"], frame_h)

    pulse = 0.5 + 0.5 * math.sin(time.time() * 4)
    outer_r = int(34 + 6 * pulse)

    overlay = frame.copy()
    cv2.circle(overlay, (x, y), outer_r + 16, PALETTE["glow_aura"], -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.12, frame, 0.88, 0, frame)
    overlay = frame.copy()
    cv2.circle(overlay, (x, y), outer_r, PALETTE["wing_tip"], -1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

    cv2.circle(frame, (x, y), 14, PALETTE["eye"], -1, cv2.LINE_AA)
    cv2.circle(frame, (x, y), 6, (255, 255, 255), -1, cv2.LINE_AA)

    for i in range(3):
        a = time.time() * 1.5 + i * (2 * math.pi / 3)
        ex = x + int(26 * math.cos(a))
        ey = y + int(26 * math.sin(a))
        cv2.circle(frame, (ex, ey), 3, PALETTE["wing_outer"], -1, cv2.LINE_AA)

    if phase == "stability":
        end_angle = int(360 * stability_progress)
        cv2.ellipse(frame, (x, y), (outer_r + 10, outer_r + 10), -90, 0, end_angle, (80, 220, 100), 3, cv2.LINE_AA)

    label = target["name"]
    (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    draw_text(frame, label, (x - tw // 2, y + outer_r + 30), 0.5, (220, 220, 220))

def apply_vignette(frame, strength=0.45):
    """Darkens the frame edges so the player (center) stays clear while
    the corners fade into mood-setting shadow."""
    h, w = frame.shape[:2]
    Y, X = np.ogrid[:h, :w]
    cx, cy = w / 2, h / 2
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    max_dist = np.sqrt(cx ** 2 + cy ** 2)
    mask = np.clip(1 - (dist / max_dist), 0, 1) ** 1.5
    vignette = 1 - strength * (1 - mask)
    for c in range(3):
        frame[:, :, c] = (frame[:, :, c] * vignette).astype(np.uint8)
    return frame

def _pseudo_random(seed):
    """Deterministic pseudo-random float in [0,1) from a seed - lets each
    ember have a stable, unique drift pattern without needing saved state."""
    x = math.sin(seed * 12.9898) * 43758.5453
    return x - math.floor(x)


def draw_embers(frame, frame_w, frame_h, count=16):
    """Slow-drifting glowing embers for background atmosphere."""
    t = time.time()
    for i in range(count):
        speed = 18 + 14 * _pseudo_random(i * 3.1)
        x_base = frame_w * _pseudo_random(i * 7.7)
        phase = 6.28 * _pseudo_random(i * 2.3)
        size = 2.5 + 2.5 * _pseudo_random(i * 5.5)
        y = frame_h - ((t * speed + i * 137) % (frame_h + 40))
        x = x_base + 10 * math.sin(t * 0.5 + phase)
        flicker = 0.55 + 0.45 * math.sin(t * 3 + phase)
        color = PALETTE["wing_tip"] if i % 2 == 0 else PALETTE["wing_outer"]

        overlay = frame.copy()
        cv2.circle(overlay, (int(x), int(y)), int(size * 2.2), color, -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.18 * flicker, frame, 1 - 0.18 * flicker, 0, frame)

        overlay = frame.copy()
        cv2.circle(overlay, (int(x), int(y)), max(1, int(size)), color, -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.55 * flicker, frame, 1 - 0.55 * flicker, 0, frame)

def apply_color_grade(frame, tint_color=(90, 30, 60), strength=0.12):
    """Subtly tints the frame toward the dark mystical palette so the raw
    webcam colors feel like they belong in this world, without losing
    recognizability."""
    overlay = np.full_like(frame, tint_color)
    cv2.addWeighted(overlay, strength, frame, 1 - strength, 0, frame)
    return frame