"""fake_bridge.py: a stand-in Philips Hue Bridge on localhost, for the hue stacklet's tests.

    with FakeBridge(certificate) as bridge:
        bridge.config()          # the stack.toml [hue] lines that point at it
        bridge.press_button()    # as a person does, so pairing succeeds
        bridge.recalled          # the scene ids called up, in order
        bridge.lights            # id -> {"on": bool, "brightness": float}
        bridge.requests          # (method, path, key sent) of every request

It answers the way the family's bridge (BSB002, API 1.78.0) answered on
2026-10-26, so the tests assert against what the real bridge does:

- HTTPS only, with the bridge's own self-signed certificate.
- `GET /api/0/config` answers without a key: name, bridge id, model.
- `POST /api` with a `devicetype` pairs: until the round button was
  pressed it answers `[{"error": {"type": 101, ... "link button not
  pressed"}}]`, after it `[{"success": {"username": ..., "clientkey": ...}}]`.
- `GET /clip/v2/resource/<kind>` answers `{"errors": [], "data": [...]}`
  with the `hue-application-key` header, and HTTP 403 without it.
- A room lists its devices as `children` and, if it has lamps, its
  `grouped_light` under `services`; a room without lamps has neither (the
  family's bedroom). A zone lists its lights directly. `bridge_home` has
  the `grouped_light` for the whole house. A light names its device as
  `owner`, and some light names end in a space ("Office Strip ").
- Scene names repeat: "Relax" in every room, and one room had two
  scenes called "Nightlight". A scene says when it was last called up in
  `status.last_recall`.
- `PUT /clip/v2/resource/scene/<id>` with `{"recall": {"action": "active"}}`
  calls a scene up and answers HTTP 200 with `{"data": [{"rid": <id>,
  "rtype": "scene"}], "errors": []}`.

- `PUT .../light/<id>` and `.../grouped_light/<id>` take `on`, `dimming`
  and `dimming_delta` (a step up or down). A group passes the change on to
  each of its lamps, and reports as its brightness the average of its
  lamps that are on (office: 80 % and 30 % read as 55 %).

Rooms, lights, scenes and ids are made up.
"""

from __future__ import annotations

import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Self
from urllib.parse import urlparse

KEY = "fake-application-key-0123456789abcdef"
BRIDGE_ID = "ECB5FAFFFE000001"
HOME_GROUP = "gl-home"

ROOMS = [
    {"id": "room-living", "name": "Living Room", "group": "gl-living",
     "devices": ["dev-ceiling", "dev-floor", "dev-reading", "dev-switch"]},
    {"id": "room-kids", "name": "Kids Room", "group": "gl-kids", "devices": ["dev-kids-floor"]},
    {"id": "room-sleep", "name": "Bedroom", "group": None, "devices": []},
]

ZONES = [
    {"id": "zone-read", "name": "Reading Corner", "group": "gl-read", "lights": ["light-floor", "light-reading"]},
]

LIGHTS = [
    {"id": "light-ceiling", "name": "Living Room Ceiling", "device": "dev-ceiling"},
    {"id": "light-floor", "name": "Floor Lamp", "device": "dev-floor"},
    {"id": "light-reading", "name": "Reading Lamp ", "device": "dev-reading"},
    {"id": "light-kids-floor", "name": "Floor Lamp", "device": "dev-kids-floor"},
]

SCENES = [
    {"id": "scene-1", "name": "Relax", "room": "room-living", "last": "2026-10-20T19:00:00.000Z"},
    {"id": "scene-2", "name": "Read", "room": "room-living", "last": "2026-10-01T19:00:00.000Z"},
    {"id": "scene-3", "name": "Relax", "room": "room-kids", "last": "2026-10-02T19:00:00.000Z"},
    {"id": "scene-4", "name": "Nightlight", "room": "room-kids", "last": "2026-09-01T20:00:00.000Z"},
    {"id": "scene-5", "name": "Nightlight", "room": "room-kids", "last": "2026-10-25T20:00:00.000Z"},
    {"id": "scene-6", "name": "Valley Dawn", "room": "room-living", "last": "2026-10-03T07:00:00.000Z"},
]


