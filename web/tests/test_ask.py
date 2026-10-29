"""`stack web ask`, as a family member or an agent runs it.

Each test runs `./stack web ask` as a process against web installed and
up (the lane's `stack`), with SearXNG (`conftest.py`) and the model (the
lane's `model`) stood in. The work runs in the bot runner: one search,
the top snippets, one model call.
"""

from __future__ import annotations

from searxng import RESPONSE

QUESTION = "does immich keep raw files"
ANSWER = "Yes. Immich stores the original RAW file and shows a preview [1][4]."


def test_ask_answers_from_the_results_with_their_sources(stack, searxng, model):
    """Given SearXNG's results and a model that answers from them, when an
    agent runs `stack web ask "<question>" --json`, then it gets the
    model's answer and the sources it was shown, numbered from 1."""
    model.answers(ANSWER)

    ran = stack.run("web", "ask", QUESTION, "--json")

    assert ran.code == 0, ran
    assert ran.json["answer"] == ANSWER
    assert [s["n"] for s in ran.json["sources"]] == list(range(1, 9))
    assert [s["url"] for s in ran.json["sources"]] == [r["url"] for r in RESPONSE["results"][:8]]


def test_the_model_is_shown_the_question_and_every_source(stack, searxng, model):
    """Given SearXNG's results, when a question is asked, then the one
    prompt the model gets holds the question and the link of every source
    it may cite."""
    model.answers(ANSWER)

    stack.run("web", "ask", QUESTION, "--sources", "4", "--json")

    [request] = model.requests
    prompt = request[-1]["content"]
    assert QUESTION in prompt
    for result in RESPONSE["results"][:4]:
        assert result["url"] in prompt


def test_people_see_the_answer_and_its_sources(stack, searxng, model):
    """Given an answer, when a person runs `stack web ask` without
    `--json`, then the answer and every source's link are on screen."""
    model.answers(ANSWER)

    ran = stack.run("web", "ask", QUESTION)

    assert ran.code == 0, ran
    assert ANSWER in ran.out
    for result in RESPONSE["results"][:8]:
        assert result["url"] in ran.out


def test_a_model_that_fails_still_leaves_the_sources(stack, searxng, model):
    """Given a model that refuses every request, when a question is
    asked, then the command fails and still hands over the sources: the
    family can read them itself."""
    model.refuses(500)

    ran = stack.run("web", "ask", QUESTION, "--json")

    assert ran.code == 1, ran
    assert ran.json["answer"] is None
    assert len(ran.json["sources"]) == 8
    assert ran.json["error"]


def test_a_search_that_finds_nothing_says_so(stack, searxng, model):
    """Given SearXNG finding nothing, when a question is asked, then the
    command fails, names the question, and the model is never asked."""
    searxng.answers([])

    ran = stack.run("web", "ask", QUESTION, "--json")

    assert ran.code == 1, ran
    assert QUESTION in ran.json["error"]
    assert model.requests == []
