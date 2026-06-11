"""Tests for AudioManager temp-dir lifecycle and non-blocking test renders."""

import os
import threading

from modules import audio
from modules.audio import AudioManager


def test_shutdown_removes_temp_dir():
    mgr = AudioManager({})
    temp_dir = mgr._temp_dir
    assert os.path.isdir(temp_dir)
    mgr.shutdown()
    assert not os.path.exists(temp_dir)


def test_play_test_renders_off_the_calling_thread(monkeypatch):
    """An uncached Test Voice click must not run the network render on the
    caller (Qt main) thread — it froze the GUI for the request duration."""
    mgr = AudioManager({"audio": {"voice": "Andrew"}})
    monkeypatch.setattr(audio, "_pygame_ok", True)

    render_threads = []
    rendered = threading.Event()
    played = threading.Event()

    async def fake_render(text, voice_id, out_path):
        render_threads.append(threading.current_thread())
        rendered.set()

    monkeypatch.setattr(AudioManager, "_async_render", staticmethod(fake_render))
    monkeypatch.setattr(mgr, "_play_tts", lambda path: played.set())

    try:
        mgr.play_test()
        assert rendered.wait(timeout=5), "render never ran"
        assert played.wait(timeout=5), "clip never played after render"
        assert render_threads[0] is not threading.current_thread()
    finally:
        mgr.shutdown()


def test_play_test_uses_cache_synchronously(monkeypatch, tmp_path):
    """Cached clips keep playing immediately, no thread involved."""
    mgr = AudioManager({"audio": {"voice": "Andrew"}})
    monkeypatch.setattr(audio, "_pygame_ok", True)

    clip = tmp_path / "clip.mp3"
    clip.write_bytes(b"mp3")
    mgr._cache[AudioManager._make_key("Andrew", "confirmed", "")] = str(clip)

    played_on = []
    monkeypatch.setattr(
        mgr, "_play_tts", lambda path: played_on.append(threading.current_thread())
    )
    try:
        mgr.play_test()
        assert played_on == [threading.current_thread()]
    finally:
        mgr.shutdown()
