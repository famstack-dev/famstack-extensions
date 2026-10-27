"""`./stack hue`, described by what the family sees the lights do.

Each test runs a command as `./stack hue <cmd>` runs it (`conftest.Stack`)
against `FakeBridge`, which answers as the family's bridge did when we
paired with it. Assertions are about the bridge afterwards (which scene it
was told to call up, which requests reached it, whether it was paired) and
the command's answer.
"""

from __future__ import annotations

import os
import stat
import threading

from conftest import Stack, write_instance
from fake_bridge import BRIDGE_ID, KEY, FakeBridge

# ── Pairing ───────────────────────────────────────────────────────────────


def test_setup_pairs_once_the_button_is_pressed(tmp_path, bridge):
    """Given a bridge whose button nobody pressed yet,
    when the admin runs `setup <address>` and presses the button meanwhile,
    then the instance is paired: stack.toml names the bridge's address, and
    the key sits in a file only the admin can read, not in stack.toml.
    Why: every instance pairs once by the button, and the key is a password."""
    stack = Stack(write_instance(tmp_path, bridge.config(host=False)))
    threading.Timer(0.3, bridge.press_button).start()

    answer = stack.hue("setup", "127.0.0.1")

    assert answer["id"] == BRIDGE_ID
    assert bridge.paired == ["famstack#stack"]
    assert 'host = "127.0.0.1"' in stack.stack_toml()
    assert KEY not in stack.stack_toml()
    key_file = stack.data / "hue" / "bridge.json"
    assert KEY in key_file.read_text()
    assert stat.S_IMODE(os.stat(key_file).st_mode) == 0o600


def test_a_command_before_setup_says_how_to_set_up(tmp_path, bridge):
    stack = Stack(write_instance(tmp_path, bridge.config(host=False)))

    assert "stack hue setup" in stack.hue("scene", "list")["error"]


def test_the_key_never_goes_to_a_device_with_another_certificate(stack, bridge, other_certificate):
    """Given a paired instance, when another device answers at the bridge's
    address, then the command refuses and that device gets no request at all.
    Why: the key opens every light in the house; it goes only to the bridge
    whose certificate was seen at pairing."""
    with FakeBridge(other_certificate) as impostor:
        toml = stack.instance / "stack.toml"
        toml.write_text(toml.read_text().replace(f"port = {bridge.port}", f"port = {impostor.port}"))

        answer = stack.hue("scene", "list")

        assert "certificate" in answer["error"]
        assert impostor.requests == []


# ── Scenes ────────────────────────────────────────────────────────────────


def test_scene_list_names_the_scenes_by_room(stack, bridge):
    scenes = stack.hue("scene", "list")["scenes"]

    assert scenes["Living Room"] == ["Read", "Relax", "Valley Dawn"]
    assert scenes["Kids Room"] == ["Nightlight", "Relax"]


def test_scene_in_a_room(stack, bridge):
    """`scene relax living room` calls up Relax in the living room,
    whatever the case of the words."""
    answer = stack.hue("scene", "relax", "Living", "Room")

    assert answer == {"scene": "Relax", "room": "Living Room"}
    assert bridge.recalled == ["scene-1"]


def test_scene_in_a_room_whose_name_has_spaces(stack, bridge):
    stack.hue("scene", "relax", "kids", "room")

    assert bridge.recalled == ["scene-3"]


def test_a_scene_whose_name_is_unique_needs_no_room(stack, bridge):
    """`scene valley dawn` is found without a room: only one
    room has it, and its name has spaces."""
    stack.hue("scene", "valley", "dawn")

    assert bridge.recalled == ["scene-6"]


def test_a_scene_in_several_rooms_without_a_room_names_the_rooms(stack, bridge):
    """Given Relax in two rooms, `scene relax` calls up nothing
    and names both rooms. Why: lighting up the wrong room is worse than asking."""
    error = stack.hue("scene", "relax")["error"]

    assert "Living Room" in error and "Kids Room" in error
    assert bridge.recalled == []


def test_of_two_scenes_with_one_name_in_one_room_the_last_used_wins(stack, bridge):
    """Given two scenes called Nightlight in one room (the family's bridge
    had that), the one called up most recently is the one meant."""
    stack.hue("scene", "nightlight", "kids", "room")

    assert bridge.recalled == ["scene-5"]


def test_an_unknown_scene_says_how_to_list_them(stack, bridge):
    error = stack.hue("scene", "disco", "living", "room")["error"]

    assert "stack hue scene list" in error
    assert bridge.recalled == []


def test_scenes_are_read_fresh_on_every_call(stack, bridge):
    """A scene renamed in the Hue app is found by its new name at once:
    nothing is cached between calls."""
    from fake_bridge import SCENES
    original = SCENES[1]["name"]
    try:
        SCENES[1]["name"] = "Read New"
        stack.hue("scene", "read new")
        assert bridge.recalled == ["scene-2"]
    finally:
        SCENES[1]["name"] = original


