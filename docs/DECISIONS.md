# Architecture decisions

Short records of the choices that shaped the build, with the reasoning and the
trade-offs. Format is lightweight ADR: context → decision → consequences.

---

## ADR-0001 — Hybrid deterministic simulation, LLM optional and non-authoritative

**Context.** The brief asks for both low-latency reliability and rich character
dialogue. Making a remote model the source of truth would make money,
relationships and schedules non-deterministic, slow and expensive.

**Decision.** The Python simulation owns all state. A deterministic composer
answers every line by default from archetype, mood, memory and intent. An
optional LLM may only *rephrase* a foreground line; if it is slow, missing or
malformed, the composer's line stands. LLM output can never mutate state.

**Consequences.**
- Tests and saves are reproducible from a seed.
- The game runs offline with zero API cost.
- Dialogue is coherent but less open-ended until a provider is enabled; the
  grounded-question layer narrows that gap for factual questions.
- Per-turn cost and latency are measurable (`/api/stats`, `/api/voice/metric`).

---

## ADR-0002 — Standard library + vanilla browser client, no build step

**Context.** The deliverable has to run anywhere the reviewer opens it, with no
package installs, and the preview iframe has no network access.

**Decision.** Python `http.server`-style server, `json` saves, and a
dependency-free ES-module front end. All art is canvas/SVG drawn in code.

**Consequences.**
- One command to run; no bundler, no lockfile drift.
- Works inside sandboxed iframes and offline (no external assets).
- We hand-roll things a framework would give us (router, state diffing), which
  is acceptable at this size (~14k lines total).

---

## ADR-0003 — Client predicts movement, server remains authoritative

**Context.** Round-tripping every step feels laggy; trusting the client lets a
player walk through walls.

**Decision.** The client animates toward a clicked point at the server's walk
speed. The server validates the destination, computes an A* path around
buildings, and streams the authoritative position on each poll. Large
divergence snaps the client back.

**Consequences.**
- Movement feels instant on any latency.
- Players cannot teleport or clip: the server never accepts a position, only a
  destination.
- Pathfinding cost is amortized with a 30 px grid, LOS smoothing and a
  per-NPC replan throttle (crucial: naive per-frame replanning made a 5-day
  simulation take minutes).

---

## ADR-0004 — Memory, belief and fact are three different things

**Context.** "Who said what, and do they believe it?" is the core of the rumor
storyline. A single `known_facts` set would make gossip impossible and let the
truth leak instantly.

**Decision.** Events are objective records. Memories are an NPC's private,
fallible recollection with importance and valence. Beliefs are claims with
confidence, a source and a truth flag, and they decay. Evidence resolution flips
beliefs rather than editing memories.

**Consequences.**
- The same event can be remembered differently by different residents.
- Rumor mechanics (spread, challenge, confidence decay) fall out naturally.
- Two NPCs can be wrong in different ways, which is where the drama lives.

---

## ADR-0005 — Economy is server-authoritative with an append-only ledger

**Context.** A closed-loop currency is only trustworthy if every change is
traceable and un-fakeable.

**Decision.** All money moves through `economy.authorize_spend` / `credit`,
which validate amount, category and balance, then append a ledger row and an
audit line. Handlers never touch `wallet` directly; the action layer maps
`EconomyError` to `SimError` so clients get clean 4xx codes.

**Consequences.**
- No client-supplied amounts; replaying requests cannot mint money.
- The wallet tab is a true audit trail.
- Categories are a closed set, which caught two real bugs during the build
  (`shop` and `dating` were invalid categories) instead of corrupting history.

---

## ADR-0006 — Chaos is slapstick, never identity-based

**Context.** The brief explicitly forbids mob attacks on identity groups and
wants cartoon comedy.

**Decision.** Conflict is triggered only by accumulated interpersonal tension
between two specific residents, is capped by cooldowns, produces a dust-cloud
scene and a venue ban, and is described in cartoon language. No crowd ever
targets an individual, and there is no mechanic that groups people by identity.

