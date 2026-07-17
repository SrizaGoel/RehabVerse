"""Archer's Draw backend: camera + MediaPipe + GameStateMachine, streamed to
the browser UI over a local WebSocket.

Python owns the camera and all game logic (state machine, scoring, day
progression, persistence). The browser only renders what it's told and
sends back key commands (SPACE/E/P/R/T/B) - it never computes game state
itself, mirroring the same "Python owns the truth" design as Tide Caller.

Frame JPEGs are only included in the payload during actual gameplay states
(mirrors Tide Caller's fix: skip the camera/pose feed and its cost on menu
screens that never show it).
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from datetime import date

import cv2
import mediapipe as mp
import numpy as np
import websockets
import websockets.exceptions

from . import config
from . import progress_store
from . import session_log
from .game import (
    ArrowState, Campaign, FrameInput, GameStateMachine, Session, ShotScorer,
)

mp_pose = mp.solutions.pose

WS_HOST = "localhost"
WS_PORT = 8765
JPEG_QUALITY = 70
TARGET_FPS = 30

_MENU_STATES = (ArrowState.INTRO, ArrowState.SESSION_COMPLETE, ArrowState.RECORDS)


def _angle(a, b, c) -> float:
    a, b, c = np.array(a), np.array(b), np.array(c)
    ba, bc = a - b, c - b
    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


class FrameSource:
    """Wraps the camera + MediaPipe elbow tracking, with a synthetic
    fallback when no camera is available."""

    def __init__(self, arm: str = config.TRACKED_ARM) -> None:
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)
        self.use_camera = self.cap.isOpened()
        if not self.use_camera:
            self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
            self.use_camera = self.cap.isOpened()
        if not self.use_camera:
            print("[archers_draw] no camera found - using a synthetic test pattern")

        self.arm = arm
        self.pose = mp_pose.Pose(
            min_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE,
        ) if self.use_camera else None

        self._t0 = time.time()
        self._last_angle = float(config.REST_ANGLE)
        self._visible = False

    def read(self, track: bool = True):
        """Return a frame. If track=True (gameplay states), also runs pose
        detection and updates current_angle()/pose_visible(). If track=False
        (menu states), returns the frame without touching MediaPipe at all -
        this is the expensive step, and menu screens never show the feed."""
        if self.use_camera:
            ok, frame = self.cap.read()
            if ok:
                frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))
                frame = cv2.flip(frame, 1)
                return self._track_elbow(frame) if track else frame
        return self._synthetic_frame()

    def _track_elbow(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)
        if not results.pose_landmarks:
            self._visible = False
            return frame

        lm = results.pose_landmarks.landmark
        L = mp_pose.PoseLandmark
        idx = ((L.RIGHT_SHOULDER, L.RIGHT_ELBOW, L.RIGHT_WRIST) if self.arm == "right"
               else (L.LEFT_SHOULDER, L.LEFT_ELBOW, L.LEFT_WRIST))
        pts = [lm[i.value] for i in idx]
        if any(p.visibility < 0.5 for p in pts):
            self._visible = False
            return frame

        h, w = frame.shape[:2]
        px = [(int(p.x * w), int(p.y * h)) for p in pts]
        self._last_angle = _angle(px[0], px[1], px[2])
        self._visible = True

        cv2.line(frame, px[0], px[1], (80, 220, 255), 4)
        cv2.line(frame, px[1], px[2], (80, 220, 255), 4)
        for p in px:
            cv2.circle(frame, p, 8, (255, 255, 255), -1)
            cv2.circle(frame, p, 8, (80, 220, 255), 2)
        cv2.circle(frame, px[1], 16, (80, 180, 255), 2)

        return frame

    def _synthetic_frame(self):
        frame = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)
        frame[:] = (40, 30, 20)
        t = time.time() - self._t0
        depth_swing = 60 + 55 * (0.5 + 0.5 * np.sin(t * 0.6))
        self._last_angle = config.REST_ANGLE - depth_swing
        self._visible = True
        cx = int(config.FRAME_WIDTH / 2)
        cy = int(config.FRAME_HEIGHT / 2 + depth_swing)
        cv2.circle(frame, (cx, cy), 40, (80, 180, 255), -1)
        cv2.putText(frame, "SYNTHETIC TEST FEED (no camera)", (30, 40),
                    cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)
        return frame

    def current_angle(self) -> float:
        return round(float(self._last_angle), 1)

    def pose_visible(self) -> bool:
        return self._visible

    def release(self) -> None:
        if self.use_camera:
            self.cap.release()
        if self.pose is not None:
            self.pose.close()


def _screen_for(state: ArrowState) -> str:
    if state == ArrowState.INTRO:
        return "intro"
    if state == ArrowState.SESSION_COMPLETE:
        return "summary"
    if state == ArrowState.RECORDS:
        return "records"
    return "gameplay"


def _new_session(campaign: Campaign):
    rx = campaign.prescription
    session = Session(target_draw_depth=rx.target_draw_depth,
                       arrow_target=rx.arrow_target,
                       time_limit=rx.time_limit_seconds)
    scorer = ShotScorer(rx.target_draw_depth, rx.hold_seconds, rx.stability_tolerance)
    return session, scorer


def _score_to_dict(score) -> dict:
    return {
        "depth": score.depth, "hold": score.hold,
        "draw_smoothness": score.draw_smoothness,
        "release_smoothness": score.release_smoothness,
        "total": score.total, "grade": score.grade,
        "peak_depth": score.peak_depth,
    }


def _session_to_dict(session: Session) -> dict:
    return {
        "target_draw_depth": session.target_draw_depth,
        "arrow_target": session.arrow_target,
        "time_limit": session.time_limit,
        "shots_done": session.shots_done,
        "clean_hits": session.clean_hits,
        "wide_hits": session.wide_hits,
        "best_score": session.best_score,
        "session_max_depth": session.session_max_depth,
        "trophy_count": len(session.trophy_by_target),
        "trophy_by_target": {str(k): v for k, v in session.trophy_by_target.items()},
        "progress_fraction": session.progress_fraction,
        "elapsed": session.elapsed(),
        "remaining": session.remaining(),
        "is_overtime": session.is_overtime(),
    }


def _campaign_to_dict(campaign: Campaign) -> dict:
    chapter = campaign.current_chapter
    return {
        "day_number": campaign.day_number,
        "streak": campaign.streak,
        "sessions_today": campaign.sessions_today,
        "total_clears": campaign.total_clears,
        "chapter_index": campaign.chapter_index,
        "chapter_name": chapter.name,
        "chapter_story": chapter.story,
        "chapter_key": chapter.key,
        "chapter_arrows_to_clear": chapter.arrows_to_clear,
        "prescription": {
            "target_draw_depth": campaign.prescription.target_draw_depth,
            "hold_seconds": campaign.prescription.hold_seconds,
            "arrow_target": campaign.prescription.arrow_target,
            "time_limit_seconds": campaign.prescription.time_limit_seconds,
        },
    }


async def handle_client(websocket) -> None:
    print("[archers_draw] client connected")
    campaign = Campaign.from_dict(progress_store.load_state())
    campaign.sync_to_today(date.today().isoformat())
    progress_store.save_state(campaign.to_dict())

    session, scorer = _new_session(campaign)
    rx = campaign.prescription
    machine = GameStateMachine(hold_seconds=rx.hold_seconds)
    source = FrameSource()

    last_score = None
    records_data = None
    command_queue: asyncio.Queue = asyncio.Queue()

    async def receiver():
        try:
            async for raw in websocket:
                try:
                    await command_queue.put(json.loads(raw))
                except Exception:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass

    receiver_task = asyncio.create_task(receiver())

    try:
        while True:
            now = time.time()
            session.paused_seconds = machine.total_pause_seconds

            # --- drain pending key commands from the browser ---
            while not command_queue.empty():
                cmd = command_queue.get_nowait()
                key = cmd.get("key") if isinstance(cmd, dict) else None

                if key == "space" and machine.state == ArrowState.INTRO:
                    machine.begin_calibration()

                elif key == "r" and machine.state == ArrowState.SESSION_COMPLETE:
                    session, scorer = _new_session(campaign)
                    machine.start_new_session(hold_seconds=campaign.prescription.hold_seconds)
                    last_score = None

                elif key == "t" and machine.state == ArrowState.SESSION_COMPLETE:
                    records_data = session_log.load_records()
                    machine.enter_records()

                elif key == "b" and machine.state == ArrowState.RECORDS:
                    machine.leave_records()

                elif key == "e" and machine.state not in (
                    ArrowState.INTRO, ArrowState.SESSION_COMPLETE,
                    ArrowState.PAUSED, ArrowState.RECORDS,
                ):
                    campaign.finish_session(session)
                    session_log.log_session(session, campaign)
                    progress_store.save_state(campaign.to_dict())
                    machine.force_complete_session()

                elif key == "p":
                    machine.pause(now)

                elif key == "r" and machine.is_paused:
                    machine.resume(time.time())

            # --- pose / angle (skip the expensive step on menu screens) ---
            needs_pose = not machine.is_paused and machine.state not in _MENU_STATES
            frame = source.read(track=needs_pose)
            angle = source.current_angle() if needs_pose else 0.0
            visible = source.pose_visible() if needs_pose else False

            # --- advance state machine ---
            machine.update(FrameInput(visible, angle, now))

            # --- a shot just completed: score it ---
            if machine.shot_ready:
                score = scorer.score(machine.take_shot_record())
                target_index = session.shots_done
                session.register_shot(score)
                if score.grade != "WIDE":
                    session.trophy_by_target[target_index] = config.trophy_name_for(
                        campaign.current_chapter.key, target_index
                    )
                last_score = score

                if session.is_complete(now):
                    campaign.finish_session(session)
                    session_log.log_session(session, campaign)
                    progress_store.save_state(campaign.to_dict())
                    machine.force_complete_session()

            # --- charge fraction (draw progress ring) ---
            charge_fraction = 0.0
            if machine.state in (ArrowState.HOLDING, ArrowState.FULL_DRAW):
                if machine._hold_start_time is not None:
                    held = now - machine._hold_start_time
                    charge_fraction = min(1.0, held / machine.hold_seconds)

            # --- build payload ---
            payload = {
                "type": "state",
                "screen": _screen_for(machine.state),
                "arrow_state": machine.state.name,
                "elbow_angle": angle,
                "draw_depth": max(0.0, config.REST_ANGLE - angle) if visible else 0.0,
                "pose_visible": visible,
                "charge_fraction": charge_fraction,
                "session": _session_to_dict(session),
                "campaign": _campaign_to_dict(campaign),
                "last_score": _score_to_dict(last_score) if last_score else None,
                "records_data": records_data,
            }

            if machine.state not in _MENU_STATES:
                ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if ok:
                    payload["jpeg_b64"] = base64.b64encode(buf).decode("ascii")

            await websocket.send(json.dumps(payload))
            await asyncio.sleep(1 / TARGET_FPS)
    except websockets.exceptions.ConnectionClosed:
        print("[archers_draw] client disconnected")
    finally:
        receiver_task.cancel()
        source.release()


async def main() -> None:
    print(f"[archers_draw] WebSocket server on ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(handle_client, WS_HOST, WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
