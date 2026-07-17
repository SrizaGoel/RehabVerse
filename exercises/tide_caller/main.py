"""Tide Caller entry point.

Game loop: webcam capture -> bilateral pose detection -> smoothed angles ->
state machine -> per-wave scoring -> day-prescription progression -> render
-> audio -> log.

Run from the repo root with:
    python -m exercises.tide_caller.main

Controls:
    SPACE  begin (from intro)     E  end session       P  pause
    R      resume / play again    T  view records      B  back (from records)
    Esc    quit

Bilateral tracking: both arms are measured as the hip-shoulder-elbow angle
(shoulder abduction). Each side is smoothed with its own moving average; the
state machine works on the average of the two, while symmetry compares them.

Difficulty is NOT computed from performance - each calendar day of the
program has a fixed, pre-decided prescription (config.prescription_for_day),
shown to the patient on the intro screen before they start. Campaign state
(program day, streak, chapter/story unlock) persists to progress_state.json
via progress_store, so it survives across app restarts.

Params (matches the payload sent by ExerciseModal's launchGame()):
    user_id        - Supabase user id
    recovery_id    - Supabase recovery/plan id
    session_type   - "morning" | "evening" (informational, echoed back)
    current_week   - int, informational, echoed back (this game schedules
                     by day_number/prescription, not by week)

Returns:
    A JSON-serializable session_result dict on exit (whether the session
    was formally completed via wave-target/'e', or the player quit early
    with Esc) - previously main() had no return statement at all, so the
    Flask layer / onComplete() had nothing to hand to Supabase for this
    game, unlike every other exercise module.
"""
from __future__ import annotations
import time
from collections import deque
from datetime import date, datetime
import cv2
import mediapipe as mp
import numpy as np
from . import config
from .audio import AudioManager
from .game import Campaign, FrameInput, GameStateMachine, Session, TideState, WaveScorer
from .renderer import TideRenderer
from . import progress_store
from . import session_log

mp_pose = mp.solutions.pose


def _angle(a, b, c) -> float:
    """Angle at b formed by points a-b-c, in degrees."""
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba, bc = a - b, c - b
    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def _abduction(landmarks, side: str) -> float | None:
    """Shoulder-abduction angle for one side (hip-shoulder-elbow)."""
    L = mp_pose.PoseLandmark
    idx = {
        "left": (L.LEFT_HIP, L.LEFT_SHOULDER, L.LEFT_ELBOW),
        "right": (L.RIGHT_HIP, L.RIGHT_SHOULDER, L.RIGHT_ELBOW),
    }[side]
    pts = [landmarks[i.value] for i in idx]
    if any(p.visibility < 0.5 for p in pts):
        return None
    hip, shoulder, elbow = ([p.x, p.y] for p in pts)
    return _angle(hip, shoulder, elbow)


def _wrist_point(lm, wrist_idx, index_idx, pinky_idx) -> tuple:
    """Average of wrist/index/pinky landmarks -> a stable fingertip-ish point."""
    w, i, p = lm[wrist_idx], lm[index_idx], lm[pinky_idx]
    return (
        int((w.x + i.x + p.x) / 3 * config.FRAME_WIDTH),
        int((w.y + i.y + p.y) / 3 * config.FRAME_HEIGHT),
    )


def _new_session(campaign: Campaign) -> tuple[Session, WaveScorer]:
    """Build a fresh Session + WaveScorer from today's fixed prescription."""
    rx = campaign.prescription
    session = Session(
        target_rom=rx.target_rom,
        wave_target=rx.wave_target,
        time_limit=rx.time_limit_seconds,
    )
    scorer = WaveScorer(rx.target_rom, rx.hold_seconds, rx.stability_tolerance)
    return session, scorer


def _save_progress(campaign: Campaign) -> None:
    progress_store.save_state(campaign.to_dict())


