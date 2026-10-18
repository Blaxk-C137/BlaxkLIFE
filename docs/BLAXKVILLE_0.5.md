# BlaxkVille 0.5 — a living, consequential neighbourhood

## Playing the update

Continue the existing save; no reset is required. The **shield button** in the top bar opens the neighbourhood panel, incident reports and service destinations. Click a new building or use its **Walk here** button. Treatment, memorial interactions and business transactions require being near the entrance; remote incident reporting is allowed.

- **Street conversations:** nearby awake residents exchange short, staggered overhead lines about food, work, music and everyday life. They pause briefly, then resume their schedules. Friendly/respectful acquaintances sometimes greet the player when passing. Per-resident cooldowns and a global limit prevent a constant wall of greetings. These lightweight encounters are local, not Gemini requests.
- **In-person conversation:** opening Talk acquires a server-validated session. The other resident stays in place while the world clock and other residents continue. Closing the panel/Escape releases the session. Heartbeats expire abandoned sessions. Harassment, refusal or a nearby dangerous confrontation can end the conversation and make the resident leave; talking is not an invulnerability exploit.
- **Non-graphic conflict:** heated disputes, theft and armed four-person bandit squads have bounded, visible encounters. Squads approach on walkable routes in distinct formation slots; unreachable raids abort rather than remotely hurting civilians. Police patrol and respond, with soldier support against raids. No blood or graphic injury rendering.
- **Hospital:** wounded residents are admitted, listed in the recovery ward and return to their schedules after recovery. Players can request treatment at BlaxkVille General.
- **Permanent consequences:** any adult resident, including named/story actors, can die. Deceased residents do not respawn on load or cast migration. Active dates, calls, conversation sessions and future participation end. Surviving partners lose their active dating flag and retain a bereavement/history record. Existing messages and relationship history remain; Juniper Rest records the person's name, age, time and cause. Story chains involving a deceased actor close rather than silently replacing them.
- **Abstract illicit businesses:** the Backlot models fictional gun/drug ventures as a stake, income balance, police attention and possible seizure. Starting requires confirmation; stake loss is real in the save. This contains no sourcing, crafting, dosing, distribution or other real-world instructions.
- **Work shifts:** starting work immediately dims the screen and intercepts game input. The server advances the shift, applies its outcome and enforces a five-real-second finishing lock. Escape, movement and purchases cannot bypass the lock. Processing time can make the total dimmed interval longer than five seconds.

Conflict rules apply equally to everyone; identity is not a targeting criterion. There is no identity-targeted attack mechanic.

## Dialogue and Gemini

Default optional provider: **`gemini-3.5-flash-lite`**. Google describes it as its fastest, most cost-effective **3.5** model for high-throughput execution; this is not a claim that it wins every latency benchmark against every other model.

```text
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.5-flash-lite
BLXVERSE_LLM_DISABLED=0
```

Set these on the server and restart. `GOOGLE_API_KEY` is an accepted alias; `.env` files are not automatically read. Never put a key in the browser. Conversations include recent exchanges and character context, with concise natural phrasing. Gemini can phrase dialogue, not authorise money, gifts, dates, consent or deaths. Chats, texts and call turns remain playable with the character-specific offline composer. A talk bubble identifies a local reply versus a successful model response; configuration alone is not reported as a successful remote reply.

Requests use `thinkingLevel: minimal`, a short output cap, a six-second timeout, bounded workers and local caps of **8 requests/minute and 150/day** per key/model. Optional server overrides: `GEMINI_LOCAL_RPM`, `GEMINI_LOCAL_RPD`. These are process-local guardrails, not Google's account quotas or a billing guarantee; restarting clears them. HTTP 429/503 adds a local cooldown. Truncated, empty, failed or blocked output falls back locally. A small output cap can truncate thinking-model responses, so remote generation is not guaranteed on every turn.

Google's Standard pricing lists a free input/output tier for this model, subject to project eligibility, availability and quotas. Free-tier data may be used to improve Google's products; review its privacy/billing terms. This workspace has **no Google API key**: HTTP behaviour was verified against a mocked delayed provider, not a live paid/free Google project. Voice uses browser speech APIs, not Gemini Live audio.

