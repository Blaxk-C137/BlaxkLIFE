# BlaxkVille 0.4 — space, phones and connections

## What changed

### 1. Residents no longer compete to be on camera

The renderer culls residents outside the camera viewport (with a small approach
margin) or beyond 580 world pixels from the player. Residents fade in between
580 and 480 pixels, well before talking distance. Hidden residents are not
clickable and do not appear in the nearby interaction rail. Phone contacts and
profiles still exist. No schedule targets depend on the camera or chase the
player. This is presentation despawning, not deleting a person or resetting
relationships every time the player turns around.

Outdoor life is autonomous across the whole cast, not an 18-person spotlight
lottery. Residents make short local trips with individual pauses and routes.
Work movements are smaller and less frequent. Home downtime is indoors. Goals
reserve personal space; 5px movement substeps check body clearance, and blocked
walkers yield/pass consistently instead of a random repulsion force. Failed
trips retry; three game-minutes without route progress trigger a body-aware
detour rather than counting sideways wall orbits as useful movement. Home
entrances clear the walls, including top entrances on the bottom boundary. Thin
edge walkways connect with physical bridge legs, not teleports. Conversing pauses a commuter without
clearing their trip and accidentally making them vanish.

A precise-goal route-cache key also prevents two destinations in the same
30px navigation cell from borrowing the same endpoint. A regression reproduces
the old 8px endpoint mix-up and verifies distinct arrivals.

Static building collision uses a broadphase index plus the original exact
circle/rectangle test. Buildings, scenery and the 1900 × 1300 city are unchanged.

### 2. Sleeping happens inside

Residents walk home, disappear when reaching the doorstep area, and remain
hidden during sleeping and ordinary home routines. Sleeping residents are not
rendered as standing people. They become visible again when leaving home for
the next outing. Shared homes do not require shared outdoor standing spots.
Messages and eligible calls can still reach an awake resident indoors; nearby
in-person actions cannot. Texting a sleeper queues a reply for later.

No reset of the player's save is needed. A backup of the original local save
was retained before starting the 0.4 preview. The live server advances that
same saved world normally. An empty nighttime street is intentional: use the
existing Sleep activity at night to advance toward morning.

### 3. Gemini dialogue, optional and server-side

Configure in Render's Environment tab or export in the server's shell:

```text
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash
BLXVERSE_LLM_DISABLED=0
```

Restart after changing environment variables. `GOOGLE_API_KEY` is accepted as
an alias. `.env` files are not automatically loaded. The existing
`BLXVERSE_LLM_API_KEY` and OpenAI-compatible base/model settings still work when
no Gemini key is present. Gemini is preferred when both provider keys are set.
An old Render Blueprint might still have the disable flag set to `1`: change it.

- Native Gemini `generateContent`, API key in an HTTP header, never in client JS.
- Detached character/memory/relationship context, with adult/PG-13 boundaries.
- In-person chat and call text generation executes outside the world lock.
- Queued texts use a bounded two-worker pool, leaving simulation ticks free.
- Six-second request timeout, local fallback on absent keys, errors or blocked output.
- The model only phrases dialogue; it cannot move money, create dates or change
  consent. Forced outcome lines are not remotely rewritten.
- Typed in-person flirting and date requests share quick-button eligibility.
  Rejected requests do not award romance. Dates are booked through in-person
  interaction; a call's date request directs the player to talk in person.
- Call speech is browser recognition/synthesis with captions, not Gemini Live audio.

When enabled, dialogue text and fictional character context go to the configured
provider. Check its privacy policies, quotas and billing. Provider spend is not
measured in-game. No live Gemini key was available for this build: native
payloads, error paths and mocked remote delivery were tested, not a paid live call.

### 4. A Samsung One UI-inspired phone

A light Messages interface with a punch-hole status bar, large title, rounded
conversation rows, blue outgoing bubbles, grey incoming bubbles, floating send
button and bottom gesture bar. Seven app tabs include Messages, Gist Hub,
Calendar, Wallet, Cases, Alerts and Connections. The composer is responsive to
a short keyboard viewport. Draft restoration, in-place polling updates and
single-send protection are retained. This is an original in-game interface,
not an official Samsung product or an Android emulator.

