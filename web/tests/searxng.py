"""SearXNG, stood in for the web extension's tests: its JSON API on `httpserver`.

The bot runner reaches SearXNG at `stack-web-search:8080` on the stack
network (`SEARCH_URL`). A test names `httpserver` for that address
(`stack.serves`), and `SearXNG` answers its `/search` there. `RESPONSE`
is the made-up page of results in `fixtures/` (its README says what it
is).
"""

from __future__ import annotations

import json
from pathlib import Path

RESPONSE = json.loads((Path(__file__).parent / "fixtures" / "searxng-response.json")
                      .read_text(encoding="utf-8"))
SEARXNG = "stack-web-search:8080"


class SearXNG:
    """SearXNG's `/search` on the test's `httpserver`: it answers `results`
    (the made-up page until a test says otherwise) and keeps each query's
    parameters. One handler reads the current answer, so a test changes
    it without touching other stand-ins on the same server (the model)."""

    def __init__(self, httpserver):
        from werkzeug.wrappers import Response

        self._httpserver = httpserver
        self._results = RESPONSE["results"]
        self._json_api = True

        def search(request):
            if not self._json_api:
                return Response("Forbidden", status=403)
            return Response(json.dumps({**RESPONSE, "results": self._results}),
                            content_type="application/json")

        httpserver.expect_request("/search").respond_with_handler(search)

    def answers(self, results: list[dict]) -> None:
        """Every query from now on finds `results`."""
        self._results = results

    def refuses_json(self) -> None:
        """SearXNG's shipped default: `search.formats` is html only."""
        self._json_api = False

    def queries(self) -> list[dict]:
        """Each query's parameters, oldest first."""
        return [dict(request.args) for request, _ in self._httpserver.log
                if request.path == "/search"]
