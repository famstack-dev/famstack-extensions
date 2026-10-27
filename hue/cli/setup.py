"""stack hue setup [<address>]: find the Hue Bridge and pair with it.

    ./stack hue setup                  # search the home network
    ./stack hue setup 192.168.1.20     # or name its address
    # Press the round button on the Hue Bridge now. Waiting up to 60 seconds ...

Every instance that talks to the bridge needs its own key, and the bridge
hands one out only within about 30 seconds of its button being pressed,
so this waits for a person at the bridge. Run it once per instance, and
again after replacing the bridge.

It records the bridge's certificate before pairing and pins it, so the key
only ever goes to this bridge (bridge.py). Nothing goes through the
Philips cloud, the search included.
"""

from __future__ import annotations

import time

from ..bridge import HueBridge, find_bridges
from ._common import save_pairing, settings

HELP = "Find the Hue Bridge and pair with it (press its button when asked): setup [<address>]"
DEVICETYPE = "famstack#stack"       # how the instance appears in the bridge's app list
PAIR_SECONDS = 60                   # time to walk to the bridge
POLL_SECONDS = 1


def run(args, stacklet, config):
    host = args[0] if args else None
    if not host:
        found = find_bridges()
        if not found:
            return {"error": "No Hue Bridge answered on the home network. "
                             "Name its address: ./stack hue setup <address>"}
        if len(found) > 1:
            listed = ", ".join(f"{address} ({bridge_id})" for address, bridge_id in found)
            return {"error": f"Found several bridges: {listed}. Name one: ./stack hue setup <address>"}
        host = found[0][0]

    bridge = HueBridge(host, port=int(settings(config).get("port", 443)))
    try:
        about = bridge.public_config()
        bridge.fingerprint = bridge.certificate_fingerprint()
    except OSError:
        return {"error": f"No Hue Bridge answers at {host}."}

    print(f"Press the round button on the Hue Bridge now. Waiting up to {PAIR_SECONDS} seconds ...",
          flush=True)
    key = _wait_for_button(bridge)
    if not key:
        return {"error": f"Nobody pressed the bridge's button within {PAIR_SECONDS} seconds. "
                         "Run ./stack hue setup again when you are next to it."}

    save_pairing(config, {"bridge_id": about.get("bridgeid", ""), "key": key,
                          "fingerprint": bridge.fingerprint})
    config["set_cfg"]("hue", "host", host)
    return {"bridge": about.get("name", ""), "id": about.get("bridgeid", ""), "host": host}


def _wait_for_button(bridge: HueBridge) -> str | None:
    deadline = time.monotonic() + PAIR_SECONDS
    while time.monotonic() < deadline:
        if key := bridge.pair(DEVICETYPE):
            return key
        time.sleep(POLL_SECONDS)
    return None
