"""
RehabVerse Backend — PyInstaller entry point.
Run this file directly in dev, or bundle it with PyInstaller for production.
"""
import sys
import os

# ─────────────────────────────────────────────────────────────
# Path setup — works both when running normally and when frozen
# by PyInstaller (sys.frozen = True, sys._MEIPASS = temp dir)
# ─────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # PyInstaller bundles everything into sys._MEIPASS
    BASE_DIR = sys._MEIPASS
else:
    # Running normally: BASE_DIR is the project root (one level up from /backend)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Make sure games/ and exercises/ are importable
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Also add backend/ itself so app.py routes are importable
BACKEND_DIR = os.path.join(BASE_DIR, "backend") if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ─────────────────────────────────────────────────────────────
# Start Flask
# ─────────────────────────────────────────────────────────────
from app import app  # noqa: E402

if __name__ == "__main__":
    print("[RehabVerse] Backend starting on http://127.0.0.1:5000")
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,   # MUST be False in production / PyInstaller
        threaded=True,
    )
