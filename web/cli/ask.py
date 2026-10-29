"""stack web ask <question>: a plain question, a short answer, its sources.

    stack web ask "does immich support raw files"
      Yes. Immich stores the original RAW file untouched [2][4];
      PhotoPrism reads RAW but converts for display [4].

      Sources
        [2] Immich vs PhotoPrism 2026
            https://example.com/immich-vs-photoprism

    stack web ask "..." --json         the answer and its sources, for an agent
    stack web ask "..." --sources 4    fewer sources, a shorter prompt

One search, the top snippets, one model call (`ask.py` says why that is
the shape). The sources print whether or not the model found an answer:
"I could not answer this, here is what I looked at" lets the family judge
for themselves. When the model cannot be reached, the command fails and
still prints them.

The work runs in core's bot runner (`bot/cli_entrypoint.py`), which has
the AI client and reaches SearXNG on the stack network. It needs the web
stacklet up for search and core up for the model.
"""

HELP = "Ask a question and get an answer with its sources"

import json

from stack import bot_runner

from ..ask import Source, render_sources


def run(args, stacklet, config):
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return {}
    answer = json.loads(bot_runner.call_stacklet(stacklet, "ask", *args))
    print(_reply(answer))
    return answer


def _reply(answer: dict) -> str:
    """The answer, then the sources under it, as people read them."""
    sources = render_sources([Source(n=s["n"], title=s["title"], url=s["url"], snippet="")
                              for s in answer["sources"]])
    said = answer["answer"] if answer["answer"] else "  No answer: the model could not be reached."
    return f"\n{said}\n\n  Sources\n{sources}\n"
