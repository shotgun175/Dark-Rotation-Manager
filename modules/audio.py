"""
audio.py - Audio manager for Dark Rotation Bot

Handles two types of audio:
  1. TTS voice lines via edge-tts (pre-rendered at bot launch, played instantly)
  2. A chime sound effect for auto-detection confirms

All pygame calls happen on the main thread (called from _on_engine_event_ui).
Pre-rendering runs in a background thread so the GUI stays responsive.
"""

import os
import shutil
import tempfile
import asyncio
import threading

from modules.paths import get_base_dir

_BASE_DIR = get_base_dir()

CHIME_PATH = os.path.join(_BASE_DIR, "assets", "sounds", "dark_confirmed.mp3")

VOICE_MAP = {
    "Andrew": "en-US-AndrewNeural",
    "Jenny":  "en-US-JennyNeural",
}

# Maps engine event names to the cue key used in config
# "missed" intentionally omitted — no TTS for missed throws
EVENT_TO_CUE = {
    "announce":          "announce",
    "warning":           "warning",
    "confirmed":         "confirmed",
    "rotation_complete": "rotation_complete",
    "reset":             "reset",
}

# ------------------------------------------------------------------
# pygame init (once at module level)
# ------------------------------------------------------------------
_pygame_ok = False
try:
    import pygame
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=512)
    pygame.mixer.init()
    pygame.mixer.set_num_channels(8)
    _pygame_ok = True
except Exception as e:
    print(f"[Audio] pygame init failed: {e}")


