# BLXVERSE — a living AI neighborhood

A playable vertical slice of a simulated neighborhood: 60 residents with
schedules, moods, memories and opinions, a closed-loop fictional currency, a
rumor-driven story that resolves whether or not you intervene, and a stylized
world you can walk around.

Everything is implemented in this repository — no image assets, no CDN, no
bundler, no database. The simulation is Python (standard library only); the
client is vanilla ES modules drawing to canvas.

```
python3 run_server.py --port 8000
# open http://localhost:8000
```

A first run shows the character creator. After that the server resumes
`data/saves/world.json` and the block keeps living in real time (1× ≈ 1 game
minute per real second; 2× and 4× are available).

## What you can do

- **Create a resident** — name, age, gender/pronouns, appearance; the avatar is
  drawn live in canvas.
- **Walk the block** — click to walk; the server pathfinds around buildings and
  stays authoritative.
- **Talk** — free text or quick intents. Ask real questions ("what are you up
  to later?") and residents answer from their actual schedule, plans and mood.
  They remember what you did, and they gossip about it.
- **Text and call** — threads with delayed replies; calls with speech in the
  browser, live captions, barge-in, and a typed fallback.
- **Work, eat, spend** — shifts pay ~70 BLX for 4 hours and cost energy; the
  cafe sells food that restores it; rent is due at 09:00.
- **Date, gift, celebrate** — eligibility gates, venue calendars, gift meaning
  that depends on the recipient.
- **Follow the story** — a rent dispute becomes a false accusation about a
  missing brass microphone. Investigate three locations, present evidence, and
  watch opinions shift. Ignore it and the block resolves it without you.
- **Build a life** — open a street cart, build reputation, get banned from a
  venue for slapstick chaos.

## Interesting parts of the implementation

| Area | Where | What makes it interesting |
|---|---|---|
| Deterministic world | `blxverse/engine/rng.py`, `generate.py` | Named RNG streams; the same seed reproduces the cast, events and rumors |
| Minds | `models.py`, `sim.py` | Memory ≠ belief ≠ fact; beliefs decay and can be challenged |
| Dialogue | `composer.py` | 16 intents, mood/archetype lines, state-grounded answers, memory callbacks |
| Optional LLM | `engine/llm.py` | Phrasing only; can never change state; silent fallback |
| Story | `director.py` | Authored chain + emergent arcs, day/hour gates, auto-resolution |
| Economy | `economy.py` | Server-authoritative ledger with categories and audit log |
| Chaos | `chaos.py` | Interpersonal slapstick only; cooldowns and venue bans |
| Navigation | `sim.py` | A* on a 30 px grid with LOS smoothing and replan throttling |
| Client | `web/js/*` | Canvas art, client-side movement prediction, phone OS, voice UX |

## Testing

```bash
pytest -q          # 61 tests: world, economy, actions, story chain, saves, HTTP API
ruff check blxverse tests scripts
```

The API tests spawn a real server subprocess on a free port, create a world and
drive it over HTTP — they exercise the same path a browser does.

Optional browser walkthrough (needs Playwright):

```bash
python3 -m pip install playwright && python3 -m playwright install chromium
python3 run_server.py --port 8000 &
python3 scripts/browser_smoke.py --base http://localhost:8000
python3 scripts/movement_probe.py --base http://localhost:8000   # click-to-walk metrics
```

`movement_probe.py` fires real canvas clicks at open ground and reports
backtracks, building penetration, walking speed, arrival error and how far the
sprite drifts from the server. It is the regression gate for movement.

## Configuration

Copy `.env.example` to `.env` if you want to change defaults. Everything is
optional; the game runs with none of it.

| Variable | Default | Meaning |
|---|---|---|
| `BLXVERSE_PORT` | `8000` | Server port |
| `BLXVERSE_DATA_DIR` | `./data` | Save + audit location |
| `BLXVERSE_SEED` | time-based | World seed for new games |
| `BLXVERSE_LLM_API_KEY` | unset | Enables optional LLM phrasing |
| `BLXVERSE_LLM_MODEL` | `gpt-4o-mini` | Model name for the provider |
| `BLXVERSE_LLM_BASE_URL` | OpenAI-compatible URL | Provider endpoint |
| `BLXVERSE_LLM_DISABLED` | unset | Force the deterministic composer |

## Privacy and safety

- **No audio is recorded or transmitted.** Speech recognition runs in the
  browser; the server only receives the text you chose to say.
- **All residents are fictional.** BLX is a closed-loop in-game credit with a
  1 BLX ≈ 1 USD internal reference and no cash value, no purchases, no payouts.
- **No identity-based conflict.** Slapstick scenes are between two specific
  residents with built-up tension; there are no mobs and no targeting of groups.
- **Boundaries matter.** Harassing text is rejected and residents disengage
  instead of escalating.
- **Local by design.** Single-player, no accounts, no telemetry.

## Repository layout

```
blxverse/
  config.py              tunables (one place)
  content/               names, traits, items, venues, feed + dialogue banks
  engine/
    rng.py               stable hash + named streams
    models.py            Player, NPC, Memory, Belief, Thread, Case, Arc
    generate.py          seeded world generation
    sim.py               clock, movement, needs, memory, saves
    composer.py          deterministic dialogue
    llm.py               optional phrasing provider
    economy.py           ledger + validation
    chaos.py             slapstick engine
    director.py          story chain + emergent arcs + ambient life
content/events.py        weekly fixtures + birthdays (the block calendar)
    actions.py           28 player actions
  server.py              HTTP API + static server
web/                     index.html, css, js (canvas world + UI)
tests/                   pytest suite
scripts/browser_smoke.py optional Playwright walkthrough
scripts/movement_probe.py click-to-walk metrics (backtracks, walls, speed)
docs/DECISIONS.md        why the system is shaped this way
PROJECT_STATUS.md        honest feature matrix
CHANGELOG.md             what changed
```

Built as a local, single-player slice. Not published. See `PROJECT_STATUS.md`
for exactly what is and isn't done.
