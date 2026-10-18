# BlaxkVille 0.3 — repair and UX notes

## Reported issues and the changes

### 1. Typing/texting/Gist Hub kept refreshing

**Reproduced:** a typed Gist Hub draft became an empty string and the active
input lost focus after a state poll. The game was not navigating/reloading the
page: `refreshOpenPanel()` replaced the entire phone body every 1.4 seconds.

**Fixed:** no automatic phone-body replacement. An open conversation refreshes
only the message list when message IDs/content change, leaving the composer DOM
node, native keyboard, caret and draft alone. Drafts survive tab navigation;
failed sends preserve text; successful sends clear only the submitted draft;
double-taps are guarded. Outdated tab fetches cannot overwrite a newly selected
tab. Gist Hub has a deliberate refresh button rather than a destructive timer.
Incoming replies still appear live. A single in-flight world poll prevents
slow mobile requests building a backlog; polls started before an action do not
overwrite that action's result.

### 2. Synchronized, stop/start resident movement

**Cause:** every resident eased rapidly to their latest position, then almost
stopped while waiting for the next snapshot.

**Fixed:** server snapshots include remaining NPC paths and individual stride
speeds. The client polls every 600 ms and uses an 800 ms jitter buffer to play
back route segments on animation frames. It turns along the path rather than
cutting a corner with a straight chord. A delayed poll can coast for at most
1.2 seconds, and only on an already-known authoritative route. Each resident
has a stable walking speed and independent gait phase, facing, joint movement,
and small idle motion. This is deliberately not animation of a server tick.

Path caches invalidate when the target changes. An unreachable final point
stops at its reachable route endpoint instead of teleporting to the original
target. Walk-home targets can finish in the sleeping state. Resident destinations now
persist across restarts; old mid-walk saves reconstruct a schedule decision
instead of leaving a resident walking in place.

### 3. Much larger offline dialogue, separate personalities

`content/voices.py` adds authored intent beats, eight speaking styles,
character-specific preferences/values/aspirations, personal asides, and
follow-up questions. The requested named residents have curated directions:
Abdullahi is a calm strategist; Smarty an analyst; Musty a relaxed storyteller;
Legend a builder; Eboh a direct creative; Joski a kind mischief-maker; Ofucks a
dry-wit night owl; Ysmanny a playlist romantic; Samban a connector; Fati quietly
fearless; Jenny a bright social butterfly; Omonu observant; Elvina a dreamy maker.
Other residents still combine their own traits, work, hobbies, goals and quirks.
Profiles and the nearby-resident sidebar expose the voice/vibe rather than
pretending everyone has the same personality.

The deck is seeded per resident and intent. Cursor positions persist in NPC
flags, so talk, text replies and calls advance the deck across a save/restart.
State-grounded questions still use actual schedule/mood/work/food/music data.
Consent/relationship decisions and story evidence override generic variation;
these are not random promises or invented bookings. No Gemini call is needed.

**What “a million dialogues” means here:**

- The audited composer produced **1,200 different greetings for each of all
  60 residents**: 72,000 actual sampled replies, not 1,200 shared across the cast.
- There are **1,152,000 conservative composition slots per resident** across nine
  ordinary intents: eight new core beats × eight style openings × 100 personal
  asides × 20 follow-ups × nine intents. Original archetype lines add more.
- This is **not** a million independently authored conversations or stories.
  It is a compact offline combinatorial dialogue system. Grounded questions,
  boundaries, and outcome-bearing turns deliberately reduce variation. Repeated
  short phrases remain possible even when complete replies differ.
- See `dialogue-audit.json` for every resident's sample count and an actual line.

### 4. Notifications stuck over the map

Pinned quest/ticker cards were replaced by deduplicated toasts. Each transient
notice has an immediately clickable close button and **exactly five seconds**
unless dismissed earlier. Polling the same story stage does not re-pin it.
The location chip also has a close button, expires after five seconds, and only
reappears on a real location change. Live fixtures announce once; full event
and story history stays in Calendar, Alerts and Journal. This does not delete
story progress when a banner is dismissed. The stack is capped at three cards.

### 5. Names and city