# ── Brightness, on and off ────────────────────────────────────────────────

LIVING = ["light-ceiling", "light-floor", "light-reading"]


def test_status_names_rooms_zones_and_lamps_with_their_state(stack, bridge):
    """Given the living room lamps at 60 % and everything else off, `status`
    says so per room, per zone and per lamp, so the family and the agent
    know the names to use."""
    for light in LIVING:
        bridge.set_light(light, True, 60)

    answer = stack.hue("status")

    assert answer["rooms"]["Living Room"] == "on 60 %"
    assert answer["rooms"]["Kids Room"] == "off"
    assert answer["rooms"]["Bedroom"] == "no lamps"
    assert answer["zones"]["Reading Corner"] == "on 60 %"
    assert answer["lamps"]["Reading Lamp (Living Room)"] == "on 60 %"


def test_brightness_of_a_room_sets_its_lamps_and_switches_them_on(stack, bridge):
    """Given the living room off, `brightness living room 40` lights all its
    lamps at 40 %, and the other rooms stay as they were.
    Why: someone who asks for 40 % wants light."""
    answer = stack.hue("brightness", "living", "room", "40")

    assert answer == {"lights": "Living Room", "brightness": 40}
    assert all(bridge.lights[light] == {"on": True, "brightness": 40.0} for light in LIVING)
    assert bridge.lights["light-kids-floor"]["on"] is False


def test_brightness_of_one_lamp_and_of_a_zone(stack, bridge):
    """A lamp or a zone (a group of lamps made in the Hue app) works like a
    room. The lamp's name ends in a space on the bridge; the words do not
    need it."""
    stack.hue("brightness", "reading", "lamp", "30%")
    assert bridge.lights["light-reading"] == {"on": True, "brightness": 30.0}
    assert bridge.lights["light-ceiling"]["on"] is False

    stack.hue("brightness", "reading", "corner", "70")
    assert bridge.lights["light-floor"] == {"on": True, "brightness": 70.0}
    assert bridge.lights["light-reading"] == {"on": True, "brightness": 70.0}


def test_brightness_steps_up_and_down(stack, bridge):
    """`+10` and `-20` change the brightness from where it is: "brighter"
    and "darker" in the chat."""
    for light in LIVING:
        bridge.set_light(light, True, 50)

    stack.hue("brightness", "living", "room", "+10")
    assert bridge.lights["light-ceiling"]["brightness"] == 60.0

    stack.hue("brightness", "living", "room", "-20")
    assert bridge.lights["light-ceiling"]["brightness"] == 40.0


def test_brightness_refuses_a_level_out_of_range(stack, bridge):
    """0 % is refused with a pointer to `off`, 150 % as out of range; the
    lamps stay as they were."""
    assert "stack hue off" in stack.hue("brightness", "living", "room", "0")["error"]
    assert "1 to 100" in stack.hue("brightness", "living", "room", "150")["error"]
    assert bridge.lights["light-ceiling"]["on"] is False


def test_off_and_on(stack, bridge):
    stack.hue("on", "living", "room")
    assert all(bridge.lights[light]["on"] for light in LIVING)

    stack.hue("off", "living", "room")
    assert not any(bridge.lights[light]["on"] for light in LIVING)


def test_off_everywhere(stack, bridge):
    """`off all` switches off every lamp in the house."""
    for light in bridge.lights:
        bridge.set_light(light, True, 80)

    answer = stack.hue("off", "all")

    assert answer == {"lights": "all", "on": False}
    assert not any(state["on"] for state in bridge.lights.values())


def test_a_room_named_exactly_wins_over_lamps_named_after_it(stack, bridge):
    """`off living room` means the room, although "Living Room Ceiling" is
    a lamp whose name contains it."""
    for light in LIVING:
        bridge.set_light(light, True, 80)

    answer = stack.hue("off", "living", "room")

    assert answer["lights"] == "Living Room"
    assert not any(bridge.lights[light]["on"] for light in LIVING)


def test_a_lamp_name_in_two_rooms_needs_the_room(stack, bridge):
    """Given a Floor Lamp in two rooms, `on floor lamp` switches nothing
    and names both rooms; `on floor lamp kids room` switches the one in
    the kids room. Why: light in the wrong room is worse than asking."""
    error = stack.hue("on", "floor", "lamp")["error"]
    assert "Living Room" in error and "Kids Room" in error
    assert not any(state["on"] for state in bridge.lights.values())

    stack.hue("on", "floor", "lamp", "kids", "room")
    assert bridge.lights["light-kids-floor"]["on"] is True
    assert bridge.lights["light-floor"]["on"] is False


def test_a_room_without_lamps_says_so(stack, bridge):
    """The family's bedroom had scenes but no lamps; asking for light there
    says so instead of pretending."""
    error = stack.hue("brightness", "bedroom", "50")["error"]

    assert "no lamps" in error


def test_an_unknown_name_says_how_to_list_them(stack, bridge):
    error = stack.hue("on", "garage")["error"]

    assert "stack hue status" in error
