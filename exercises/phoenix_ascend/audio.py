"""
Sound effects + background music for Phoenix Ascend, via pygame's mixer.
"""
import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

# SFX_DIR = os.path.join("assets", "sfx")
# MUSIC_DIR = os.path.join("assets", "music")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SFX_DIR = os.path.join(BASE_DIR, "assets", "sfx")
MUSIC_DIR = os.path.join(BASE_DIR, "assets", "music")
SFX_FILES = {
    "target_hit": "target_hit.mp3",
    "energy_collected": "energy_collected.mp3",
    "bank_success": "bank_success.mp3",  # still need to download this one
    "level_up": "level_up.ogg",
    "combo_tier": "combo_tier.ogg",
}

MUSIC_FILE = "ambient_theme.mp3"  # change to "ambient_theme.mp3" if that's what you downloaded


class AudioManager:
    def __init__(self, sfx_volume=0.7, music_volume=0.4):
        self.enabled = True
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"[Audio] Could not initialize sound: {e}. Running muted.")
            self.enabled = False
            return

        self.sounds = {}
        for key, filename in SFX_FILES.items():
            path = os.path.join(SFX_DIR, filename)
            if os.path.exists(path):
                snd = pygame.mixer.Sound(path)
                snd.set_volume(sfx_volume)
                self.sounds[key] = snd
            else:
                print(f"[Audio] Missing SFX (skipping): {path}")

        self._music_loaded = False
        music_path = os.path.join(MUSIC_DIR, MUSIC_FILE)
        if os.path.exists(music_path):
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.set_volume(music_volume)
            self._music_loaded = True
        else:
            print(f"[Audio] Missing background music (skipping): {music_path}")

    def play(self, key):
        if not self.enabled:
            return
        snd = self.sounds.get(key)
        if snd:
            snd.play()

    def start_music(self, loop=True):
        if self.enabled and self._music_loaded:
            pygame.mixer.music.play(-1 if loop else 0)

    def stop_music(self):
        if self.enabled and self._music_loaded:
            pygame.mixer.music.stop()

    def close(self):
        if self.enabled:
            pygame.mixer.quit()