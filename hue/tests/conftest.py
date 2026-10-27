"""conftest.py: a fabricated stack instance with this extension, and a fake Hue Bridge.

Run the tests with famstack's test environment, from anywhere:

    FAMSTACK_REPO=<famstack checkout> \\
        uv run --project "$FAMSTACK_REPO" --extra test pytest hue/tests

`FAMSTACK_REPO` is required: hue runs inside the stack, so its tests
import famstack's framework from that checkout. The commands run as
`./stack hue <cmd>` runs them, through `Stack.run_cli_command`. The bridge
is `FakeBridge` (`fake_bridge.py`) on localhost over HTTPS, with
certificates made for the session by `openssl`; nothing here reaches the
real network.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

EXTENSION = Path(__file__).resolve().parents[1]
FAMSTACK = Path(os.environ.get("FAMSTACK_REPO", "")).expanduser()

if not (FAMSTACK / "lib" / "stack").is_dir():
    pytest.exit("Set FAMSTACK_REPO to a famstack checkout: hue's tests run it inside the stack.",
                returncode=2)
if str(FAMSTACK / "lib") not in sys.path:
    sys.path.insert(0, str(FAMSTACK / "lib"))

from fake_bridge import FakeBridge


def write_instance(root: Path, hue_section: str) -> Path:
    """A minimal instance under `root` whose only extension directory is
    the one holding this stacklet, with `hue_section` as its [hue]."""
    instance = root / "instance"
    (instance / ".stack").mkdir(parents=True)
    (root / "data").mkdir()
    (instance / "stack.toml").write_text(
        f'[core]\nname = "stack"\ndomain = ""\nhost = "127.0.0.1"\n'
        f'data_dir = "{root / "data"}"\nextension_dirs = ["{EXTENSION.parent}"]\n'
        f'timezone = "Europe/Berlin"\nlanguage = "en"\n\n{hue_section}',
        encoding="utf-8")
    (instance / "users.toml").write_text("", encoding="utf-8")
    (instance / ".stack" / "secrets.toml").write_text("", encoding="utf-8")
    return instance


class Stack:
    """`./stack hue ...` for one fabricated instance."""

    def __init__(self, instance: Path):
        from stack import Stack as RealStack
        from stack.output import CollectorOutput
        self.instance = instance
        self.data = instance.parent / "data"
        self._stack = RealStack(root=FAMSTACK, data=self.data,
                                instance_dir=instance, output=CollectorOutput())

    def hue(self, command: str, *args: str) -> dict:
        return self._stack.run_cli_command("hue", command, list(args)) or {}

    def stack_toml(self) -> str:
        return (self.instance / "stack.toml").read_text()


def make_certificate(directory: Path) -> tuple[Path, Path]:
    """A self-signed certificate and its key, as the bridge has one."""
    cert, key = directory / "cert.pem", directory / "key.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", "/CN=ecb5fafffe000001", "-keyout", str(key), "-out", str(cert)],
                   check=True, capture_output=True)
    return cert, key


@pytest.fixture(scope="session")
def certificate(tmp_path_factory) -> tuple[Path, Path]:
    return make_certificate(tmp_path_factory.mktemp("bridge-cert"))


@pytest.fixture(scope="session")
def other_certificate(tmp_path_factory) -> tuple[Path, Path]:
    """A second certificate: a different device at the bridge's address."""
    return make_certificate(tmp_path_factory.mktemp("other-cert"))


@pytest.fixture
def bridge(certificate):
    with FakeBridge(certificate) as fake:
        yield fake


@pytest.fixture
def stack(tmp_path, bridge) -> Stack:
    """An instance where `stack hue setup` already ran against `bridge`."""
    stack = Stack(write_instance(tmp_path, bridge.config(host=False)))
    bridge.press_button()
    answer = stack.hue("setup", "127.0.0.1")
    assert "error" not in answer, answer
    return stack
