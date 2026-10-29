# Testing an extension

## What is the extension lane?

The **extension lane** runs the tests of an extension against a famstack checkout. An [extension](https://github.com/famstack-dev/famstack/blob/feature/0.5.0-beta.1/docs/admin-guide.md#extensions) is a stacklet that famstack does not ship. Its code lives in this repository, but it runs inside the stack. Because of this, its tests run inside the stack too.

For example, [`web/tests/test_search.py`](../web/tests/test_search.py) runs `./stack web search` as a family member does. The stack is a made-up instance on your machine, and SearXNG is a stand-in on `127.0.0.1`.

## What does a test check?

A test drives what a family member or an agent can call, and checks what they get back. That is the exit code, the JSON and the text on the screen. A test does not import a command's code and does not call its functions. Such a test passes when the command is broken, because it skips the path that the stack takes.

| What the extension has | How a test drives it | Where it runs |
|---|---|---|
| A command, `./stack <id> <command>` | `stack.run("<id>", "<command>", ...)` | CI, any machine |
| Work that a command runs in the bot runner | The same call | CI, any machine |
| A service that the work reaches | A stand-in on `httpserver`, named with `stack.serves` | CI, any machine |
| The AI model | The `model` fixture | CI, any machine |
| A module of pure code | `from stacklets.<id>.<module> import ...` | CI, any machine |
| Its containers | A live test against a running instance | A Mac with the extension up |

## How does a command run in a test?

Each `stack.run` starts `./stack` as its own process, the way a person starts it. When the command has work for the bot runner, the stand-in for Docker starts that work as one more process on your machine:

```
 the test (pytest)
 ┌───────────────────────────────────────────────┐
 │ stack.run("web", "search", "tent", "--json")  │
 └───────────────────────┬───────────────────────┘
                         │ a process: ./stack, STACK_DIR = the instance
                         ▼
 ┌───────────────────────────────────────────────┐
 │ ./stack web search tent --json                │
 │ web/cli/search.py, on the host                │
 └───────────────────────┬───────────────────────┘
                         │ docker exec stack-core-bot-runner python ...
                         ▼
 ┌───────────────────────────────────────────────┐
 │ the bot runner, stood in: a process here      │
 │ web/bot/cli_entrypoint.py search tent         │
 │ env: core's, then web's own .env              │
 └───────────────────────┬───────────────────────┘
                         │ http://stack-web-search:8080
                         ▼
 ┌───────────────────────────────────────────────┐
 │ httpserver on 127.0.0.1: the test's SearXNG   │
 └───────────────────────────────────────────────┘
```

The command's code never loads into the test's process. Because of this, a test sees what a person sees: the same discovery, `--json` output and exit code.

## How to run the tests

You need a famstack checkout and [uv](https://docs.astral.sh/uv/). The lane uses the test environment of that checkout.

To run the tests of one extension, run this from the root of this repository:

```bash
"$FAMSTACK_REPO/script/test" extension web
```

To run one test file, give its path:

```bash
"$FAMSTACK_REPO/script/test" extension web/tests/test_search.py
```

The lane runs the tests in parallel, with one worker for each core. To run them in one process, for example to debug a test, add `-n 0`:

```bash
"$FAMSTACK_REPO/script/test" extension web -n 0
```

To run every check that CI runs, run:

```bash
FAMSTACK_REPO=<your famstack checkout> script/cibuild
```

CI tests against the famstack branch in `.github/workflows/ci.yml` (`FAMSTACK_REF`). Use a checkout of the same branch, because the lane and the framework change with famstack.

## How to write a test for a command

1. Put the test in `<id>/tests/test_<command>.py`.
2. Ask for the fixture `stack`. It is your extension, installed and up in a made-up instance.
3. Stand in for each service that the command reaches (see [How to stand in for a service](#how-to-stand-in-for-a-service)).
4. Run the command with `stack.run`, with the same words that a person types after `./stack`.
5. Assert the exit code first, with `ran` as the message. The message then shows the output of the command when the test fails.
6. Assert the JSON, or facts in the text on the screen.

This test is from [`web/tests/test_search.py`](../web/tests/test_search.py):

```python
def test_count_is_how_many_results_come_back(stack, searxng):
    """Given a full page of results, when an agent asks for `--count 3`,
    then three come back: an agent budgets its context by this number."""
    ran = stack.run("web", "search", "immich vs photoprism", "--count", "3", "--json")

    assert ran.code == 0, ran
    assert len(ran.json["results"]) == 3
```

Give each test a name that says what the caller sees. Write its docstring as given, when and then, plus one sentence on why the case matters.

## How to stand in for a service

On a family's Mac, the work of a command reaches a service by its container address. An example is `http://stack-web-search:8080` on the stack network. In a test, nothing answers at that name. You tell the instance which stand-in answers instead.

| | On a family's Mac | In a test |
|---|---|---|
| Where the address comes from | `[env.defaults]` in `stacklet.toml`, rendered into the extension's `.env` by `stack up` | The same |
| What answers at `stack-web-search:8080` | The SearXNG container | `httpserver`, named with `stack.serves` |
| A container that is not running | The connection is refused | `stack.stopped("stack-web-search:8080")` |

Put the address of a service in `[env.defaults]`, and read it from the environment in the code:

```toml
[env.defaults]
SEARCH_URL = "http://stack-web-search:8080"
```

Then name the stand-in in the test:

```python
def test_search_answers_what_searxng_found(stack, httpserver):
    httpserver.expect_request("/search").respond_with_json({"results": RESULTS})
    stack.serves("stack-web-search:8080", httpserver)

    ran = stack.run("web", "search", "tent", "--json")
```

When several tests use the same stand-in, put it in its own module in `<id>/tests/`. Then give a fixture for it in `conftest.py`. Web's SearXNG is in [`web/tests/searxng.py`](../web/tests/searxng.py).

> [!WARNING]
> **Name a stand-in for every container address that a command reaches.** The lane guards only the test's own process against the network. The `./stack` processes of a test are not guarded. An address without a stand-in makes a name lookup that can leave your machine.

## How to stand in for the model

Ask for the fixture `model`. The work of a command in the bot runner then reaches the stand-in instead of the model.

| To | Write |
|---|---|
| Answer the next requests with a text | `model.answers("Yes. Immich keeps the RAW file [1].")` |
| Answer with JSON | `model.answers({"title": "Tent for four"})` |
| Make every request fail with an HTTP status | `model.refuses(500)` |
| Read the messages that the model got | `model.requests[-1][-1]["content"]` |

The stand-in is the model's HTTP API, not a mock of the client. The real AI client of famstack sends the request and reads the answer.

## How to test a module

A module of pure code (no network, no files) gets module tests. The lane makes each file of your extension importable as its package, `stacklets.<id>`:

```python
from stacklets.web.ask import build_prompt, sources_from
```

Import a module by this name only. Do not put a folder on `sys.path`, and do not load a file by its path. A module that loads under two names is two modules, and its classes do not match.

## How to test the containers

The lane runs no containers. To check a container, write a live test that runs against an instance where the extension is up. Web's live tests are in `web/tests/live/`. CI skips them, because they skip when nothing answers on the extension's port.

To run them on a Mac, run these commands:

```bash
./stack extensions add web
./stack up web
"$FAMSTACK_REPO/script/test" extension web/tests/live
```

## What the fixtures give

| Fixture | What it is | What it has |
|---|---|---|
| `stack` | Your extension, installed and up in a made-up instance | `run(*args)` gives `ran.code`, `ran.out`, `ran.err` and `ran.json`. `serves(address, httpserver)`, `stopped(address)`, `uses_model(model)`, `up()` |
| `model` | The model's HTTP API, on `httpserver` | `answers(...)`, `answering(fn)`, `refuses(status)`, `requests` |
| `httpserver` | A web server on `127.0.0.1` for this test ([pytest-httpserver](https://pytest-httpserver.readthedocs.io/)) | `expect_request(path)`, `url_for(path)`, `log` |

The instance is the made-up Simpson family. Its `stack.toml` has a default AI model, as the installer writes it. A test must leave no process, server or file behind, because the tests run in parallel and in any order.

## Pitfalls

| You see | The cause | Do this |
|---|---|---|
| `web is shipped in .../stacklets/web: the release wins that clash, so the extension in ... would never load.` | famstack ships a stacklet with the same `id`. | Give the extension another `id`, or remove the stacklet from famstack first. |
| `web has no settings yet: stack up web` | Its `.env` does not exist, because the extension was never brought up. | Use the `stack` fixture, which brings the extension up. With `installed(..., up=False)`, this error is the expected answer. |
| `web is in ..., which stack-core-bot-runner does not see: it mounts only the first of [core] extension_dirs.` | The extension is in a second extension folder. | Install it in the first extension folder. |
| `--json` prints the text for people and then `{"ok": true}` | The command streams the output of its work (`bot_runner.dispatch`). | Call the work with `bot_runner.call_stacklet`, and let the work answer JSON. In the host command, print the text for people and return the dict. |
| A stand-in gets no requests, and the command reports a connection error | The address is fixed in the code, or the test named a different address. | Read the address from `[env.defaults]`. Name the same `name:port` in `stack.serves`. |
| `ValueError: No model configured for '<id>/<task>'` | The work asks the model in an instance without a default model. | Use the `stack` fixture. Its instance has a default model. |
| The model stand-in stops answering when a second stand-in changes its answer | `httpserver.clear_all_handlers()` removes every handler on the server, the model's too. | Register one handler per stand-in that reads its current answer. See [`web/tests/searxng.py`](../web/tests/searxng.py). |
| A test passes alone and fails in CI | The test left something behind: a process, a server or a changed file. Or it depends on the order of the tests. | Stop servers when the block ends, wait for processes, and use `tmp_path` for files. |
| A test fails after a change to the text of a message | The test checks the wording. | Check the facts that the message carries. Examples are the command to run, a path and an `id`. |
| A test is slow | Each `./stack` call starts a process, about 0.2 to 0.6 seconds. | Keep to one or two commands per test. Say in the docstring why a test takes more than a second. |
| An entry point fails to write a file under `/data` in a test | The stand-in for the bot runner maps only the code folders, `/stacklets/` and `/extensions/`. | Test that code as a module, or in a live test. |

Use made-up data in tests and fixtures: no real addresses, device IDs, rooms or names. Web's recorded search answer is made up too ([`web/tests/fixtures/README.md`](../web/tests/fixtures/README.md)).
