"""The web extension's tests: the lane's fixtures, plus SearXNG.

The extension lane (`script/test extension web`, from a famstack checkout)
gives every test `stack` (web installed and up in a made-up instance),
`model` and `httpserver`. This file adds `searxng`: SearXNG's JSON API
(`searxng.py`) at the address the bot runner reaches it by.
"""

from __future__ import annotations

import pytest
from searxng import SEARXNG, SearXNG


@pytest.fixture
def searxng(stack, httpserver) -> SearXNG:
    """SearXNG, answering the made-up page of results."""
    stack.serves(SEARXNG, httpserver)
    return SearXNG(httpserver)
