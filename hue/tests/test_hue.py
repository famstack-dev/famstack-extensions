"""`./stack hue`, described by what the family sees the lights do.

Each test runs a command as a family member or an agent runs it, a real
`./stack hue <cmd> --json` process (the lane's `stack`, here `unpaired` or
`paired`, see `conftest.py`), against `FakeBridge`, which answers as the
family's bridge did when we paired with it. Assertions are about the
bridge afterwards (which scene it was told to call up, which requests
reached it, whether it was paired) and the command's exit code and answer.
"""

from __future__ import annotations

import os
import stat
import threading
import tomllib
from pathlib import Path

from fake_bridge import BRIDGE_ID, KEY, FakeBridge


def hue(stack, *args: str):
    """`./stack hue <args> --json`, as an agent runs it."""
    return stack.run("hue", *args, "--json")


def stack_toml(stack) -> Path:
    return stack.instance / "stack.toml"


def data_dir(stack) -> Path:
    """Where the instance keeps its stacklets' data, as `[core] data_dir` says."""
    return Path(tomllib.loads(stack_toml(stack).read_text())["core"]["data_dir"])


# ── Pairing ───────────────────────────────────────────────────────────────


def test_setup_pairs_once_the_button_is_pressed(unpaired, bridge):
    """Given a bridge whose button nobody pressed yet,
    when the admin runs `setup <address>` and presses the button meanwhile,
    then the instance is paired: stack.toml names the bridge's address, and
    the key sits in a file only the admin can read, not in stack.toml.
    Why: every instance pairs once by the button, and the key is a password."""
    threading.Timer(0.3, bridge.press_button).start()

    ran = hue(unpaired, "setup", "127.0.0.1")

    assert ran.code == 0, ran
    assert ran.json["id"] == BRIDGE_ID
    assert bridge.paired == ["famstack#stack"]
    toml = stack_toml(unpaired).read_text()
    assert 'host = "127.0.0.1"' in toml
    assert KEY not in toml
    key_file = data_dir(unpaired) / "hue" / "bridge.json"
    assert KEY in key_file.read_text()
    assert stat.S_IMODE(os.stat(key_file).st_mode) == 0o600


def test_a_command_before_setup_says_how_to_set_up(unpaired, bridge):
    ran = hue(unpaired, "scene", "list")

    assert ran.code == 1, ran
    assert "stack hue setup" in ran.json["error"]


def test_the_key_never_goes_to_a_device_with_another_certificate(paired, bridge, other_certificate):
    """Given a paired instance, when another device answers at the bridge's
    address, then the command refuses and that device gets no request at all.
    Why: the key opens every light in the house; it goes only to the bridge
    whose certificate was seen at pairing."""
    with FakeBridge(other_certificate) as impostor:
        toml = stack_toml(paired)
        toml.write_text(toml.read_text().replace(f"port = {bridge.port}", f"port = {impostor.port}"))

        ran = hue(paired, "scene", "list")

        assert ran.code == 1, ran
        assert "certificate" in ran.json["error"]
        assert impostor.requests == []


# ── Scenes ────────────────────────────────────────────────────────────────


def test_scene_list_names_the_scenes_by_room(paired, bridge):
    ran = hue(paired, "scene", "list")

    assert ran.code == 0, ran
    assert ran.json["scenes"]["Living Room"] == ["Read", "Relax", "Valley Dawn"]
    assert ran.json["scenes"]["Kids Room"] == ["Nightlight", "Relax"]


def test_scene_in_a_room(paired, bridge):
    """`scene relax living room` calls up Relax in the living room,
    whatever the case of the words."""
    ran = hue(paired, "scene", "relax", "Living", "Room")

    assert ran.code == 0, ran
    assert ran.json == {"scene": "Relax", "room": "Living Room"}
    assert bridge.recalled == ["scene-1"]


