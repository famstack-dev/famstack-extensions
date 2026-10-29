# famstack-extensions

Stacklets for [famstack](https://github.com/famstack-dev/famstack) that are not
part of its release. Some are too specific for every family, some are too young
for the core. Each folder here is one extension.

| Extension | What it does | Stage |
|---|---|---|
| [hue](hue/) | Philips Hue scenes, brightness, on and off over the bridge's local API. No Philips cloud. | incubating |
| [web](web/) | Private web search through your own SearXNG, and a question answered from the results with its sources. | incubating |

The extensions here follow famstack's integration branch, `feature/0.5.0-beta.1`.
They need famstack 0.5, which is not released yet.

## Install

famstack finds an extension in its extension folder, `~/famstack-extensions`
([ADR-013](https://github.com/famstack-dev/famstack/blob/feature/0.5.0-beta.1/docs/adr/adr-013-stacklet-locations-and-stages.md)).
famstack 0.5 brings a command for it:

```
./stack extensions list          what is here, and what you have installed
./stack extensions add hue       copy it into your extension folder
./stack extensions update hue    take the newest version from this repo
```

Until that command lands, copy the folder by hand:

```
git clone https://github.com/famstack-dev/famstack-extensions
mkdir -p ~/famstack-extensions
cp -R famstack-extensions/hue ~/famstack-extensions/
```

Each extension's README says what comes next (`./stack hue setup` for hue,
`./stack up <id>` for one that runs containers).

## What you trust

An extension runs on your Mac. Its hooks and commands run as you, with access to
the stack's secrets. Every extension in this repo is reviewed before it is
merged. An extension from anywhere else is that author's code:
`./stack extensions add <git-url>` installs it too, after a warning that says
exactly this.

## Adding an extension

Open a pull request with:

- one folder, named after the stacklet's `id`, with `stacklet.toml` at its top
  ([creating stacklets](https://github.com/famstack-dev/famstack/blob/main/docs/creating-stacklets.md));
- a README: what it does, how to set it up, what was tested and on which hardware;
- tests under `<id>/tests` that run inside famstack, through its extension lane
  ([testing an extension](docs/testing.md));
- made-up data in tests and examples: no real addresses, device IDs or names.

CI checks every manifest and runs every extension's tests against famstack. The
same checks run on your machine:

```
FAMSTACK_REPO=<your famstack checkout> script/cibuild
```

## License

AGPL-3.0, like famstack.

Product names here (Philips Hue, SearXNG and others) are trademarks of their owners. The
extensions are not affiliated with or endorsed by them.
