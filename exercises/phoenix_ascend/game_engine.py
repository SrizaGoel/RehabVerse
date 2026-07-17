"""
Core game logic for Phoenix Ascend: the abduct -> hold -> adduct -> reward
cycle, scoring, level progression, and combo tracking.
"""
import time
from . import config


class Phase:
    COLLECTION = "collection"
    STABILITY = "stability"
    BANKING = "banking"


class GameEngine:
    def __init__(self):
        self.level_index = 0
        self.score = 0
        self.feathers = 0
        self.total_reps = 0
        self.reps_this_level = 0
        self.combo = 0
        self.best_combo = 0
        self.combo_tier_name = None

        self.phase = Phase.COLLECTION
        self.current_target_index = 0
        self.stability_start_time = None
        self.stability_progress = 0.0  # 0.0 - 1.0
        self.energy_banked_this_cycle = 0
        self.feedback_color = "red"
        self.feedback_text = ""
        self.last_event = None
        self.last_event_time = 0
        self.pending_sounds = []
    
    # ---------- Level helpers ----------
    @property
    def level(self):
        return config.LEVELS[self.level_index]

    @property
    def active_targets(self):
        max_angle = self.level["max_angle"]
        targets = [t for t in config.ORB_TARGETS if t["angle"] <= max_angle]
        return targets if targets else config.ORB_TARGETS[:1]

    @property
    def current_target(self):
        targets = self.active_targets
        idx = self.current_target_index % len(targets)
        return targets[idx]

    def _advance_level_if_ready(self):
        if self.reps_this_level >= self.level["reps_to_advance"] and \
           self.level_index < len(config.LEVELS) - 1:
            self.level_index += 1
            self.reps_this_level = 0
            self._fire_event(f"Level Up! {self.level['name']}")
            self.pending_sounds.append("level_up")

    def _fire_event(self, text):
        self.last_event = text
        self.last_event_time = time.time()

    # ---------- Combo helpers ----------
    def _register_success(self):
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        for tier in reversed(config.COMBO_TIERS):
            if self.combo == tier["reps"]:
                self.combo_tier_name = tier["name"]
                self._fire_event(tier["name"] + "!")
                self.pending_sounds.append("combo_tier")
                break

    def _current_multiplier(self):
        tier_count = sum(1 for t in config.COMBO_TIERS if self.combo >= t["reps"])
        return config.BASE_BANK_MULTIPLIER + tier_count * config.COMBO_MULTIPLIER_STEP

    # ---------- Main update ----------
    def update(self, angle, arm_visible):
        """
        Call once per frame with the current best shoulder abduction angle
        (degrees). Drives the abduct -> hold -> adduct -> reward cycle.
        """
        if not arm_visible:
            self.feedback_color = "red"
            self.feedback_text = "No arm detected - step into frame"
            return

        target_angle = self.current_target["angle"]
        diff = abs(angle - target_angle)

        if diff <= config.GREEN_TOLERANCE_DEG:
            self.feedback_color = "green"
            self.feedback_text = "Movement correct"
        elif diff <= config.YELLOW_TOLERANCE_DEG:
            self.feedback_color = "yellow"
            self.feedback_text = "Partial range - keep going"
        else:
            self.feedback_color = "red"
            self.feedback_text = "Adjust your position"

        if self.phase == Phase.COLLECTION:
            self._update_collection(diff)
        elif self.phase == Phase.STABILITY:
            self._update_stability(angle, target_angle)
        elif self.phase == Phase.BANKING:
            self._update_banking(angle)

    def _update_collection(self, diff):
        if diff <= config.GREEN_TOLERANCE_DEG:
            self.phase = Phase.STABILITY
            self.stability_start_time = time.time()
            self.stability_progress = 0.0
            self._fire_event(f"{self.current_target['name']} reached!")
            self.pending_sounds.append("target_hit")

    def _update_stability(self, angle, target_angle):
        diff = abs(angle - target_angle)
        if diff <= config.STABILITY_TOLERANCE_DEG:
            elapsed = time.time() - self.stability_start_time
            self.stability_progress = min(1.0, elapsed / config.STABILITY_HOLD_SECONDS)
            if self.stability_progress >= 1.0:
                self.energy_banked_this_cycle = self.current_target["points"]
                self.feathers += self.current_target["feathers"]
                self.phase = Phase.BANKING
                self._fire_event("Energy collected! Lower your arm to bank it.")
                self.pending_sounds.append("energy_collected")
        else:
            # Lost the hold - drop back to collection (no combo penalty)
            self.phase = Phase.COLLECTION
            self.stability_start_time = None
            self.stability_progress = 0.0

    def _update_banking(self, angle):
        if angle <= config.ADDUCTION_BANK_ANGLE:
            multiplier = self._current_multiplier()
            earned = int(self.energy_banked_this_cycle * multiplier)
            self.score += earned
            self._register_success()

            self.total_reps += 1
            self.reps_this_level += 1
            self._fire_event(f"+{earned} pts banked! (x{multiplier:.1f})")
            self.pending_sounds.append("bank_success")

            self.current_target_index += 1
            self.energy_banked_this_cycle = 0
            self.phase = Phase.COLLECTION
            self._advance_level_if_ready()
    
    def drain_pending_sounds(self):
        sounds = self.pending_sounds
        self.pending_sounds = []
        return sounds

    def snapshot(self):
        """Lightweight dict of current state for rendering / logging."""
        return {
            "level_name": self.level["name"],
            "level_id": self.level["id"],
            "score": self.score,
            "feathers": self.feathers,
            "total_reps": self.total_reps,
            "reps_this_level": self.reps_this_level,
            "reps_to_advance": self.level["reps_to_advance"],
            "combo": self.combo,
            "best_combo": self.best_combo,
            "phase": self.phase,
            "target": self.current_target,
            "stability_progress": self.stability_progress,
            "feedback_color": self.feedback_color,
            "feedback_text": self.feedback_text,
            "last_event": self.last_event,
            "last_event_time": self.last_event_time,
        }
