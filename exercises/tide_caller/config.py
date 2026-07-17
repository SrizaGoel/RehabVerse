"""All tunable constants and chapter/level data for Tide Caller.

Single source of truth: window/camera settings, ROM thresholds, scoring
weights, colors, and the chapter (level) list with each chapter's
difficulty + visual theme. Nothing else in the game hardcodes numbers.

Angles are in DEGREES (shoulder abduction). Colors are BGR tuples (cv2).
"""

from __future__ import annotations
from dataclasses import dataclass

# =============================================================
# WINDOW / CAMERA
# =============================================================
WINDOW_NAME = "RehabVerse - Tide Caller"
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
CAMERA_INDEX = 0

# =============================================================
# POSE / DETECTION
# =============================================================
MIN_DETECTION_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5
ROM_HISTORY_LEN = 10  # smoothing window for the moving average

# =============================================================
# ROM THRESHOLDS (shoulder abduction angle, degrees)
# =============================================================
REST_ANGLE = 25          # arm at side
RISE_UP = 50             # crossing this latches "rising"
RISE_DOWN = 35           # dropping below this latches "back at rest"
WAVE_MIN_ANGLE = 70       # below this peak -> RIPPLE tier
TSUNAMI_ANGLE = 120       # at/above this peak -> TSUNAMI eligible
PEAK_BAND_DEG = 10.0      # "still near peak" tolerance while charging

# =============================================================
# SCORING WEIGHTS (sum to 1.0)
# =============================================================
WEIGHT_ROM = 0.25
WEIGHT_HOLD = 0.20
WEIGHT_ECCENTRIC = 0.25
WEIGHT_CONCENTRIC = 0.15
WEIGHT_SYMMETRY = 0.15

GRADE_RIPPLE_MAX = 40
GRADE_WAVE_MAX = 65
GRADE_BREAKER_MAX = 85
# above GRADE_BREAKER_MAX + TSUNAMI_ANGLE peak -> TSUNAMI

JERK_MAX_ECCENTRIC = 6.0
JERK_MAX_CONCENTRIC = 9.0
SYMMETRY_TOLERANCE_DEG = 25.0

# =============================================================
# DISPLAY SMOOTHING
# =============================================================
TIDE_SMOOTHING_PREV = 0.92
TIDE_SMOOTHING_TARGET = 0.08

# =============================================================
# SESSION / PROGRESSIVE OVERLOAD (campaign-wide defaults)
# =============================================================
SESSION_TIME_CAP_SECONDS = 15 * 60
OVERLOAD_TARGET_FACTOR = 0.90
OVERLOAD_STEP_DEG = 3.0
MAX_SAFE_ROM_DEG = 150.0  # clinical ceiling; never auto-escalate past this

# =============================================================
# BASE COLOR PALETTE (BGR) - used by menu/HUD chrome, not the ocean/beach
# (those come from the current chapter's palette below)
# =============================================================
COL_FOAM = (245, 245, 240)
COL_TEXT = (245, 245, 245)
COL_HUD_BG = (30, 22, 14)
COL_HUD_ACCENT = (220, 180, 90)
COL_NEON_BLUE = (255, 190, 70)
COL_NEON_GLOW = (255, 225, 150)
COL_SEA_GREEN = (110, 190, 80)
COL_PANEL_FILL = (48, 30, 16)
COL_RUNE = (200, 220, 255)
COL_DARKNESS = (40, 30, 35)
COL_DARKNESS_MURKY = (70, 60, 70)
COL_SHORE_SUNSET = (70, 140, 255)

GRADE_COLORS = {
    "RIPPLE": (200, 200, 200),
    "WAVE": (200, 180, 90),
    "BREAKER": (90, 220, 120),
    "TSUNAMI": (70, 140, 255),
}

# =============================================================
# CHAPTERS / LEVELS
# =============================================================
@dataclass(frozen=True)
class Chapter:
    """One coastal zone: visual theme + story only.

    Difficulty (target ROM, hold time, wave count, timer) no longer lives
    here - it comes from the day-indexed clinical prescription below, so a
    patient's difficulty tracks their program day, not which chapter they're
    currently unlocking. waves_to_clear still gates the chapter/story unlock
    (effort-based, never score-based).
    """
    key: str
    name: str
    story: str
    waves_to_clear: int
    col_deep: tuple
    col_shallow: tuple
    col_sand: tuple


CHAPTERS: list[Chapter] = [
    Chapter("shallows", "The Shallows",
            "The first tides return to a forgotten coast.",
            waves_to_clear=30,
            col_deep=(90, 50, 15), col_shallow=(200, 180, 90),
            col_sand=(130, 200, 235)),
    Chapter("tide_pools", "Tide Pools",
            "Sea creatures stir awake in the cleared pools.",
            waves_to_clear=40,
            col_deep=(80, 70, 10), col_shallow=(150, 190, 80),
            col_sand=(120, 190, 150)),
    Chapter("reef", "The Reef",
            "Color floods back as the coral revives.",
            waves_to_clear=50,
            col_deep=(120, 60, 20), col_shallow=(180, 160, 230),
            col_sand=(150, 210, 255)),
    Chapter("market", "Sunken Market",
            "Artifacts of a lost civilization surface.",
            waves_to_clear=60,
            col_deep=(60, 90, 120), col_shallow=(120, 180, 220),
            col_sand=(100, 180, 230)),
    Chapter("lighthouse", "The Lighthouse",
            "Relight the beacon and guide the ships home.",
            waves_to_clear=70,
            col_deep=(70, 50, 30), col_shallow=(160, 150, 120),
            col_sand=(140, 150, 160)),
    Chapter("the_deep", "The Deep",
            "Confront the source of the darkness below.",
            waves_to_clear=80,
            col_deep=(40, 20, 10), col_shallow=(90, 70, 40),
            col_sand=(60, 70, 80)),
    Chapter("dawn_coast", "Dawn Coast",
            "The coastline is whole again. Dawn breaks.",
            waves_to_clear=90,
            col_deep=(80, 90, 180), col_shallow=(140, 180, 255),
            col_sand=(160, 200, 255)),
]


