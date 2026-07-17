"""Persists campaign progress (program day, streak, chapter/story unlock
state) to disk so "Day N" survives across app restarts.

Design goal: NEVER crash the game over a storage problem. Load returns
sensible defaults on any error; save fails silently rather than
interrupting play.
"""

from __future__ import annotations

import json
import os

STATE_PATH = os.path.join(os.path.dirname(__file__), "progress_state.json")

_DEFAULTS = {
    "day_number": 1,
    "streak": 1,
    "longest_streak": 1,
    "sessions_today": 0,
    "total_sessions_played": 0,
    "last_play_date": None,
    "recorded_max_depth": 0.0,
    "total_clears": 0,
    "chapter_index": 0,
}


def load_state() -> dict:
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
    try:
        payload = {k: state.get(k, _DEFAULTS[k]) for k in _DEFAULTS}
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass
