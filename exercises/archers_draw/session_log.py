"""Session history logging for Archer's Draw.

Appends one row per completed session to session_log.csv and reads it back
for the RECORDS screen. Never crashes the game over logging.

CSV schema:
    date, time, duration_s, shots_done, arrow_target, clean_hits,
    wide_hits, best_score, avg_draw_smoothness, avg_release_smoothness,
    peak_depth, chapter_index, chapter_name
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta

CSV_PATH = os.path.join(os.path.dirname(__file__), "session_log.csv")

FIELDS = [
    "date", "time", "duration_s", "shots_done", "arrow_target",
    "clean_hits", "wide_hits", "best_score", "avg_draw_smoothness",
    "avg_release_smoothness", "peak_depth", "chapter_index", "chapter_name",
]


def _avg(values) -> float:
    values = list(values)
    return (sum(values) / len(values)) if values else 0.0


def log_session(session, campaign) -> None:
    try:
        scores = session.scores
        row = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "duration_s": round(session.elapsed(), 1),
            "shots_done": session.shots_done,
            "arrow_target": session.arrow_target,
            "clean_hits": session.clean_hits,
            "wide_hits": session.wide_hits,
            "best_score": session.best_score,
            "avg_draw_smoothness": round(_avg(s.draw_smoothness for s in scores), 3),
            "avg_release_smoothness": round(_avg(s.release_smoothness for s in scores), 3),
            "peak_depth": round(session.session_max_depth, 1),
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
        pass


def _read_rows() -> list:
    if not os.path.isfile(CSV_PATH):
        return []
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return []

    numeric = ("duration_s", "shots_done", "arrow_target", "clean_hits",
               "wide_hits", "best_score", "avg_draw_smoothness",
               "avg_release_smoothness", "peak_depth", "chapter_index")
    out = []
    for r in rows:
        try:
            for key in numeric:
                r[key] = float(r.get(key, 0) or 0)
            out.append(r)
        except (TypeError, ValueError):
            continue
    return out


def _summarize(rows: list) -> dict:
    if not rows:
        return {"best_score": 0, "max_shots": 0, "max_clean_hits": 0, "sessions": 0}
    return {
        "best_score": int(max(r["best_score"] for r in rows)),
        "max_shots": int(max(r["shots_done"] for r in rows)),
        "max_clean_hits": int(max(r["clean_hits"] for r in rows)),
        "sessions": len(rows),
    }


def load_records() -> dict:
    rows = _read_rows()
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())

    today_rows = [r for r in rows if r.get("date") == today.isoformat()]
    week_rows = [r for r in rows if r.get("date", "") >= week_start.isoformat()]

    daily_totals = {}
    for r in rows:
        d = r.get("date", "")
        if d:
            daily_totals[d] = daily_totals.get(d, 0) + int(r["shots_done"])

    daily_shots = []
    for i in range(13, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        daily_shots.append((d, daily_totals.get(d, 0)))

    return {
        "today": _summarize(today_rows),
        "this_week": _summarize(week_rows),
        "all_time": _summarize(rows),
        "daily_shots": daily_shots,
    }
