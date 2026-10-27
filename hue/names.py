"""names.py: how words from a person meet names on the bridge.

    clean("Office Strip ")                        # "office strip"
    split_room(["floor", "lamp", "kids", "room"], {"Kids Room"})
    # ("floor lamp", "Kids Room")

Shared by scenes.py and lights.py, so a scene and a lamp are found by the
same rules: case does not matter, nor do spaces at the ends (the family's
bridge has lamp names ending in a space), and the words may end with a
room name to say which room is meant.
"""

from __future__ import annotations


def clean(name: str) -> str:
    """A name as compared: lowercase, no spaces at the ends."""
    return name.strip().lower()


def split_room(words: list[str], rooms: set[str]) -> tuple[str, str]:
    """(the name, the room or "") from the words, the room being the longest
    run of trailing words that names a room. Room names may have spaces."""
    by_clean = {clean(room): room for room in rooms}
    for start in range(1, len(words)):
        tail = clean(" ".join(words[start:]))
        if tail in by_clean:
            return " ".join(words[:start]), by_clean[tail]
    return " ".join(words), ""
