# hue: the family's Hue lights, from the stack, locally

An extension stacklet for famstack. It calls up Philips Hue scenes and
sets brightness, on and off through the Hue Bridge's local API: no Philips
cloud, no account, no app on the phone. No container either, nothing to `stack up`: each command talks to
the bridge from the Mac.

```
./stack hue setup [<address>]          find the bridge, pair with its button (once per instance)
./stack hue scene list                 the scenes, by room
./stack hue scene <name> [<room>]      call one up: scene relax living room
./stack hue status                     every room, zone and lamp: on or off, how bright
./stack hue brightness <name> <level>  40, 30%, +10, -20: brightness office 50
./stack hue on <name> | off <name>     off living room, off all
```

`<name>` is a room, a zone (a group of lamps made in the Hue app), a single
lamp, or `all` for the whole house. A room named exactly wins over lamps
named after it ("Office" over "Office Lamp"); a lamp name in several rooms
needs the room after it (`on floor lamp kids room`). The rules are in
`lights.py` and `scenes.py`.

Scenes, rooms and zones are made, renamed and deleted in the Hue app;
every command reads them fresh from the bridge, so changes count at once.
Colour and colour temperature are left to the scenes (Arthur, 2026-10-26):
a scene "Warm" or "Cool" per room does that.

## How a command reaches the lamps

```
 family chat                              admin's terminal
 "Office light to 40 %, please"           ./stack hue brightness office 40
            │                                         │
            ▼                                         │
 ┌──────────────────────────┐                         │
 │ Stacky, the agent,       │                         │
 │ in core's bot runner     │                         │
 └────────────┬─────────────┘                         │
              │ a command [agent] allow lists,        │
              │ through the core API                  │
              ▼                                       ▼
 ┌────────────────────────────────────────────────────────────┐
 │ ./stack hue <cmd>     on the Mac, Python standard library  │
 │ reads stack.toml [hue] host, <data_dir>/hue/bridge.json    │
 └─────────────────────────────┬──────────────────────────────┘
                               │ HTTPS on port 443, certificate pinned,
                               │ key in the hue-application-key header
                               ▼
 ┌────────────────────────────────────────────────────────────┐
 │ Hue Bridge     /clip/v2/resource/room, light, scene, ...   │
 └─────────────────────────────┬──────────────────────────────┘
                               │ Zigbee
                               ▼
                             lamps
```

Every command runs on the Mac, whoever asked: the agent's container never
talks to the bridge, it asks the core API to run the command. Only `setup`
does more: it finds the bridge by an SSDP search on the home network (UDP
port 1900) and asks it for a key (`POST /api`) until the button is
pressed. Nothing on this path goes through the Philips cloud.

## Pairing

Every program that talks to the bridge (the Hue app, Home Assistant, each
famstack instance) needs its own key, and the bridge hands one out only
within about 30 seconds of its round button being pressed. So `setup` runs
once per instance, with someone next to the bridge:

```
./stack hue setup
Press the round button on the Hue Bridge now. Waiting up to 60 seconds ...
```

It finds the bridge by SSDP on the home network (not through Philips'
discovery service), writes its address to `stack.toml` `[hue] host`, and
keeps the rest in `<data_dir>/hue/bridge.json`, readable by the admin only:

- **The key** opens every light in the house. It is not in `stack.toml`,
  which `stack config` prints, and not in the stack's secrets, which a
  stacklet command can read but not write. The data dir is in the backup.
- **The certificate fingerprint.** The bridge's certificate is
  self-signed, so `setup` pins it, and every call checks it before sending
  anything. Another device at the bridge's address gets no request and no
  key; after replacing the bridge, run `setup` again.

The bridge lists each pairing as an app ("famstack#stack"). Removing one is
possible only in the Hue app (Settings > Apps); Philips switched off doing
it over the local API.

**From the chat:** `[agent] allow = ["hue"]` in `stack.toml`, then
`./stack up agent`.

**On a timer:** `./stack core schedule add evening "daily 19:00" -- hue scene relax living room`

## Without the cloud

The local API works without the bridge reaching the internet. To take it
off the internet on a Fritz!Box: Internet > Filters > Parental Controls,
the device "Hue Bridge", access profile "Blocked". What that costs, as far as
the sources say (not tried here yet):

- the Hue app from outside the home, and Alexa or Google through the Hue cloud;
- firmware updates, security fixes included (unblock now and then);
- possibly the bridge's clock, if it sets it from the internet, and with it
  the Hue app's timed routines; `stack core schedule` can take those over.

Setting the bridge up in the Hue app needs a Philips account since
2023/24; after that, Philips says, the lights work without internet.

## What was tested

On the family's bridge (BSB002, API 1.78.0), 2026-10-26, through `./stack hue`.
Its rooms and scenes have German names; they are given in English here.

| | Result |
|---|---|
| `setup` without an address | found the bridge by SSDP (`hue-bridgeid` header) |
| pairing | error 101 until the button, then a key; 15 s with a person walking over |
| no button within 60 s | clear error, nothing written |
| `scene list` | 3 rooms, 37 scene names |
| `scene concentrate office` | HTTP 200, `{"data": [{"rid", "rtype": "scene"}], "errors": []}`; the bridge then reports the scene `active: static` |
| `brightness office 50`, then `-20` | both office lamps 50 %, then 30 % |
| `brightness office strip 80` | that lamp 80 %, the other unchanged; the room reports 55 % |
| `off office`, `on office` | off, then on as before |
| `status` | rooms, lamps and their state; a room without lamps reads "no lamps" |

Not tried live: zones (the bridge had none), `all`, and what a step does
below the lowest brightness.

## Layout

```
bridge.py     the bridge: HTTPS with the pinned certificate, pairing, rooms and scenes, SSDP
names.py      how words compare with names (case, spaces at the ends, a room at the end)
scenes.py     which scene the words mean (pure functions)
lights.py     which room, zone or lamp the words mean, and brightness levels (pure)
cli/          setup, scene, status, brightness, on, off; _common.py reads the pairing
tests/        the commands against a stand-in bridge that answers like the real one
```

## Tests

```
FAMSTACK_REPO=<famstack checkout> \
    uv run --project "$FAMSTACK_REPO" --extra test pytest hue/tests
```

22 tests, about 4 seconds, nothing leaves localhost. They need `openssl`
for the stand-in bridge's certificates, and `FAMSTACK_REPO` for the
framework they run hue in. `script/cibuild` at the repo root runs them
with every other extension's.

## Trademark

Philips Hue is a trademark of Signify. This extension is not affiliated with
or endorsed by Signify; it talks to the bridge over its documented local API.
