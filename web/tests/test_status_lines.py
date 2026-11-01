"""The agent's view of the web commands: `cli/status.toml` matches the commands.

An agent's runtime reads `cli/status.toml` to show a status line while a
command runs and to know that a command only reads. A command missing there
counts as a change, and the runtime tells "That worked." after a search. These
tests keep the file and the commands in step: every command has an entry, every
entry is a command, and each says it reads and has its status line in German
and English.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "cli"


def _entries() -> dict:
    return tomllib.loads((CLI / "status.toml").read_text(encoding="utf-8"))


def _commands() -> set[str]:
    return {p.stem for p in CLI.glob("*.py") if not p.stem.startswith("_")}


def test_every_command_has_an_entry_and_every_entry_is_a_command():
    assert set(_entries()) == _commands()


def test_every_entry_reads_and_has_its_status_line_in_both_languages():
    for name, entry in _entries().items():
        assert entry.get("read") is True, name
        assert entry.get("takes") == "rest", name
        assert "{rest}" in entry["en"] and "{rest}" in entry["de"], name
