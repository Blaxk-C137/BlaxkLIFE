# Changelog

All notable changes to this project. Dates are local build dates.

## [0.2.0] — 2026-10-17

Movement, gifting and the calendar rebuilt from player reports. Everything here
was reproduced first, then fixed, then re-verified in a real browser.

### Movement (click-to-walk, WASD)
- **The sprite no longer walks to the click point.** The server is the only
  thing that plans a route; `/api/state` and `move` now return `route[]` +
  `dest`, and the client walks those waypoints at the server's 230 px/s. This
  removes the front/back jitter (the client used to interpolate straight to the
  click, and every poll snapped it back onto the A* detour) and the "walks over
  houses" bug (the straight line cut through building footprints).
- Arrival is a settle, not a snap: the client ignores a lagging poll while it
  still has route left, and only glides to a *confirmed* resting position (two
  identical server reports) at walking speed.
- **The floating "talk to nearest" bubble is gone.** It sat over the middle of
  the map and swallowed clicks; the nearby rail and `E` do the same job.
- Pathfinder hardening: A* snaps start/goal to the nearest walkable cell (a
  legal standing spot could sit over a blocked cell centre, which made the walk
  die half-way), smoothing starts from the walker's real position, line-of-sight
  is sampled every 6 px with a 2 px margin, pocket destinations stop at the last
  reachable point instead of replanning forever, and a blocked leg rewinds to the
  last good point instead of wedging the walker in a gap.
- Crowd spacing: venue spots use a building-sized ellipse with per-index radii
  (golden-angle angles repeat every 34 steps), plus a deterministic separation
  pass, so residents and nameplates stop stacking.
- `scripts/movement_probe.py` drives real canvas clicks in Chromium and measures
  backtracks, building penetration, speed and arrival error.

### Gifts
- **Every purchasable item is giftable.** `act_gift` resolved through
  `ITEM_BY_ID` (catalog items only) and rejected every cafe consumable; it now
  uses `buyable()`.
- Reaction scoring is recipient-sensitive instead of flat: hobby overlap,
  favourite food, price value, a small penalty for generic food, and a
  repetition decay that keys on the exact item.
- The picker shows what the giftee likes, why the gift landed the way it did
  ("because it matches their hobbies and it's a real spend"), warns when you are
  too far away and walks you over before reopening.

### The block calendar
- New `blxverse/content/events.py`: eight weekly fixtures (Open Mic Night,
  Quiz Night, Market Day, Sunrise Run, Open Studio, Late Film Club, Flea Market,
  Sunday Roast) plus a stable birthday slot for every resident.
- Residents with matching hobbies drift into a live fixture (deterministic ~1 in
  3 turnout), so venues visibly fill up; the player gets a notice when one starts.
- Journal "Coming up" now lists live events, the week ahead and birthdays with
  icons, countdowns and a **Go** button.
- Phone → **Calendar** tab (`GET /api/calendar`) lists live/upcoming fixtures and
  birthdays with one-tap walk-to and message.
- HUD pill under the location card shows what is on right now.

### Docs / verification
- 70 tests (was 61), including walker fuzzing, venue crowding, gift gradient and
  calendar determinism.
- `pytest`, `ruff`, `compileall`, `node --check` clean; Playwright smoke plus the
  new movement probe pass.

## [0.1.0] — 2026-10-17

The vertical slice. Everything below was built in this pass; there is no earlier
public release.

### World & simulation
- Deterministic 60-resident neighborhood generated from a seed (unique first
  names, households, workplaces, birthdays, voices, looks, schedules).
- 11 venues plus player and resident homes on a 1900×1300 stylized map.
- Weekday/weekend schedules with sleep, work, meals, leisure and social blocks.
- Needs simulation: energy, social battery, stress, plus mood valence.
- Tiered updates (foreground/nearby/background) with batched background work.
- A* pathfinding on a 30 px navigation grid with line-of-sight smoothing,
  per-NPC path throttling and replanning; residents no longer clip through
  buildings and no longer stall in doorways.
