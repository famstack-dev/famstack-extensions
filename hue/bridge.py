"""bridge.py: one Philips Hue Bridge, over its local API, and finding it.

    bridge = HueBridge("192.168.1.20", key=..., fingerprint=...)
    bridge.resources("scene")       # [{"id", "metadata": {"name"}, "group": {"rid"}, ...}]
    bridge.recall("<scene id>")
    bridge.update("grouped_light", "<id>", {"on": {"on": False}})

    find_bridges()                  # [("192.168.1.20", "ECB5FAFFFE000001")]
    HueBridge(host).pair("famstack#stack")   # the key, once the button was pressed

The bridge has a documented local API, so nothing here goes through the
Philips cloud: the v1 endpoint `/api` pairs, the v2 endpoints
`/clip/v2/resource/<kind>` read rooms and scenes and call a scene up. Every
call is HTTPS on port 443 with the bridge's own certificate.

SAFETY: the key opens every light in the house, and the bridge's
certificate is self-signed. So the certificate is pinned: `setup` records
its SHA-256 fingerprint at pairing (trust on first use), and every later
call checks the certificate it is shown against that fingerprint before it
sends anything. A different device at the bridge's address gets no request
and no key.

Tried on the family's bridge (BSB002, API 1.78.0) on 2026-10-26: SSDP
finds it with a `hue-bridgeid` header, `/api/0/config` answers without a
key, pairing answers error 101 until the button is pressed, the v2 reads
answer 403 without the key.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import socket
import ssl
import time

CALL_SECONDS = 5
FIND_SECONDS = 3            # the bridge answered SSDP within a second


class BridgeError(Exception):
    """The bridge refused a call, or the device at its address is not it."""


class HueBridge:
    """The bridge at `host`. Without `fingerprint` it trusts any certificate,
    which only `setup` does, once, to pair and record the fingerprint."""

    def __init__(self, host: str, port: int = 443, key: str = "", fingerprint: str = ""):
        self.host = host
        self.port = port
        self.key = key
        self.fingerprint = fingerprint

    # ── Who it is ─────────────────────────────────────────────────────

    def public_config(self) -> dict:
        """What the bridge says about itself without a key: `name`,
        `bridgeid`, `modelid`, `apiversion`."""
        return self._call("GET", "/api/0/config", send_key=False)

    def certificate_fingerprint(self) -> str:
        """The SHA-256 of the certificate the device at `host` shows now."""
        connection = self._connect()
        try:
            return _fingerprint(connection)
        finally:
            connection.close()

    # ── Pairing ───────────────────────────────────────────────────────

    def pair(self, devicetype: str) -> str | None:
        """Ask for a key as `devicetype`; the key once the round button was
        pressed (the bridge allows it for about 30 seconds after), None
        until then. Raises BridgeError for any other refusal."""
        answer = self._call("POST", "/api", {"devicetype": devicetype, "generateclientkey": True},
                            send_key=False)
        first = answer[0] if isinstance(answer, list) and answer else {}
        if "success" in first:
            return first["success"]["username"]
        error = first.get("error") or {}
        if error.get("type") == 101:        # link button not pressed
            return None
        raise BridgeError(f"the bridge refused pairing: {error.get('description', answer)}")

    # ── Rooms and scenes ──────────────────────────────────────────────

    def resources(self, kind: str) -> list[dict]:
        """The v2 resources of `kind` (`room`, `zone`, `scene`)."""
        return self._call("GET", f"/clip/v2/resource/{kind}").get("data", [])

    def recall(self, scene_id: str) -> None:
        """Call the scene up: its lights go on in its colours."""
        self.update("scene", scene_id, {"recall": {"action": "active"}})

    def update(self, kind: str, resource_id: str, change: dict) -> None:
        """Change one resource: a `light`, a `grouped_light` (a room, a zone
        or the whole house), a `scene`. `change` is v2 JSON such as
        `{"on": {"on": true}, "dimming": {"brightness": 40}}`."""
        answer = self._call("PUT", f"/clip/v2/resource/{kind}/{resource_id}", change)
        if answer.get("errors"):
            raise BridgeError(f"the bridge refused the change: {answer['errors']}")

    # ── HTTPS with a pinned certificate ───────────────────────────────

    def _connect(self) -> http.client.HTTPSConnection:
        # Verification is the fingerprint check below, not a CA: the
        # bridge's certificate is self-signed.
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        connection = http.client.HTTPSConnection(self.host, self.port, context=context,
                                                 timeout=CALL_SECONDS)
        connection.connect()
        return connection

    def _call(self, method: str, path: str, body: dict | None = None, send_key: bool = True):
        """One request, answered as parsed JSON. Raises BridgeError when the
        certificate does not match or the bridge answers an HTTP error,
        OSError when nothing answers."""
        connection = self._connect()
        try:
            # SAFETY: check the certificate before a single byte of the
            # request, key included, goes out.
            if self.fingerprint and _fingerprint(connection) != self.fingerprint:
                raise BridgeError(
                    f"the device at {self.host} shows a different certificate than the bridge "
                    "did at setup. If you replaced the bridge, run ./stack hue setup again.")
            headers = {"Content-Type": "application/json"}
            if send_key:
                headers["hue-application-key"] = self.key
            connection.request(method, path, body=json.dumps(body) if body is not None else None,
                               headers=headers)
            response = connection.getresponse()
            data = response.read()
        finally:
            connection.close()
        if response.status >= 400:
            raise BridgeError(f"the bridge answered HTTP {response.status} to {method} {path}")
        return json.loads(data or b"{}")


def _fingerprint(connection: http.client.HTTPSConnection) -> str:
    assert connection.sock is not None
    der = connection.sock.getpeercert(binary_form=True) or b""
    return hashlib.sha256(der).hexdigest()


# ── Finding the bridge ────────────────────────────────────────────────────

def find_bridges(seconds: float = FIND_SECONDS) -> list[tuple[str, str]]:
    """The (address, bridge id) of every Hue Bridge answering an SSDP search.

    Local only: Philips also offers a discovery service in its cloud, which
    this does not use. Devices that are not Hue bridges send no
    `hue-bridgeid` header and stay out."""
    search = (b"M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\n"
              b'MAN: "ssdp:discover"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n')
    found: dict[str, str] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.settimeout(0.5)
        sock.sendto(search, ("239.255.255.250", 1900))
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                answer, (address, _port) = sock.recvfrom(4096)
            except TimeoutError:
                continue
            for line in answer.decode(errors="replace").split("\r\n"):
                name, _, value = line.partition(":")
                if name.strip().lower() == "hue-bridgeid":
                    found[address] = value.strip()
    return sorted(found.items())
