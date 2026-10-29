# Web search

**Web search** is a famstack extension that searches the internet through your own [SearXNG](https://docs.searxng.org/). It also answers a question from the search results, and lists the sources.

SearXNG is a metasearch engine. It sends a query to public search engines and merges their results. The extension runs SearXNG in one container on your Mac.

## What it does

- `./stack web search "<query>"` lists the results, each with its link.
- `./stack web ask "<question>"` answers the question from the top results, and lists the sources under the answer. The stack's AI model on your Mac writes the answer.
- The search page is on port 42100 of your Mac, or at `web.<your domain>` in domain mode.

The public search engines see the Mac, not a family member's account. The search words still go to those engines. Nothing else leaves the house.

To read one web page as the stack reads a link, use `./stack core web fetch <url>`. That command is part of famstack and does not need this extension.

## How to install it

To install the extension and start it, run:

```bash
./stack extensions add web
./stack up web
```

`ask` also needs core, because it runs in the bot runner of core. Core is up when the stack runs.

## How to use it

To search, run:

```bash
./stack web search "immich vs photoprism"
```

To ask a question, run:

```bash
./stack web ask "does immich support raw files"
```

| To | Add |
|---|---|
| Get the answer as JSON, for an agent | `--json` |
| Get fewer search results | `--count 5` (search) |
| Give the model fewer sources | `--sources 4` (ask) |

## When something goes wrong

| You see | The cause | Do this |
|---|---|---|
| `Search needs the web stacklet running: stack up web` | The SearXNG container is not running. | Run `./stack up web`. |
| `SearXNG refused its JSON API (403)` | SearXNG does not get the extension's settings file. | Make sure that `config/settings.yml` is in the extension's folder, then run `./stack up web`. |
| Fewer results than before | Public search engines block SearXNG from time to time. | Run `./stack logs web` to see which engines fail. |
| `Could not reach the model` | The AI model of the stack does not answer. | Run `./stack status`. The sources are still in the answer. |

## What was tested

- **CI**, on every pull request: every command against a stand-in SearXNG and a stand-in model, through famstack's extension lane ([`tests/`](tests/), [how the lane works](../docs/testing.md)).
- **Live**, against a running instance: [`tests/live/`](tests/live/) checks that SearXNG's JSON API is on and that more than one engine answers.
- **On hardware**: as a famstack stacklet, web ran on an Apple Silicon Mac with SearXNG `2026.9.15-ca4965040` in September 2026. As an extension, it is not tested on hardware yet.

## Not affiliated

SearXNG is an independent open-source project. This extension is not affiliated with or endorsed by it.
