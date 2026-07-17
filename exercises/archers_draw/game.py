"""Pure game logic for Archer's Draw: state machine, scoring, progression.

No cv2, no camera, no rendering - consumes smoothed single-arm elbow angles
and produces game state. Mirrors Tide Caller's game.py architecture closely
(same naming discipline: every per-frame handler is `_handle_*`, every flag
is `is_*`/`has_*`, so a handler and a flag can never collide under the same
name - a real bug hit once in the sibling project).

Angle convention: REST_ANGLE (~165 deg) = arm extended, bow lowered.
Drawing = elbow flexion = angle DECREASES. "draw depth" = REST_ANGLE minus
the current angle, so bigger depth = deeper draw = harder, keeping the same
"bigger number = more achievement" mental model as Tide Caller's ROM.

Gentle-draw design (mirrors Tide Caller's gentle-ripple philosophy): a draw
that never reaches full depth still scores as a shot (a WIDE) on release,
instead of aborting. Only a draw that never leaves the rest band returns to
IDLE without forming a shot at all.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np

from . import config


# =============================================================
# STATE MACHINE
# =============================================================
class ArrowState(Enum):
    INTRO = auto()             # story/mission screen, waiting for SPACE
    CALIBRATING = auto()       # finding a stable extended-arm stance
    IDLE = auto()               # arm extended, waiting to begin a draw
    DRAWING = auto()            # concentric: bending the elbow, drawing back
    HOLDING = auto()            # holding near full draw, arrow charging
    FULL_DRAW = auto()          # hold complete, shot fully drawn
    RELEASING = auto()          # eccentric: controlled return toward rest
    LANDING = auto()             # brief animation gate (arrow lands)
    ARROW_SCORED = auto()        # grade shown briefly, then back to IDLE
    PAUSED = auto()               # manual pause
    SESSION_COMPLETE = auto()     # arrow target or time cap reached
    RECORDS = auto()              # viewing session history


@dataclass
class FrameInput:
    """Immutable per-frame snapshot handed to the state machine."""
    pose_visible: bool
    angle: float
    now: float


@dataclass
class ShotRecord:
    """Buffers captured across one shot, consumed by ShotScorer."""
    drawing_angles: list = field(default_factory=list)
    hold_angles: list = field(default_factory=list)
    releasing_angles: list = field(default_factory=list)
    peak_depth: float = 0.0
    hold_duration: float = 0.0

    def reset(self) -> None:
        self.drawing_angles = []
        self.hold_angles = []
        self.releasing_angles = []
        self.peak_depth = 0.0
        self.hold_duration = 0.0


class GameStateMachine:
    """Drives ArrowState transitions from per-frame elbow-angle input."""

    LANDING_ANIMATION_SECONDS = 0.8
    SCORE_DISPLAY_SECONDS = 1.5

    def __init__(self, hold_seconds: float = 2.0) -> None:
        self.state: ArrowState = ArrowState.INTRO
        self.hold_seconds = hold_seconds
        self.record = ShotRecord()
        self.shot_ready: bool = False

        self._prev_state: ArrowState = ArrowState.INTRO
        self._draw_min_angle: float = config.REST_ANGLE
        self._hold_start_time: float | None = None
        self._landing_deadline: float = 0.0
        self._score_deadline: float = 0.0

        self._is_paused: bool = False
        self._pause_started_at: float = 0.0
        self.total_pause_seconds: float = 0.0

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    # ------------------------------------------------------------------
    def begin_calibration(self) -> None:
        if self.state == ArrowState.INTRO:
            self.state = ArrowState.CALIBRATING

    def pause(self, now: float) -> None:
        if not self._is_paused and self.state not in (
            ArrowState.INTRO, ArrowState.SESSION_COMPLETE, ArrowState.RECORDS
        ):
            self._is_paused = True
            self._pause_started_at = now
            self._prev_state = self.state
            self.state = ArrowState.PAUSED

    def resume(self, now: float) -> None:
        if self._is_paused:
            self._is_paused = False
            self.total_pause_seconds += now - self._pause_started_at
            self.state = self._prev_state

    def force_complete_session(self) -> None:
        self.state = ArrowState.SESSION_COMPLETE

    def enter_records(self) -> None:
        if self.state == ArrowState.SESSION_COMPLETE:
            self._prev_state = self.state
            self.state = ArrowState.RECORDS

    def leave_records(self) -> None:
        if self.state == ArrowState.RECORDS:
            self.state = ArrowState.SESSION_COMPLETE

    def start_new_session(self, hold_seconds: float) -> None:
        self.hold_seconds = hold_seconds
        self.record.reset()
        self._draw_min_angle = config.REST_ANGLE
        self._hold_start_time = None
        self.state = ArrowState.IDLE

    # ------------------------------------------------------------------
    def update(self, f: FrameInput) -> None:
        self.shot_ready = False
        if self._is_paused:
            return
        handler = _HANDLERS.get(self.state)
        if handler is not None:
            handler(self, f)

    # ------------------------------------------------------------------
    # PER-STATE HANDLERS
    # ------------------------------------------------------------------
    def _handle_calibrating(self, f: FrameInput) -> None:
        if f.pose_visible and f.angle >= config.REST_ANGLE - config.PEAK_BAND_DEG:
            self.state = ArrowState.IDLE

    def _handle_idle(self, f: FrameInput) -> None:
        if not f.pose_visible:
            return
        if f.angle <= config.DRAW_START_ANGLE:
            self.record.reset()
            self._draw_min_angle = f.angle
            self._hold_start_time = None
            self.state = ArrowState.DRAWING

    def _handle_drawing(self, f: FrameInput) -> None:
        self.record.drawing_angles.append(f.angle)
        self._draw_min_angle = min(self._draw_min_angle, f.angle)

        settled_near_deepest = f.angle <= self._draw_min_angle + config.PEAK_BAND_DEG
        if settled_near_deepest and f.angle <= config.DRAW_START_ANGLE:
            self._hold_start_time = f.now
            self.state = ArrowState.HOLDING
            return

        # Relaxed back to rest without ever really drawing: no shot forms.
        if f.angle >= config.DRAW_END_ANGLE and self._draw_min_angle > config.DRAW_START_ANGLE:
            self.state = ArrowState.IDLE

    def _handle_holding(self, f: FrameInput) -> None:
        self.record.hold_angles.append(f.angle)
        self._draw_min_angle = min(self._draw_min_angle, f.angle)

        left_peak_band = f.angle >= self._draw_min_angle + config.PEAK_BAND_DEG
        if left_peak_band:
            self._finalize_peak(f.now)
            self.state = ArrowState.RELEASING
            return

        held_for = f.now - (self._hold_start_time or f.now)
        if held_for >= self.hold_seconds:
            self.state = ArrowState.FULL_DRAW

    def _handle_full_draw(self, f: FrameInput) -> None:
        self.record.hold_angles.append(f.angle)
        self._draw_min_angle = min(self._draw_min_angle, f.angle)
        if f.angle >= self._draw_min_angle + config.PEAK_BAND_DEG:
            self._finalize_peak(f.now)
            self.state = ArrowState.RELEASING

    def _handle_releasing(self, f: FrameInput) -> None:
        self.record.releasing_angles.append(f.angle)
        if f.angle >= config.DRAW_END_ANGLE:
            self._landing_deadline = f.now + self.LANDING_ANIMATION_SECONDS
            self.state = ArrowState.LANDING

    def _handle_landing(self, f: FrameInput) -> None:
        if f.now >= self._landing_deadline:
            self.shot_ready = True
            self._score_deadline = f.now + self.SCORE_DISPLAY_SECONDS
            self.state = ArrowState.ARROW_SCORED

    def _handle_arrow_scored(self, f: FrameInput) -> None:
        if f.now >= self._score_deadline:
            self.state = ArrowState.IDLE

    # ------------------------------------------------------------------
    def _finalize_peak(self, now: float) -> None:
        self.record.peak_depth = config.REST_ANGLE - self._draw_min_angle
        if self._hold_start_time is not None:
            self.record.hold_duration = max(0.0, now - self._hold_start_time)

    def take_shot_record(self) -> ShotRecord:
        return self.record


_HANDLERS = {
    ArrowState.CALIBRATING: GameStateMachine._handle_calibrating,
    ArrowState.IDLE: GameStateMachine._handle_idle,
    ArrowState.DRAWING: GameStateMachine._handle_drawing,
    ArrowState.HOLDING: GameStateMachine._handle_holding,
    ArrowState.FULL_DRAW: GameStateMachine._handle_full_draw,
    ArrowState.RELEASING: GameStateMachine._handle_releasing,
    ArrowState.LANDING: GameStateMachine._handle_landing,
    ArrowState.ARROW_SCORED: GameStateMachine._handle_arrow_scored,
}


# =============================================================
# METRICS (pure math on angle buffers)
# =============================================================
def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def mean_jerk(angles) -> float:
    a = np.asarray(angles, dtype=float)
    if a.size < 4:
        return 0.0
    return float(np.mean(np.abs(np.diff(a, n=3))))


def smoothness_score(angles, jerk_max: float) -> float:
    return _clamp01(1.0 - mean_jerk(angles) / (jerk_max + 1e-8))


def stability_score(hold_angles, tolerance: float) -> float:
    a = np.asarray(hold_angles, dtype=float)
    if a.size < 2:
        return 1.0
    wobble = float(np.std(a))
    return _clamp01(1.0 - wobble / max(tolerance, 1e-8))


def depth_score(peak_depth: float, target_depth: float) -> float:
    if target_depth <= 0:
        return 0.0
    return _clamp01(peak_depth / target_depth)


# =============================================================
# SCORING
# =============================================================
@dataclass
class ShotScore:
    depth: float
    hold: float
    draw_smoothness: float
    release_smoothness: float
    total: int
    grade: str
    peak_depth: float


class ShotScorer:
    def __init__(self, target_draw_depth: float, hold_seconds: float,
                 stability_tolerance: float) -> None:
        self.target_draw_depth = target_draw_depth
        self.hold_seconds = hold_seconds
        self.stability_tolerance = stability_tolerance

    def score(self, record: ShotRecord) -> ShotScore:
        depth = depth_score(record.peak_depth, self.target_draw_depth)

        stability = stability_score(record.hold_angles, self.stability_tolerance)
        hold_factor = min(1.0, record.hold_duration / max(self.hold_seconds, 1e-8))
        hold = stability * hold_factor

        draw_smoothness = smoothness_score(record.drawing_angles, config.JERK_MAX_DRAW)
        release_smoothness = smoothness_score(record.releasing_angles, config.JERK_MAX_RELEASE)

        total = int(round(100.0 * (
            config.WEIGHT_DEPTH * depth
            + config.WEIGHT_HOLD * hold
            + config.WEIGHT_DRAW_SMOOTHNESS * draw_smoothness
            + config.WEIGHT_RELEASE_SMOOTHNESS * release_smoothness
        )))

        grade = self._grade(total, record.peak_depth)
        return ShotScore(depth, hold, draw_smoothness, release_smoothness,
                          total, grade, record.peak_depth)

    def _grade(self, total: int, peak_depth: float) -> str:
        if total <= config.GRADE_WIDE_MAX:
            return "WIDE"
        if total <= config.GRADE_INNER_MAX:
            return "INNER_RING"
        if total <= config.GRADE_BULLSEYE_MAX:
            return "BULLSEYE"
        if peak_depth >= config.DEEP_DRAW_BONUS_ANGLE:
            return "PERFECT_SHOT"
        return "BULLSEYE"


# =============================================================
# SESSION (one play session)
# =============================================================
@dataclass
class Session:
    target_draw_depth: float
    arrow_target: int
    time_limit: float = config.SESSION_TIME_CAP_SECONDS

    shots_done: int = 0
    clean_hits: int = 0
    wide_hits: int = 0
    best_score: int = 0
    session_max_depth: float = 0.0
    scores: list = field(default_factory=list)
    trophy_by_target: dict = field(default_factory=dict)  # {target_index: name}
    paused_seconds: float = 0.0

    _start_time: float = field(default_factory=time.time)

    def register_shot(self, score: ShotScore) -> None:
        self.scores.append(score)
        self.shots_done += 1
        self.best_score = max(self.best_score, score.total)
        self.session_max_depth = max(self.session_max_depth, score.peak_depth)
        if score.grade == "WIDE":
            self.wide_hits += 1
        else:
            self.clean_hits += 1

    def elapsed(self, now: float | None = None) -> float:
        raw = (now or time.time()) - self._start_time
        return max(0.0, raw - self.paused_seconds)

    def remaining(self, now: float | None = None) -> float:
        return self.time_limit - self.elapsed(now)

    def is_overtime(self, now: float | None = None) -> bool:
        return self.elapsed(now) > self.time_limit

    @property
    def targets_hit(self) -> int:
        return self.shots_done

    @property
    def progress_fraction(self) -> float:
        if self.arrow_target <= 0:
            return 1.0
        return min(1.0, self.shots_done / self.arrow_target)

    def is_complete(self, now: float | None = None) -> bool:
        """Arrow-target only: the timer is a soft, informational guide -
        running past it never force-ends the session."""
        return self.shots_done >= self.arrow_target


# =============================================================
# CAMPAIGN (day-indexed program progression + chapter/story unlock)
# =============================================================
@dataclass
class Campaign:
    recorded_max_depth: float = 0.0
    total_clears: int = 0
    chapter_index: int = 0

    day_number: int = 1
    streak: int = 1
    longest_streak: int = 1
    sessions_today: int = 0
    total_sessions_played: int = 0
    last_play_date: str | None = None

    @property
    def prescription(self) -> config.DayPrescription:
        return config.prescription_for_day(self.day_number)

    def sync_to_today(self, today_iso: str, missed_day_rollback_cap: int = 7) -> None:
        if self.last_play_date is None:
            self.last_play_date = today_iso
            self.sessions_today = 0
            return
        if self.last_play_date == today_iso:
            return

        from datetime import date
        try:
            last = date.fromisoformat(self.last_play_date)
            today = date.fromisoformat(today_iso)
            gap = (today - last).days
        except ValueError:
            gap = 1

        if gap == 1:
            self.day_number += 1
            self.streak += 1
            self.longest_streak = max(self.longest_streak, self.streak)
        elif gap > 1:
            rollback = min(gap - 1, missed_day_rollback_cap)
            self.day_number = max(1, self.day_number - rollback) + 1
            self.streak = 1

        self.last_play_date = today_iso
        self.sessions_today = 0

    def finish_session(self, session: Session) -> bool:
        """Fold results in; returns True if a new chapter just unlocked."""
        self.sessions_today += 1
        self.total_sessions_played += 1
        self.total_clears += session.targets_hit
        self.recorded_max_depth = max(self.recorded_max_depth, session.session_max_depth)
        before = self.chapter_index
        self._advance_chapter()
        return self.chapter_index > before

    def _advance_chapter(self) -> None:
        while (self.chapter_index < len(config.CHAPTERS) - 1
               and self.total_clears >= config.CHAPTERS[self.chapter_index].arrows_to_clear):
            self.chapter_index += 1

    @property
    def current_chapter(self) -> config.Chapter:
        return config.CHAPTERS[min(self.chapter_index, len(config.CHAPTERS) - 1)]

    def to_dict(self) -> dict:
        return {
            "recorded_max_depth": self.recorded_max_depth,
            "total_clears": self.total_clears,
            "chapter_index": self.chapter_index,
            "day_number": self.day_number,
            "streak": self.streak,
            "longest_streak": self.longest_streak,
            "sessions_today": self.sessions_today,
            "total_sessions_played": self.total_sessions_played,
            "last_play_date": self.last_play_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Campaign":
        return cls(
            recorded_max_depth=data.get("recorded_max_depth", 0.0),
            total_clears=data.get("total_clears", 0),
            chapter_index=data.get("chapter_index", 0),
            day_number=data.get("day_number", 1),
            streak=data.get("streak", 1),
            longest_streak=data.get("longest_streak", 1),
            sessions_today=data.get("sessions_today", 0),
            total_sessions_played=data.get("total_sessions_played", 0),
            last_play_date=data.get("last_play_date"),
        )