def _group_service(group_id: str | None) -> list[dict]:
    """A room's or zone's `services` entry for its grouped light, if it has lamps."""
    return [{"rid": group_id, "rtype": "grouped_light"}] if group_id else []


class FakeBridge:
    """A Hue Bridge on 127.0.0.1 over HTTPS with `certificate`, a
    (cert file, key file) pair. Every lamp starts off at 50 %."""

    def __init__(self, certificate: tuple[Path, Path]):
        self.button_pressed = False
        self.recalled: list[str] = []
        self.paired: list[str] = []
        self.requests: list[tuple[str, str, str | None]] = []
        self.lights = {light["id"]: {"on": False, "brightness": 50.0} for light in LIGHTS}
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(certificate[0]), str(certificate[1]))
        self._server.socket = context.wrap_socket(self._server.socket, server_side=True)

    def __enter__(self) -> Self:
        threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.05},
                         daemon=True).start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def config(self, host: bool = True) -> str:
        """The stack.toml [hue] section for this bridge. `host=False`
        leaves out the address, as before `stack hue setup` ran."""
        lines = ["[hue]", f"port = {self.port}"]
        if host:
            lines.insert(1, 'host = "127.0.0.1"')
        return "\n".join(lines) + "\n"

    def press_button(self) -> None:
        self.button_pressed = True

    def set_light(self, light_id: str, on: bool, brightness: float) -> None:
        """Set a lamp's state directly, as the Hue app would."""
        self.lights[light_id] = {"on": on, "brightness": brightness}

    # ── Groups of lights ──────────────────────────────────────────────

    def _group_lights(self, group_id: str) -> list[str]:
        if group_id == HOME_GROUP:
            return [light["id"] for light in LIGHTS]
        for room in ROOMS:
            if room["group"] == group_id:
                return [light["id"] for light in LIGHTS if light["device"] in room["devices"]]
        for zone in ZONES:
            if zone["group"] == group_id:
                return list(zone["lights"])
        raise KeyError(group_id)

    def _group_state(self, group_id: str) -> dict:
        states = [self.lights[light] for light in self._group_lights(group_id)]
        lit = [state["brightness"] for state in states if state["on"]]
        return {"on": bool(lit), "brightness": sum(lit) / len(lit) if lit else 0.0}

    def _apply(self, light_id: str, change: dict) -> None:
        state = self.lights[light_id]
        if "on" in change:
            state["on"] = change["on"]["on"]
        if "dimming" in change:
            state["brightness"] = float(change["dimming"]["brightness"])
        if "dimming_delta" in change:
            delta = change["dimming_delta"]
            step = delta["brightness_delta"] if delta["action"] == "up" else -delta["brightness_delta"]
            state["brightness"] = min(100.0, max(0.0, state["brightness"] + step))

    # ── What the bridge answers ───────────────────────────────────────

    def _resource(self, kind: str) -> list[dict]:
        group = _group_service
        if kind == "room":
            return [{"id": r["id"], "id_v1": "/groups/1", "type": "room",
                     "children": [{"rid": d, "rtype": "device"} for d in r["devices"]],
                     "services": group(r["group"]),
                     "metadata": {"name": r["name"], "archetype": "living_room"}} for r in ROOMS]
        if kind == "zone":
            return [{"id": z["id"], "id_v1": "/groups/9", "type": "zone",
                     "children": [{"rid": light, "rtype": "light"} for light in z["lights"]],
                     "services": group(z["group"]),
                     "metadata": {"name": z["name"], "archetype": "reading"}} for z in ZONES]
        if kind == "bridge_home":
            return [{"id": "home", "id_v1": "/groups/0", "type": "bridge_home",
                     "children": [{"rid": r["id"], "rtype": "room"} for r in ROOMS],
                     "services": group(HOME_GROUP)}]
        if kind == "light":
            return [{"id": light["id"], "id_v1": "/lights/1", "type": "light",
                     "owner": {"rid": light["device"], "rtype": "device"},
                     "metadata": {"name": light["name"], "archetype": "classic_bulb", "function": "mixed"},
                     "on": {"on": self.lights[light["id"]]["on"]},
                     "dimming": {"brightness": self.lights[light["id"]]["brightness"], "min_dim_level": 0.2}}
                    for light in LIGHTS]
        if kind == "grouped_light":
            owners = ([(r["group"], r["id"], "room") for r in ROOMS if r["group"]]
                      + [(z["group"], z["id"], "zone") for z in ZONES] + [(HOME_GROUP, "home", "bridge_home")])
            return [{"id": group_id, "id_v1": "/groups/1", "type": "grouped_light",
                     "owner": {"rid": owner, "rtype": rtype},
                     "on": {"on": self._group_state(group_id)["on"]},
                     "dimming": {"brightness": self._group_state(group_id)["brightness"]}}
                    for group_id, owner, rtype in owners]
        if kind == "scene":
            return [{"id": s["id"], "id_v1": "/scenes/x", "actions": [], "palette": {},
                     "metadata": {"name": s["name"], "image": {"rid": "i", "rtype": "public_image"}},
                     "group": {"rid": s["room"], "rtype": "room"}, "speed": 0.6,
                     "auto_dynamic": False, "recall": {},
                     "status": {"active": "inactive", "last_recall": s["last"]}, "type": "scene"}
                    for s in SCENES]
        raise KeyError(kind)

    def _put(self, kind: str, resource_id: str, change: dict) -> bool:
        """Apply a PUT; False for an id the bridge does not know."""
        with self._lock:
            if kind == "scene":
                if change.get("recall", {}).get("action") == "active":
                    self.recalled.append(resource_id)
                return True
            if kind == "light" and resource_id in self.lights:
                self._apply(resource_id, change)
                return True
            if kind == "grouped_light":
                try:
                    lights = self._group_lights(resource_id)
                except KeyError:
                    return False
                for light in lights:
                    self._apply(light, change)
                return True
        return False

    def _handler(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def parse_request(self) -> bool:
                ok = super().parse_request()
                if ok:
                    bridge.requests.append((self.command, urlparse(self.path).path,
                                            self.headers.get("hue-application-key")))
                return ok

            def _json(self, status: int, body) -> None:
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _body(self) -> dict:
                return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")

            def _authorized(self) -> bool:
                if self.headers.get("hue-application-key") == KEY:
                    return True
                self._json(403, {"errors": [{"description": "Forbidden"}], "data": []})
                return False

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/api/0/config":
                    return self._json(200, {"name": "Hue Bridge", "apiversion": "1.78.0",
                                            "bridgeid": BRIDGE_ID, "modelid": "BSB002"})
                if path.startswith("/clip/v2/resource/") and self._authorized():
                    with bridge._lock:
                        data = bridge._resource(path.rsplit("/", 1)[1])
                    return self._json(200, {"errors": [], "data": data})

            def do_POST(self):
                if urlparse(self.path).path != "/api":
                    return self._json(404, [])
                devicetype = self._body().get("devicetype", "")
                if not bridge.button_pressed:
                    return self._json(200, [{"error": {"type": 101, "address": "",
                                                       "description": "link button not pressed"}}])
                bridge.paired.append(devicetype)
                self._json(200, [{"success": {"username": KEY, "clientkey": "FAKECLIENTKEY"}}])

            def do_PUT(self):
                parts = urlparse(self.path).path.split("/")
                if len(parts) != 6 or parts[1:4] != ["clip", "v2", "resource"] or not self._authorized():
                    return self._json(404, {"errors": [{"description": "not found"}], "data": []})
                kind, resource_id = parts[4], parts[5]
                if not bridge._put(kind, resource_id, self._body()):
                    return self._json(404, {"errors": [{"description": f"{kind} {resource_id} not found"}],
                                            "data": []})
                self._json(200, {"data": [{"rid": resource_id, "rtype": kind}], "errors": []})

        return Handler
