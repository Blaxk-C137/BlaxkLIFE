# BLXVERSE — life in BlaxkVille

A playable vertical slice of a simulated neighborhood: 72 adult residents with
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

## BlaxkVille 0.6: shared memory, Nigerian voice and cleaner chats

- Texts, phone calls and in-person chats now share persistent per-resident memory.
- Relevant older exchanges and explicit player disclosures reach Gemini, not just a generic event summary.
- Natural Nigerian English/light Pidgin; channel-specific WhatsApp-style texts versus spoken replies.
- Real casual meetup requests: **“Abeg wait for me at the park”**, **“Meet me at the cafe in 20 minutes”**.
  Residents can accept/decline, walk there, wait, report arrival/departure and cancel; vague requests ask for details.
- Cleaner conversation panels: visible composers, less clutter, newest sent message auto-scroll and non-overlapping call captions.
- Existing saved threads migrate. Older call words that were never stored cannot be recovered retroactively.

**[Changes, supported commands and memory limits →](docs/BLAXKVILLE_0.6.md)**

## BlaxkVille 0.5: conversations, safety and consequences

- Casual NPC-to-NPC overhead speech bubbles and restrained friendly pass-by greetings.
- Server-backed Talk sessions: the other resident stays until you finish or they leave upset/in danger.
- Stylized non-graphic disputes/theft, armed four-person bandit formations, police and soldiers.
- A hospital and recovery ward, plus permanent adult deaths and named memorials.
  **Named/story residents are not immune.** Relationships and affected stories end honestly.
- New hospital, graveyard, police station, barracks and Backlot, with walkable entrances.
- Abstract fictional gun/drug ventures: stakes, returns and police seizure risk, no real-world instructions.
- Work dims the screen and blocks controls, including a server-enforced five-second finishing lock.
- Optional Gemini **3.5 Flash-Lite**, recent-conversation context, local request caps and offline fallback.
- Same **72-person cast** and original save; no cast replacement or world reset.
- Additional sleep-interruption and tree-edge pathfinding regressions fixed and tested.

Open the **shield button** in the header for neighbourhood services and reports.
**[Full changes, evidence and limitations →](docs/BLAXKVILLE_0.5.md)**

## BlaxkVille 0.4: space, phone and connections

- Residents fade in as you approach; actors outside the camera or beyond the
  local visibility radius are not drawn or clickable. They still live offscreen.
- Residents walk to their doorstep, disappear indoors, and emerge for their
  next outing. No sleeping actors left on lawns. Home downtime is indoors too.
- Independent local movement, reserved destinations and yielding reduce piles.
- A **Samsung One UI-inspired** phone, blue/grey message bubbles, draft-safe
  typing, punch-hole status bar and responsive composer. Not affiliated with Samsung.
- Quiet original procedural background music, gesture-started, with a **♫**
  mute toggle, saved preference and automatic speech/call ducking.
- **72 adult residents**, including **12 additional women**, Zayyan, Bashir,
  Dominion, and an expanded female-name roster. Older 60-person saves migrate
  without replacing existing IDs or resetting progress.
- A **Connections** phone guide, live relationship milestones and conversation
  notes support listening, mutual interest, dates and respectful boundaries.
  Typed date/flirt requests obey the same rules as quick buttons.

### Enable Gemini

Set these in your **server environment** (Render → Environment), then restart:

```text
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.5-flash-lite
BLXVERSE_LLM_DISABLED=0
```

`GOOGLE_API_KEY` is also accepted. Keys stay on the server. Local `.env` files
are **not automatically loaded**; export the variables in your shell or use your
host's environment settings. Never put a key in `web/` or client JavaScript.
Gemini supplies text for chats, texts and call turns; speech uses browser
recognition/synthesis, **not Gemini Live audio**. Network work does not hold the
simulation lock. Missing keys, timeouts and blocked responses keep the offline
composer playable. Consent/date outcomes remain authoritative. Text and
character context are sent to the configured provider when enabled; consult
its privacy terms and billing. The game does not measure actual provider spend.

**[Previous 0.4 verification →](docs/BLAXKVILLE_0.4.md)**

## BlaxkVille 0.3 update

Typing no longer loses focus on world polls. Residents use continuous buffered
route playback, trees have correct occlusion and solid bases, and notifications
can be dismissed or expire in five seconds. Phone/tablet layouts were verified
at six viewport sizes. The city stays 1900 × 1300.

The offline character voices were audited at **1,200 distinct greetings for each
of 60 residents**. There are over one million **composition slots** per resident,
not one million independently written stories. The requested local names are
included without replacing the story anchors.

**[Detailed fixes, evidence and honest limitations →](docs/BLAXKVILLE_0.3.md)**

## Deploy on Render (CPU only)

Use the included [`render.yaml`](render.yaml) Blueprint: one Python CPU web
service, a persistent save disk, and a generated browser login password.
**[Step-by-step Render deployment guide →](docs/RENDER.md)**

The Blueprint uses a **paid Starter service + 1 GB disk**; review costs before
confirming. No GPU, model download, frontend build, or runtime pip dependencies
are required. This is one shared single-player world, not a multi-account server.

```bash
python3 scripts/render_check.py --seconds 30  # isolated PORT/CPU/save/restart check
```

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
pytest -q          # 85 tests: world, economy, actions, story chain, saves, HTTP API
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
python3 scripts/ui_regression.py                               # isolated focus/mobile/NPC gate
python3 scripts/dialogue_audit.py --samples 1200                # every character, offline
```

`movement_probe.py` fires real canvas clicks at open ground and reports
backtracks, building penetration, walking speed, arrival error and how far the
sprite drifts from the server. It is the regression gate for movement.

## Configuration

Set environment variables in your shell or Render dashboard to change defaults.
`.env.example` documents them; the app does not automatically load `.env` files.
Everything is optional for local use; the game runs with none of it.

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | unset | Hosting platform port (Render supplies this) |
| `BLXVERSE_PORT` | `8000` | Local override; wins over `PORT` |
| `BLXVERSE_HOST` | `0.0.0.0` | Bind address |
| `BLXVERSE_ACCESS_PASSWORD` | unset | Optional HTTP Basic password (username `blxverse`); Blueprint generates it |
| `BLXVERSE_DATA_DIR` | `./data` | Save + audit location |
| `BLXVERSE_WORLD_SEED` | `20261017` | World seed for new games |
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

Built as a single-player slice; local and Render deployment configurations are included.
Not yet deployed to an external hosting account. See `PROJECT_STATUS.md`
for exactly what is and isn't done.
