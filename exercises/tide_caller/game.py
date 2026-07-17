"""Pure game logic for Tide Caller: state machine, scoring, progression.

No cv2, no camera, no rendering - this module only consumes numbers (smoothed
shoulder-abduction angles) and produces game state. Kept dependency-light
(numpy only) and fully unit-testable in isolation from the render/main loop.

Gentle-ripple design: a rise that never reaches WAVE_MIN_ANGLE still forms a
wave (a RIPPLE) on the way down, instead of aborting. Only a rise that never
leaves the rest band returns to IDLE without forming anything - this game
targets pain and anxiety patients, so "nothing happened" is never the result
of a genuine attempt.

Naming note: every per-frame state handler is prefixed `_handle_*` and every
boolean flag is prefixed `is_*`/`has_*`, specifically so a handler method and
a state flag can never collide under the same name (a real bug from the
previous version of this file, where a `_charged` flag silently overwrote a
`_charged` handler method once a wave finished charging).
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
class TideState(Enum):
    SPLASH = auto()             # static title/lore screen, waiting for SPACE
    INTRO = auto()             # story/mission screen, waiting for SPACE
    CALIBRATING = auto()       # finding a stable neutral stance
    IDLE = auto()               # arms at side, waiting to begin a wave
    RISING = auto()             # concentric: raising both arms
    CHARGING = auto()           # holding near peak, wave swelling
    CHARGED = auto()            # hold complete, wave fully formed
    LOWERING = auto()           # eccentric: lowering arms, wave crashing
    WASHING = auto()            # foam sweeps the beach (brief animation gate)
    WAVE_SCORED = auto()        # grade shown briefly, then back to IDLE
    PAUSED = auto()              # manual pause
    SESSION_COMPLETE = auto()    # wave target or time cap reached
    RECORDS = auto()             # viewing session history


@dataclass
class FrameInput:
    """Immutable per-frame snapshot handed to the state machine."""
    pose_visible: bool
    left_angle: float
    right_angle: float
    avg_angle: float
    now: float


@dataclass
class WaveRecord:
    """Buffers captured across one wave, consumed by WaveScorer."""
    rising_angles: list = field(default_factory=list)
    rising_left: list = field(default_factory=list)
    rising_right: list = field(default_factory=list)
    hold_angles: list = field(default_factory=list)
    lowering_angles: list = field(default_factory=list)
    lowering_left: list = field(default_factory=list)
    lowering_right: list = field(default_factory=list)
    peak_angle: float = 0.0
    hold_duration: float = 0.0

    def reset(self) -> None:
        self.rising_angles = []
        self.rising_left = []
        self.rising_right = []
        self.hold_angles = []
        self.lowering_angles = []
        self.lowering_left = []
        self.lowering_right = []
        self.peak_angle = 0.0
        self.hold_duration = 0.0


class GameStateMachine:
    """Drives TideState transitions from per-frame pose input.

    Usage (per frame):
        machine.update(frame_input)
        if machine.wave_ready:
            record = machine.take_wave_record()
            score = scorer.score(record)
    """

    WASH_ANIMATION_SECONDS = 0.8
    SCORE_DISPLAY_SECONDS = 1.5

    def __init__(self, hold_seconds: float = 2.0) -> None:
        self.state: TideState = TideState.SPLASH
        self.hold_seconds = hold_seconds
        self.record = WaveRecord()
        self.wave_ready: bool = False

        self._prev_state: TideState = TideState.SPLASH
        self._rise_peak: float = 0.0
        self._hold_start_time: float | None = None
        self._wash_deadline: float = 0.0
        self._score_deadline: float = 0.0

        self._is_paused: bool = False
        self._pause_started_at: float = 0.0
        self.total_pause_seconds: float = 0.0

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    # ------------------------------------------------------------------
    def leave_splash(self) -> None:
        """SPLASH -> INTRO, triggered externally by a SPACE press."""
        if self.state == TideState.SPLASH:
            self.state = TideState.INTRO

    def begin_calibration(self) -> None:
        """INTRO -> CALIBRATING, triggered externally by a SPACE press."""
        if self.state == TideState.INTRO:
            self.state = TideState.CALIBRATING

    def pause(self, now: float) -> None:
        if not self._is_paused and self.state not in (
            TideState.SPLASH, TideState.INTRO, TideState.SESSION_COMPLETE, TideState.RECORDS
        ):
            self._is_paused = True
            self._pause_started_at = now
            self._prev_state = self.state
            self.state = TideState.PAUSED

    def resume(self, now: float) -> None:
        if self._is_paused:
            self._is_paused = False
            self.total_pause_seconds += now - self._pause_started_at
            self.state = self._prev_state

    def force_complete_session(self) -> None:
        self.state = TideState.SESSION_COMPLETE

    def enter_records(self) -> None:
        if self.state == TideState.SESSION_COMPLETE:
            self._prev_state = self.state
            self.state = TideState.RECORDS

    def leave_records(self) -> None:
        if self.state == TideState.RECORDS:
            self.state = TideState.SESSION_COMPLETE

    def start_new_session(self, hold_seconds: float) -> None:
        """Reset into a fresh session, keeping calibration (skip straight
        to IDLE - the patient is already positioned)."""
        self.hold_seconds = hold_seconds
        self.record.reset()
        self._rise_peak = 0.0
        self._hold_start_time = None
        self.state = TideState.IDLE

    # ------------------------------------------------------------------
    def update(self, f: FrameInput) -> None:
        self.wave_ready = False
        if self._is_paused:
            return

        handler = _HANDLERS.get(self.state)
        if handler is not None:
            handler(self, f)

    # ------------------------------------------------------------------
    # PER-STATE HANDLERS (all pure, all prefixed _handle_ to avoid any
    # possible collision with a data attribute of the same name)
    # ------------------------------------------------------------------
    def _handle_calibrating(self, f: FrameInput) -> None:
        if f.pose_visible and f.avg_angle <= config.REST_ANGLE + config.PEAK_BAND_DEG:
            self.state = TideState.IDLE

    def _handle_idle(self, f: FrameInput) -> None:
        if not f.pose_visible:
            return
        if f.avg_angle >= config.RISE_UP:
            self.record.reset()
            self._rise_peak = f.avg_angle
            self._hold_start_time = None
            self.state = TideState.RISING

    def _handle_rising(self, f: FrameInput) -> None:
        self.record.rising_angles.append(f.avg_angle)
        self.record.rising_left.append(f.left_angle)
        self.record.rising_right.append(f.right_angle)
        self._rise_peak = max(self._rise_peak, f.avg_angle)

        settled_near_peak = f.avg_angle >= self._rise_peak - config.PEAK_BAND_DEG
        if settled_near_peak and f.avg_angle >= config.RISE_UP:
            self._hold_start_time = f.now
            self.state = TideState.CHARGING
            return

        # Dropped back to rest without ever really rising: no wave forms.
        if f.avg_angle < config.RISE_DOWN and self._rise_peak < config.RISE_UP:
            self.state = TideState.IDLE

    def _handle_charging(self, f: FrameInput) -> None:
        self.record.hold_angles.append(f.avg_angle)
        self._rise_peak = max(self._rise_peak, f.avg_angle)

        left_peak_band = f.avg_angle < self._rise_peak - config.PEAK_BAND_DEG
        if left_peak_band:
            self._finalize_peak(f.now)
            self.state = TideState.LOWERING
            return

        held_for = f.now - (self._hold_start_time or f.now)
        if held_for >= self.hold_seconds:
            self.state = TideState.CHARGED

    def _handle_charged(self, f: FrameInput) -> None:
        self.record.hold_angles.append(f.avg_angle)
        self._rise_peak = max(self._rise_peak, f.avg_angle)
        if f.avg_angle < self._rise_peak - config.PEAK_BAND_DEG:
            self._finalize_peak(f.now)
            self.state = TideState.LOWERING

    def _handle_lowering(self, f: FrameInput) -> None:
        self.record.lowering_angles.append(f.avg_angle)
        self.record.lowering_left.append(f.left_angle)
        self.record.lowering_right.append(f.right_angle)
        if f.avg_angle <= config.RISE_DOWN:
            self._wash_deadline = f.now + self.WASH_ANIMATION_SECONDS
            self.state = TideState.WASHING

    def _handle_washing(self, f: FrameInput) -> None:
        if f.now >= self._wash_deadline:
            self.wave_ready = True
            self._score_deadline = f.now + self.SCORE_DISPLAY_SECONDS
            self.state = TideState.WAVE_SCORED

    def _handle_wave_scored(self, f: FrameInput) -> None:
        if f.now >= self._score_deadline:
            self.state = TideState.IDLE

    # ------------------------------------------------------------------
    def _finalize_peak(self, now: float) -> None:
        self.record.peak_angle = self._rise_peak
        if self._hold_start_time is not None:
            self.record.hold_duration = max(0.0, now - self._hold_start_time)

    def take_wave_record(self) -> WaveRecord:
        return self.record


_HANDLERS = {
    TideState.CALIBRATING: GameStateMachine._handle_calibrating,
    TideState.IDLE: GameStateMachine._handle_idle,
    TideState.RISING: GameStateMachine._handle_rising,
    TideState.CHARGING: GameStateMachine._handle_charging,
    TideState.CHARGED: GameStateMachine._handle_charged,
    TideState.LOWERING: GameStateMachine._handle_lowering,
    TideState.WASHING: GameStateMachine._handle_washing,
    TideState.WAVE_SCORED: GameStateMachine._handle_wave_scored,
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


def symmetry_score(left, right) -> float:
    l = np.asarray(left, dtype=float)
    r = np.asarray(right, dtype=float)
    n = min(l.size, r.size)
    if n == 0:
        return 1.0
    mean_delta = float(np.mean(np.abs(l[:n] - r[:n])))
    return _clamp01(1.0 - mean_delta / config.SYMMETRY_TOLERANCE_DEG)


def stability_score(hold_angles, tolerance: float) -> float:
    a = np.asarray(hold_angles, dtype=float)
    if a.size < 2:
        return 1.0
    wobble = float(np.std(a))
    return _clamp01(1.0 - wobble / max(tolerance, 1e-8))


def rom_score(peak_angle: float, target_angle: float) -> float:
    if target_angle <= 0:
        return 0.0
    return _clamp01(peak_angle / target_angle)


# =============================================================
# SCORING
# =============================================================
@dataclass
class WaveScore:
    rom: float
    hold: float
    eccentric: float
    concentric: float
    symmetry: float
    total: int
    grade: str
    peak_angle: float

    @property
    def color(self):
        return config.GRADE_COLORS.get(self.grade, config.COL_TEXT)


class WaveScorer:
    def __init__(self, target_rom: float, hold_seconds: float,
                 stability_tolerance: float) -> None:
        self.target_rom = target_rom
        self.hold_seconds = hold_seconds
        self.stability_tolerance = stability_tolerance

    def score(self, record: WaveRecord) -> WaveScore:
        rom = rom_score(record.peak_angle, self.target_rom)

        stability = stability_score(record.hold_angles, self.stability_tolerance)
        hold_factor = min(1.0, record.hold_duration / max(self.hold_seconds, 1e-8))
        hold = stability * hold_factor

        eccentric = smoothness_score(record.lowering_angles, config.JERK_MAX_ECCENTRIC)
        concentric = smoothness_score(record.rising_angles, config.JERK_MAX_CONCENTRIC)

        left = list(record.rising_left) + list(record.lowering_left)
        right = list(record.rising_right) + list(record.lowering_right)
        symmetry = symmetry_score(left, right)

        total = int(round(100.0 * (
            config.WEIGHT_ROM * rom
            + config.WEIGHT_HOLD * hold
            + config.WEIGHT_ECCENTRIC * eccentric
            + config.WEIGHT_CONCENTRIC * concentric
            + config.WEIGHT_SYMMETRY * symmetry
        )))

        grade = self._grade(total, record.peak_angle)
        return WaveScore(rom, hold, eccentric, concentric, symmetry,
                          total, grade, record.peak_angle)

    def _grade(self, total: int, peak_angle: float) -> str:
        if total <= config.GRADE_RIPPLE_MAX:
            return "RIPPLE"
        if total <= config.GRADE_WAVE_MAX:
            return "WAVE"
        if total <= config.GRADE_BREAKER_MAX:
            return "BREAKER"
        if peak_angle >= config.TSUNAMI_ANGLE:
            return "TSUNAMI"
        return "BREAKER"


# =============================================================
# SESSION (one play session)
# =============================================================
@dataclass
class Session:
    target_rom: float
    wave_target: int
    time_limit: float = config.SESSION_TIME_CAP_SECONDS

    waves_done: int = 0
    clean_clears: int = 0
    murky_clears: int = 0
    best_score: int = 0
    session_max_rom: float = 0.0
    scores: list = field(default_factory=list)
    artifact_by_patch: dict = field(default_factory=dict)  # {patch_index: artifact_name}
    paused_seconds: float = 0.0  # kept in sync from GameStateMachine.total_pause_seconds

    _start_time: float = field(default_factory=time.time)

    def register_wave(self, score: WaveScore) -> None:
        self.scores.append(score)
        self.waves_done += 1
        self.best_score = max(self.best_score, score.total)
        self.session_max_rom = max(self.session_max_rom, score.peak_angle)
        if score.grade == "RIPPLE":
            self.murky_clears += 1
        else:
            self.clean_clears += 1

    def elapsed(self, now: float | None = None) -> float:
        """Wall-clock time spent actually playing - time spent paused is
        excluded, so pausing never eats into the session timer."""
        raw = (now or time.time()) - self._start_time
        return max(0.0, raw - self.paused_seconds)

    def remaining(self, now: float | None = None) -> float:
        """Seconds left on the clock. Can go negative once overtime -
        callers use is_overtime() rather than clamping this to zero, so the
        overtime amount stays visible."""
        return self.time_limit - self.elapsed(now)

    def is_overtime(self, now: float | None = None) -> bool:
        return self.elapsed(now) > self.time_limit

    @property
    def patches_cleared(self) -> int:
        return self.waves_done

    @property
    def progress_fraction(self) -> float:
        if self.wave_target <= 0:
            return 1.0
        return min(1.0, self.waves_done / self.wave_target)

    def is_complete(self, now: float | None = None) -> bool:
        """Wave-target only: the timer is a soft, informational guide (per
        product decision) - running past it never force-ends the session.
        The patient can always end early with E if they choose to stop."""
        return self.waves_done >= self.wave_target


# =============================================================
# CAMPAIGN (day-indexed program progression + chapter/story unlock)
# =============================================================
@dataclass
class Campaign:
    """Cross-session state: which program day the patient is on, their
    day-streak, and the chapter/story unlock progress (visual only - see
    config.Chapter). Persisted via to_dict()/from_dict() + progress_store.
    """
    recorded_max_rom: float = config.WAVE_MIN_ANGLE
    total_clears: int = 0
    chapter_index: int = 0

    day_number: int = 1
    streak: int = 1
    longest_streak: int = 1
    sessions_today: int = 0
    total_sessions_played: int = 0
    last_play_date: str | None = None  # ISO date string

    @property
    def prescription(self) -> config.DayPrescription:
        return config.prescription_for_day(self.day_number)

    def sync_to_today(self, today_iso: str, missed_day_rollback_cap: int = 7) -> None:
        """Advance day/streak based on the calendar gap since last play.

        - Same day as last play (or first ever launch): no change.
        - Exactly one day later: day advances, streak extends.
        - A gap of 2+ days: streak resets to 1, and the prescribed day
          gently rolls back (capped) rather than resuming at the previous
          peak difficulty - a deconditioned patient shouldn't be asked to
          pick up exactly where a high-difficulty day left off.
        """
        if self.last_play_date is None:
            self.last_play_date = today_iso
            self.sessions_today = 0
            return
        if self.last_play_date == today_iso:
            return  # already playing today - same prescription all session

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
        # gap <= 0 (clock oddities): treat as same day, no change

        self.last_play_date = today_iso
        self.sessions_today = 0

    def finish_session(self, session: Session) -> bool:
        """Fold results in; returns True if a new chapter just unlocked."""
        self.sessions_today += 1
        self.total_sessions_played += 1
        self.total_clears += session.patches_cleared
        self.recorded_max_rom = max(self.recorded_max_rom, session.session_max_rom)
        before = self.chapter_index
        self._advance_chapter()
        return self.chapter_index > before

    def _advance_chapter(self) -> None:
        while (self.chapter_index < len(config.CHAPTERS) - 1
               and self.total_clears >= config.CHAPTERS[self.chapter_index].waves_to_clear):
            self.chapter_index += 1

    @property
    def current_chapter(self) -> config.Chapter:
        return config.CHAPTERS[min(self.chapter_index, len(config.CHAPTERS) - 1)]

    # ----- persistence -----
    def to_dict(self) -> dict:
        return {
            "recorded_max_rom": self.recorded_max_rom,
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
            recorded_max_rom=data.get("recorded_max_rom", config.WAVE_MIN_ANGLE),
            total_clears=data.get("total_clears", 0),
            chapter_index=data.get("chapter_index", 0),
            day_number=data.get("day_number", 1),
            streak=data.get("streak", 1),
            longest_streak=data.get("longest_streak", 1),
            sessions_today=data.get("sessions_today", 0),
            total_sessions_played=data.get("total_sessions_played", 0),
            last_play_date=data.get("last_play_date"),
        )
