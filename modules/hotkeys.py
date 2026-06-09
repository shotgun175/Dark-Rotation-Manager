"""
hotkeys.py - Global hotkey listener (works while Lost Ark is in focus)
"""

import logging

import keyboard

logger = logging.getLogger(__name__)


class HotkeyManager:
    def __init__(self, config: dict, callbacks: dict):
        """
        config    — the 'hotkeys' section from config.yaml
        callbacks — dict mapping action names to functions:
                    {
                        'start_stop': fn,
                        'confirm':    fn,
                    }
        """
        self.config = config
        self.callbacks = callbacks
        self._registered = []

    def start(self):
        """Register all hotkeys."""
        mappings = {
            "start_stop": self.config.get("start_stop", "f8"),
            "confirm":    self.config.get("confirm",    "f9"),
            "missed":     self.config.get("missed",     "f10"),
            "reset":      self.config.get("reset",      "f11"),
        }

        for action, key in mappings.items():
            fn = self.callbacks.get(action)
            if fn:
                keyboard.add_hotkey(key, fn, suppress=False)
                self._registered.append(key)
                logger.debug(f"[Hotkeys] {key.upper()} -> {action}")

        logger.info("[Hotkeys] Listening.")

    def stop(self):
        """Unregister all hotkeys."""
        for key in self._registered:
            try:
                keyboard.remove_hotkey(key)
            except Exception:
                pass
        self._registered.clear()
        logger.info("[Hotkeys] Unregistered.")

    def update_key(self, action: str, new_key: str):
        """Hot-swap a key binding without restarting."""
        old_key = self.config.get(action)
        if old_key:
            try:
                keyboard.remove_hotkey(old_key)
            except Exception:
                pass

        fn = self.callbacks.get(action)
        if fn:
            keyboard.add_hotkey(new_key, fn, suppress=False)
            self.config[action] = new_key
            logger.info(f"[Hotkeys] {action} rebound to {new_key.upper()}")
