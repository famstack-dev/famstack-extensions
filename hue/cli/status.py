"""stack hue status: every room, zone and lamp, on or off and how bright.

    ./stack hue status
    # rooms: {"Office": "on 100 %", "Bedroom": "no lamps", ...}
    # zones: {...}
    # lamps: {"Office Lamp (Office)": "on 100 %", ...}

It names everything the other commands take, so the family and the agent
know what to say. A room's brightness is what the bridge reports for the
room as a whole (about the average of its lamps that are on).
"""

from __future__ import annotations

from ._common import paired_bridge, targets_of

HELP = "Show every room, zone and lamp: on or off and how bright"


def run(args, stacklet, config):
    bridge, error = paired_bridge(config)
    if error:
        return error
    states = {item["id"]: item for item in bridge.resources("grouped_light") + bridge.resources("light")}
    answer: dict[str, dict[str, str]] = {"rooms": {}, "zones": {}, "lamps": {}}
    for target in targets_of(bridge):
        if target.kind == "home":
            continue
        section = {"room": "rooms", "zone": "zones", "lamp": "lamps"}[target.kind]
        answer[section][target.label] = describe(states.get(target.rid or ""))
    return answer


def describe(state: dict | None) -> str:
    """"on 60 %", "off", or "no lamps" for a room without any."""
    if state is None:
        return "no lamps"
    if not state.get("on", {}).get("on"):
        return "off"
    return f"on {round(state.get('dimming', {}).get('brightness', 0))} %"
