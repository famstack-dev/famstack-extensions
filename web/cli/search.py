"""stack web search <query>: search the internet through your own SearXNG.

    stack web search "immich vs photoprism"
      1. Immich vs PhotoPrism: which self-hosted photo manager
         https://example.com/immich-vs-photoprism
         Both index a library and serve it over the LAN, but they ...

    stack web search "immich vs photoprism" --json    the results, for an agent
    stack web search "mac mini idle watts" --count 5

SearXNG forwards the query to upstream engines and merges the results, so
Google and Bing see the instance, not a logged-in family member. The query
itself still reaches an upstream engine.

The search runs in core's bot runner (`bot/cli_entrypoint.py`), which
reaches SearXNG on the stack network. It needs the web stacklet up; when
it is not, the command says so instead of printing no results, because
"no results" and "nothing is running" are different problems.
"""

HELP = "Search the internet through your own SearXNG"

import argparse
import json

from stack import bot_runner

DEFAULT_COUNT = 8
SNIPPET_WIDTH = 88  # one line per snippet keeps the list a column to scan


def run(args, stacklet, config):
    parser = argparse.ArgumentParser(prog="stack web search", add_help=False)
    parser.add_argument("query", nargs="*")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("-h", "--help", action="store_true")
    opts = parser.parse_args(args)
    query = " ".join(opts.query).strip()
    if opts.help or not query:
        print(__doc__.strip())
        return {}

    answer = json.loads(bot_runner.call_stacklet(stacklet, "search", query,
                                                  "--count", str(opts.count)))
    print(_listing(answer))
    return answer


def _listing(answer: dict) -> str:
    """The results as people read them: number, title, link, one line of snippet."""
    if not answer["results"]:
        return f'\n  No results for "{answer["query"]}".\n'
    lines = [""]
    for n, item in enumerate(answer["results"], 1):
        lines += [f"  {n}. {item['title']}", f"     {item['url']}"]
        if item["content"]:
            lines.append(f"     {_one_line(item['content'])}")
        lines.append("")
    return "\n".join(lines)


def _one_line(text: str) -> str:
    """A snippet cut to one line rather than wrapped."""
    flat = " ".join(text.split())
    return flat if len(flat) <= SNIPPET_WIDTH else flat[: SNIPPET_WIDTH - 1] + "…"
