"""stack hue on <name>: switch a room, zone, lamp or the whole house on.

    ./stack hue on office        # lights: Office   on: True
    ./stack hue on all

The lights come on as they were last (brightness and colour); a scene or
`brightness` sets them. Which words name which lights is in lights.py.
"""

from __future__ import annotations

from ._common import switch

HELP = "Switch a room, zone or lamp on: on <name> (all for the whole house)"


def run(args, stacklet, config):
    if not args:
        return {"error": "Use: ./stack hue on <name>"}
    target, error = switch(config, list(args), {"on": {"on": True}})
    if error:
        return error
    return {"lights": target.name, "on": True}
