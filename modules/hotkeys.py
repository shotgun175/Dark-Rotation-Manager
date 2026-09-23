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
        self._registered = []  # (remove function, handle) pairs for stop()
        self._armed = set()    # single-key actions whose key has been released

    def start(self):
        """Register all hotkeys."""
        mappings = {
            "start_stop": self.config.get("start_stop", "f8"),
            "confirm":    self.config.get("confirm",    "f9"),
            "missed":     self.config.get("missed",     "f10"),
            "reset":      self.config.get("reset",      "f11"),
        }

        key_actions = {}  # single key -> [(action, handler)], one hook per key
        for action, key in mappings.items():
            fn = self.callbacks.get(action)
            if fn:
                steps = keyboard.parse_hotkey(key)
                if len(steps) == 1 and len(steps[0]) == 1:
                    # A key hook fires even while other keys are held, unlike
                    # add_hotkey, which needs the held set to equal the combo.
                    # Its KEY_UP re-arms the action so OS auto-repeat of a held
                    # key fires it once. One hook_key per key, not on_press_key
                    # plus on_release_key or one hook per action: the library
                    # keys unhook entries by key name, so stop() could only
                    # remove one of two hooks on the same key.
                    self._armed.add(action)
                    if key not in key_actions:
                        pairs = key_actions[key] = []

                        def on_key(e, pairs=pairs):
                            for a, h in pairs:
                                if e.event_type == keyboard.KEY_UP:
                                    self._armed.add(a)
                                else:
                                    h()

                        self._registered.append((keyboard.unhook, keyboard.hook_key(
                            key, on_key, suppress=False)))
                    key_actions[key].append((action, self._guard(action, fn, latch=True)))
                else:
                    # Hand-written combos (ctrl+f9, "a, s"): the key hooks reject them.
                    handler = self._guard(action, fn, latch=False)
                    self._registered.append((keyboard.remove_hotkey, keyboard.add_hotkey(
                        key, handler, suppress=False)))
                logger.debug(f"[Hotkeys] {key.upper()} -> {action}")

        logger.info("[Hotkeys] Listening.")

    def stop(self):
        """Unregister all hotkeys."""
        for remove, handle in self._registered:
            try:
                remove(handle)
            except Exception:
                pass
        self._registered.clear()
        logger.info("[Hotkeys] Unregistered.")

    def _guard(self, action: str, fn, latch: bool):
        """Wrap fn so a raising action is logged instead of killing the
        keyboard library's listener thread (and every hotkey with it)."""
        def run():
            if latch:
                if action not in self._armed:
                    return  # still held since the last press
                self._armed.discard(action)
            try:
                fn()
            except Exception:
                logger.exception("[Hotkeys] %s handler failed", action)
        return run