### 5. Subtle background music

An original procedural sine-pad/melody score plays quietly after the first
pointer/keyboard gesture, subject to browser autoplay rules. The ♫ header button
mutes/unmutes and remembers the choice. Music fades down during speech/calls and
when the tab is hidden. It requires no external asset, API or GPU.

### 6. More residents and names

The full cast is now 72 adults, adding 12 women to the previous 60-person town.
Older saves are extended in place; existing IDs, genders, homes, memories,
wallets, player progress and saved relationships are preserved. Names are
migrated idempotently while Zara, Daniel and Femi remain story anchors.

Featured men include Zayyan, Bashir and Dominion alongside the earlier requested
names. Featured women include Fati, Jenny, Omonu, Elvina, Zainab, Amina, Chiamaka,
Zuri, Ene, Adaeze, Amara, Aisha, Halima, Ifeoma, Sade, Imani, Naomi, Layla, Nadia,
Nkechi, Maya, Bisi, Lola, Yara, Khadija, Rahma, Nneka, Uchechi, Chinaza, Tomi,
Damilola, Hauwa, Maryam, Simi, Teni and Bisola. Procedural traits, hobbies,
boundaries, schedules and voices still distinguish people beyond their names.

### 7. Practising conversation and relationships

The Connections phone app gives a short progression guide: break the ice, build
trust, find mutual interest and make a real plan. Milestones read actual
relationship state, including completed dates. In-person conversations return a
short note about listening, genuine follow-ups, sincerity, mutual interest or
respecting rejection. Work, gifts, social activities, calendar dates and
relationship progression remain playable. These are fictional practice
situations, not a guarantee of real-world dating outcomes or a way to purchase
affection. All romance is between adults.

## Verification evidence

- `docs/population-audit.json`: five scenarios, each sampled at 120 quarter-minute
  ticks over 30 game minutes. Settled weekday: **71 of 71 eligible outdoor
  residents moved >8px**, including **54 non-spotlight residents**. Across all
  scenarios: **zero sampled outdoor pairs under 22px**, **zero blocked position
  samples**. Night: all **72 indoors**. A copied real save was audited without modifying its source; its current
  daytime/evening state is recorded in the JSON report.
- `docs/live-preview-0.4.json`: the actual resumed Ada save at Thu 11:11
  exposed at most **19 actors** from 72 residents; **13 visible residents moved**
  within a four-second browser sample, with no page errors.
- `docs/ui-regression.json`: Chromium at widths **320, 360, 390, 768, 1024, 1440**;
  seven phone tabs, short keyboard viewport, draft/focus continuity, failed-send
  retention, actual incoming text, feed posting/commenting, five-second notices,
  music gesture unlock and mute/unmute. No physical-device certification.
- `docs/dialogue-network-check.json`: deliberately slow local mock provider
  delivered chat/call/text replies while state polls and the game clock stayed
  responsive. **Not a live Gemini API test.**
- `docs/dialogue-audit.json`: **86,400 actual samples**, **1,200 distinct greetings
  per each of 72 residents**. **1,152,000 nominal composition slots**, not a million
  independently authored stories.
- `docs/render-check-0.4.json`: local CPU, 72-resident/4× polling, auth, PORT bind,
  SIGTERM, persistent-directory restart and save export checks. This is a local
  sandbox measurement, not a deployment or benchmark on Render hardware.
- Unit/API regressions cover autonomous non-spotlight life, home entry/wake,
  legacy cast extension, collision broadphase, culling, Gemini requests/errors,
  asynchronous texting, paused conversations, indoor calls/texts and consent.

## Remaining limits

The world is one shared, server-authoritative single-player save. It is not a
multi-account service. Render persistence still needs the mounted paid disk.
No actual Render deployment, physical mobile-device audit or full accessibility
audit was performed. Network speech latency depends on provider and browser;
local dialogue remains the reliable fallback. Path playback retains its 800ms
jitter buffer, and narrow passage queues can still produce natural waits.
