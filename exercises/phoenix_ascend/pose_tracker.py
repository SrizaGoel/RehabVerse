"""
Pose tracking + shoulder abduction/adduction angle extraction using
MediaPipe's Pose Landmarker (the current "Tasks" API).

IMPORTANT: Recent mediapipe releases (0.10.18+) removed the old
`mp.solutions.pose` interface entirely. This module uses the API that
`pip install mediapipe` actually ships today, which requires a separately
downloaded .task model file (handled automatically below on first run).
"""
import math
import os
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

from . import config
# Official Google-hosted model bundles for the Pose Landmarker task.
# "lite" is fastest / least accurate, "heavy" is slowest / most accurate.
MODEL_URLS = {
    "lite": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
    "full": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task",
    "heavy": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task",
}

# Classic MediaPipe landmark indices (unchanged across API versions)
LEFT_HIP, RIGHT_HIP = 23, 24
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_ELBOW, RIGHT_ELBOW = 13, 14


def ensure_model_downloaded(model_name="lite", dest_path=None):
    """
    Download the pose landmarker .task model file on first run if it isn't
    already present locally. Requires an internet connection the first time
    only; the file is cached afterwards.
    """
    dest_path = dest_path or (
    BASE_DIR / f"pose_landmarker_{model_name}.task"
)
    dest_path = str(dest_path)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        return dest_path

    url = MODEL_URLS[model_name]
    print(f"[Phoenix Ascend] Downloading pose model '{model_name}' (first run only)...")
    print(f"  {url}")
    try:
        urllib.request.urlretrieve(url, dest_path)
    except Exception as e:
        raise RuntimeError(
            "Could not auto-download the MediaPipe pose model.\n"
            f"Reason: {e}\n\n"
            "If your network blocks storage.googleapis.com (common on "
            "school/corporate Wi-Fi), download the file manually from:\n"
            f"  {url}\n"
            f"and save it as '{dest_path}' in this project folder, then "
            "run the program again."
        )
    print("[Phoenix Ascend] Model downloaded.")
    return dest_path


class SmoothedValue:
    """Exponential moving average smoother to reduce landmark jitter."""
    def __init__(self, alpha):
        self.alpha = alpha
        self.value = None

    def update(self, new_value):
        if self.value is None:
            self.value = new_value
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value
        return self.value


class ArmState:
    """Holds the latest tracked state for one arm (left or right)."""
    def __init__(self, side, alpha):
        self.side = side
        self.angle_smoother = SmoothedValue(alpha)
        self.angle = 0.0
        self.visible = False


def _vector_angle_deg(v1, v2):
    """Angle in degrees between two 2D vectors, range [0, 180]."""
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)
    if mag1 == 0 or mag2 == 0:
        return 0.0
    cos_angle = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cos_angle))


class LandmarkPoint:
    __slots__ = ("x", "y", "z", "visibility", "presence")
    def __init__(self, x, y, z, visibility, presence):
        self.x = x; self.y = y; self.z = z
        self.visibility = visibility; self.presence = presence


class LandmarkSmoother:
    """
    Applies an EMA filter to every landmark's x/y/z so the skeleton (and
    anything computed from it) doesn't visibly vibrate when the limb is
    actually still - MediaPipe's raw per-frame output has a few pixels of
    natural jitter even on a static pose.
    """
    def __init__(self, num_landmarks=33, alpha=config.LANDMARK_SMOOTHING_ALPHA):
        self.alpha = alpha
        self._smoothed = [None] * num_landmarks

    def update(self, raw_landmarks):
        if not raw_landmarks:
            return None
        out = []
        for i, lm in enumerate(raw_landmarks):
            prev = self._smoothed[i]
            if prev is None:
                sx, sy, sz = lm.x, lm.y, lm.z
            else:
                a = self.alpha
                sx = a * lm.x + (1 - a) * prev.x
                sy = a * lm.y + (1 - a) * prev.y
                sz = a * lm.z + (1 - a) * prev.z
            point = LandmarkPoint(sx, sy, sz, lm.visibility, lm.presence)
            self._smoothed[i] = point
            out.append(point)
        return out


class PoseTracker:
    """
    Wraps MediaPipe's PoseLandmarker task to provide shoulder abduction
    angles for both arms.

    Abduction angle definition:
        The angle between the torso vector (shoulder -> hip, i.e. "down",
        matching the direction a relaxed arm points) and the upper-arm
        vector (shoulder -> elbow), measured in the camera's 2D image plane.
            ~0 deg          = arm relaxed at the side
            ~90 deg         = arm raised straight out to the side
            ~150-180 deg    = arm raised overhead

    NOTE: this is a monocular 2D approximation, good enough for a
    front-facing gamified rehab exercise but NOT a clinical goniometer
    replacement. Camera should be roughly perpendicular to the player.
    """

    def __init__(self, model_name="lite"):
        model_path = ensure_model_downloaded(model_name)
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(options)
        self.landmark_smoother = LandmarkSmoother()
        self.left = ArmState("left", config.ANGLE_SMOOTHING_ALPHA)
        self.right = ArmState("right", config.ANGLE_SMOOTHING_ALPHA)
        self._timestamp_ms = 0
        self.last_landmarks = None  # flat list of 33 landmarks, or None

    def process(self, frame_rgb):
        """
        Run pose estimation on an RGB frame (HxWx3 uint8 numpy array) and
        update both arm states. Returns the flat landmark list (or None).
        """
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        # detect_for_video just needs a monotonically increasing timestamp;
        # it doesn't need to match a real clock.
        self._timestamp_ms += 33
        result = self.landmarker.detect_for_video(mp_image, self._timestamp_ms)

        raw_landmarks = result.pose_landmarks[0] if result.pose_landmarks else None
        landmarks = self.landmark_smoother.update(raw_landmarks)
        self.last_landmarks = landmarks

        self._update_arm(self.left, landmarks, LEFT_HIP, LEFT_SHOULDER, LEFT_ELBOW)
        self._update_arm(self.right, landmarks, RIGHT_HIP, RIGHT_SHOULDER, RIGHT_ELBOW)

        return landmarks

    def _update_arm(self, arm_state, landmarks, hip_idx, shoulder_idx, elbow_idx):
        if not landmarks:
            arm_state.visible = False
            return

        hip = landmarks[hip_idx]
        shoulder = landmarks[shoulder_idx]
        elbow = landmarks[elbow_idx]

        visibility_ok = min(hip.visibility, shoulder.visibility, elbow.visibility) > 0.5
        arm_state.visible = visibility_ok
        if not visibility_ok:
            return

        # Torso vector points DOWN (shoulder -> hip), matching the direction
        # a relaxed arm hangs in. This makes a resting arm read ~0 deg and
        # an overhead arm read ~180 deg, as intended.
        torso_vec = (hip.x - shoulder.x, hip.y - shoulder.y)
        arm_vec = (elbow.x - shoulder.x, elbow.y - shoulder.y)

        raw_angle = _vector_angle_deg(torso_vec, arm_vec)
        arm_state.angle = arm_state.angle_smoother.update(raw_angle)

    def best_arm(self):
        """Return whichever visible arm currently has the larger angle."""
        candidates = [a for a in (self.left, self.right) if a.visible]
        if not candidates:
            return None
        return max(candidates, key=lambda a: a.angle)

    def close(self):
        self.landmarker.close()