- Schedule-gap wake rule: nobody is flagged "sleeping" while standing in the
  park at 6 pm (previously the last status could freeze).

### People
- Personality archetypes, traits, values, quirks, goals, secrets, boundaries.
- Mood model driving dialogue tone, availability and chaos thresholds.
- Structured memories with importance/valence/witnesses, including seeded
  backstory so residents feel like they existed before the player arrived.
- Beliefs stored separately from facts, with confidence, source and decay.
- Relationships with familiarity/trust/affinity/romance/tension and labels.

### Conversation
- Deterministic composer with 16 intents and archetype/mood-specific lines.
- **New:** state-grounded answers to player questions. Asking "What are you up
  to later?" now answers from the NPC's actual schedule/plans instead of a
  generic line. Whole-word keyword matching fixed ("hi" no longer matches
  inside "right").
- Memory and belief callbacks woven into replies.
- Text threads with delayed replies; calling with accept/decline.
- In-call captioning, barge-in that stops speech on microphone input, and a
  latency instrumentation endpoint.
- **New:** in-call typed composer (no `window.prompt`), so calls are fully
  usable without a microphone.
- Optional selective LLM phrasing layer (`engine/llm.py`) behind an env var,
  with timeout → deterministic fallback and cost/latency metrics. Never
  authoritative over simulation state.

### Economy
- Server-authoritative closed-loop BLX ledger: wages, rent, purchases, gifts,
  activities, dates, delivery fees, cart income, rewards and fines.
- Atomic money mutations with audit JSONL and category-validated ledger rows.
- **New:** cafe counter food (sandwich, iced coffee, smoothie) that closes the
  energy loop; `use_item` previously crashed on every item because the
  consumable schema lacked a `verb` field.
- Remote ordering (+10%) versus buying in person.

### Story
- Six-stage Mon–Fri chain: rent dispute → cafe meeting → missing brass mic
  rumor → investigation → public apology or cartoon clash → resolution.
- Rumor propagation with provenance and per-resident confidence; evidence
  clears a false accusation and shifts opinions.
- Emergent arcs: deepening friendship, business dream → stall, birthday
  picnic, rivalry heat. Capped at four concurrent; business arcs now progress
  through scouting before opening instead of resolving on day one.
- World Director cadences for feed posts, NPC chats, ambient events, rumors and
  emergent arcs.
- Cartoon slapstick scenes gated by tension, with cooldowns and venue bans.
  No identity-based groups or mobs are ever targeted.

### Client
- Canvas world with stylized non-photoreal art drawn entirely in code
  (no image or font downloads), day/night tint, weather particles.
- Character creator with live avatar preview and server-validated fields.
- HUD, action wheel, people/story/alerts sidebar, nearby rail, interact bubble.
- Phone OS: messages, feed, wallet/ledger/bag, case files, alerts.
- Journal with upcoming plans and a timeline.
- **Fixes:** player sprite no longer throws every frame; talk modal no longer
  crashes on open; sleeping residents disable the composer with an explanation;
  clearer "you" chat bubbles; local walk prediction so movement feels immediate
  while the server stays authoritative; save-overwrite warning on setup.

### Platform
- Standard-library HTTP server with 20 s autosave, rate limiting, request
  validation, sanitization, schema versioning and `.bak` save rotation.
- 54-test pytest suite (world, economy, actions, chain, persistence, HTTP API),
  including a real server subprocess for API tests.
- Playwright browser smoke script covering world → phone → venue → activity →
  work → profile → call → mobile layout.
- GitHub Actions workflow running lint + tests. Local git history only; not
  pushed.

### Known limitations
See `PROJECT_STATUS.md` §"Known gaps". Short version: voice depends on browser
speech APIs, the LLM layer is optional and untested live, social groups don't
yet run their own events, and long-run balance is tuned from 6-day runs.