# =============================================================
# DAY-INDEXED CLINICAL PRESCRIPTION (fixed progression, not adaptive)
# =============================================================
@dataclass(frozen=True)
class DayPrescription:
    """What today's session asks of the patient - decided in advance, shown
    on the intro screen before they start. Not recalculated from performance;
    the same day always prescribes the same targets."""
    day: int
    target_rom: float
    hold_seconds: float
    wave_target: int
    stability_tolerance: float
    time_limit_seconds: float


def _build_day_program() -> list[DayPrescription]:
    """Fixed 30-day curve, four weekly phases, linearly interpolated between
    anchor points and then held at the Day-30 (maintenance) level forever
    after. A clinician can hand-edit specific days in the resulting list
    later; this generator just avoids typing thirty near-duplicate lines.

    Anchors (day -> target_rom, hold_s, wave_target, stability_tol, time_min):
      Day 1  (Foundation):    60 deg, 1.0s hold,  6 waves, 12 deg tol,  8 min
      Day 8  (Building):      80 deg, 1.5s hold,  8 waves, 10 deg tol, 10 min
      Day 15 (Progressing):   95 deg, 2.0s hold, 10 waves,  8 deg tol, 12 min
      Day 22 (Advanced):     110 deg, 2.5s hold, 12 waves,  7 deg tol, 13 min
      Day 30 (Maintenance):  120 deg, 3.0s hold, 13 waves,  6 deg tol, 15 min
    """
    anchors = [
        (1, 60.0, 1.00, 6, 12.0, 8),
        (8, 80.0, 1.50, 8, 10.0, 10),
        (15, 95.0, 2.00, 10, 8.0, 12),
        (22, 110.0, 2.50, 12, 7.0, 13),
        (30, 120.0, 3.00, 13, 6.0, 15),
    ]
    program: list[DayPrescription] = []
    for day in range(1, 31):
        # find the two surrounding anchors and linearly interpolate
        for (d0, r0, h0, w0, s0, t0), (d1, r1, h1, w1, s1, t1) in zip(anchors, anchors[1:]):
            if d0 <= day <= d1:
                frac = 0.0 if d1 == d0 else (day - d0) / (d1 - d0)
                program.append(DayPrescription(
                    day=day,
                    target_rom=round(r0 + (r1 - r0) * frac, 1),
                    hold_seconds=round(h0 + (h1 - h0) * frac, 2),
                    wave_target=round(w0 + (w1 - w0) * frac),
                    stability_tolerance=round(s0 + (s1 - s0) * frac, 1),
                    time_limit_seconds=round((t0 + (t1 - t0) * frac) * 60, 0),
                ))
                break
    return program


DAY_PROGRAM: list[DayPrescription] = _build_day_program()


def prescription_for_day(day_number: int) -> DayPrescription:
    """Day 1..30 map directly; Day 31+ holds at the Day-30 maintenance level
    (never auto-escalates past the clinically reviewed ceiling)."""
    idx = min(max(day_number, 1), len(DAY_PROGRAM)) - 1
    return DAY_PROGRAM[idx]

# =============================================================
# ARTIFACT NAMES (discovery/collection flavor per chapter)
# =============================================================
# A clean-cleared wave (grade above RIPPLE) reveals an artifact on its beach
# patch. Names cycle by patch index within the chapter's list, so they're
# deterministic and repeatable rather than random.
ARTIFACT_NAMES: dict[str, list[str]] = {
    "shallows": ["Sea Glass Shard", "Driftwood Rune", "Tide-Worn Coin",
                 "Barnacle Cluster", "Sand Dollar", "Broken Compass Needle"],
    "tide_pools": ["Anemone Charm", "Hermit Crab Shell", "Kelp-Wrapped Bead",
                   "Starfish Fragment", "Pool-Glass Marble"],
    "reef": ["Coral Fragment", "Pearl of the Reef", "Reef Shark Tooth",
             "Sea Fan Piece", "Clownfish Charm"],
    "market": ["Sunken Ledger Page", "Bronze Amulet", "Merchant's Seal",
               "Cracked Urn", "Silver Trade Coin", "Chest Key"],
    "lighthouse": ["Beacon Lens Shard", "Captain's Compass", "Ship's Bell",
                   "Keeper's Log Page", "Signal Flag Remnant"],
    "the_deep": ["Abyssal Shard", "Anchor Chain Link", "Deep Current Stone",
                 "Bioluminescent Pearl", "Forgotten Figurehead"],
    "dawn_coast": ["Dawn Medallion", "Horizon Shell", "Sunrise Prism",
                   "First Light Feather", "Coast Emblem"],
}
DEFAULT_ARTIFACT_NAMES = ["Ocean Relic", "Tide-Worn Fragment", "Coastal Keepsake"]


def artifact_name_for(chapter_key: str, patch_index: int) -> str:
    """Deterministic artifact name for a given chapter + cleared-patch index."""
    names = ARTIFACT_NAMES.get(chapter_key, DEFAULT_ARTIFACT_NAMES)
    return names[patch_index % len(names)]
