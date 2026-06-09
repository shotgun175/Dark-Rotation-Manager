"""
update_check.py - Non-blocking "update available" check.

On launch the app compares its own __version__ against the latest GitHub
release (unauthenticated GitHub REST API) on a daemon thread, so the UI is
never blocked. On any network or parse error it logs a warning and does
nothing. It never downloads or self-updates — the onefile build is unsigned.
"""

import json
import logging
import threading
import urllib.request

from modules.version import __version__

logger = logging.getLogger(__name__)

# Derived from `git remote -v` (origin = shotgun175/Dark-Rotation-Manager).
GITHUB_API_LATEST = (
    "https://api.github.com/repos/shotgun175/Dark-Rotation-Manager/releases/latest"
)
# Public release page where the .exe assets live; "{tag}" -> the release tag.
GITHUB_RELEASES_URL = "https://github.com/shotgun175/Dark-Rotation-Manager/releases"
_USER_AGENT = "Dark-Rotation-Manager-update-check"
_TIMEOUT_SECONDS = 5.0


def _parse_version(tag: str) -> tuple[int, ...] | None:
    """Parse a 'vX.Y.Z' (or 'X.Y.Z') tag into a comparable int tuple.

    Returns None if the tag has no numeric version component.
    """
    if not tag:
        return None
    cleaned = tag.strip().lstrip("vV")
    try:
        return tuple(int(part) for part in cleaned.split("."))
    except ValueError:
        return None


def _fetch_latest_tag(url: str, timeout: float) -> str | None:
    """Return the tag_name of the latest GitHub release, or None."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return data.get("tag_name")


def check_for_update(
    on_update_available,
    current_version: str = __version__,
    url: str = GITHUB_API_LATEST,
    timeout: float = _TIMEOUT_SECONDS,
) -> None:
    """Synchronously check GitHub for a newer release.

    Calls on_update_available(tag) exactly once if the latest release is newer
    than current_version. All network/parse errors are swallowed and logged.
    """
    try:
        tag = _fetch_latest_tag(url, timeout)
        latest = _parse_version(tag)
        current = _parse_version(current_version)
        if latest is None or current is None:
            logger.warning(
                "[Update] Could not compare versions: latest=%r current=%r",
                tag,
                current_version,
            )
            return
        if latest > current:
            logger.info(
                "[Update] Newer release available: %s (current v%s)",
                tag,
                current_version,
            )
            on_update_available(tag)
        else:
            logger.debug(
                "[Update] Up to date (latest %s, current v%s)", tag, current_version
            )
    except Exception as e:
        logger.warning("[Update] Update check failed: %s", e)


def check_for_update_async(on_update_available, **kwargs) -> threading.Thread:
    """Run check_for_update on a daemon thread so it never blocks the UI."""
    thread = threading.Thread(
        target=check_for_update,
        args=(on_update_available,),
        kwargs=kwargs,
        daemon=True,
    )
    thread.start()
    return thread