def _build_session_result(campaign, session, session_finished, user_id, recovery_id,
                           session_type, current_week):
    """Shared by both exit paths (formal completion and Esc quit) so the
    Flask layer / Supabase always gets something back for this game."""
    waves_met = session.waves_done >= session.wave_target
    return {
        "game": "tide_caller",
        "session": {
            "user_id": user_id,
            "recovery_id": recovery_id,
            "session_type": session_type,
            "week": current_week,  # standardize on week to match other games
            "day_number": campaign.day_number,
            "streak": campaign.streak,
            "chapter_index": campaign.chapter_index,
            "chapter_name": campaign.current_chapter.name,
        },
        "completed": bool(session_finished),
        "objectives": [
            { "label": "Wave Target Cleared", "completed": bool(waves_met) }
        ],
        "metrics": [
            { "label": "Target ROM", "value": session.target_rom, "unit": "°" },
            { "label": "Max ROM Achieved", "value": round(session.session_max_rom, 1), "unit": "°" },
            { "label": "Waves Cleared", "value": session.waves_done, "unit": "" },
            { "label": "Wave Target", "value": session.wave_target, "unit": "" },
            { "label": "Clean Clears", "value": session.clean_clears, "unit": "" },
            { "label": "Murky Clears", "value": session.murky_clears, "unit": "" },
            { "label": "Best Wave Score", "value": session.best_score, "unit": "" },
            { "label": "Session Duration", "value": round(session.elapsed(), 1), "unit": "s" }
        ],
        "timestamp": datetime.now().isoformat(),
    }


