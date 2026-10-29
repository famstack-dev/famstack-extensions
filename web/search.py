"""Searching through the family's SearXNG: a query in, the results out.

The module `stacklets.web.search`. It runs in the bot runner, where
`stack web search` and `stack web ask` do their work, and reaches SearXNG
at its address on the stack network (`SEARCH_URL` in the web stacklet's
settings).

SearXNG's JSON API is off in its shipped defaults (`search.formats` is
`[html]`), and `config/settings.yml` turns it on. Without that setting the
web page keeps working and every query here is answered 403, so that
answer has a name of its own (`JsonApiOff`): "no results" and "the
setting is gone" are different problems.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

# A page of results an agent can read in one go, and what `ask` shows the
# model (`ask.DEFAULT_SOURCES`).
DEFAULT_COUNT = 8


class JsonApiOff(RuntimeError):
    """SearXNG answered 403 to a JSON query: its JSON API is off."""


def search(query: str, *, base_url: str, count: int = DEFAULT_COUNT,
           timeout: int = 20) -> list[dict]:
    """The first `count` results for `query`, each `{title, url, content,
    engine}`.

    Raises JsonApiOff when SearXNG refuses JSON, and OSError when it
    cannot be reached. SearXNG's `number_of_results` is not used: it is 0
    or null while `results` holds a full page.
    """
    params = urllib.parse.urlencode({"q": query, "format": "json"})
    request = urllib.request.Request(f"{base_url}/search?{params}",
                                     headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as err:
        if err.code == 403:
            raise JsonApiOff("SearXNG refused its JSON API (403)") from err
        raise
    return [{"title": (item.get("title") or "").strip(),
             "url": (item.get("url") or "").strip(),
             "content": (item.get("content") or "").strip(),
             "engine": item.get("engine") or ""}
            for item in payload.get("results", [])[:count]]
