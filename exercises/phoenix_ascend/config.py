"""
Phoenix Ascend - Configuration & Constants
Tune these values to adjust difficulty, sensitivity, and game balance.
"""

# ---------- Camera / Pose Detection ----------
CAMERA_INDEX = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
MIN_DETECTION_CONFIDENCE = 0.6
MIN_TRACKING_CONFIDENCE = 0.6

# ---------- Angle Measurement ----------
# Tolerance windows used to score how close the player's arm is to a target
GREEN_TOLERANCE_DEG = 7       # "Correct" - full reward
YELLOW_TOLERANCE_DEG = 18     # "Partial" - reduced reward
# Anything beyond YELLOW_TOLERANCE_DEG is "Red" - incorrect / off target

# Smoothing factor for the angle signal (exponential moving average, 0-1)
# Lower = smoother but more lag, higher = more responsive but jittery
ANGLE_SMOOTHING_ALPHA = 0.35

# Smooths raw landmark x/y/z before anything (skeleton, angle calc, wing
# overlay) uses them - prevents visible vibration on a still limb.
LANDMARK_SMOOTHING_ALPHA = 0.25

# ---------- Target Orbs (Phase 1: Energy Collection) ----------
ORB_TARGETS = [
    {"name": "Low-altitude Orb",  "angle": 30,  "points": 10, "feathers": 1},
    {"name": "Mid-altitude Orb",  "angle": 60,  "points": 20, "feathers": 2},
    {"name": "High-altitude Orb", "angle": 90,  "points": 35, "feathers": 3},
    {"name": "Legendary Orb",     "angle": 120, "points": 60, "feathers": 5},
]

# ---------- Stability Challenge (Phase 2) ----------
STABILITY_HOLD_SECONDS = 3.0
STABILITY_TOLERANCE_DEG = 10

# ---------- Energy Banking (Phase 3) ----------
ADDUCTION_BANK_ANGLE = 15      # arm must drop below this angle to "bank" energy
BASE_BANK_MULTIPLIER = 1.0
COMBO_MULTIPLIER_STEP = 0.1    # multiplier added per combo tier reached

# ---------- Levels ----------
LEVELS = [
    {"id": 1, "name": "Hatchling Phoenix", "min_angle": 0, "max_angle": 45,  "reps_to_advance": 8},
    {"id": 2, "name": "Young Phoenix",     "min_angle": 0, "max_angle": 90,  "reps_to_advance": 12},
    {"id": 3, "name": "Sky Guardian",      "min_angle": 0, "max_angle": 120, "reps_to_advance": 16},
    {"id": 4, "name": "Eternal Phoenix",   "min_angle": 0, "max_angle": 150, "reps_to_advance": 999999},
]

# ---------- Combo System ----------
COMBO_TIERS = [
    {"reps": 5,  "name": "Flame Combo"},
    {"reps": 10, "name": "Solar Combo"},
    {"reps": 20, "name": "Legendary Phoenix Combo"},
]

# ---------- Database ----------
DB_PATH = "phoenix_ascend.db"
