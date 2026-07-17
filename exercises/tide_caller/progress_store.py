"""Persists campaign progress (program day, streak, chapter/story unlock
state) to disk so "Day N" survives across app restarts - without this, the
day/streak counters would silently reset to Day 1 every time the game is
relaunched, which defeats the entire point of a day-indexed program.

Design goal (same as audio.py / session_log.py): NEVER crash the game over
a storage problem. Load returns sensible defaults on any error; save fails
silently rather than interrupting play.
"""

from __future__ import annotations

import json
import os
import re

def set_user(user_id=None, recovery_id=None):
    global STATE_PATH

    base = os.path.dirname(__file__)

    if user_id and recovery_id:
        uid = re.sub(r"[^a-zA-Z0-9_-]", "", str(user_id))
        rid = re.sub(r"[^a-zA-Z0-9_-]", "", str(recovery_id))

        STATE_PATH = os.path.join(
            base,
            f"rehab_progress_{uid}_{rid}.json"
        )
    else:
        STATE_PATH = os.path.join(
            base,
            "progress_state.json"
        )
STATE_PATH = os.path.join(os.path.dirname(__file__), "progress_state.json")

_DEFAULTS = {
    "day_number": 1,
    "streak": 1,
    "longest_streak": 1,
    "sessions_today": 0,
    "total_sessions_played": 0,
    "last_play_date": None,       # ISO date string, e.g. "2026-07-09"
    "recorded_max_rom": 0.0,
    "total_clears": 0,
    "chapter_index": 0,
}


def load_state() -> dict:
    """Read persisted campaign state. Missing/corrupt file -> fresh defaults."""
    if not os.path.isfile(STATE_PATH):
        return dict(_DEFAULTS)
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        state = dict(_DEFAULTS)
        state.update({k: v for k, v in data.items() if k in _DEFAULTS})
        return state
    except Exception:
        return dict(_DEFAULTS)


def save_state(state: dict) -> None:
    """Write campaign state. Never raises - a failed save just means the
    next launch falls back to the last successfully saved state."""
    try:
        payload = {k: state.get(k, _DEFAULTS[k]) for k in _DEFAULTS}
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass
