# BLXVERSE — Project Status

Honest feature matrix for the vertical slice. "Verified" means a test or a
recorded manual run exercised it against the real simulation, not that the code
merely exists. Last full verification: see `CHANGELOG.md` and the commands at
the bottom of this file.

- Version: `0.2.0` · Schema: `3`
- Architecture: Python standard-library simulation server + dependency-free
  browser client (canvas world, DOM UI). No bundler, no CDN, no external assets.
- Save format: JSON with schema version, atomic write + `.bak` rotation.

## How to run

```bash
python3 run_server.py --port 8000      # serves API + web/ on 0.0.0.0
pytest -q                              # 70 tests, ~8 min (API tests spawn a server)
ruff check blxverse tests scripts      # lint
python3 scripts/browser_smoke.py --base http://localhost:8000   # optional, needs Playwright
python3 scripts/movement_probe.py --base http://localhost:8000  # click-to-walk metrics
```

Open `http://localhost:8000`. First run shows the character creator; afterwards
the server resumes the save in `data/saves/world.json`.

## Feature matrix

Legend: **Done** = implemented and verified · **Ready** = implemented, verified
for core paths but not exhaustive · **Partial** = works with known gaps noted ·
**Not built** = out of scope for the slice.

### 1. Living neighborhood

| Feature | Status | Evidence / notes |
|---|---|---|
| 60 residents generated per seed | Done | `test_world.py`: 60 NPCs, unique first names, 18 spotlight |
| 12–20 resident vertical slice with named cast | Done | Zara Adeyemi, Daniel Okafor, Femi Balogun + spotlight tier |
| 11 venues, homes, park, square | Done | `/api/world` payload asserted |
| Households, coworkers, friendships, couples, exes, rivalries | Done | fabric generation; `test_world.py` relationship assertions |
| Schedules (weekday/weekend), sleep, work, leisure | Done | schedule blocks serialized and followed by the sim |
| Autonomous movement between venues | Done | A* navigation on a 30 px grid, replan-on-blockage, no wall clipping |
| Awake between scheduled activities | Done | schedule gaps resolve to "between things", never a false bedtime |
| Needs: energy, social battery, stress | Done | drains and recovers; hunger loop closed via cafe food |
| Tiered simulation (foreground / nearby / background) | Ready | tier counts exposed in `/api/state`; background NPCs batch-update |
| Off-screen lives (feed, messages, rumors continue) | Done | ambient posts, NPC-to-NPC chats, rumor spread without the player |
| Deterministic world from seed | Done | `RngHub` named streams; same seed reproduces the cast and events |

### 2. Character creator

| Feature | Status | Evidence / notes |
|---|---|---|
| Name, age (22–90), gender + pronouns | Done | server validates; `player.first/occupation/pronouns` in state |
| Appearance: skin, hair style/colour, outfit, accessory | Done | canvas-drawn portraits, no image assets |
| Live avatar preview | Done | `avatarUrl()` renders to data URI |
| Overwrite protection on an existing save | Done | `world_exists` unless `overwrite:true`; prior save rotated to `.prev-<ts>` |
| Player identity in HUD/profile | Done | portrait, wallet, energy, reputation, bag |

### 3. NPC minds

| Feature | Status | Evidence / notes |
|---|---|---|
| Personality traits, values, quirks, goals | Done | archetype + stats drive dialogue and decisions |
| Mood model (valence, stress, excitement, irritation, social battery) | Done | mood label drives replies, chaos thresholds, availability |
| Structured memory (event, importance, valence, witnesses) | Done | 180+ seeded backstory memories; recall hooks in dialogue |
| Separate beliefs vs facts | Done | `Belief` with truth flag, confidence, source, rumor id, evidence |
| Belief decay and challenge | Done | 0.045/day decay; `challenge_rumor` lowers confidence, `present_case` clears |
| Relationships: familiarity, trust, affinity, romance, tension | Done | bounded deltas, labels (stranger → partner/rival) |
| Recipient-specific gift meaning | Done | tags vs hobbies vs repeated gifts |
| Boundary/harassment handling | Done | 422 `harassment` path; NPCs disengage, no identity-based aggression |

### 4. Conversation, text and voice

| Feature | Status | Evidence / notes |
|---|---|---|
| Free-text conversation with intent classification | Done | 16 intents, word-boundary keyword matching |
| State-grounded answers to real questions | Done | "What are you up to later?" → schedule/plans answer |
| Quick intents (greet/joke/flirt/talk/gossip/apologize/invite) | Done | effect chips returned to the client |
| Memory/belief callbacks inside dialogue | Done | hook templates, ~16% per turn |
| Text messages with delayed replies | Done | pending replies 2–14 min, threads capped at 80 |
| Incoming calls with ring UI | Done | pending call in state, accept/decline |
| Call with realtime captions + barge-in | Ready | browser SpeechRecognition + SpeechSynthesis; barge-in stops TTS on speech start; graceful fallback to typing |
| Typed input during a call (accessibility/no-mic path) | Done | inline composer, replies spoken |
| Voice latency instrumentation | Done | `/api/voice/metric`, p50/p95 in state; target 800 ms |
| Selective LLM phrasing (optional) | Ready | `blxverse/engine/llm.py`; off unless `BLXVERSE_LLM_API_KEY`; deterministic composer is the default |

### 5. Social life

| Feature | Status | Evidence / notes |
|---|---|---|
| Dates: ask, venue pick, calendar, miss/handle outcomes | Done | eligibility gates, cost table, `date_go`, `missed_date` |
| Gifts | Done | any `buyable()` item, recipient scoring (hobby / favourite / price / food penalty / repetition), walk-to-nudge in the picker |
| Calendar/upcoming plans in journal | Done | `journal.upcoming`: accepted dates + plans + weekly fixtures + birthdays, with countdowns and Go |
| Weekly block fixtures | Done | 8 recurring events (`content/events.py`), live window, notices on start |
| Residents attend fixtures | Done | hobby match + deterministic turnout (~1 in 3); studio holds 6 during Open Studio |
| Birthdays | Done | stable per resident, weekly recurrence, surfaced for the named cast and anyone you know |
| Phone OS (messages, feed, calendar, wallet, cases, alerts) | Done | 6 tabs, all live data (`/api/calendar`) |
| Social groups / crews | Partial | `group_hint` chip from generation; no group events beyond ambient ones |
| Feed: post, like, comment | Done | reactions from NPC moods and relationships |
| In-game social network with rumor provenance | Done | post `author`, rumor `origin_id`, belief `source_id`; player-planted gossip is tagged `planted_by` |
| Rumor uncertainty display | Done | profile shows beliefs with confidence; challenge action lowers it (0.55 → 0.37 verified) |
| Stir the pot | Done | whisper becomes a real rumor with provenance, not just a tension nudge |

### 6. Economy

| Feature | Status | Evidence / notes |
|---|---|---|
| Closed-loop BLX ledger | Done | every mutation is a ledger row with category + memo |
| Server-authoritative balances | Done | no client-supplied amounts; validation in `economy.py` |
| Income: shifts, cart, daily stipend | Done | 4 h shift ≈ 70 ± 46 BLX, energy cost |
| Expenses: rent, food, activities, dates, gifts, delivery fee | Done | rent 32 at 09:00, remote +10% |
| Insufficient funds / limit handling | Done | `insufficient_funds`, `limit` mapped to 4xx |
| Audit log | Done | append-only JSONL in `data/audit/` + in-memory ledger |
| 1 BLX = 1 USD reference, no cash value | Done | shown in shop/wallet copy; no purchase path |
| Persistence of money across restarts | Done | save round-trip test |

### 7. Story engine

| Feature | Status | Evidence / notes |
|---|---|---|
| Mon–Fri authored chain (Zara/Daniel/landlord) | Done | 6 stages, day/hour gates, survives restarts |
| Rumor → case → investigation → resolution | Done | 3 clue locations, 2 needed, `present_case` verdicts |
| Branch on player action (cleared vs clash) | Done | apology path vs slapstick path; Zara's opinion shifts |
| Emergent arcs (friendship, business, birthday, rivalry) | Done | capped at 4 concurrent, staged with feed posts |
| World Director cadence (feed/chat/ambient/director/rumor) | Done | 45–280 min cadences, deterministic streams |
| Auto-resolution if the player never intervenes | Done | a witness comes forward on day 5 |
| Cartoon slapstick chaos (no identity-based mobs) | Done | tension gate, pair cooldown, dust-cloud scene, 6 h ban |

### 8. Presentation

| Feature | Status | Evidence / notes |
|---|---|---|
| Stylized non-photoreal 3D-ish world | Done | canvas isometric-ish art, 11 venues, animated residents |
| Day/night tint, weather particles | Done | clock-driven |
| HUD: clock, speed, wallet, energy, reputation, alerts | Done | all live |
| Action wheel, sidebar (people/story/alerts), nearby rail | Done | keyboard + mouse |
| Mobile layout | Partial | responsive to 390 px; touch walk works, no dedicated gestures |
| Accessibility: keyboard controls, reduced motion | Partial | WASD/keys, `prefers-reduced-motion`; no full screen-reader pass |
| External assets | None | everything is inline/canvas — works offline and in sandboxed iframes |

### 9. Platform & operations

| Feature | Status | Evidence / notes |
|---|---|---|
| JSON save/load, atomic writes, `.bak` | Done | `test_persistence.py` |
| Schema versioning + migration guard | Done | `schema_mismatch` error |
| Autosave every 20 s + on shutdown | Done | server loop |
| Rate limiting | Done | 90 actions/min; movement gets its own budget |
| Input sanitization | Done | length caps, control-char strip, harassment patterns |
| Structured event log | Done | every scene/event with actors, location, witnesses |
| Deterministic tests | Done | seeded fixtures, no wall-clock dependence |
| CI workflow (lint + tests) | Done | `.github/workflows/ci.yml` |
| Browser smoke script | Ready | `scripts/browser_smoke.py` (Playwright, run manually) |
| Deployment hardening (TLS, auth, multi-user) | Not built | single-player local server by design |

### 10. Explicitly not built (slice boundaries)

- Multiplayer, accounts, cloud saves, leaderboards.
- Payment flows of any kind — BLX is fictional and closed-loop.
- Voice cloning or stored audio. Speech runs in the browser; the server only
  receives transcripts.
- A hosted LLM dependency. The optional provider is off by default and never
  changes simulation state.
- Real-world brands, licensed music, or identity-targeted conflict content.

## Definition of done for this slice

- [x] `pytest -q` green (70 tests)
- [x] `ruff check` clean, `compileall` clean, `node --check` clean on all JS
- [x] End-to-end flow works in a real browser: create → walk → talk → text →
      call → gift → work → eat → investigate → present case → date → save/reload
- [x] Honest matrix (this file), `CHANGELOG.md`, `docs/DECISIONS.md`
- [x] Local git history with descriptive commits
- [x] Not pushed to GitHub

## Verification record

Run on 2026-10-17 against the committed tree:

| Check | Result |
|---|---|
| `pytest -q` | 70 passed in ~8 min |
| `ruff check blxverse tests scripts` | clean |
| `python -m compileall` | clean |
| `node --check` × 5 bundles | clean |
| Browser smoke (Playwright, 1440×900 + 390×844) | pass, zero page errors |
| `scripts/movement_probe.py` (real canvas clicks) | pass: 0 backtracks, 0 px inside buildings, 230 px/s, arrival error ≤0.2 px, sync error ≤0.3 px |
| Manual flows over live HTTP | talk (grounded answers), text thread, gift, shop buy + eat, activity, shift work, investigate ×3, present case (Daniel cleared, rep 67.1), ask date → calendar → date, stir → rumor → challenge, street cart |

## Known gaps / honest caveats

1. **Pocketed destinations.** A few percent of map points sit in a courtyard the
   30 px nav grid cannot enter (e.g. a 20 px slot between two buildings). Clicks
   there walk to the last reachable point and stop — they never clip a wall or
   loop. `scripts/movement_probe.py` aims at open ground on purpose.
2. **Voice** depends on the browser's `SpeechRecognition`. Chrome/Edge provide
   it; Firefox does not. The UI always offers typed input as an equal path, and
   captions/latency instrumentation still work.
3. **LLM phrasing** is optional and untested against a live provider in this
   environment (no key). Failure is designed to fall back silently to the
   composer.
4. **Social groups** are generated and displayed but do not yet drive group
   events of their own.
5. **Long-run balance** is tuned from 6-day scripted runs, not weeks of play.
6. **Accessibility** coverage is keyboard + reduced motion, not a full audit.
