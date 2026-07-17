"""
Phoenix Ascend - main entry point.

Controls:
  q  - quit and save session
  r  - reset current session (score/level reset) without restarting the app

Setup:
  pip install -r requirements.txt
  python main.py

Params (matches the payload sent by ExerciseModal's launchGame()):
  user_id        - Supabase user id
  recovery_id    - Supabase recovery/plan id
  side           - "L" or "R" (which arm to track). Falls back to
                   tracker.best_arm() if omitted / unrecognized.
  session_type   - "morning" | "evening" (informational, echoed back in result)
  current_week   - int, informational, echoed back in result

Returns:
  A JSON-serializable session_result dict on normal completion (mirrors the
  shape forgotten_orchestra.main() returns), so the Flask layer can hand it
  straight back to the frontend and onComplete()/Supabase can persist it.
  Returns None if the user quits from the start screen before a session
  ever begins (same as forgotten_orchestra's briefing-screen quit).
"""
import sys
import platform
import time
from datetime import datetime

import cv2

from . import config
from .pose_tracker import PoseTracker
from .game_engine import GameEngine
from .database import SessionLogger
from . import renderer
from .audio import AudioManager


def _select_arm(tracker, side):
    """Pick the arm to track based on the `side` param, falling back to
    tracker.best_arm() if side isn't specified/recognized or isn't visible."""
    arm = None
    if side == "L":
        arm = getattr(tracker, "left", None)
    elif side == "R":
        arm = getattr(tracker, "right", None)

    if arm is not None and getattr(arm, "visible", False):
        return arm
    return tracker.best_arm()


def main(params=None):
    params = params or {}
    user_id = params.get("user_id")
    recovery_id = params.get("recovery_id")
    side = params.get("side", "L")
    session_type = params.get("session_type", "morning")
    current_week = params.get("current_week", 1)

    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
    cap = cv2.VideoCapture(config.CAMERA_INDEX, backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

    if not cap.isOpened():
        print("ERROR: Could not open webcam. Check CAMERA_INDEX in config.py.")
        sys.exit(1)

    tracker = PoseTracker()

    # --- Start screen: let the player get positioned before the session begins ---
    while True:
        ok, frame = cap.read()
        if not ok:
            print("WARNING: Failed to read frame from webcam.")
            cap.release()
            tracker.close()
            return None
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        renderer.apply_vignette(frame)
        renderer.apply_color_grade(frame)
        renderer.draw_embers(frame, w, h)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        landmarks = tracker.process(rgb)
        ready = tracker.best_arm() is not None
        renderer.draw_skeleton(frame, landmarks)
        renderer.draw_start_screen(frame, ready)
        cv2.imshow("Phoenix Ascend", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            cap.release()
            cv2.destroyAllWindows()
            tracker.close()
            return None
        if key == ord(' ') and ready:
            break

    audio = AudioManager()
    audio.start_music()
    engine = GameEngine()
    logger = SessionLogger(user_id, recovery_id)
    logger.start_session()
    max_rom_angle = 0.0

    print("Phoenix Ascend running. Press 'q' to quit, 'r' to reset session.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("WARNING: Failed to read frame from webcam.")
                break

            frame = cv2.flip(frame, 1)  # mirror for natural movement
            h, w = frame.shape[:2]
            renderer.apply_vignette(frame)
            renderer.apply_color_grade(frame)
            renderer.draw_embers(frame, w, h)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            landmarks = tracker.process(rgb)

            # Faint skeleton overlay - useful while calibrating camera position
            renderer.draw_skeleton(frame, landmarks)
            renderer.draw_arm_wings(frame, landmarks, w, h)

            best = _select_arm(tracker, side)
            angle = best.angle if best else 0.0
            visible = best is not None
            max_rom_angle = max(max_rom_angle, angle)

            engine.update(angle, visible)
            for sound_key in engine.drain_pending_sounds():
                audio.play(sound_key)
            snapshot = engine.snapshot()

            renderer.draw_target_orb(frame, snapshot["target"], snapshot["phase"], snapshot["stability_progress"], w, h)

            phoenix_x = w // 2
            phoenix_y = renderer.altitude_to_y(angle, h)
            renderer.draw_phoenix(
                frame, phoenix_x, phoenix_y,
                tracker.left.angle if tracker.left.visible else 0,
                tracker.right.angle if tracker.right.visible else 0,
                snapshot["feedback_color"],
            )
            renderer.draw_hud(frame, snapshot)

            cv2.imshow("Phoenix Ascend", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                engine = GameEngine()
                max_rom_angle = 0.0

        # --- End screen: show session summary until a key is pressed ---
        snapshot = engine.snapshot()
        end_start = time.time()
        while time.time() - end_start < 15:  # auto-exit after 15s if no key pressed
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)
            renderer.draw_end_screen(frame, snapshot, max_rom_angle)
            cv2.imshow("Phoenix Ascend", frame)
            key = cv2.waitKey(1) & 0xFF
            if key != 255:
                break

    finally:
        logger.end_session(engine.snapshot(), max_rom_angle)
        logger.close()
        tracker.close()
        audio.close()
        cap.release()
        cv2.destroyAllWindows()

        final_snapshot = engine.snapshot()

        session_result = {
            "game": "phoenix_ascend",
            "session": {
                "user_id": user_id,
                "recovery_id": recovery_id,
                "side": side,
                "session_type": session_type,
                "week": current_week,
            },
            "completed": engine.total_reps >= 1,
            "objectives": [
                { "label": "Session Completed", "completed": engine.total_reps >= 1 }
            ],
            "metrics": [
                { "label": "Session Score", "value": engine.score, "unit": "" },
                { "label": "Level Reached", "value": final_snapshot["level_name"], "unit": "" },
                { "label": "Total Repetitions", "value": engine.total_reps, "unit": "" },
                { "label": "Best Combo", "value": engine.best_combo, "unit": "" },
                { "label": "Feathers Collected", "value": engine.feathers, "unit": "" },
                { "label": "Max ROM Achieved", "value": round(max_rom_angle, 1), "unit": "°" }
            ],
            "timestamp": datetime.now().isoformat(),
        }

        print(f"Session saved. Final score: {engine.score}, Max ROM: {max_rom_angle:.1f} deg")
        print(session_result)

        return session_result


if __name__ == "__main__":
    result = main()
    print("\nReturned Result:")
    print(result)