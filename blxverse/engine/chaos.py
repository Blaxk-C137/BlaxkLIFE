"""Cartoon chaos engine.

Non-graphic, exaggerated slapstick: spinning dust clouds, wobbling props,
comedic sound cues, stars and pratfalls. Nobody is hurt. Consequences are
social: gossip, apologies, reputations, temporary security bans.

Hard rule (design section 3): chaos is caused by *actions and disputes*, never
by identity. There is no mob mechanic and no identity-based punishment.
"""

from __future__ import annotations

from blxverse import config
from blxverse.engine.models import NPC
from blxverse.engine.rng import RngHub, clamp

SCENE_PROPS = [
    "a spinning dust cloud", "an upturned fruit crate", "a runaway shopping trolley",
    "a suspiciously bouncy awning", "three angry pigeons", "a wobbly sandwich board",
    "a lone squeaky shoe", "a cartwheel of loose receipts",
]

SOUND_CUES = ["BOING", "WHOOMP", "PLINK", "THWAP", "RATTLE", "SPROING", "DOINK"]

WIN_LINES = [
    "{winner} ends up balanced on one foot, arms out, victorious.",
    "{winner} sticks the landing on a nearby bench. The bench is surprised.",
    "{winner} dismounts from the dust cloud with a stray leaf on their head, undefeated.",
]

LOSE_LINES = [
    "{loser} emerges from the dust cloud wearing a lampshade.",
    "{loser} tumbles out, sits down hard on the pavement, and points accusingly at the air.",
    "{loser} spins twice and lands in a flowerbed, blinking at the sky.",
]

BYSTANDER_REACTIONS = {
    "calm": "tries to talk both of them down",
    "kind": "steps between them and offers tea instead",
    "gossipy": "narrates the whole thing to a nearby phone camera",
    "anxious": "hides behind a menu and quietly panics",
    "bold": "cheers for whoever has better footwork",
    "playful": "starts a chant that nobody else joins",
    "grumpy": "shouts 'not in front of the fountain!' and walks away",
    "practical": "checks the property damage and starts a repair list",
}

SECURITY_NOTICES = [
    "Neighborhood security responded to a public disturbance at {loc}. No injuries. A banner reading 'please remember to hydrate' was deployed.",
    "Security broke up a cartoon dust cloud at {loc}. Two residents received a short cooling-off notice.",
    "A loud dispute at {loc} has been logged. The fountain is fine. The fruit crate did not make it.",
]

APOLOGY_PROMPTS = [
    "I said things I shouldn't have. The pigeons were a bad touch. I'm sorry.",
    "I let it get loud and that's on me. I'm sorry for the scene.",
    "I stand by the point but not the dust cloud. Sorry, genuinely.",
]


