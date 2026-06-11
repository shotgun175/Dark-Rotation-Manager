"""
detection.py - Auto-detects dark grenade debuff on the boss HP bar using
OpenCV template matching. Runs in a background thread alongside the engine.

Finds the Lost Ark window automatically (works on any monitor setup) and
scans a small relative region for the dark grenade / splendid dark grenade
debuff icon. When detected, calls on_detected(is_splendid) on the main
rotation engine.
"""

import logging
import os
import time
import threading

import cv2
import numpy as np
import mss

from modules.paths import get_resource, find_lostark_window

logger = logging.getLogger(__name__)

DARK_TEMPLATE_PATH      = get_resource(os.path.join("assets", "templates", "dark_grenade.png"))
SPLENDID_TEMPLATE_PATH  = get_resource(os.path.join("assets", "templates", "splendid_dark_grenade.png"))

# Detection-region defaults: where the boss debuff bar sits relative to the
# Lost Ark window's client top-left. Calibrated against a 2560x1440 display
# (the reference frame the GUI's region preview also draws against); other
# resolutions/UI scales should redraw the region in the Overlay tab.
# Single source of truth — overlay_tab and config.example.yaml mirror these.
DEFAULT_REGION_REL_X  = 875
DEFAULT_REGION_REL_Y  = 325
DEFAULT_REGION_WIDTH  = 456
DEFAULT_REGION_HEIGHT = 46
DEFAULT_THRESHOLD     = 0.75   # OpenCV template-match confidence
CALIBRATION_WIDTH     = 2560
CALIBRATION_HEIGHT    = 1440


class DetectionEngine:
    def __init__(self, config: dict, on_detected):
        """
        config       — full app config dict
        on_detected  — callable(is_splendid: bool) called on match
        """
        self._config = config
        self._on_detected = on_detected
        self._load_config()

        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._dark_tmpl     = self._load_template(DARK_TEMPLATE_PATH)
        self._splendid_tmpl = self._load_template(SPLENDID_TEMPLATE_PATH)

        if self._dark_tmpl is None:
            logger.warning(f"[Detection] dark_grenade.png not found at {DARK_TEMPLATE_PATH}")
        if self._splendid_tmpl is None:
            logger.warning(f"[Detection] splendid_dark_grenade.png not found at {SPLENDID_TEMPLATE_PATH}")

    def _load_config(self):
        det = self._config.get("detection", {})
        self.rel_x          = det.get("rel_x", DEFAULT_REGION_REL_X)
        self.rel_y          = det.get("rel_y", DEFAULT_REGION_REL_Y)
        self.width          = det.get("width", DEFAULT_REGION_WIDTH)
        self.height         = det.get("height", DEFAULT_REGION_HEIGHT)
        self.threshold      = det.get("threshold", DEFAULT_THRESHOLD)
        self.scan_interval  = det.get("scan_interval_ms", 500) / 1000.0

    def _load_template(self, path: str):
        if not os.path.exists(path):
            return None
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        return img

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        if self._running:
            return
        if self._dark_tmpl is None or self._splendid_tmpl is None:
            logger.error("[Detection] Cannot start — template images missing.")
            return
        self._running = True
        self._paused = False
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("[Detection] Started.")

    def stop(self):
        self._running = False
        self._stop_event.set()
        logger.info("[Detection] Stopped.")

    def pause(self):
        """Call while dark buff is active — no need to scan."""
        self._paused = True

    def resume(self):
        """Call when next player window starts."""
        self._paused = False

    def check_now(self) -> tuple[bool, bool]:
        """One-shot synchronous scan. Returns (dark_found, is_splendid)."""
        try:
            with mss.mss() as sct:
                win_pos = find_lostark_window()
                if win_pos is None:
                    return False, False
                win_x, win_y = win_pos
                region = {
                    "left":   win_x + self.rel_x,
                    "top":    win_y + self.rel_y,
                    "width":  self.width,
                    "height": self.height,
                }
                shot = sct.grab(region)
                frame = np.array(shot)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                if self._match(gray, self._splendid_tmpl):
                    return True, True
                if self._match(gray, self._dark_tmpl):
                    return True, False
                return False, False
        except Exception as e:
            logger.exception(f"[Detection] check_now error: {e}")
            return False, False

    def update_config(self, config: dict):
        self._config = config
        self._load_config()

    # ------------------------------------------------------------------
    # Detection loop
    # ------------------------------------------------------------------

    def _loop(self):
        with mss.mss() as sct:
            while not self._stop_event.is_set():
                if not self._paused:
                    try:
                        self._scan(sct)
                    except Exception as e:
                        logger.exception(f"[Detection] Scan error: {e}")
                time.sleep(self.scan_interval)

    def _scan(self, sct):
        win_pos = find_lostark_window()
        if win_pos is None:
            return  # Lost Ark not running/visible — silently skip

        win_x, win_y = win_pos
        region = {
            "left":   win_x + self.rel_x,
            "top":    win_y + self.rel_y,
            "width":  self.width,
            "height": self.height,
        }

        shot = sct.grab(region)
        frame = np.array(shot)
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

        # Check splendid first (more specific match wins)
        if self._match(gray, self._splendid_tmpl):
            logger.info("[Detection] Splendid Dark Grenade detected!")
            self._paused = True   # stop scanning until resumed
            self._on_detected(is_splendid=True)
            return

        if self._match(gray, self._dark_tmpl):
            logger.info("[Detection] Dark Grenade detected!")
            self._paused = True
            self._on_detected(is_splendid=False)

    def _match(self, frame_gray: np.ndarray, template: np.ndarray) -> bool:
        if template is None:
            return False
        # Template must be smaller than the region
        fh, fw = frame_gray.shape[:2]
        th, tw = template.shape[:2]
        if th > fh or tw > fw:
            # Scale template down to fit if needed
            scale = min(fh / th, fw / tw) * 0.9
            template = cv2.resize(template, (int(tw * scale), int(th * scale)))

        result = cv2.matchTemplate(frame_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val >= self.threshold
