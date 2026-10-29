"""check-manifests.py: every root folder here is one stacklet famstack can install.

    uv run --project <famstack checkout> python script/check-manifests.py <famstack checkout>

`./stack extensions add <id>` copies one root folder of this repo into an
instance's extension folder, and famstack's discovery there reads
`<folder>/stacklet.toml`. So each root folder with a manifest must:

- parse as TOML and carry `id`, `name` and `description`;
- be named after its `id`, so the folder and `stack extensions add <id>`
  agree;
- not take an `id` famstack ships in `stacklets/`: discovery lets the
  release win that clash, so the extension would never load.
- publish its ports in 42100 to 42199 (famstack's ADR-007), the range for
  extensions: `port`, `[ports]` and the host side of each port binding in
  its `docker-compose.yml`. famstack's own stacklets use the rest of 42xxx,
  so an extension there could take a port a family's stack already uses.
  Two extensions on one port are refused too, because a family may run both.

A manifest at the repo root is refused: the installer would read this repo
as one single extension instead of a catalog.

Prints one line per problem and exits 1 if there was any. Needs Python 3.11
(tomllib), hence famstack's environment through uv.
"""

from __future__ import annotations

import re
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("id", "name", "description")
EXTENSION_PORTS = range(42100, 42200)

# The host port of a compose binding: `"${PORT_BIND_IP:-127.0.0.1}:42100:8080"`
# or `- 42100:8080`, the number before the container's port.
_BINDING = re.compile(r"(\d+):\d+(?:/(?:tcp|udp))?[\"']?\s*$")


def shipped_ids(famstack: Path) -> set[str]:
    """The ids famstack's release ships; a folder without an `id` is named
    by its folder, as famstack's discovery does."""
    ids = set()
    for manifest in (famstack / "stacklets").glob("*/stacklet.toml"):
        raw = tomllib.loads(manifest.read_text(encoding="utf-8"))
        ids.add(raw.get("id", manifest.parent.name))
    return ids


def ports_of(folder: Path, manifest: dict) -> set[int]:
    """The host ports an extension publishes: its manifest's `port` and
    `[ports]`, and the host side of its compose bindings."""
    ports = {manifest["port"]} if isinstance(manifest.get("port"), int) else set()
    ports |= {p for p in (manifest.get("ports") or {}).values() if isinstance(p, int)}
    compose = folder / "docker-compose.yml"
    if compose.is_file():
        for line in compose.read_text(encoding="utf-8").splitlines():
            if match := _BINDING.search(line.split("#", 1)[0]):
                ports.add(int(match.group(1)))
    return ports


def problems(root: Path, shipped: set[str]) -> Iterator[str]:
    """Every rule above that a folder in `root` breaks, one line each."""
    if (root / "stacklet.toml").exists():
        yield "stacklet.toml at the repo root: extensions live one folder down"
    taken: dict[int, str] = {}
    for manifest in sorted(root.glob("*/stacklet.toml")):
        folder = manifest.parent.name
        try:
            raw = tomllib.loads(manifest.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            yield f"{folder}: stacklet.toml does not parse: {error}"
            continue
        for key in REQUIRED:
            if not raw.get(key):
                yield f"{folder}: stacklet.toml has no {key}"
        if raw.get("id") and raw["id"] != folder:
            yield f"{folder}: id is '{raw['id']}'; name the folder after it"
        if raw.get("id", folder) in shipped:
            yield f"{folder}: famstack already ships a stacklet with this id"
        for port in sorted(ports_of(manifest.parent, raw)):
            if port not in EXTENSION_PORTS:
                yield f"{folder}: port {port} is outside 42100-42199, the range for extensions"
            elif port in taken:
                yield f"{folder}: port {port} is {taken[port]}'s already"
            taken.setdefault(port, folder)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not (Path(argv[1]) / "stacklets").is_dir():
        print("Use: check-manifests.py <famstack checkout>", file=sys.stderr)
        return 2
    found = list(problems(ROOT, shipped_ids(Path(argv[1]))))
    for line in found:
        print(line)
    count = len(list(ROOT.glob("*/stacklet.toml")))
    print(f"check-manifests: {count} extensions, {len(found)} problems", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
