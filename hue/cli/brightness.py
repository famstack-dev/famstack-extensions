"""stack hue brightness <name> <level>: set the brightness of a room, zone or lamp.

    ./stack hue brightness living room 40     # lights: Living Room   brightness: 40
    ./stack hue brightness reading lamp 30%
    ./stack hue brightness office +10         # brighter; -20 darker
    ./stack hue brightness all 20

A level switches the lights on at it (who asks for 40 % wants light); a
step moves them from where they are and leaves them on or off. Colour and
colour temperature are left to the scenes (Arthur, 2026-10-26). Which
words name which lights is in lights.py.
"""

from __future__ import annotations

from ..lights import level_change
from ._common import switch

HELP = "Set the brightness of a room, zone or lamp: brightness <name> <1-100 | +step | -step>"


def run(args, stacklet, config):
    if len(args) < 2:
        return {"error": "Use: ./stack hue brightness <name> <1-100 | +10 | -20>"}
    change, level, reason = level_change(args[-1])
    if not change:
        return {"error": reason}
    target, error = switch(config, list(args[:-1]), change)
    if error:
        return error
    return {"lights": target.name, "brightness": level}