**Consequences.**
- Comedy without cruelty; the worst outcome is a public apology or a ban.
- Tension must be built by the player (or the chain) before anything happens.
- Easy to audit: `chaos.py` contains the only conflict trigger.

---

## ADR-0007 — Deterministic named random streams

**Context.** Python's `hash()` is salted per process, and one shared RNG makes
one change reshuffle the entire world.

**Decision.** Every random decision draws from a named stream
(`RngHub.stream("weather")`, `"compose:<npc>"`, `"rumor:<id>"`, …) seeded by
`stable_hash(seed, name)`. `hash()` is banned.

**Consequences.**
- Same seed → same world, across machines and restarts.
- Changing one subsystem does not invalidate unrelated test fixtures.
- Tests can assert exact outcomes where it matters and ranges elsewhere.

---

## ADR-0008 — Voice in the browser, transcripts only on the wire

**Context.** Privacy rules in the brief: no stored audio, no voice cloning,
explicit consent.

**Decision.** Speech recognition and synthesis run in the browser. The server
receives only text and client-measured latency samples. A consent dialog
explains exactly what leaves the device, and typed input is always available.

**Consequences.**
- No audio ever reaches the server or disk.
- Feature availability depends on the browser's speech APIs; the UI degrades to
  typing, and says so.
- Latency is measured client-side, which is the number that matters to players.

---

## ADR-0009 — Story chains are scripted skeletons with simulated flesh

**Context.** The brief's Mon–Fri example is specific, but the world must feel
alive and must not break if the player ignores it.

**Decision.** The chain advances on day/hour gates with authored beats; every
beat injects real state (rumors, beliefs, a case, relationship changes, feed
posts) that the simulation then propagates on its own. If the player does
nothing, a witness comes forward on day 5.

**Consequences.**
- The story is legible and reviewable, not a random walk.
- It still resolves without the player, so the world never stalls.
- Player intervention changes the ending (cleared case → apology; ignored →
  clash), which is the point.

---

## ADR-0010 — One save file, atomic, versioned, with rotation

**Context.** Local single-player game; data loss is unacceptable; formats will
change.

**Decision.** Save to `world.json.tmp`, rotate the previous file to `.bak`,
then atomically replace. A new game rotates the old save to
`world.json.prev-<timestamp>` rather than deleting it. `SCHEMA_VERSION` guards
loads and refuses mismatches with a clear error.

**Consequences.**
- Crash-safe writes; a corrupt file can't take the save with it.
- Starting over is reversible.
- Old saves fail loudly instead of silently mis-loading.

---

## ADR-0011 — The client never plans movement; it follows the server's route

**Context.** Clicking to walk produced front/back jitter and sprites crossing
buildings. The client interpolated straight to the clicked point while the
server walked an A* detour; every poll then snapped the sprite back onto the
authoritative path — and the straight line itself was the thing cutting through
building footprints.

**Decision.** The server owns the route. `move` and `/api/state` return
`route[]` (remaining waypoints) and `dest`; the client walks those waypoints at
the server's speed (230 px/s). The client only *settles* — it ignores a lagging
poll while it still has route left, and glides to a server position only after
two identical reports confirm the body has actually stopped.

**Consequences.**
- No snapping, because the sprite is never ahead of or beside the route.
- Buildings can only be entered if the pathfinder allows it.
- The client's animation speed must match the server's; a mismatch shows up as
  a slow drift, so the constant lives in one place (`PLAYER_MAX_SPEED`).

---

## ADR-0012 — One weekly calendar, generated, not authored per save

**Context.** "Coming up" only showed dates the player had already accepted, so
the neighborhood had no future in it.

**Decision.** `content/events.py` declares eight recurring fixtures on a
weekday/clock grid and derives a stable birthday slot per resident from
`stable_hash`. Occurrences are computed from the absolute game minute, never
stored, so the calendar survives save/load, rewinds and new games without
migration.

**Consequences.**
- No schema change and no per-save drift.
- Residents can be pulled into a live fixture with a deterministic rule
  (hobby overlap + `stable_hash` turnout), which makes venues visibly fill up.