def trigger_clash(sim, a: NPC, b: NPC, *, cause: str, loc_label: str, player_involved: bool = False) -> dict:
    """Run a full slapstick scene between two NPCs, applying consequences."""
    hub: RngHub = sim.hub
    rng = hub.fork(f"chaos:{a.id}:{b.id}")
    loc = a.location_id if a.location_id == b.location_id else "square"

    a_power = a.energy * 0.4 + a.stats.get("risk", 0.5) * 30 + a.stats.get("energy", 0.5) * 10
    b_power = b.energy * 0.4 + b.stats.get("risk", 0.5) * 30 + b.stats.get("energy", 0.5) * 10
    a_power += rng.uniform(-12, 12)
    b_power += rng.uniform(-12, 12)
    winner, loser = (a, b) if a_power >= b_power else (b, a)

    prop = SCENE_PROPS[rng.randrange(len(SCENE_PROPS))]
    cue = SOUND_CUES[rng.randrange(len(SOUND_CUES))]
    win_line = WIN_LINES[rng.randrange(len(WIN_LINES))].format(winner=winner.first)
    lose_line = LOSE_LINES[rng.randrange(len(LOSE_LINES))].format(loser=loser.first)

    witnesses = [
        n for n in sim.npcs
        if n.id not in (a.id, b.id) and n.location_id == loc and n.status != "sleeping"
    ][: config.MAX_BYSTANDERS]

    reactions = []
    for w in witnesses:
        key = w.archetype if w.archetype in BYSTANDER_REACTIONS else "calm"
        reactions.append({"npc": w.id, "name": w.first, "reaction": BYSTANDER_REACTIONS.get(
            key, "watches, wide-eyed")})
        w.mood.excitement = clamp(w.mood.excitement + 18, 0, 100)

    event = sim.add_event(
        kind="slapstick", actor=a.id, targets=[b.id], location=loc,
        facts={
            "cause": cause, "prop": prop, "sound": cue, "winner": winner.id,
            "loser": loser.id, "witnesses": [w.id for w in witnesses],
            "reactions": reactions, "non_graphic": True, "player_involved": player_involved,
            "caption": f"{cue}! {win_line} {lose_line}",
        },
        witnesses=[w.id for w in witnesses], visibility="public",
        summary=f"{a.first} and {b.first} set off a cartoon dust cloud at {loc_label}.",
    )

    # relationship consequences
    sim.adjust_rel(a.id, b.id, affinity=-8, tension=-18, conflicts=1)
    sim.adjust_rel(b.id, a.id, affinity=-9, tension=-14, conflicts=1)
    sim.adjust_rel("player", a.id, familiarity=2)
    sim.adjust_rel("player", b.id, familiarity=2)

    for w in witnesses:
        sim.remember(w, event, importance=0.6, valence=-0.2, source="witnessed")
    sim.remember(a, event, importance=0.8, valence=-0.5, source="participated")
    sim.remember(b, event, importance=0.8, valence=-0.4, source="participated")

    # security + notice + temporary cooling-off ban
    banned_until = sim.minute + config.SECURITY_BAN_HOURS * 60
    for n in (a, b):
        n.flags["banned_until"] = banned_until
        n.flags["banned_from"] = loc
        n.mood.stress = clamp(n.mood.stress + 22, 0, 100)
        n.mood.irritation = clamp(n.mood.irritation + 8, 0, 100)
        n.energy = clamp(n.energy - 10, 5, 100)
    sim.set_rel_flag(a.id, b.id, "rival", True)
    sim.set_rel_flag(b.id, a.id, "rival", True)

    sim.add_notice(
        kind="alert", title="Public disturbance",
        body=SECURITY_NOTICES[rng.randrange(len(SECURITY_NOTICES))].format(loc=loc_label),
        location=loc,
    )
    sim.push_feed(
        author_id=witnesses[0].id if witnesses else a.id,
        text=f"Okay so at {loc_label}: {cue}. {win_line} {lose_line} The {prop} will be missed. 😭",
        mood="shocked", tag="chaos", loc=loc,
    )
    if witnesses:
        sim.push_feed(
            author_id=witnesses[-1].id,
            text=f"I have never seen {a.first} move that fast. The {prop} did nothing wrong.",
            mood="amused", tag="chaos", loc=loc,
        )
    sim.record_rivalry(a.id, b.id, cause=cause, tension=max(
        sim.rel(a.id, b.id).get("tension", 0), sim.rel(b.id, a.id).get("tension", 0)
    ))
    sim.log_metric("chaos_scene", {"a": a.id, "b": b.id, "loc": loc})
    return event


def maybe_escalate(sim) -> dict | None:
    """Check rival pairs sharing a location; escalate when tension is high."""
    if sim.minute - sim.world_flags.get("chaos_last_minute", -9999) < config.CHAOS_COOLDOWN_MINUTES:
        return None
    by_loc: dict[str, list[NPC]] = {}
    for n in sim.npcs:
        if n.status == "sleeping" or n.location_id == "home":
            continue
        if n.flags.get("banned_until", 0) > sim.minute:
            continue
        by_loc.setdefault(n.location_id, []).append(n)
    def pair_on_cooldown(a_id: str, b_id: str) -> bool:
        rv = next((r for r in sim.rivalries if {r.a, r.b} == {a_id, b_id}), None)
        if not rv:
            return False
        return rv.clashes >= 2 or sim.minute - rv.last_minute < 2 * 1440

    candidates = []
    for loc, crew in by_loc.items():
        for i, a in enumerate(crew):
            for b in crew[i + 1:]:
                if pair_on_cooldown(a.id, b.id):
                    continue
                r = sim.rel(a.id, b.id)
                if r.get("tension", 0) >= max(config.CHAOS_TENSION_THRESHOLD, 66.0):
                    candidates.append((r.get("tension", 0), a, b, loc))
    if not candidates:
        return None
    candidates.sort(key=lambda c: -c[0])
    tension, a, b, loc = candidates[0]
    rng = sim.hub.stream("chaos-gate")
    if rng.random() > 0.35:
        return None
    cause = sim.rel(a.id, b.id).get("cause") or sim.rel(b.id, a.id).get("cause") or "an argument that got out of hand"
    loc_label = sim.location_names.get(loc, "the neighborhood")
    event = trigger_clash(sim, a, b, cause=cause, loc_label=loc_label)
    sim.world_flags["chaos_last_minute"] = sim.minute
    return event


def schedule_reconciliation(sim, a_id: str, b_id: str) -> None:
    """Queue a reconciliation attempt after a cooldown (used by the director)."""
    due = sim.minute + 2 * 24 * 60
    for npc_id in (a_id, b_id):
        npc = sim.npc(npc_id)
        if npc:
            npc.plans.append({
                "id": f"reconcile_{npc_id}_{int(due)}", "kind": "reconcile",
                "title": f"clear the air with {'the neighbor' if npc_id == a_id else 'the neighbor'}",
                "due": due, "done": False, "with": b_id if npc_id == a_id else a_id,
            })