def main(params=None):
    params = params or {}
    user_id = params.get("user_id")
    recovery_id = params.get("recovery_id")
    session_type = params.get("session_type", "morning")
    current_week = params.get("current_week", 1)

    if user_id and recovery_id:
        progress_store.set_user(user_id, recovery_id)
        session_log.set_user(user_id, recovery_id)

    pose = mp_pose.Pose(
        min_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
    )

    audio = AudioManager()
    if audio.missing_files:
        print("[tide_caller] running without these audio files (optional):")
        for f in audio.missing_files:
            print("   -", f)

    campaign = Campaign.from_dict(progress_store.load_state())
    campaign.sync_to_today(date.today().isoformat())
    _save_progress(campaign)  # persist the day/streak advance immediately

    session, scorer = _new_session(campaign)
    rx = campaign.prescription
    machine = GameStateMachine(hold_seconds=rx.hold_seconds)
    renderer = TideRenderer()

    left_hist: deque = deque(maxlen=config.ROM_HISTORY_LEN)
    right_hist: deque = deque(maxlen=config.ROM_HISTORY_LEN)

    last_score = None
    prev_state = machine.state
    first_wave_announced = False
    first_tsunami_announced = False
    left_wrist = None
    right_wrist = None
    records_data = None
    session_finished = False

    cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
    cv2.namedWindow(config.WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(config.WINDOW_NAME, config.FRAME_WIDTH, config.FRAME_HEIGHT)

    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))
            frame = cv2.flip(frame, 1)
            now = time.time()

            # --- keep the session timer in sync with total pause time ---
            session.paused_seconds = machine.total_pause_seconds

            # --- pose / bilateral angles ---
            # Skip the (expensive) pose model entirely on screens that never
            # use its output - menu screens don't need bilateral angles, and
            # this is the single heaviest step in the whole frame loop.
            pose_visible = False
            left_angle = right_angle = avg_angle = 0.0
            needs_pose = not machine.is_paused and machine.state not in (
                TideState.SPLASH, TideState.INTRO, TideState.SESSION_COMPLETE, TideState.RECORDS,
            )
            if needs_pose:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(rgb)
                if results.pose_landmarks:
                    lm = results.pose_landmarks.landmark
                    la = _abduction(lm, "left")
                    ra = _abduction(lm, "right")
                    L = mp_pose.PoseLandmark
                    left_wrist = _wrist_point(lm, L.LEFT_WRIST.value, L.LEFT_INDEX.value, L.LEFT_PINKY.value)
                    right_wrist = _wrist_point(lm, L.RIGHT_WRIST.value, L.RIGHT_INDEX.value, L.RIGHT_PINKY.value)

                    if la is not None:
                        left_hist.append(la)
                    if ra is not None:
                        right_hist.append(ra)
                    if left_hist and right_hist:
                        pose_visible = True
                        left_angle = sum(left_hist) / len(left_hist)
                        right_angle = sum(right_hist) / len(right_hist)
                        avg_angle = (left_angle + right_angle) / 2.0

            # --- advance state machine ---
            machine.update(FrameInput(pose_visible, left_angle, right_angle, avg_angle, now))

            # --- audio cues on state entry ---
            if machine.state != prev_state:
                cue = {
                    TideState.RISING: "rise",
                    TideState.CHARGING: "magic_water",
                    TideState.CHARGED: "charged",
                    TideState.WASHING: "crash",
                }.get(machine.state)
                if cue:
                    audio.play(cue)
                prev_state = machine.state

            # --- a wave just completed: score it ---
            if machine.wave_ready:
                last_score = scorer.score(machine.take_wave_record())
                patch_index = session.waves_done  # index this wave will occupy
                session.register_wave(last_score)
                if last_score.grade != "RIPPLE":
                    session.artifact_by_patch[patch_index] = config.artifact_name_for(
                        campaign.current_chapter.key, patch_index
                    )
                audio.play_for_grade(last_score.grade)
                audio.play("reveal")
                if not first_wave_announced:
                    audio.play("first_wave")
                    first_wave_announced = True
                if last_score.grade == "TSUNAMI" and not first_tsunami_announced:
                    audio.play("first_tsunami")
                    first_tsunami_announced = True

                if session.is_complete(now):
                    unlocked = campaign.finish_session(session)
                    session_log.log_session(session, campaign)
                    _save_progress(campaign)
                    session_finished = True
                    machine.force_complete_session()
                    audio.play("session_complete")
                    audio.play("coast_restored")
                    if unlocked:
                        audio.play("chapter")

            # --- charge fraction for the renderer (foam pulse) ---
            charge_fraction = 0.0
            if machine.state in (TideState.CHARGING, TideState.CHARGED):
                rec = machine.record
                if rec.hold_angles:
                    held = now - (machine._hold_start_time or now)
                    charge_fraction = min(1.0, held / machine.hold_seconds)

            # --- symmetry % for HUD ---
            delta = abs(left_angle - right_angle)
            symmetry_pct = max(0.0, 1.0 - delta / config.SYMMETRY_TOLERANCE_DEG) * 100

            # --- render ---
            renderer.render(
                frame,
                state=machine.state,
                avg_angle=avg_angle,
                left_angle=left_angle,
                right_angle=right_angle,
                symmetry_pct=symmetry_pct,
                session=session,
                campaign=campaign,
                left_wrist=left_wrist,
                right_wrist=right_wrist,
                last_score=last_score,
                charge_fraction=charge_fraction,
                records_data=records_data,
            )
            cv2.imshow(config.WINDOW_NAME, frame)

            # --- input ---
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" ") and machine.state == TideState.SPLASH:
                machine.leave_splash()

            elif key == ord(" ") and machine.state == TideState.INTRO:
                machine.begin_calibration()
                audio.play("session_started")

            elif key == ord("r") and machine.state == TideState.SESSION_COMPLETE:
                session, scorer = _new_session(campaign)
                machine.start_new_session(hold_seconds=campaign.prescription.hold_seconds)
                last_score = None
                first_wave_announced = False
                first_tsunami_announced = False
                session_finished = False
                prev_state = machine.state
                audio.play("session_started")

            elif key == ord("t") and machine.state == TideState.SESSION_COMPLETE:
                records_data = session_log.load_records()
                machine.enter_records()

            elif key == ord("b") and machine.state == TideState.RECORDS:
                machine.leave_records()

            elif key == ord("e") and machine.state not in (
                TideState.INTRO, TideState.SESSION_COMPLETE,
                TideState.PAUSED, TideState.RECORDS,
            ):
                unlocked = campaign.finish_session(session)
                session_log.log_session(session, campaign)
                _save_progress(campaign)
                session_finished = True
                machine.force_complete_session()
                audio.play("session_complete")
                audio.play("coast_restored")
                if unlocked:
                    audio.play("chapter")

            elif key == ord("p"):
                machine.pause(now)
                audio.play("pause")
                audio.pause_ambience()

            elif key == ord("r") and machine.is_paused:
                machine.resume(time.time())
                audio.play("resume")
                audio.resume_ambience()

            elif key == 27:  # Esc
                break
    finally:
        _save_progress(campaign)
        cap.release()
        cv2.destroyAllWindows()
        audio.stop()

    session_result = _build_session_result(
        campaign, session, session_finished, user_id, recovery_id,
        session_type, current_week,
    )
    print(f"Session saved. Waves: {session.waves_done}/{session.wave_target}, "
          f"Best score: {session.best_score}, Day {campaign.day_number}, "
          f"Streak {campaign.streak} ({'completed' if session_finished else 'quit early'})")
    return session_result


if __name__ == "__main__":
    result = main()
    print("\nReturned Result:")
    print(result)