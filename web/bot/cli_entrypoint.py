"""The web extension's work in the bot runner: `search` and `ask`.

`stack web search` and `stack web ask` (`cli/`) start this file in core's
bot runner as `python /extensions/web/bot/cli_entrypoint.py <command> ...`,
with the web stacklet's settings (`stack.bot_runner.call_stacklet`). It
answers JSON on stdout, which the host command renders for people or
prints as it is for `--json`. A failure is one line on stderr and exit 1,
which the host command reports as its error.

Commands:
    search <query...> [--count N]     {"query", "results": [{title, url, content, engine}]}
    ask <question...> [--sources N]   {"question", "answer", "sources": [{n, title, url}]}

Why the bot runner and not the host:

- **One LLM client.** `stack.ai.client` carries what a local model needs
  and what is invisible until it is missing. The sharpest case is
  `chat_template_kwargs: {enable_thinking: False}`: without it a Qwen3
  writes its deliberation into `content` and never reaches the answer. A
  hand-written urllib client lost exactly that, and answered "Here's a
  thinking process: 1. Analyze User Question".
- **Hostile input belongs in a container.** Search snippets are text any
  page that ranks can choose. Here it goes into a prompt and back out to
  the caller. The completion holds no tools, so the risk is content, not
  execution, but the host is where the SSH keys and the family's files
  live.
- **The host is stdlib-only**, and the LLM client is not.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, "/app")  # stack.*, which core mounts there

from stack.stacklet_code import import_stacklets  # noqa: E402

import_stacklets([Path(__file__).resolve().parents[2]])

from stack.ai.client import LLM, LLMError  # noqa: E402

from stacklets.web.ask import DEFAULT_SOURCES, build_prompt, sources_from  # noqa: E402
from stacklets.web.search import DEFAULT_COUNT, JsonApiOff, search  # noqa: E402

# A valid answer is a few sentences with citations. Without a cap, a
# model caught in a repetition loop writes until the client times out.
MAX_ANSWER_TOKENS = 600
MODEL_TIMEOUT_S = 180.0


class Refused(Exception):
    """A command that cannot answer: the one line the caller is shown."""


def _results(query: str, count: int) -> list[dict]:
    """The results for `query`, or Refused saying what to do."""
    try:
        return search(query, base_url=os.environ["SEARCH_URL"], count=count)
    except JsonApiOff:
        raise Refused("SearXNG refused its JSON API (403): `search.formats` is html only. "
                      "Check that web/config/settings.yml is mounted, then: stack up web") from None
    except OSError:
        raise Refused("Search needs the web stacklet running: stack up web") from None


def _words(argv: list[str], prog: str, count_flag: str, default: int) -> tuple[str, int]:
    """The words of a query or question, and its count flag."""
    parser = argparse.ArgumentParser(prog=prog, add_help=False)
    parser.add_argument("words", nargs="*")
    parser.add_argument(count_flag, type=int, default=default)
    opts = parser.parse_args(argv)
    text = " ".join(opts.words).strip()
    if not text:
        raise Refused(f'usage: {prog} "<words>" [{count_flag} N]')
    return text, getattr(opts, count_flag.lstrip("-"))


def run_search(argv: list[str]) -> dict:
    query, count = _words(argv, "stack web search", "--count", DEFAULT_COUNT)
    return {"query": query, "results": _results(query, count)}


async def run_ask(argv: list[str]) -> dict:
    """One search, its top snippets, one model call. When the model fails,
    the sources still go back: the family can read them itself."""
    question, count = _words(argv, "stack web ask", "--sources", DEFAULT_SOURCES)
    sources = sources_from(_results(question, count), limit=count)
    if not sources:
        raise Refused(f'Search found nothing for "{question}".')
    listed = [{k: v for k, v in asdict(s).items() if k != "snippet"} for s in sources]

    llm = LLM.from_env(namespace="web")
    try:
        answer = (await llm.complete("ask", build_prompt(question, sources), temperature=0.0,
                                     max_tokens=MAX_ANSWER_TOKENS, timeout=MODEL_TIMEOUT_S)).strip()
    except LLMError as e:
        return {"question": question, "answer": None, "sources": listed,
                "error": f"Could not reach the model ({e}). The sources are what search found."}
    finally:
        await llm.aclose()
    return {"question": question, "answer": answer, "sources": listed}


def main(argv: list[str]) -> int:
    try:
        match argv[:1]:
            case ["search"]:
                answer = run_search(argv[1:])
            case ["ask"]:
                answer = asyncio.run(run_ask(argv[1:]))
            case _:
                raise Refused("commands: search, ask")
    except Refused as refused:
        print(refused, file=sys.stderr)
        return 1
    print(json.dumps(answer, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
