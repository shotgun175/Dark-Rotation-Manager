"""
event_router.py - Dispatches engine events to overlay, detection, and audio.
"""

from modules.events import EngineEvent


class EventRouter:
    def __init__(self, controller):
        self._ctrl = controller
        self._handlers = {
            EngineEvent.STATE_CHANGE:      None,  # handled inline (needs status_text_cb)
            EngineEvent.RESET:             self._on_reset,
            EngineEvent.CONFIRMED:         self._on_confirmed,
            EngineEvent.MISSED:            self._on_missed,
            EngineEvent.WARNING:           self._on_warning,
            EngineEvent.ROTATION_COMPLETE: self._on_rotation_complete,
            EngineEvent.COOLDOWN_SKIP:     self._on_cooldown_skip,
            EngineEvent.ANNOUNCE:          self._on_announce,
        }

    def handle(self, event_type, data: dict, status_text_cb):
        """Main entry. status_text_cb is a callable (text, color) used
        by state_change events to update the bottom-bar status."""
        if event_type == EngineEvent.STATE_CHANGE:
            self._on_state_change(data, status_text_cb)
            return

        handler = self._handlers.get(event_type)
        if handler:
            handler(data)

        # Detection pause/resume around the buff window
        det = self._ctrl.detection
        if det:
            if event_type == EngineEvent.CONFIRMED:
                det.pause()
            elif event_type in (EngineEvent.ANNOUNCE, EngineEvent.MISSED, EngineEvent.COOLDOWN_SKIP):
                det.resume()

        # Audio cues
        audio = self._ctrl.audio
        if audio:
            if event_type == EngineEvent.CONFIRMED:
                if self._ctrl.last_confirm_source == "detection":
                    audio.play_chime()
                else:
                    audio.play_event(event_type, data)
                self._ctrl.reset_last_confirm_source()
            else:
                audio.play_event(event_type, data)

    # ── Per-event handlers ───────────────────────────────────────────
    def _on_state_change(self, data, status_text_cb):
        new_state = data.get("state", "")
        if new_state == "PAUSED":
            status_text_cb("Paused  —  press F8 to resume", "#ffaa00")
        elif new_state in ("RUNNING_PLAYER_WINDOW", "RUNNING_DARK_WINDOW"):
            status_text_cb("Running", "#44ff88")
        elif new_state == "IDLE":
            status_text_cb("Armed  —  press F8 to start", "#ffaa00")

    def _on_reset(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.set_status_message("Rotation reset", "#88ccff")

    def _on_confirmed(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.flash("#1a4a1a")
            self._ctrl.overlay.set_status_message(f"OK {data['player']} confirmed", "#44ff88")

    def _on_missed(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.flash("#4a1a1a")
            self._ctrl.overlay.set_status_message(f"X {data['player']} missed", "#ff4444")

    def _on_warning(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.set_status_message(
                f"Next up: {data['next']} in {data['seconds']}s", "#ffdd44"
            )

    def _on_rotation_complete(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.set_status_message("Rotation complete", "#aaaaaa")

    def _on_cooldown_skip(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.set_status_message(f"{data['player']} on cooldown", "#ffaa00")

    def _on_announce(self, data):
        # No overlay/UI side-effect — handled by overlay's polled status read.
        pass
