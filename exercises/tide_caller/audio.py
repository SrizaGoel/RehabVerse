"""Audio manager for Tide Caller.

Maps game states/events to sound cues: ocean ambience (looped), rising swell,
charge hum, wave crash, reveal sparkle, chapter unlock, pause/resume.

Design goal: NEVER crash on a missing file. The SLR engine hard-loads sounds
and dies if any are absent; this manager loads each cue defensively and simply
skips anything it can't find. The game stays fully playable in silence, so a
patient (or you, while developing) can run it before any audio is added.

Drop .ogg / .wav / .mp3 files into games/tide_caller/assets/sounds/ using the
filenames in CUE_FILES below and they start playing automatically.
"""

from __future__ import annotations

import os

try:
    import pygame
    _PYGAME_AVAILABLE = True
except Exception:  # pragma: no cover - pygame missing entirely
    _PYGAME_AVAILABLE = False


# Directory holding this game's audio assets.
_SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "assets", "sounds")

# Logical cue name -> filename expected in the sounds dir.
# (Add the files later; missing ones are silently skipped.)
CUE_FILES = {
    "rise": "rise_swell.wav",
    "charge": "charge_hum.wav",
    "charged": "charged_ready.wav",
    "crash": "wave_crash.ogg",
    "reveal": "reveal_sparkle.wav",
    "tsunami": "charged_ready.wav",
    "chapter": "chapter_unlock.ogg",
    "session_complete": "coast_restored.ogg",
    "pause": "pause.ogg",
    "resume": "resume.ogg",
    "session_started": "session_started.ogg",
    "first_wave": "first_wave.ogg",
    "first_tsunami": "first_tsunami.ogg",
    "coast_restored": "coast_restored.ogg",
    "symmetry_good": "symmetry_good.ogg",
    "symmetry_bad": "symmetry_bad.ogg",
    "magic_water": "magic_water_ambience.wav",
}

# Looping background ambience (played at low volume under everything).
AMBIENCE_FILE = "ocean_ambience.mp3"
AMBIENCE_VOLUME = 1.0


class AudioManager:
    """Loads cues defensively and plays them by logical name.

    All public methods are no-ops when pygame is unavailable or a cue/file
    is missing, so callers never need to guard their calls.
    """

    def __init__(self, sounds_dir: str = _SOUNDS_DIR) -> None:
        self.enabled = _PYGAME_AVAILABLE
        self.sounds_dir = sounds_dir
        self._cues: dict[str, "pygame.mixer.Sound"] = {}
        self._missing: list[str] = []

        if not self.enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception:
            # Audio device unavailable (e.g. headless) -> run silent.
            self.enabled = False
            return

        self._load_cues()
        self._start_ambience()

    # ------------------------------------------------------------------
    # LOADING
    # ------------------------------------------------------------------
    def _load_cues(self) -> None:
        for name, filename in CUE_FILES.items():
            path = os.path.join(self.sounds_dir, filename)
            if not os.path.isfile(path):
                self._missing.append(filename)
                continue
            try:
                self._cues[name] = pygame.mixer.Sound(path)
            except Exception:
                self._missing.append(filename)

    def _start_ambience(self) -> None:
        path = os.path.join(self.sounds_dir, AMBIENCE_FILE)
        if not os.path.isfile(path):
            self._missing.append(AMBIENCE_FILE)
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(AMBIENCE_VOLUME)
            pygame.mixer.music.play(-1)  # loop forever
        except Exception:
            self._missing.append(AMBIENCE_FILE)

    # ------------------------------------------------------------------
    # PLAYBACK
    # ------------------------------------------------------------------
    def play(self, cue: str) -> None:
        """Play a one-shot cue by logical name. No-op if missing."""
        if not self.enabled:
            return
        sound = self._cues.get(cue)
        if sound is not None:
            try:
                sound.play()
            except Exception:
                pass

    def play_for_grade(self, grade: str) -> None:
        """Convenience: tsunami gets its own cue, others share the crash."""
        self.play("tsunami" if grade == "TSUNAMI" else "crash")

    def pause_ambience(self) -> None:
        if self.enabled:
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass

    def resume_ambience(self) -> None:
        if self.enabled:
            try:
                pygame.mixer.music.unpause()
            except Exception:
                pass

    def stop(self) -> None:
        if self.enabled:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # DIAGNOSTICS
    # ------------------------------------------------------------------
    @property
    def missing_files(self) -> list[str]:
        """Filenames that were expected but not found (for a dev log line)."""
        return list(self._missing)