The full cast guarantees Abdullahi, Smarty, Musty, Legend, Eboh, Joski, Ofucks,
Ysmanny, Samban, Fati, Jenny, Omonu and Elvina, plus Ibrahim, Dami, Chuks, Zainab,
Amina, Chiamaka, Zuri and Ene. Zara, Daniel and Femi remain as story anchors.

The city is **BlaxkVille**. It remains **1900 × 1300**. Existing saves migrate
names without changing resident IDs, wallets or relationship links. Old authored
story titles/descriptions use the new city name so an old arc does not fork into
a duplicate. Historical quoted personal names are not comprehensively rewritten.

### 6. Phone/tablet/desktop fit

Viewport-aware sizing uses `visualViewport` where available, with a dynamic
height fallback. Phone panels shrink when the software-keyboard viewport does;
only the message list scrolls, while the send row stays visible. Text inputs
are 16 px to avoid iOS focus zoom. Flex/grid children have zero minimum sizes,
long posts wrap, dialogs scroll inside the viewport, mobile headers use two
rows, and horizontal tabs/nearby residents scroll intentionally. World shortcuts
do not hijack typing or run behind a phone/modal. Tab remains native keyboard
focus navigation. Close/send controls have mobile-sized hit targets. The touch menu includes
Journal, Calendar and pause/1×/2×/4× controls, so hiding the narrow-screen HUD
controls does not remove access to story history or game speed.

### 7. Trees/bushes and character visuals

The server and client share 74 deterministic scenery props. Tree trunks and
bush bases are solid navigation obstacles, but the space under a tree's canopy
is traversable. Only shadows live in the static ground image: trees/bushes join
the Y-sorted actor drawing queue, so residents pass behind foliage instead of
being painted on top. Loading an old save moves any embedded body to clear ground.

Residents now have articulated legs and shoes, swinging sleeves/hands, necklines,
tee/jacket/hoodie/tunic silhouettes, seams, scarf/chain/earring details, subtle
face expressions and independent walking phases. This is an improved procedural
2D renderer, not a new 3D-model/physics engine.

## Verification

```bash
pytest -q
ruff check .
python3 -m compileall -q blxverse scripts tests
python3 scripts/dialogue_audit.py --samples 1200 --output docs/dialogue-audit.json
python3 scripts/ui_regression.py                         # Playwright + Chromium
python3 scripts/movement_probe.py --base http://localhost:8111
python3 scripts/render_check.py --seconds 30 --output docs/render-check.json
```

- 85 Python/optional-Node tests (10 added for this release).
- `ui-regression.json`: slow typing through polls; exact composer identity/focus;
  one send; incoming reply; failed-send draft; Gist Hub post/comment; five-second
  notice expiry and dismissal; six viewport sizes (320/360/390/768/1024/1440),
  all six phone tabs and profile/shop/settings/help/stats/journal panels.
- Actual resident animation sampled across 98 frames, with no stationary frames
  during the measured walk. DOM-free Node tests cover route corners, continuous
  interpolation, pause/hold behavior and bounded extrapolation.
- Browser smoke (activities, work, calls, mobile) passed. Player movement probe
  passed with no backtracks or building penetration. Pocketed clicks may still
  stop at the last reachable point of the 30 px navigation grid.
- Render-style boot/auth/persistent restart test passed. Latest short local
  CPU probe: 4.7% of one core, 28.45 MiB sampled peak RSS (not Render hardware).

Browser test worlds and probes are isolated from the live save. An autouse
pytest fixture now also isolates tests that omit a save path, so running the
suite cannot silently replace a local game.

## Remaining boundaries

- Device coverage is **Chromium viewport and shortened-viewport keyboard
  emulation**, not a physical iOS Safari/Android hardware test or full screen
  reader audit. Keyboard viewport behavior varies by browser.
- Game code is still single-player/shared-world on Render, with one server
  process. No external deployment or public multiplayer scalability claim.
- Dialogue is offline composition, not free-form human-level reasoning. Unknown
  questions can receive a clarification prompt. Repeated fragments remain.
- Canvas actors deliberately lag authority by ~800 ms for smooth playback.
  This means very close-range interactions can use a position slightly ahead
  of the picture; range validation is still server-authoritative.
- Optional remote phrasing remains optional and disabled in the Render Blueprint.
