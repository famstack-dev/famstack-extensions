"""`stack web search`, as a family member or an agent runs it.

Each test runs `./stack web search` as a process against web installed
and up (the lane's `stack`), with SearXNG stood in (`conftest.py`). The
search itself runs in the bot runner, which reaches SearXNG by its
address on the stack network, so these cover that path end to end.
"""

from __future__ import annotations

from searxng import RESPONSE, SEARXNG


def test_search_answers_what_searxng_found(stack, searxng):
    """Given SearXNG answering its page of results, when an agent runs
    `stack web search "immich vs photoprism" --json`, then the answer is
    those results with title and link, and the query reached SearXNG
    asking for JSON."""
    ran = stack.run("web", "search", "immich vs photoprism", "--json")

    assert ran.code == 0, ran
    found = ran.json["results"]
    assert [r["url"] for r in found] == [r["url"] for r in RESPONSE["results"][:8]]
    assert all(r["title"] for r in found)
    assert searxng.queries() == [{"q": "immich vs photoprism", "format": "json"}]


def test_count_is_how_many_results_come_back(stack, searxng):
    """Given a full page of results, when an agent asks for `--count 3`,
    then three come back: an agent budgets its context by this number."""
    ran = stack.run("web", "search", "immich vs photoprism", "--count", "3", "--json")

    assert ran.code == 0, ran
    assert len(ran.json["results"]) == 3


def test_people_see_each_result_with_its_link(stack, searxng):
    """Given SearXNG's results, when a person runs `stack web search`
    without `--json`, then every link is on screen, and no JSON."""
    ran = stack.run("web", "search", "immich vs photoprism")

    assert ran.code == 0, ran
    for result in RESPONSE["results"][:8]:
        assert result["url"] in ran.out
    assert '"results"' not in ran.out


def test_searxng_refusing_json_names_the_setting(stack, searxng):
    """Given SearXNG with its JSON API off (its shipped default), when a
    person searches, then the command fails and names the settings file
    that turns it on, not "no results".

    The web page keeps working in that state, so nothing else shows it."""
    searxng.refuses_json()

    ran = stack.run("web", "search", "tent", "--json")

    assert ran.code == 1, ran
    assert "config/settings.yml" in ran.json["error"]


def test_searxng_not_running_says_to_start_web(stack):
    """Given the web stacklet's container not running, when a person
    searches, then the command fails and names `stack up web`."""
    stack.stopped(SEARXNG)

    ran = stack.run("web", "search", "tent", "--json")

    assert ran.code == 1, ran
    assert "stack up web" in ran.json["error"]
