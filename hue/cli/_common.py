"""_common.py: the paired bridge, for every `stack hue` command.

    bridge, error = paired_bridge(config)     # error when setup has not run

Where the pairing lives:

- stack.toml `[hue] host`: the bridge's address, written by `setup`.
  (`[hue] port` too, only in the tests, for a stand-in bridge.)
- `<data_dir>/hue/bridge.json`, readable by the admin only: the bridge id,
  the key and the certificate fingerprint.

Why not the key in stack.toml or the stack's secrets: `stack config`
prints stack.toml, and a stacklet command can read the secrets but has no
way to write one (only hooks can, `ctx.secret`). The data dir is in the
backup, so the pairing survives a restore.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..bridge import HueBridge
from ..lights import Target, all_targets, find

NOT_SET_UP = {"error": "No Hue bridge is paired yet. Run: ./stack hue setup"}


def settings(config: dict) -> dict:
    return dict((config.get("stack") or {}).get("hue") or {})


def pairing_file(config: dict) -> Path:
    return Path(config["data_dir"]) / "hue" / "bridge.json"


def save_pairing(config: dict, pairing: dict) -> None:
    """Write the pairing readable by the admin only (mode 0600 from the
    start, not after: the key is never on disk for anyone else to read)."""
    path = pairing_file(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as file:
        json.dump(pairing, file)
    temporary.replace(path)


def paired_bridge(config: dict) -> tuple[HueBridge | None, dict | None]:
    """The bridge from stack.toml and the pairing file, or the error that
    says how to pair."""
    host = settings(config).get("host")
    path = pairing_file(config)
    if not host or not path.exists():
        return None, NOT_SET_UP
    pairing = json.loads(path.read_text())
    return HueBridge(str(host), port=int(settings(config).get("port", 443)),
                     key=pairing["key"], fingerprint=pairing["fingerprint"]), None


def targets_of(bridge: HueBridge) -> list[Target]:
    """Every room, zone and lamp on the bridge, and the whole house."""
    return all_targets(bridge.resources("room"), bridge.resources("zone"),
                       bridge.resources("bridge_home"), bridge.resources("light"))


def switch(config: dict, words: list[str], change: dict) -> tuple[Target | None, dict | None]:
    """Apply `change` to what the words name; the target, or the error."""
    bridge, error = paired_bridge(config)
    if error:
        return None, error
    target, reason = find(targets_of(bridge), words)
    if not target:
        return None, {"error": reason}
    if not target.rid:
        return None, {"error": f"{target.name} has no lamps. Assign them to it in the Hue app."}
    bridge.update(target.rtype, target.rid, change)
    return target, None