def test_scene_in_a_room_whose_name_has_spaces(paired, bridge):
    ran = hue(paired, "scene", "relax", "kids", "room")

    assert ran.code == 0, ran
    assert bridge.recalled == ["scene-3"]


def test_a_scene_whose_name_is_unique_needs_no_room(paired, bridge):
    """`scene valley dawn` is found without a room: only one
    room has it, and its name has spaces."""
    ran = hue(paired, "scene", "valley", "dawn")

    assert ran.code == 0, ran
    assert bridge.recalled == ["scene-6"]


def test_a_scene_in_several_rooms_without_a_room_names_the_rooms(paired, bridge):
    """Given Relax in two rooms, `scene relax` calls up nothing
    and names both rooms. Why: lighting up the wrong room is worse than asking."""
    ran = hue(paired, "scene", "relax")

    assert ran.code == 1, ran
    assert "Living Room" in ran.json["error"] and "Kids Room" in ran.json["error"]
    assert bridge.recalled == []


def test_of_two_scenes_with_one_name_in_one_room_the_last_used_wins(paired, bridge):
    """Given two scenes called Nightlight in one room (the family's bridge
    had that), the one called up most recently is the one meant."""
    ran = hue(paired, "scene", "nightlight", "kids", "room")

    assert ran.code == 0, ran
    assert bridge.recalled == ["scene-5"]


def test_an_unknown_scene_says_how_to_list_them(paired, bridge):
    ran = hue(paired, "scene", "disco", "living", "room")

    assert ran.code == 1, ran
    assert "stack hue scene list" in ran.json["error"]
    assert bridge.recalled == []


def test_scenes_are_read_fresh_on_every_call(paired, bridge):
    """A scene renamed in the Hue app is found by its new name at once:
    nothing is cached between calls."""
    from fake_bridge import SCENES
    original = SCENES[1]["name"]
    try:
        SCENES[1]["name"] = "Read New"
        ran = hue(paired, "scene", "read new")
        assert ran.code == 0, ran
        assert bridge.recalled == ["scene-2"]
    finally:
        SCENES[1]["name"] = original


# ── Brightness, on and off ────────────────────────────────────────────────

LIVING = ["light-ceiling", "light-floor", "light-reading"]


def test_status_names_rooms_zones_and_lamps_with_their_state(paired, bridge):
    """Given the living room lamps at 60 % and everything else off, `status`
    says so per room, per zone and per lamp, so the family and the agent
    know the names to use."""
    for light in LIVING:
        bridge.set_light(light, True, 60)

    ran = hue(paired, "status")

    assert ran.code == 0, ran
    assert ran.json["rooms"]["Living Room"] == "on 60 %"
    assert ran.json["rooms"]["Kids Room"] == "off"
    assert ran.json["rooms"]["Bedroom"] == "no lamps"
    assert ran.json["zones"]["Reading Corner"] == "on 60 %"
    assert ran.json["lamps"]["Reading Lamp (Living Room)"] == "on 60 %"


def test_brightness_of_a_room_sets_its_lamps_and_switches_them_on(paired, bridge):
    """Given the living room off, `brightness living room 40` lights all its
    lamps at 40 %, and the other rooms stay as they were.
    Why: someone who asks for 40 % wants light."""
    ran = hue(paired, "brightness", "living", "room", "40")

    assert ran.code == 0, ran
    assert ran.json == {"lights": "Living Room", "brightness": 40}
    assert all(bridge.lights[light] == {"on": True, "brightness": 40.0} for light in LIVING)
    assert bridge.lights["light-kids-floor"]["on"] is False


def test_brightness_of_one_lamp_and_of_a_zone(paired, bridge):
    """A lamp or a zone (a group of lamps made in the Hue app) works like a
    room. The lamp's name ends in a space on the bridge; the words do not
    need it."""
    ran = hue(paired, "brightness", "reading", "lamp", "30%")
    assert ran.code == 0, ran
    assert bridge.lights["light-reading"] == {"on": True, "brightness": 30.0}
    assert bridge.lights["light-ceiling"]["on"] is False

    ran = hue(paired, "brightness", "reading", "corner", "70")
    assert ran.code == 0, ran
    assert bridge.lights["light-floor"] == {"on": True, "brightness": 70.0}
    assert bridge.lights["light-reading"] == {"on": True, "brightness": 70.0}


