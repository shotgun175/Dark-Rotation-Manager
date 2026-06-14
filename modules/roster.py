"""
roster.py - Load, save, and manage player rotation lists
"""

import logging
import os

import yaml

from modules.paths import atomic_write_text

logger = logging.getLogger(__name__)


class RosterManager:
    def __init__(self, rosters_dir: str):
        self.rosters_dir = rosters_dir
        self.current_roster_name = None

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def load(self, filename: str) -> list[str]:
        """Load a roster YAML file. Returns list of player names."""
        path = os.path.join(self.rosters_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Roster file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        players = [str(p) for p in data.get("players", [])]
        self.current_roster_name = data.get("name", filename)
        logger.info(f"[Roster] Loaded '{self.current_roster_name}': {players}")
        return players

    def save(self, filename: str, name: str, players: list[str]):
        """Save a roster to a YAML file (atomic write)."""
        path = os.path.join(self.rosters_dir, filename)
        data = {"name": name, "players": players}
        atomic_write_text(
            path, yaml.dump(data, default_flow_style=False, allow_unicode=True)
        )
        logger.info(f"[Roster] Saved '{name}' to {path}")

