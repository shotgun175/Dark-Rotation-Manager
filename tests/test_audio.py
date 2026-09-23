"""Tests for AudioManager temp-dir lifecycle and non-blocking test renders."""

import asyncio
import os
import shutil
import threading

import pytest

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
    monkeypatch.setattr(mgr, "_play_test_clip", lambda path: played.set())

    try:
        mgr.play_test()
        assert rendered.wait(timeout=5), "render never ran"
        assert played.wait(timeout=5), "clip never played after render"
        assert render_threads[0] is not threading.current_thread()
    finally:
        mgr.shutdown()


def test_play_test_ignores_clicks_while_render_in_flight(monkeypatch):
    """Concurrent renders would interleave writes to the same output file."""
    mgr = AudioManager({"audio": {"voice": "Andrew"}})
    monkeypatch.setattr(audio, "_pygame_ok", True)

    started = threading.Event()
    release = threading.Event()
    render_count = []

    async def slow_render(text, voice_id, out_path):
        render_count.append(1)
        started.set()
        release.wait(timeout=5)

    monkeypatch.setattr(AudioManager, "_async_render", staticmethod(slow_render))
    monkeypatch.setattr(mgr, "_play_test_clip", lambda path: None)

    try:
        mgr.play_test()
        assert started.wait(timeout=5)
        mgr.play_test()  # second click while the first render is in flight
        release.set()
        mgr._test_thread.join(timeout=5)
        assert len(render_count) == 1
    finally:
        release.set()
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


def test_stalled_render_times_out_and_the_run_still_becomes_ready(monkeypatch, caplog):
    """A websocket that stalls after the handshake must not mute every cue."""
    import edge_tts

    class StalledCommunicate:
        def __init__(self, text, voice_id):
            pass

        async def save(self, out_path):
            await asyncio.sleep(5)

    monkeypatch.setattr(edge_tts, "Communicate", StalledCommunicate)
    monkeypatch.setattr(audio, "RENDER_TIMEOUT_SECONDS", 0.05)
    mgr = AudioManager({"audio": {"voice": "Andrew"}})
    try:
        mgr._render_all([])
        assert mgr._ready is True
        assert mgr._cache == {}
        assert "Render failed" in caplog.text
    finally:
        mgr.shutdown()


def test_shutdown_removes_temp_dir_after_a_clip_was_played():
    """pygame keeps the loaded clip open; shutdown must release it first."""
    if not audio._pygame_ok:
        pytest.skip("pygame mixer unavailable (no audio device)")
    mgr = AudioManager({"audio": {"volume": 0}})
    temp_dir = mgr._temp_dir
    clip = os.path.join(temp_dir, "clip.mp3")
    shutil.copy(audio.CHIME_PATH, clip)
    mgr._play_tts(clip)
    try:
        mgr.shutdown()
        assert not os.path.exists(temp_dir)
    finally:
        if os.path.exists(temp_dir):
            audio.pygame.mixer.music.unload()
            shutil.rmtree(temp_dir, ignore_errors=True)


def test_play_test_caches_its_clip_so_a_second_click_renders_nothing(monkeypatch):
    import edge_tts

    constructed = []

    class FakeCommunicate:
        def __init__(self, text, voice_id):
            constructed.append(text)

        async def save(self, out_path):
            with open(out_path, "wb") as f:
                f.write(b"mp3")

    monkeypatch.setattr(edge_tts, "Communicate", FakeCommunicate)
    mgr = AudioManager({"audio": {"voice": "Andrew"}})
    monkeypatch.setattr(audio, "_pygame_ok", True)
    monkeypatch.setattr(mgr, "_play_test_clip", lambda path: None)
    monkeypatch.setattr(mgr, "_play_tts", lambda path: None)
    try:
        mgr.play_test()
        first = mgr._test_thread
        first.join(timeout=5)
        mgr.play_test()
        assert mgr._test_thread is first  # second click started no thread
        assert len(constructed) == 1
    finally:
        if mgr._test_thread:
            mgr._test_thread.join(timeout=5)
        mgr.shutdown()
