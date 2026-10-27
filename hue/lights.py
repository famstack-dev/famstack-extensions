"""lights.py: what "living room", "reading lamp" or "all" means, as lights to switch.

    targets = all_targets(rooms, zones, homes, lights)
    target, reason = find(targets, ["floor", "lamp", "kids", "room"])
    target.kind, target.rtype, target.rid    # "lamp", "light", "<id>"

    level_change("40")     # ({"on": {"on": True}, "dimming": {"brightness": 40}}, 40, "")
    level_change("-20")    # ({"dimming_delta": {"action": "down", "brightness_delta": 20}}, "-20", "")

Something to switch is a room, a zone (a group of lamps made in the Hue
app), a single lamp, or the whole house ("all"). Rooms, zones and the
house switch through their `grouped_light`, a lamp through its `light`;
the bridge passes a group's change on to its lamps.

Rules for the words, in this order (names compare as names.py says):

1. "all" (or "alle") is the whole house.
2. A room or zone named exactly. It wins over lamps whose names contain
   it: a room "Office" over a lamp "Office Lamp".
3. A lamp named exactly; if lamps of that name are in several rooms, the
   words must end with the room ("floor lamp kids room").
4. A lamp named by part of its name, within the room the words end with.
5. Part of any name, if only one fits.

Pure functions over the bridge's v2 answers, no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .names import clean, split_room

EVERYWHERE = {"alle", "all"}
LEVEL = re.compile(r"^(?P<sign>[+-]?)(?P<number>\d{1,3})%?$")


@dataclass(frozen=True)
class Target:
    """Lights to switch. `rid` is None for a room without lamps.

    >>> Target("Reading Lamp", "lamp", "light", "light-reading", room="Living Room").label
    'Reading Lamp (Living Room)'
    """
    name: str
    kind: str               # room, zone, lamp, home
    rtype: str              # grouped_light or light
    rid: str | None
    room: str = ""          # for a lamp: the room it is in

    @property
    def label(self) -> str:
        return f"{self.name} ({self.room})" if self.room else self.name


def all_targets(rooms: list[dict], zones: list[dict], homes: list[dict], lights: list[dict]) -> list[Target]:
    """Every room, zone and lamp, and the whole house, from the v2 answers."""
    device_room = {child["rid"]: room["metadata"]["name"].strip()
                   for room in rooms for child in room["children"] if child["rtype"] == "device"}
    found = [Target(group["metadata"]["name"].strip(), kind, "grouped_light", _grouped_light(group))
             for kind, groups in (("room", rooms), ("zone", zones)) for group in groups]
    found += [Target(light["metadata"]["name"].strip(), "lamp", "light", light["id"],
                     room=device_room.get(light["owner"]["rid"], ""))
              for light in lights]
    found += [Target("all", "home", "grouped_light", _grouped_light(home)) for home in homes[:1]]
    return found


def find(targets: list[Target], words: list[str]) -> tuple[Target | None, str]:
    """The target the words mean, or None and the reason (rules above)."""
    phrase = clean(" ".join(words))
    groups = [t for t in targets if t.kind in ("room", "zone")]
    lamps = [t for t in targets if t.kind == "lamp"]

    if phrase in EVERYWHERE:
        return next((t for t in targets if t.kind == "home"), None), ""
    if exact := [t for t in groups if clean(t.name) == phrase]:
        return exact[0], ""
    if exact := [t for t in lamps if clean(t.name) == phrase]:
        return _one(exact, " ".join(words))

    name, room = split_room(words, {t.name for t in groups if t.kind == "room"})
    if room:
        in_room = [t for t in lamps if t.room == room]
        exact = [t for t in in_room if clean(t.name) == clean(name)]
        return _one(exact or [t for t in in_room if clean(name) in clean(t.name)], " ".join(words))

    partial = [t for t in groups + lamps if phrase in clean(t.name)]
    if not partial:
        return None, f"No room, zone or lamp called '{' '.join(words)}'. ./stack hue status shows them all."
    return _one(partial, " ".join(words))


def level_change(level: str) -> tuple[dict | None, int | str, str]:
    """The v2 change for a brightness: an absolute level switches the
    lights on at it, a step (+10, -20) moves them from where they are.
    None and the reason for a level out of range."""
    match = LEVEL.match(level.strip())
    if not match:
        return None, "", "Give a brightness from 1 to 100, or a step like +10 or -20."
    number = int(match["number"])
    if match["sign"]:
        action = "up" if match["sign"] == "+" else "down"
        return {"dimming_delta": {"action": action, "brightness_delta": min(number, 100)}}, level.strip(), ""
    if number == 0:
        return None, "", "0 % is off: ./stack hue off <name>"
    if number > 100:
        return None, "", "Give a brightness from 1 to 100."
    return {"on": {"on": True}, "dimming": {"brightness": number}}, number, ""


def _one(matches: list[Target], words: str) -> tuple[Target | None, str]:
    if not matches:
        return None, f"No lamp called '{words}' there. ./stack hue status shows them all."
    if len(matches) == 1:
        return matches[0], ""
    rooms = sorted({t.room for t in matches if t.room})
    if len({t.name for t in matches}) == 1 and rooms:
        return None, (f"'{matches[0].name}' is a lamp in several rooms: {', '.join(rooms)}. "
                      "Say which: <lamp> <room>")
    return None, f"'{words}' fits several: {', '.join(sorted(t.label for t in matches))}"


def _grouped_light(group: dict) -> str | None:
    return next((s["rid"] for s in group.get("services", []) if s["rtype"] == "grouped_light"), None)
