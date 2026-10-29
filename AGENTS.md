# AGENTS.md: famstack-extensions

For any AI agent working in this repo. Public, on GitHub, AGPL-3.0.

## What this repo is

The catalog of famstack extensions: stacklets that are not part of famstack's
release. `./stack extensions add <id>` copies one root folder of this repo into an
instance's extension folder (`~/famstack-extensions/<id>/`), where famstack's
discovery reads `<id>/stacklet.toml`. Every rule below follows from that.

```
famstack-extensions/
├── <id>/                 one extension per root folder, never deeper
│   ├── stacklet.toml     id = folder name
│   ├── README.md         what it does, setup, what was tested on which hardware
│   └── tests/            run inside famstack, through its extension lane
├── docs/testing.md       how to test an extension, and the pitfalls
├── script/cibuild        everything CI checks; runs the same on a laptop
├── script/check-manifests.py
└── .github/workflows/ci.yml
```

## Rules

- **One folder per extension, named after its `id`.** No `stacklet.toml` at the
  repo root, no extension inside another's folder. `script/check-manifests.py`
  enforces it, and refuses an `id` famstack ships in `stacklets/` (the release
  wins that clash, so the extension would never load).
- **Ports 42100 to 42199**, the range famstack's ADR-007 keeps for extensions:
  `port`, `[ports]` and each compose binding's host port. No two extensions
  share a port. `script/check-manifests.py` enforces both.
- **An extension stands alone.** It is copied without the rest of the repo, so
  it imports nothing from outside its own folder.
- **Made-up data only.** Tests, examples and docstrings never carry a real
  address, device ID, room or person's name. Fabricate them.
- **Tests run inside famstack**, through its extension lane:
  `"$FAMSTACK_REPO/script/test" extension <id>`. A test drives `./stack <id>
  <cmd>` as a process (the fixture `stack`), stands in for every service by its
  container address, and imports the extension's modules only as
  `stacklets.<id>.*`, never through `sys.path`. `docs/testing.md` has how and
  the pitfalls. CI uses the famstack branch in `.github/workflows/ci.yml`
  (`FAMSTACK_REF`).
- **Other makers' names only to say what an extension works with.** The
  manifest's `name` combines a brand with plain words ("Hue lights", never
  "Hue" alone), no logos, and the README says the extension is not affiliated
  with the maker. Philips Hue: Signify's developer terms, section 8.1(xi),
  and no security features such as alarms or presence (section 8.2(iv)).
- **Literate code**: every file says what it is, how it is used and why it
  exists; comments say why.
- **`main` changes only through a reviewed PR** with green CI.

## Commits

Conventional Commits, the types famstack uses (`feat`, `fix`, `security`,
`perf`, `docs` show in release notes; `refactor`, `test`, `build`, `ci`, `chore`,
`style` do not). The scope is the extension's `id`: `feat(hue): call up a scene
by room`. Changes to the repo itself go without a scope, or with `ci`. No AI
attribution: no `Co-Authored-By` for an AI, no "Generated with" line.

## Check before a PR

```
FAMSTACK_REPO=<famstack checkout> script/cibuild
```
