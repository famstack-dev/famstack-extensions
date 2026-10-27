"""stack hue off <name>: switch a room, zone, lamp or the whole house off.

    ./stack hue off living room  # lights: Living Room   on: False
    ./stack hue off all          # every lamp in the house

Which words name which lights is in lights.py.
"""

from __future__ import annotations

from ._common import switch

HELP = "Switch a room, zone or lamp off: off <name> (all for the whole house)"


def run(args, stacklet, config):
    if not args:
        return {"error": "Use: ./stack hue off <name>"}
    target, error = switch(config, list(args), {"on": {"on": False}})
    if error:
        return error
    return {"lights": target.name, "on": False}