- Adding a fixture is a data edit, not a migration.

---

## ADR-0013 — Gifts are scored, not scripted

**Context.** Gifting "didn't work": `act_gift` looked items up in the catalog
table, so every cafe consumable was rejected as unknown. Reactions were also
close to binary.

**Decision.** Any item reachable through `buyable()` can be gifted. The
reaction is a score built from hobby overlap, favourite food, price (a real
spend matters), a small penalty for generic food, and a repetition decay keyed
on the item id. The reply quotes the reasons it landed the way it did.

**Consequences.**
- Every purchasable item is valid, and the UI cannot offer an un-giftable one.
- Players can read why a gift worked, which makes the next choice informed.
- Balance lives in one function (`compose_gift_reaction`) with thresholds
  documented in the payload.


---

## ADR-0014 — CPU-only Render hosting keeps one authoritative process

**Context.** The game needs to run on Render CPU instances. The server already
uses the Python standard library and the browser draws the world; there is no
local neural model or GPU dependency. However, it did not read `PORT`, and local
save paths would be ephemeral on a hosted service.

**Decision.** Ship a native Python Blueprint, one Starter instance, and a disk
mounted at `/var/data`; store both save and audit data beneath it. Use a single
bounded-thread server, not multiple worker processes. Add a generated shared
HTTP Basic password (health checks exempt), idle socket deadlines, and graceful
shutdown that drains handlers before the final save. Retain optional external
LLM phrasing but disable it by default in the hosting configuration.

**Consequences.**
- No GPU cost, dependency-heavy serving stack, frontend rewrite, or database is
  necessary for a private single-player deployment.
- Durable hosting has service + disk costs; free ephemeral demos are explicitly
  documented as nondurable.
- The hosted game still shares one world/player across authenticated visitors.
  Multi-account isolation, horizontal scaling, and adversarial public-internet
  load hardening are separate future work, not claimed by this patch.
- Local deployment tests prove environment and persistence contracts, not a
  completed external deployment or performance on a particular Render plan.


---

## ADR-0015 — Poll world state, never replace an active composer

**Context.** A full phone re-render on every poll destroyed native keyboard focus
and in-progress texts/posts. Saving a value and refocusing after replacement
would still flicker the software keyboard and disrupt selection/IME input.

**Decision.** Keep composer nodes mounted. Update message content separately;
make other phone refreshes deliberate. Store drafts for explicit tab changes,
retain them on errors, and discard async tab responses targeting detached nodes.
Use a visual-viewport-height layout and scroll only the message list.

**Consequences.** Incoming messages remain live without keyboard interruption.
Gist Hub gets an explicit refresh button, not silent background content churn.

---

## ADR-0016 — Buffered authoritative NPC routes, shared solid scenery

**Context.** Easing to a sparse snapshot made all NPCs lurch and stop together.
Static tree art also forced actors to be painted over foliage.

**Decision.** Publish NPC routes and individualized speeds. Play route segments
in a small client jitter buffer; extrapolate only briefly along known paths.
Publish shared scenery definitions with solid trunks/bush bases; draw only their
shadows in the ground layer and Y-sort the upright props with actors.

**Consequences.** Frame-continuous, obstacle-respecting movement and correct
occlusion, at the cost of ~800 ms NPC visual delay. The authoritative interaction
range and the 30 px navigation-grid caveat remain documented.

---

## ADR-0017 — A large offline character-voice deck, not a million-line file

**Context.** Repeated dialogue made residents feel interchangeable; synchronous
remote-model phrasing would add latency/cost and a network dependency.

**Decision.** Compose authored intent beats, style-specific openings, factual
personal asides and follow-ups with resident/intent-seeded decks and persistent
cursors. Named personas, hobbies, values and goals define the voice. Keep actual
questions grounded and consent/outcome lines outside generic variation.

**Consequences.** Over a million nominal slots per resident with no GPU, model
API, giant text download or runtime dependency. This is explicitly compositional
variation, not a million authored narratives. Audit sampled 1,200 distinct actual
greetings for EVERY resident; repeated fragments and limited reasoning remain.