class AudioManager:
    def __init__(self, config: dict):
        self._config     = config
        self._cache: dict[str, str] = {}          # key -> mp3 path
        self._temp_dir   = tempfile.mkdtemp(prefix="darkbot_tts_")
        self._ready      = False
        self._volume     = float(config.get("audio", {}).get("volume", 0.8))
        self._render_thread: threading.Thread | None = None

        # Reserve channel 0 for chime
        if _pygame_ok:
            self._chime_channel = pygame.mixer.Channel(0)
            self._chime_sound   = self._load_chime()
        else:
            self._chime_channel = None
            self._chime_sound   = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prerender(self, players: list[str]):
        """Kick off background pre-rendering of all TTS phrases."""
        self._ready = False
        self._render_thread = threading.Thread(
            target=self._render_all,
            args=(list(players),),
            daemon=True,
        )
        self._render_thread.start()

    def play_event(self, event_type: str, data: dict):
        """Play the TTS cue for an engine event. No-ops if not ready/enabled."""
        if not _pygame_ok:
            return
        cfg = self._config.get("audio", {})
        if not cfg.get("enabled", True):
            return

        cue_key = EVENT_TO_CUE.get(event_type)
        if not cue_key:
            return
        if not cfg.get("cues", {}).get(cue_key, True):
            return
        if not self._ready:
            return

        voice = cfg.get("voice", "Andrew")

        # Player-specific cues use the player name in the cache key.
        # Warning uses "next" (the upcoming player), not "player".
        # Static cues (confirmed, missed, rotation_complete) use no player.
        if cue_key == "announce":
            player = data.get("player", "")
        elif cue_key == "warning":
            player = data.get("next", "")
        else:
            player = ""

        cache_key = self._make_key(voice, cue_key, player)

        path = self._cache.get(cache_key)
        if path and os.path.exists(path):
            self._play_tts(path)

    def play_chime(self):
        """Play the auto-detect chime. Separate from TTS."""
        if not _pygame_ok or self._chime_sound is None:
            return
        cfg = self._config.get("audio", {})
        if not cfg.get("enabled", True):
            return
        if not cfg.get("cues", {}).get("chime", True):
            return
        self._chime_channel.set_volume(self._volume)
        self._chime_channel.play(self._chime_sound)

    def play_test(self):
        """Play a sample line for the currently configured voice."""
        if not _pygame_ok:
            return
        cfg   = self._config.get("audio", {})
        voice = cfg.get("voice", "Andrew")
        key   = self._make_key(voice, "confirmed", "")
        path  = self._cache.get(key)
        if path and os.path.exists(path):
            self._play_tts(path)
        else:
            # Render on the fly for test
            voice_id = VOICE_MAP.get(voice, VOICE_MAP["Andrew"])
            out = os.path.join(self._temp_dir, f"test_{voice}.mp3")
            try:
                asyncio.run(self._async_render("Dark confirmed", voice_id, out))
                self._play_tts(out)
            except Exception as e:
                print(f"[Audio] Test render failed: {e}")

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, volume))

    def update_config(self, config: dict, players: list[str] | None = None):
        old_voice = self._config.get("audio", {}).get("voice", "Andrew")
        new_voice = config.get("audio", {}).get("voice", "Andrew")
        self._config = config
        self._volume = float(config.get("audio", {}).get("volume", 0.8))

        # Re-render if voice changed or new players added
        if players is not None and (old_voice != new_voice or self._has_new_players(players)):
            self._cache.clear()
            self.prerender(players)

    def shutdown(self):
        """Clean up temp files. Call on bot stop and app close."""
        try:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _render_all(self, players: list[str]):
        """Background thread: render every TTS phrase to mp3 in parallel."""
        cfg      = self._config.get("audio", {})
        voice    = cfg.get("voice", "Andrew")
        voice_id = VOICE_MAP.get(voice, VOICE_MAP["Andrew"])

        # Build phrase list (missed intentionally excluded)
        phrases = []
        for player in players:
            phrases += [
                (f"{player}, throw dark",  self._make_key(voice, "announce", player)),
                (f"{player}, get ready",   self._make_key(voice, "warning",  player)),
            ]
        phrases += [
            ("Dark confirmed",        self._make_key(voice, "confirmed",         "")),
            ("All darks used",        self._make_key(voice, "rotation_complete", "")),
            ("Dark rotation reset",   self._make_key(voice, "reset",             "")),
        ]

        # Only render clips not already in cache
        to_render = [(text, key) for text, key in phrases if key not in self._cache]
        out_paths  = {key: os.path.join(self._temp_dir, f"{key}.mp3") for _, key in to_render}

        async def _run_parallel():
            results = await asyncio.gather(
                *[self._async_render(text, voice_id, out_paths[key])
                  for text, key in to_render],
                return_exceptions=True,
            )
            for (text, key), result in zip(to_render, results):
                if isinstance(result, Exception):
                    print(f"[Audio] Render failed for '{text}': {result}")
                else:
                    self._cache[key] = out_paths[key]

        try:
            asyncio.run(_run_parallel())
        except Exception as e:
            print(f"[Audio] Parallel render error: {e}")

        self._ready = True
        print(f"[Audio] Pre-render complete — {len(self._cache)} clips ready.")

    @staticmethod
    async def _async_render(text: str, voice_id: str, out_path: str):
        import edge_tts
        tts = edge_tts.Communicate(text, voice_id)
        await tts.save(out_path)

    def _play_tts(self, path: str):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self._volume)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"[Audio] Playback error: {e}")

    def _load_chime(self):
        if not os.path.exists(CHIME_PATH):
            print(f"[Audio] Chime not found: {CHIME_PATH}")
            return None
        try:
            return pygame.mixer.Sound(CHIME_PATH)
        except Exception as e:
            print(f"[Audio] Failed to load chime: {e}")
            return None

    @staticmethod
    def _make_key(voice: str, cue: str, player: str) -> str:
        slug = player.lower().replace(" ", "_")
        return f"{voice}_{cue}_{slug}" if slug else f"{voice}_{cue}"

    def _has_new_players(self, players: list[str]) -> bool:
        voice = self._config.get("audio", {}).get("voice", "Andrew")
        for p in players:
            if self._make_key(voice, "announce", p) not in self._cache:
                return True
        return False
