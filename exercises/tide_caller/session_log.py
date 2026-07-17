"""Session history logging for Tide Caller.

Appends one row per completed session to session_log.csv (same directory as
this module) and reads it back for the RECORDS screen: TODAY / THIS WEEK /
ALL TIME summaries plus a 14-day daily-waves series for the line chart.

Design goal (same as audio.py): NEVER crash the game over logging. Writing
and reading are both wrapped defensively; a missing or corrupt CSV just
means empty records, not a crash.

CSV schema:
    date, time, duration_s, waves_done, wave_target, clean_clears,
    murky_clears, best_score, avg_symmetry, avg_eccentric, avg_concentric,
    peak_rom, chapter_index, chapter_name
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta
import re

def set_user(user_id=None, recovery_id=None):
    global CSV_PATH

    base = os.path.dirname(__file__)

    if user_id and recovery_id:
        uid = re.sub(r"[^a-zA-Z0-9_-]", "", str(user_id))
        rid = re.sub(r"[^a-zA-Z0-9_-]", "", str(recovery_id))

        CSV_PATH = os.path.join(
            base,
            f"session_log_{uid}_{rid}.csv"
        )
    else:
        CSV_PATH = os.path.join(
            base,
            "session_log.csv"
        )
CSV_PATH = os.path.join(os.path.dirname(__file__), "session_log.csv")

FIELDS = [
    "date", "time", "duration_s", "waves_done", "wave_target",
    "clean_clears", "murky_clears", "best_score", "avg_symmetry",
    "avg_eccentric", "avg_concentric", "peak_rom",
    "chapter_index", "chapter_name",
]


def _avg(values) -> float:
    values = list(values)
    return (sum(values) / len(values)) if values else 0.0


def log_session(session, campaign) -> None:
    """Append one row summarizing a just-finished session. Never raises."""
    try:
        scores = session.scores
        row = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "duration_s": round(session.elapsed(), 1),
            "waves_done": session.waves_done,
            "wave_target": session.wave_target,
            "clean_clears": session.clean_clears,
            "murky_clears": session.murky_clears,
            "best_score": session.best_score,
            "avg_symmetry": round(_avg(s.symmetry for s in scores), 3),
            "avg_eccentric": round(_avg(s.eccentric for s in scores), 3),
            "avg_concentric": round(_avg(s.concentric for s in scores), 3),
            "peak_rom": round(session.session_max_rom, 1),
            "chapter_index": campaign.chapter_index,
            "chapter_name": campaign.current_chapter.name,
        }
        file_exists = os.path.isfile(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception:
        pass  # logging must never break the game


def _read_rows() -> list[dict]:
    """Read all rows, with numeric fields coerced. Empty list on any error."""
    if not os.path.isfile(CSV_PATH):
        return []
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return []

    numeric = ("duration_s", "waves_done", "wave_target", "clean_clears",
               "murky_clears", "best_score", "avg_symmetry", "avg_eccentric",
               "avg_concentric", "peak_rom", "chapter_index")
    out = []
    for r in rows:
        try:
            for key in numeric:
                r[key] = float(r.get(key, 0) or 0)
            out.append(r)
        except (TypeError, ValueError):
            continue
    return out


def _summarize(rows: list[dict]) -> dict:
    """Aggregate a set of rows into the RECORDS panel's headline stats."""
    if not rows:
        return {"best_score": 0, "max_waves": 0, "max_clean_clears": 0,
                "sessions": 0}
    return {
        "best_score": int(max(r["best_score"] for r in rows)),
        "max_waves": int(max(r["waves_done"] for r in rows)),
        "max_clean_clears": int(max(r["clean_clears"] for r in rows)),
        "sessions": len(rows),
    }


def load_records() -> dict:
    """Build everything the RECORDS screen needs in one call.

    Returns a dict with 'today', 'this_week', 'all_time' summaries (each
    from _summarize) and 'daily_waves' - a list of (date_str, total_waves)
    pairs for the last 14 days, oldest first, for the line chart.
    """
    rows = _read_rows()
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())

    today_rows = [r for r in rows if r.get("date") == today.isoformat()]
    week_rows = [r for r in rows if r.get("date", "") >= week_start.isoformat()]

    daily_totals: dict[str, int] = {}
    for r in rows:
        d = r.get("date", "")
        if d:
            daily_totals[d] = daily_totals.get(d, 0) + int(r["waves_done"])

    daily_waves = []
    for i in range(13, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        daily_waves.append((d, daily_totals.get(d, 0)))

    return {
        "today": _summarize(today_rows),
        "this_week": _summarize(week_rows),
        "all_time": _summarize(rows),
        "daily_waves": daily_waves,
    }