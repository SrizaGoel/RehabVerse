"""All tunable constants and day/chapter data for Archer's Draw.

Single-arm elbow flexion/extension exercise (shoulder-elbow-wrist angle).
Mirrors Tide Caller's config.py structure closely, adapted for a single
tracked arm instead of bilateral shoulder abduction.

Angle convention: arm extended (rest / bow lowered) reads close to
REST_ANGLE (~165 deg). Drawing the bow = elbow flexion = the angle
DECREASES as the arm bends. "draw depth" = REST_ANGLE - current_angle, so
bigger draw depth = deeper draw = harder, same mental model as Tide
Caller's target_rom (bigger = more achievement).
"""

from __future__ import annotations
from dataclasses import dataclass

# =============================================================
# WINDOW / CAMERA
# =============================================================
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
CAMERA_INDEX = 0
TRACKED_ARM = "right"  # "right" or "left"

# =============================================================
# POSE / DETECTION
# =============================================================
MIN_DETECTION_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5
ANGLE_HISTORY_LEN = 10  # smoothing window for the moving average

# =============================================================
# ELBOW ANGLE THRESHOLDS (degrees)
# =============================================================
REST_ANGLE = 165          # arm extended - bow lowered
DRAW_START_ANGLE = 140    # crossing below this (from rest) latches "drawing"
DRAW_END_ANGLE = 150      # rising back above this latches "back at rest"
PEAK_BAND_DEG = 8.0        # "still near full draw" tolerance while holding
MIN_DRAW_DEPTH = 35.0      # a draw shallower than this never really drew - RISK gentle floor still applies on release though

# =============================================================
# SCORING WEIGHTS (sum to 1.0)
# Release (eccentric / controlled return) weighted highest - the clinically
# most valuable phase, same philosophy as Tide Caller's eccentric weighting.
# =============================================================
WEIGHT_DEPTH = 0.30
WEIGHT_HOLD = 0.20
WEIGHT_DRAW_SMOOTHNESS = 0.20      # concentric (pulling back)
WEIGHT_RELEASE_SMOOTHNESS = 0.30   # eccentric (controlled return) - most important

GRADE_WIDE_MAX = 40
GRADE_INNER_MAX = 65
GRADE_BULLSEYE_MAX = 85
# above GRADE_BULLSEYE_MAX + deep-draw tier reached -> PERFECT SHOT

JERK_MAX_DRAW = 9.0        # concentric smoothness ceiling
JERK_MAX_RELEASE = 6.0     # eccentric smoothness ceiling (stricter)

# Top grade (PERFECT SHOT) requires reaching this absolute draw depth, on
# top of a high score band - so it can't be earned by gaming the smoothness
# metrics with a shallow draw. Mirrors Tide Caller's TSUNAMI_ANGLE gate.
DEEP_DRAW_BONUS_ANGLE = 70.0

# =============================================================
# DISPLAY SMOOTHING
# =============================================================
BOWSTRING_SMOOTHING_PREV = 0.90
BOWSTRING_SMOOTHING_TARGET = 0.10

# =============================================================
# SESSION DEFAULTS
# =============================================================
SESSION_TIME_CAP_SECONDS = 15 * 60

# =============================================================
# ARTIFACT / REWARD NAMES (target hits reveal a trophy, archery-themed)
# =============================================================
TROPHY_NAMES: dict[str, list[str]] = {
    "training_yard": ["Practice Arrow", "Straw Target Badge", "Novice Quiver"],
    "forest_range": ["Fletched Feather", "Hunter's Token", "Oakwood Bow Charm"],
    "mountain_pass": ["Wind-Reader's Medal", "Stone Target Shard", "Eagle Feather"],
    "castle_walls": ["Guard Captain's Seal", "Iron Arrowhead", "Banner Fragment"],
    "royal_tournament": ["Champion's Laurel", "Golden Arrowhead", "King's Favor"],
}
DEFAULT_TROPHY_NAMES = ["Archer's Trophy", "Range Medal", "Bowyer's Token"]


def trophy_name_for(chapter_key: str, target_index: int) -> str:
    names = TROPHY_NAMES.get(chapter_key, DEFAULT_TROPHY_NAMES)
    return names[target_index % len(names)]


# =============================================================
# CHAPTERS (visual/story theme only - see Campaign for day-based difficulty)
# =============================================================
@dataclass(frozen=True)
class Chapter:
    key: str
    name: str
    story: str
    arrows_to_clear: int  # cumulative arrows (across campaign) to unlock next
    col_accent: tuple     # BGR-ish theme accent, if/when a renderer needs it


CHAPTERS: list[Chapter] = [
    Chapter("training_yard", "The Training Yard",
            "A quiet yard behind the old barracks, arrows and morning mist.",
            arrows_to_clear=30, col_accent=(180, 200, 140)),
    Chapter("forest_range", "Forest Range",
            "Sunlight through the trees, targets hidden among the leaves.",
            arrows_to_clear=40, col_accent=(90, 170, 90)),
    Chapter("mountain_pass", "Mountain Pass",
            "Thin air and shifting wind test every draw.",
            arrows_to_clear=50, col_accent=(180, 160, 140)),
    Chapter("castle_walls", "Castle Walls",
            "Arrow slits and banners - the garrison is watching.",
            arrows_to_clear=60, col_accent=(140, 140, 170)),
    Chapter("royal_tournament", "Royal Tournament",
            "The final range, crowds waiting on the last arrow.",
            arrows_to_clear=70, col_accent=(80, 180, 230)),
]


# =============================================================
# DAY-INDEXED CLINICAL PRESCRIPTION (fixed progression, not adaptive)
# =============================================================
@dataclass(frozen=True)
class DayPrescription:
    """What today's session asks of the patient, decided in advance.

    target_draw_depth: how many degrees of elbow flexion from REST_ANGLE
    the patient is asked to reach (bigger = deeper draw = harder).
    """
    day: int
    target_draw_depth: float
    hold_seconds: float
    arrow_target: int
    stability_tolerance: float
    time_limit_seconds: float


def _build_day_program() -> list[DayPrescription]:
    """Fixed 30-day curve, four weekly phases, linearly interpolated between
    anchor points and held at the Day-30 (maintenance) level afterward.

    Anchors (day -> draw_depth, hold_s, arrows, stability_tol, time_min):
      Day 1  (Foundation):    30 deg, 1.0s hold,  6 arrows, 12 deg tol,  8 min
      Day 8  (Building):      45 deg, 1.5s hold,  8 arrows, 10 deg tol, 10 min
      Day 15 (Progressing):   60 deg, 2.0s hold, 10 arrows,  8 deg tol, 12 min
      Day 22 (Advanced):      75 deg, 2.5s hold, 12 arrows,  7 deg tol, 13 min
      Day 30 (Maintenance):   90 deg, 3.0s hold, 13 arrows,  6 deg tol, 15 min
    """
    anchors = [
        (1, 30.0, 1.00, 6, 12.0, 8),
        (8, 45.0, 1.50, 8, 10.0, 10),
        (15, 60.0, 2.00, 10, 8.0, 12),
        (22, 75.0, 2.50, 12, 7.0, 13),
        (30, 90.0, 3.00, 13, 6.0, 15),
    ]
    program: list[DayPrescription] = []
    for day in range(1, 31):
        for (d0, dep0, h0, a0, s0, t0), (d1, dep1, h1, a1, s1, t1) in zip(anchors, anchors[1:]):
            if d0 <= day <= d1:
                frac = 0.0 if d1 == d0 else (day - d0) / (d1 - d0)
                program.append(DayPrescription(
                    day=day,
                    target_draw_depth=round(dep0 + (dep1 - dep0) * frac, 1),
                    hold_seconds=round(h0 + (h1 - h0) * frac, 2),
                    arrow_target=round(a0 + (a1 - a0) * frac),
                    stability_tolerance=round(s0 + (s1 - s0) * frac, 1),
                    time_limit_seconds=round((t0 + (t1 - t0) * frac) * 60, 0),
                ))
                break
    return program


DAY_PROGRAM: list[DayPrescription] = _build_day_program()


def prescription_for_day(day_number: int) -> DayPrescription:
    idx = min(max(day_number, 1), len(DAY_PROGRAM)) - 1
    return DAY_PROGRAM[idx]