def test_brightness_steps_up_and_down(paired, bridge):
    """`+10` and `-20` change the brightness from where it is: "brighter"
    and "darker" in the chat."""
    for light in LIVING:
        bridge.set_light(light, True, 50)

    ran = hue(paired, "brightness", "living", "room", "+10")
    assert ran.code == 0, ran
    assert bridge.lights["light-ceiling"]["brightness"] == 60.0

    ran = hue(paired, "brightness", "living", "room", "-20")
    assert ran.code == 0, ran
    assert bridge.lights["light-ceiling"]["brightness"] == 40.0


def test_brightness_refuses_a_level_out_of_range(paired, bridge):
    """0 % is refused with a pointer to `off`, 150 % as out of range; the
    lamps stay as they were."""
    zero = hue(paired, "brightness", "living", "room", "0")
    too_bright = hue(paired, "brightness", "living", "room", "150")

    assert zero.code == 1 and too_bright.code == 1, (zero, too_bright)
    assert "stack hue off" in zero.json["error"]
    assert "1 to 100" in too_bright.json["error"]
    assert bridge.lights["light-ceiling"]["on"] is False


def test_off_and_on(paired, bridge):
    ran = hue(paired, "on", "living", "room")
    assert ran.code == 0, ran
    assert all(bridge.lights[light]["on"] for light in LIVING)

    ran = hue(paired, "off", "living", "room")
    assert ran.code == 0, ran
    assert not any(bridge.lights[light]["on"] for light in LIVING)


def test_off_everywhere(paired, bridge):
    """`off all` switches off every lamp in the house."""
    for light in bridge.lights:
        bridge.set_light(light, True, 80)

    ran = hue(paired, "off", "all")

    assert ran.code == 0, ran
    assert ran.json == {"lights": "all", "on": False}
    assert not any(state["on"] for state in bridge.lights.values())


def test_a_room_named_exactly_wins_over_lamps_named_after_it(paired, bridge):
    """`off living room` means the room, although "Living Room Ceiling" is
    a lamp whose name contains it."""
    for light in LIVING:
        bridge.set_light(light, True, 80)

    ran = hue(paired, "off", "living", "room")

    assert ran.code == 0, ran
    assert ran.json["lights"] == "Living Room"
    assert not any(bridge.lights[light]["on"] for light in LIVING)


def test_a_lamp_name_in_two_rooms_needs_the_room(paired, bridge):
    """Given a Floor Lamp in two rooms, `on floor lamp` switches nothing
    and names both rooms; `on floor lamp kids room` switches the one in
    the kids room. Why: light in the wrong room is worse than asking."""
    ran = hue(paired, "on", "floor", "lamp")
    assert ran.code == 1, ran
    assert "Living Room" in ran.json["error"] and "Kids Room" in ran.json["error"]
    assert not any(state["on"] for state in bridge.lights.values())

    ran = hue(paired, "on", "floor", "lamp", "kids", "room")
    assert ran.code == 0, ran
    assert bridge.lights["light-kids-floor"]["on"] is True
    assert bridge.lights["light-floor"]["on"] is False


def test_a_room_without_lamps_says_so(paired, bridge):
    """The family's bedroom had scenes but no lamps; asking for light there
    says so instead of pretending."""
    ran = hue(paired, "brightness", "bedroom", "50")

    assert ran.code == 1, ran
    assert "no lamps" in ran.json["error"]


def test_an_unknown_name_says_how_to_list_them(paired, bridge):
    ran = hue(paired, "on", "garage")

    assert ran.code == 1, ran
    assert "stack hue status" in ran.json["error"]
