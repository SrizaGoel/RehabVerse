"""Archer's Draw - launcher (proof-of-concept step).

Starts the Python WebSocket server (camera + data) in a background thread,
then opens the game UI in a native window via pywebview.

Run with:
    python -m archers_draw.main
"""

from __future__ import annotations

import asyncio
import os
import threading

import webview

from . import server as backend


def _run_server_thread() -> None:
    asyncio.run(backend.main())


def main() -> None:
    thread = threading.Thread(target=_run_server_thread, daemon=True)
    thread.start()

    html_path = os.path.join(os.path.dirname(__file__), "web", "index.html")
    webview.create_window("Archer's Draw - Pipeline Test", html_path,
                           width=1280, height=760)
    webview.start()


if __name__ == "__main__":
    main()
