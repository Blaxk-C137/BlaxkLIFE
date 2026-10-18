# BlaxkVille 0.6 — conversations that carry over

## What was wrong

Version 0.5 had three disconnected paths. In-person conversations retained only six exchanges. Calls did not add their actual player/NPC turns to that history. Text threads existed, but their content was not added to the shared conversation context. Gemini usually received a generic last world-event summary instead of the things you had actually said. Casual invitations were dialogue classifications, not movement commitments.

## Shared memory

Each resident now has one persistent, private-to-that-resident conversation ledger across **texts, calls and in-person conversations**:

- Up to **80 exchanges** in a rolling transcript, including the actual player words, the resident reply, channel and game time.
- Up to **32 explicit player disclosures** retained beyond that rolling window. These are quoted statements, not invented AI biographies. Questions are not saved as personal facts.
- Retrieval selects relevant older turns, recent exchanges and relevant disclosures for the next Gemini request. The model is told that quoted memory is untrusted dialogue, not instructions; game outcomes remain server-authoritative.
- Calls now receive a stable turn ID, so the actual successful Gemini reply replaces the local placeholder in memory, just as it does in person.
- Text receipt and eventual reply update the same exchange, rather than losing both into a disconnected message thread. Outbound ordinary NPC texts are recorded too. Pending replies are processed in order per resident.
- Retained legacy text threads and existing in-person exchanges migrate lazily on the next interaction. Old call words that version 0.5 never stored **cannot be reconstructed retroactively**.
- Memory survives normal save/restart. It is bounded, not a promise of an infinite or perfect transcript.
- Opening an in-person panel displays the last shared exchanges, labelled by channel. This is actual retained history, not a fabricated recap.

Offline dialogue can also retrieve statements when asked to remember something. It quotes the actual disclosure and does not claim a shared memory when none is available. Different residents do not receive one another's private conversation ledger.

## Nigerian conversation style

Gemini's character prompt now explicitly requests contemporary **Nigerian English**, natural code-switching and light Pidgin when it fits the character and player's register. Texts should feel like concise WhatsApp messages, with occasional fitting emojis; calls and in-person speech use spoken language rather than text abbreviations.

The prompt asks for specificity, opinions, playful teasing where welcome, and continuity rather than generic reassurance. It discourages piling slang into every sentence, identical voices, name/gender-based dialect assumptions, repeated introductions, canned follow-up questions and invented memories. Offline support includes familiar Nigerian greetings and grounded responses for selected everyday topics. It remains a bounded composer, not a local general-purpose language model.

No key or billing settings changed. Existing `GEMINI_API_KEY` / `GOOGLE_API_KEY` environment configuration continues to work. The workspace's provider checks use mocks; a live Google project is not certified here.

## Real casual meetups

Supported examples, through any of the three channels:

- **“Abeg wait for me at the park.”**
- **“Meet me at the cafe in 20 minutes.”**
- **“Let's meet at the square at 6pm.”**
- **“Wait for me at the park for 10 minutes.”**
- **“Cancel our meeting.”**

A clear request is validated against familiarity/tension, social energy, work/rest commitments, venue hours, and a reachable route. Acceptance is an authoritative local outcome, not something Gemini can invent. The response confirms the venue, **game day/time** and wait duration.

The resident starts travelling up to 60 game minutes before the agreed time, walks on the existing collision-aware navigation system, and waits once physically there. A later meeting does not freeze the resident all day beforehand. Arrival and departure generate texts. A normal conversation at the waiting spot marks the meetup as fulfilled. Cancellation, timeout or hospital admission releases the commitment; director staging cannot teleport a travelling/waiting resident away. Death still removes that resident permanently.

The default wait is **90 game minutes** after arrival or the agreed due time, whichever is later. Explicit waits are bounded to 5–120 game minutes. Requests can be scheduled within the next day. Ambiguous places/times ask a clarifying question rather than silently pretending to comply. A resident can decline. Long travel can make arrival late; this is a real walking trip, not teleportation or a guaranteed arrival-time solver.

This is a casual meetup system, **not** a way to bypass romantic consent, date costs, or other game rules. It does not implement arbitrary natural-language errands or item transfers.

## Conversation-first UI

- **Talking:** a height-constrained panel with a dedicated scrolling transcript. Input and Send stay visible. Quick replies are collapsed by default; effects/coaching use one compact status line rather than filling the transcript after every turn. Pending sends are guarded; failed typed sends restore the draft. An old call to a nonexistent `refreshStateSoon` method was removed: it could report failure even after a successful reply and make an already-sent draft reappear. Footer buttons now have real space on narrow screens.
- **Texting:** reduced header clutter and a shrinkable transcript. Sending your own message scrolls to it even if you were reading older messages. Incoming polling still preserves drafts/focus and does not yank you out of older history unnecessarily.
- **Calls:** the oversized central portrait is replaced by a compact layout; the typed composer is visible by default. Captions have their own flexible space, explicit speaker labels and up to 60 visible turns. Composer, captions and call controls have separate layout rows instead of overlapping absolute positions. Interim speech captions update one provisional line; confirmed turns replace it. Overlapping voice turns are queued in order (up to five), and typed sends are guarded while a reply is pending. Short keyboard-height views hide decorative elements first.
- Existing visual-viewport height handling is shared by the call screen, so reduced keyboard space also constrains that layout.

## Preservation and deployment

The original Ada save is retained with a local `world.json.before-0.6` backup. No cast replacement or world reset. Keep the same persistent disk when redeploying. Upload the updated release files and restart/redeploy your existing server; **keep your server-side API variables**. Refresh the browser after deployment so the new JavaScript/CSS loads.

**Verification:** 144 Python tests passed (948.12 seconds); conversation/browser, phone regression, mocked-network, population and CPU/persistence checks passed. The local 4× probe measured 12.66% of one core, 32.83 MiB peak RSS and 60.17ms p95 state latency. See `release-check-0.6.json` for the final inventory. `conversation-browser-check-0.6.json` exercises long real threads, cross-channel recall and layout at six viewport sizes including a 390×440 reduced-height keyboard simulation. These are isolated synthetic browser fixtures, not edits to the original world. Emulation is not physical-device certification. CPU/persistence results are local sandbox measurements, not a Render hardware benchmark.
