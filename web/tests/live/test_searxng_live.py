"""SearXNG itself, against a running web extension on this Mac.

The unit tests stand SearXNG in, so they cannot see the two settings that
only the real container shows:

- **The JSON API is on.** SearXNG ships `search.formats: [html]`, so every
  JSON query is refused (403) until `config/settings.yml` adds `json`.
  The web page keeps working when the file stops reaching the container,
  so nothing else shows it.
- **More than one engine answers.** SearXNG has no index; it forwards a
  query to public engines. Those engines block it from time to time, so
  "search got worse" looks like fewer results, not like an error.

Run them where web is up:

    ./stack up web
    "$FAMSTACK_REPO/script/test" extension web/tests/live

They skip when nothing answers on the extension's port, which is how CI
runs them.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from stacklets.web.search import search

SEARXNG = "http://localhost:42100"


@pytest.fixture(scope="module", autouse=True)
def web_is_up():
    try:
        with urllib.request.urlopen(f"{SEARXNG}/healthz", timeout=5) as response:
            if response.status != 200:
                pytest.skip("the web extension is not healthy")
    except OSError:
        pytest.skip("the web extension is not running here (./stack up web)")


def _query(words: str) -> dict:
    request = urllib.request.Request(f"{SEARXNG}/search?q={words}&format=json",
                                     headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def test_the_json_api_is_on():
    """Given web up, when SearXNG is asked for JSON, then it answers
    results and does not refuse (403 means the settings file is not
    mounted)."""
    try:
        payload = _query("famstack")
    except urllib.error.HTTPError as err:
        if err.code == 403:
            pytest.fail("SearXNG refused format=json: config/settings.yml is not mounted")
        raise
    assert "results" in payload


def test_more_than_one_engine_answers():
    """Given web up, when a common query runs, then results come from two
    engines or more: one engine left is the state before none."""
    engines = set()
    for item in _query("self+hosted+photos").get("results", []):
        engines.update(item.get("engines") or [])
    assert len(engines) >= 2, f"only {sorted(engines) or 'no'} engine(s) answered"


def test_results_carry_a_title_and_a_link():
    """Given web up, when the search module queries SearXNG, then every
    result has a title and a link, and `count` is a limit."""
    results = search("immich vs photoprism", base_url=SEARXNG, count=3)
    assert 0 < len(results) <= 3
    assert all(r["title"] and r["url"].startswith("http") for r in results)