Official references checked for this update:
- [Model catalogue](https://ai.google.dev/gemini-api/docs/models)
- [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
- [Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Thinking settings](https://ai.google.dev/gemini-api/docs/generate-content/thinking) — the table explicitly includes 3.5 Flash-Lite and supports `minimal` as its default.

## Preserved systems and migration

The original Ada save remains the live world on port **8111**. Its pre-update backup is retained locally as `data/saves/world.json.before-0.5`; private saves and credentials are not in the release archive. All **72 existing identities remain unchanged: 27 men, 42 women and 3 nonbinary adults**. The requested cast replacement was skipped, as instructed. Police/soldier/bandit presentation actors are additional encounter actors, not replacements in that resident roster.

The city remains **1900 × 1300**. Approach-based visibility, tree/bush occlusion, independent body-aware movement, indoor sleep, gifts, Samsung One UI-inspired texting, draft/focus stability, procedural muteable music and relationship/consent systems remain.

Two additional movement regressions were corrected during the saved-world audit:
1. A midnight story move can interrupt an already-current sleep block; an idle outdoor sleeper now replans the walk home rather than standing outside until morning.
2. Two clear navigation-grid centres can have a tree base between them. A* now validates each static connecting edge at physical body radius; bounded memoisation avoids repeatedly checking the same edge.

All five new facility entrances were checked at exact targets with 16px body clearance. Hospital/police footprints leave room for neighbouring entrances.

## Verification and evidence

Machine-readable final inventory: **`release-check-0.5.json`**. Evidence files:

| Area | Evidence |
|---|---|
| Full Python regression suite | **127 passed**, 0 failed, 699.62 seconds; final production source fingerprint and test names in release inventory |
| Movement and sleep | `population-audit.json`: fresh, settled, indoor night, next morning and an unreset copy of the original saved world; no collision/stack frames in the sampled windows |
| Responsive UI and phone | `ui-regression.json`: Chromium at 320, 360, 390, 768, 1024 and 1440px widths; phone tabs, draft/focus, notifications, music and actual walker trajectories |
| Conversation / civic UI / work | `civic-browser-check-0.5.json`: actual session lease/freeze/release, staged bubbles, populated ward/memorial, all five facilities, work dimming, server 423 and timed unlock |
| Interrupted-night reproduction | `interrupted-sleep-audit-0.5.json`: all 11 affected outdoor residents moved, all 72 ended indoors; zero sampled collisions/stack frames |
| Offline dialogue | `dialogue-audit.json`: 86,400 distinct sampled greetings, 1,200 per resident across all 72; composition slots are not individually authored stories |
| New destination routes | `civic-entrances-0.5.json` |
| Network isolation / fallback | `dialogue-network-check.json`: delayed mocked provider; world polling remains responsive |
| CPU / persistent saves | `render-check-0.5.json`: local Render-style PORT/auth/static/SIGTERM/same-disk restart probe at 72 residents and 4× |
| Cast preservation | `cast-preservation-0.5.json` |
| Original live preview | `live-preview-0.5.json` |

Screenshots are in the workspace's `screenshots/blaxkville-05-*.png`. Populated ward, death and overhead-bubble scenarios use an **isolated synthetic fixture**, never the original player's world. Autonomous chatter and injury/death mechanics are also exercised by Python tests. The browser fixture stages social encounters to make timing deterministic.

Latest local 4× probe: **15.86% of one CPU core**, **33.01 MiB peak RSS**, **141.83ms p95 state latency**, 120 requests across 30.07 seconds. CPU results are sandbox measurements, **not a Render hardware benchmark**. Browser viewport emulation is not physical-device certification. The game remains a single shared world, one process/instance, no GPU and no runtime external model download. A persistent disk is required on Render to preserve saves across deployments; the supplied Starter + disk Blueprint incurs hosting charges. See [deployment instructions](RENDER.md).
