"""
Lightweight SQLite logging for session history (score, reps, ROM achieved).
This matches the 'Database: SQLite' line in the project spec. The
Node.js/Express backend mentioned in the spec can later read from this
same file, or this module can be swapped for HTTP calls to that backend
once it exists.
"""
import sqlite3
import time
from . import config

import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_db_path(user_id=None, recovery_id=None):
    if user_id and recovery_id:
        uid = re.sub(r"[^a-zA-Z0-9_-]", "", str(user_id))
        rid = re.sub(r"[^a-zA-Z0-9_-]", "", str(recovery_id))

        return os.path.join(
            BASE_DIR,
            f"phoenix_{uid}_{rid}.db"
        )

    return os.path.join(
        BASE_DIR,
        "phoenix_ascend.db"
    )
class SessionLogger:
    def __init__(self, user_id=None, recovery_id=None):
        db_path = get_db_path(user_id, recovery_id)
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
        self.session_id = None
        self.session_start = None

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at REAL,
                ended_at REAL,
                final_score INTEGER,
                final_level TEXT,
                total_reps INTEGER,
                best_combo INTEGER,
                max_rom_angle REAL
            )
        """)
        self.conn.commit()

    def start_session(self):
        self.session_start = time.time()
        cur = self.conn.execute(
            "INSERT INTO sessions (started_at) VALUES (?)", (self.session_start,)
        )
        self.conn.commit()
        self.session_id = cur.lastrowid
        return self.session_id

    def end_session(self, snapshot, max_rom_angle):
        if self.session_id is None:
            return
        self.conn.execute("""
            UPDATE sessions
            SET ended_at=?, final_score=?, final_level=?, total_reps=?, best_combo=?, max_rom_angle=?
            WHERE id=?
        """, (
            time.time(), snapshot["score"], snapshot["level_name"],
            snapshot["total_reps"], snapshot["best_combo"], max_rom_angle,
            self.session_id
        ))
        self.conn.commit()

    def close(self):
        self.conn.close()
