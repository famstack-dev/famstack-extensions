"""The hue extension's tests: the lane's fixtures, plus a stand-in Hue Bridge.

The extension lane (`script/test extension hue`, from a famstack checkout)
gives every test `stack`: hue installed and up in a made-up instance, where
each `stack.run("hue", ...)` is a real `./stack hue ...` process. This file
adds the bridge, `FakeBridge` (`fake_bridge.py`), on localhost over HTTPS
with certificates made for the session by `openssl`, and two states of the
instance: `unpaired` (its `[hue]` names the bridge's port, before `stack hue
setup`) and `paired` (after it). Nothing here reaches the real network.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fake_bridge import FakeBridge


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
def unpaired(stack, bridge):
    """hue before `stack hue setup`: the instance's `[hue]` names the
    bridge's port and no address, as the admin finds it after
    `stack extensions add hue`, with the bridge on a port of its own."""
    toml = stack.instance / "stack.toml"
    toml.write_text(toml.read_text() + "\n" + bridge.config(host=False))
    return stack


@pytest.fixture
def paired(unpaired, bridge):
    """hue after `stack hue setup` ran against `bridge`, button pressed."""
    bridge.press_button()
    ran = unpaired.run("hue", "setup", "127.0.0.1", "--json")
    assert ran.code == 0, ran
    return unpaired
