"""stack hue scene list | <name> [<room>]: the Hue scenes, and calling one up.

    ./stack hue scene list                         # scenes: {"Living Room": ["Read", ...]}
    ./stack hue scene relax living room            # scene: Relax   room: Living Room
    ./stack hue scene valley dawn                  # a name only one room has needs no room

Scenes are made and named in the Hue app; this reads them from the bridge
on every call, so a renamed or deleted scene counts at once. How the words
are matched to a scene is in scenes.py.
"""

from __future__ import annotations

from ..scenes import by_room, choose
from ._common import paired_bridge

HELP = "List the Hue scenes or call one up: scene list | scene <name> [<room>]"
USAGE = {"error": "Use: ./stack hue scene list, or ./stack hue scene <name> [<room>]"}


def run(args, stacklet, config):
    if not args:
        return USAGE
    bridge, error = paired_bridge(config)
    if error:
        return error
    rooms = bridge.resources("room") + bridge.resources("zone")
    scenes = bridge.resources("scene")
    if args == ["list"]:
        return {"scenes": by_room(scenes, rooms)}

    scene, room, reason = choose(scenes, rooms, list(args))
    if not scene:
        return {"error": reason}
    bridge.recall(scene["id"])
    return {"scene": scene["metadata"]["name"], "room": room}
