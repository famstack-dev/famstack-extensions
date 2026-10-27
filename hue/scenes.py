"""scenes.py: which scene a person means, from the words they used.

    choose(scenes, rooms, ["relax", "living", "room"])
    # (scene dict, "Living Room", "")     or (None, "", "the reason")

    by_room(scenes, rooms)
    # {"Living Room": ["Read", "Relax"], ...}

Pure functions over the bridge's v2 answers, no I/O, so the rules are easy
to read and to test:

- The words are a scene name, optionally followed by a room name; both may
  have spaces ("Valley Dawn", "Kids Room"). Names
  compare as names.py says. An exact name wins over a partial one.
- A name in several rooms without a room is refused with the rooms: lights
  going on in the wrong room is worse than a question.
- Two scenes with the same name in the same room (the family's bridge had
  two "Nightlight" in one room): the one called up most recently is meant.
"""

from __future__ import annotations

from .names import clean, split_room


def room_names(rooms: list[dict]) -> dict[str, str]:
    """Room and zone ids to their names."""
    return {room["id"]: room["metadata"]["name"] for room in rooms}


def by_room(scenes: list[dict], rooms: list[dict]) -> dict[str, list[str]]:
    """The scene names per room, both sorted, each name once."""
    names = room_names(rooms)
    grouped: dict[str, set[str]] = {}
    for scene in scenes:
        room = names.get(scene["group"]["rid"], "?")
        grouped.setdefault(room, set()).add(scene["metadata"]["name"])
    return {room: sorted(found, key=str.lower) for room, found in sorted(grouped.items())}


def choose(scenes: list[dict], rooms: list[dict], words: list[str]) -> tuple[dict | None, str, str]:
    """The scene `words` mean, its room's name, and "" for no reason, or
    None, "" and the reason nothing was chosen."""
    names = room_names(rooms)
    name, room = split_room(words, set(names.values()))
    candidates = [s for s in scenes if not room or names.get(s["group"]["rid"], "") == room]

    matches = [s for s in candidates if clean(s["metadata"]["name"]) == clean(name)]
    if not matches:
        matches = [s for s in candidates if clean(name) in clean(s["metadata"]["name"])]
    where = f" in {room}" if room else ""
    if not matches:
        return None, "", f"No scene called '{name}'{where}. ./stack hue scene list shows them all."

    found_rooms = sorted({names.get(s["group"]["rid"], "?") for s in matches})
    found_names = sorted({s["metadata"]["name"] for s in matches})
    if len(found_rooms) > 1:
        return None, "", (f"'{name}' is a scene in several rooms: {', '.join(found_rooms)}. "
                          "Say which: ./stack hue scene <name> <room>")
    if len(found_names) > 1:
        return None, "", f"'{name}' fits several scenes{where}: {', '.join(found_names)}"

    newest = max(matches, key=lambda s: (s.get("status") or {}).get("last_recall") or "")
    return newest, found_rooms[0], ""
