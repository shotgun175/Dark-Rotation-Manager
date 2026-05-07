"""
events.py - Engine event names.

String-Enum: members compare equal to their string value, so consumers
can branch on either `event == EngineEvent.CONFIRMED` or `event == "confirmed"`.
"""

from enum import Enum


class EngineEvent(str, Enum):
    STATE_CHANGE      = "state_change"
    ANNOUNCE          = "announce"
    WARNING           = "warning"
    CONFIRMED         = "confirmed"
    MISSED            = "missed"
    RESET             = "reset"
    ROTATION_COMPLETE = "rotation_complete"
    COOLDOWN_SKIP     = "cooldown_skip"
