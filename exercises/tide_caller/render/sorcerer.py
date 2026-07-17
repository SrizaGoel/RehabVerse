"""Player-body VFX: tide-magic energy overlay on the patient's arms."""
import cv2
import numpy as np
import math
import time


def draw_magic_circle(
    frame,
    center,
    radius=45,
    glow=1.0
):

    x, y = center

    overlay = frame.copy()
    pulse = 1.0 + 0.15 * math.sin(time.time() * 3)
    radius = int(radius * pulse)

    # glow rings

    for r in range(radius + 20, radius, -5):

        alpha = 0.03 * glow

        cv2.circle(
            overlay,
            (x, y),
            r,
            (255,255,255),
            -1
        )

        cv2.addWeighted(
            overlay,
            alpha,
            frame,
            1-alpha,
            0,
            frame
        )

    # outer ring

    cv2.circle(
        frame,
        (x,y),
        radius,
        (255,240,200),
        2
    )

    # inner ring

    cv2.circle(
        frame,
        (x, y),
        int(radius * 0.65),
        (255, 240, 200),
        1
    )

    # rotating spokes

    angle = time.time() * 35

    for i in range(12):

        a = math.radians(angle + i*45)

        x2 = int(x + radius * 0.8 * math.cos(a))
        y2 = int(y + radius * 0.8 * math.sin(a))

        cv2.line(
            frame,
            (x,y),
            (x2,y2),
            (255,220,180),
            1
        )

    # ==================================================
    # WATER ORB
    # ==================================================

    orb_radius = int(radius * 0.30)

    orb_overlay = frame.copy()

    for r in range(
        orb_radius + 12,
        orb_radius,
        -3
    ):

        cv2.circle(
            orb_overlay,
            (x, y),
            r,
            (255,180,80),
            -1
        )

        cv2.addWeighted(
            orb_overlay,
            0.05,
            frame,
            0.95,
            0,
            frame
        )

    cv2.circle(
        frame,
        (x, y),
        orb_radius,
        (255,160,40),
        -1
    )

    cv2.circle(
        frame,
        (x, y),
        int(orb_radius * 0.45),
        (255,255,220),
        -1
    )

    t = time.time()

    for i in range(6):

        a = t * 2.5 + i * (math.pi / 6)

        px = int(x + radius * 0.9 * math.cos(a))
        py = int(y + radius * 0.9 * math.sin(a))

        cv2.circle(
            frame,
            (px, py),
            6,
            (255,255,255),
            -1
        )

        cv2.circle(
            frame,
            (px, py),
            3,
            (255,200,120),
            -1
        )

def draw_energy_link(frame,left_center,right_center ):

    overlay = frame.copy()

    #cv2.line(
    #    overlay,
    #    left_center,
    #    right_center,
    #    (255,230,180),
    #    8
    #)

    cv2.addWeighted(
        overlay,
        0.12,
        frame,
        0.88,
        0,
        frame
    )

    #cv2.line(
    #    frame,
    #   left_center,
    #    right_center,
    #    (255,255,255),
    #    2
    #)

    offset = int(
        15 * math.sin(time.time() * 3)
    )

    mid_x = (left_center[0] + right_center[0]) // 2
    mid_y = (left_center[1] + right_center[1]) // 2 - offset

    pts = np.array([
        left_center,
        (mid_x, mid_y),
        right_center
    ], np.int32)

    cv2.polylines(
        frame,
        [pts],
        False,
        (255,240,200),
        3
    )

    cv2.polylines(
        frame,
        [pts],
        False,
        (255,255,255),
        1
    )

def draw_tide_orb(
    frame,
    left_center,
    right_center,
    charge_fraction
 ):

    cx = (left_center[0] + right_center[0]) // 2
    cy = (left_center[1] + right_center[1]) // 2
    float_y = int(
        15 * math.sin(time.time() * 2)
    )

    cy -= float_y
    radius = 20 + int(charge_fraction * 35)

    overlay = frame.copy()

    for r in range(radius + 25, radius, -4):

        cv2.circle(
            overlay,
            (cx, cy),
            r,
            (255,180,80),
            -1
        )

        cv2.addWeighted(
            overlay,
            0.04,
            frame,
            0.96,
            0,
            frame
        )

    cv2.circle(
        frame,
        (cx, cy),
        radius,
        (255,160,40),
        -1
    )

    cv2.circle(
        frame,
        (cx, cy),
        int(radius * 0.45),
        (255,255,220),
        -1
    )
    spirit_count = 4 + int(charge_fraction * 6)

    ring_angle = time.time() * 45

    for i in range(spirit_count):

        a = (
            ring_angle * 0.04
            + i * (2 * math.pi / spirit_count)
        )

        orbit_radius = radius + 20 + int(
            12 * math.sin(time.time() * 2 + i)
        )

        px = int(
            cx + orbit_radius * math.cos(a)
        )

        py = int(
            cy + orbit_radius * math.sin(a)
        )

        spirit_size = 4 + int(
            2 * math.sin(time.time() * 3 + i)
        )

        cv2.circle(
            frame,
            (px, py),
            spirit_size,
            (255,255,255),
            -1
        )

        cv2.circle(
            frame,
            (px, py),
            max(1, spirit_size - 2),
            (255,220,180),
            -1
        )