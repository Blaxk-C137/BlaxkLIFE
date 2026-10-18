"""Player action layer.

Every action is validated, costed, applied to the simulation, and returned as a
JSON-safe payload for the HTTP layer. The server is authoritative: wallets,
relationship deltas, case outcomes and caller identity are never trusted from
the client.

Design rules enforced here:
- conversation requires proximity and an awake, reachable resident
- spending goes through the audited ledger (no negative balances)
- romance progress is consentful: interest, compatibility and rejection are real
- violence is never initiated by the player; tension can escalate into
  non-graphic cartoon chaos handled by the chaos engine
"""

from __future__ import annotations

import math
import time
from typing import Any

from blxverse import config
from blxverse.content.items import CONSUMABLES, buyable
from blxverse.content.locations import LOCATION_BY_ID
from blxverse.engine import civic, conversation, llm
from blxverse.engine.composer import (
    classify_intent,
    compose_gift_reaction,
    compose_reply,
)
from blxverse.engine.models import Message, Post, Thread, new_id
from blxverse.engine.rng import clamp
from blxverse.engine.sim import SimError, clock_label_for

# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------
HARASSMENT_PATTERNS = (
    "kill all", "kill every", "go back to your country", "should be deported",
    "don't belong here", "vermin", "subhuman",
)


def _player(sim):
    if sim.player is None:
        raise SimError("No resident is loaded.", "no_player")
    return sim.player


def _npc(sim, npc_id: Any):
    npc = sim.npc(str(npc_id or ""))
    if npc is None:
        raise SimError("That resident doesn't exist.", "not_found", 404)
    return npc


def _moderate(text: str) -> None:
    low = text.lower()
    if any(p in low for p in HARASSMENT_PATTERNS):
        raise SimError(
            "That message crosses a line — BLXVERSE is a kind-of-chaotic neighborhood, not a cruelty sandbox.",
            "harassment", 422,
        )


def _sanitize(text: Any, limit: int = config.MAX_CHAT_LENGTH) -> str:
    if text is None:
        raise SimError("Say something first.", "empty")
    s = "".join(ch for ch in str(text) if ch.isprintable() or ch in "\n\t")
    s = " ".join(s.split())
    if not s:
        raise SimError("Say something first.", "empty")
    if len(s) > limit:
        s = s[:limit].rstrip()
    _moderate(s)
    return s


def _dist_to_npc(sim, npc) -> float:
    p = _player(sim)
    return math.hypot(npc.x - p.x, npc.y - p.y)


def _require_near_npc(sim, npc, radius: float | None = None) -> None:
    if npc is None:
        raise SimError("That resident doesn't exist.", "not_found", 404)
    if npc.status == "sleeping":
        raise SimError(f"{npc.first} is asleep. Even this neighborhood has limits.", "asleep", 422)
    if sim._indoors(npc):
        raise SimError(f"{npc.first} is indoors at home. Try a text or a call instead.", "indoors", 422)
    if npc.flags.get("banned_from") and npc.location_id == "home":
        raise SimError(f"{npc.first} is lying low after some cartoon nonsense. Try later.", "unavailable", 422)
    if _dist_to_npc(sim, npc) > (radius or config.TALK_RADIUS + 25):
        raise SimError(f"You need to walk closer to {npc.first}.", "too_far", 422)


def _loc_rect_distance(sim, loc: dict) -> float:
    p = _player(sim)
    cx = min(max(p.x, loc["x"]), loc["x"] + loc["w"])
    cy = min(max(p.y, loc["y"]), loc["y"] + loc["h"])
    return math.hypot(p.x - cx, p.y - cy)


def _require_near_loc(sim, loc_id: str, pad: float = 110) -> dict:
    loc = LOCATION_BY_ID.get(loc_id)
    if loc is None:
        raise SimError("That place doesn't exist.", "bad_destination", 404)
    if _loc_rect_distance(sim, loc) > pad:
        raise SimError(f"Walk closer to {loc['name']} first.", "too_far", 422)
    return loc


def _is_open(sim, loc: dict) -> bool:
    start, end = loc["hours"]
    h = sim.hour_of_day
    if start <= end:
        return start <= h < end
    return h >= start or h < end


def _rel_payload(sim, npc_id: str) -> dict:
    r = sim.rel(npc_id, "player")
    from blxverse.engine.models import Relationship
    obj = Relationship.from_dict(r)
    return {
        "label": obj.label(), "familiarity": round(r.get("familiarity", 0), 1),
        "trust": round(r.get("trust", 0), 1), "affinity": round(r.get("affinity", 0), 1),
        "romance": round(r.get("romance", 0), 1), "tension": round(r.get("tension", 0), 1),
        "flags": list(r.get("flags", [])), "dates": int(r.get("dates", 0)),
    }


def _effect_lines(effects: dict, prefix: str = "") -> list[str]:
    out = []
    labels = {"familiarity": "familiarity", "affinity": "affinity", "trust": "trust",
              "romance": "romance", "tension": "tension"}
    for key, label in labels.items():
        val = float(effects.get(key, 0) or 0)
        if abs(val) < 0.05:
            continue
        out.append(f"{prefix}{label} {'+' if val > 0 else ''}{round(val, 1)}")
    return out


def _apply_effects(sim, npc, effects: dict, *, reverse: bool = True) -> None:
    sim.adjust_rel(npc.id, "player", familiarity=effects.get("familiarity", 0),
                   trust=effects.get("trust", 0), affinity=effects.get("affinity", 0),
                   romance=effects.get("romance", 0), tension=effects.get("tension", 0),
                   count_interaction=True)
    if reverse:
        sim.adjust_rel("player", npc.id, familiarity=effects.get("familiarity", 0),
                       trust=effects.get("trust", 0), affinity=effects.get("affinity", 0),
                       romance=effects.get("romance", 0), tension=effects.get("tension", 0))


def _record_talk(sim, npc, intent: str, summary: str, *, importance: float = 0.3,
                 valence: float = 0.2, kind: str = "talk") -> dict:
    ev = sim.add_event(kind=kind, actor="player", targets=[npc.id], location=npc.location_id,
                       facts={"intent": intent}, witnesses=[], visibility="participants",
                       summary=summary)
    sim.remember(npc, ev, importance=importance, valence=valence, source="participated")
    return ev


# ---------------------------------------------------------------------------
# movement
# ---------------------------------------------------------------------------
def act_move(sim, action: dict) -> dict:
    p = _player(sim)
    try:
        x = float(action.get("x", p.x))
        y = float(action.get("y", p.y))
    except (TypeError, ValueError):
        raise SimError("Bad destination coordinates.", "bad_request") from None
    x = clamp(x, 40, config.WORLD_WIDTH - 40)
    y = clamp(y, 60, config.WORLD_HEIGHT - 30)
    # The server walks you there at PLAYER_MAX_SPEED; the client only requests
    # a destination. Pathfinding is server-side so walls are never crossed.
    sim.set_player_destination(x, y)
    route = sim.player_route_payload()
    return {"ok": True, "x": round(p.x, 1), "y": round(p.y, 1),
            "target": route["dest"], "route": route["route"],
            "moving": sim._player_dest is not None}


def act_stop(sim, action: dict) -> dict:
    _player(sim)
    return {"ok": True, "text": "You stop and take in the block."}


def act_speed(sim, action: dict) -> dict:
    _player(sim)
    try:
        speed = int(action.get("speed", 1))
    except (TypeError, ValueError):
        raise SimError("Speed must be 0, 1, 2 or 4.", "bad_request") from None
    if speed not in config.ALLOWED_SPEEDS:
        raise SimError("Speed must be 0, 1, 2 or 4.", "bad_request")
    sim.speed = speed
    return {"ok": True, "speed": speed, "text": "Time is paused." if speed == 0 else f"Time speed set to {speed}×."}


# ---------------------------------------------------------------------------
# conversation
# ---------------------------------------------------------------------------
QUICK_TEXT = {
    "greet": "Hey — good to see you.",
    "smalltalk": "How's your day been?",
    "joke": "Okay, quick joke: why did the streetlight go to therapy?",
    "compliment": "You have great taste — I mean it.",
    "flirt": "I keep finding reasons to walk past here.",
    "ask_date": "Would you want to get dinner with me sometime?",
    "apology": "I'm sorry about how things went. I want to fix it.",
    "gossip": "So... what's the latest on the block?",
    "invite": "A few of us are heading out later. Come with?",
    "deep": "Can I ask you something real?",
    "goodbye": "Alright, I'll let you get back to it.",
    "insult": "That was a cheap shot, honestly.",
}

QUICK_LABELS = {
    "greet": "greeted", "smalltalk": "chatted with", "joke": "joked with",
    "compliment": "complimented", "flirt": "flirted with", "ask_date": "asked out",
    "apology": "apologized to", "gossip": "asked for gossip from",
    "invite": "invited", "deep": "had a real conversation with",
    "goodbye": "said goodbye to", "insult": "insulted",
}


def _date_eligible(sim, npc) -> tuple[bool, str]:
    rel = sim.rel(npc.id, "player")
    if rel.get("familiarity", 0) < config.DATE_MIN_FAMILIARITY:
        return False, "not_familiar"
    if rel.get("trust", 0) < config.DATE_MIN_TRUST:
        return False, "not_trusted"
    if rel.get("romance", 0) < config.DATE_MIN_ROMANCE:
        return False, "no_spark"
    if rel.get("tension", 0) >= config.DATE_MAX_TENSION:
        return False, "tense"
    if rel.get("flags") and "rival" in rel["flags"]:
        return False, "tense"
    if npc.mood.social_energy < 22:
        return False, "drained"
    for other_id, other in sim.outgoing_rels(npc.id):
        if other_id != "player" and other.get("flags") and "dating" in other["flags"]:
            return False, "taken"
    return True, ""


def _flirt_eligible(sim, npc) -> tuple[bool, str]:
    rel = sim.rel(npc.id, "player")
    if rel.get("familiarity", 0) < config.FLIRT_MIN_FAMILIARITY:
        return False, "not_familiar"
    if rel.get("trust", 0) < config.FLIRT_MIN_TRUST:
        return False, "not_trusted"
    if rel.get("tension", 0) >= 58:
        return False, "tense"
    if npc.mood.social_energy < 16:
        return False, "drained"
    return True, ""


def _line(obj) -> str:
    """LINES banks can contain plain strings; always resolve through line_pool."""
    if isinstance(obj, str):
        return obj
    return str(obj)


def act_talk(sim, action: dict) -> dict:
    p = _player(sim)
    npc = _npc(sim, action.get("npc_id"))
    _require_near_npc(sim, npc)
    text = _sanitize(action.get("text"))
    intent = classify_intent(text) or "smalltalk"
    if intent in ('ask_date', 'flirt', 'apology', 'invite', 'gossip'):
        return act_intent(sim, {'npc_id': npc.id, 'intent': intent, 'text': text})
    return _converse(sim, npc, text, intent, medium="talk", player=p)


def act_intent(sim, action: dict) -> dict:
    from blxverse.content.dialogue_content import line_pool

    p = _player(sim)
    npc = _npc(sim, action.get("npc_id"))
    _require_near_npc(sim, npc)
    intent = str(action.get("intent", "greet"))
    if intent not in QUICK_TEXT:
        raise SimError("Unknown conversation move.", "bad_request")
    text = _sanitize(action["text"]) if action.get("text") else QUICK_TEXT[intent]
    forced = None

    if intent == "ask_date":
        ok, why = _date_eligible(sim, npc)
        forced = list(line_pool("date_yes" if ok else "date_no", npc.archetype)) or [
            "Not right now." if not ok else "Yes — I'd like that."
        ]
        result = _converse(sim, npc, text, intent, medium="talk", player=p, forced=forced)
        result["accepted"] = ok
        if not ok:
            result["reason"] = {
                "not_familiar": "You need to know each other better first.",
                "not_trusted": "They don't trust you enough yet.",
                "no_spark": "There's no romantic spark yet — try flirting first.",
                "tense": "The tension between you two is too high for a date.",
                "drained": "They're socially exhausted right now.",
                "taken": "They're already seeing someone.",
            }.get(why, "Not right now.")
            return result
        venue = _pick_date_venue(sim, npc)
        due = sim.minute + config.DATE_LEAD_MINUTES
        offer = {
            "id": new_id("date"), "npc_id": npc.id, "npc_name": npc.name, "npc_first": npc.first,
            "venue": venue, "venue_name": sim.location_names.get(venue, venue),
            "due": round(due, 1), "expires": round(due + 240, 1), "created": round(sim.minute, 1),
            "status": "accepted", "cost": config.DATE_COSTS.get(venue, config.DATE_DEFAULT_COST),
        }
        sim.world_flags.setdefault("date_offers", []).append(offer)
        npc.plans.append({"id": new_id("plan"), "kind": "date", "with": "player",
                          "due": due, "venue": venue, "done": False})
        sim.note("Date confirmed", f"{npc.first} said yes. {sim.location_names.get(venue, venue)} at "
                                    f"{_clock_short(due)}.", kind="date")
        sim.set_rel_flag(npc.id, "player", "asked_out", True)
        result["date_offer"] = offer
        return result

    if intent == "flirt":
        ok, why = _flirt_eligible(sim, npc)
        forced = list(line_pool("flirt_yes" if ok else "flirt_no", npc.archetype)) or [
            "Not now." if not ok else "Oh. Hi."
        ]
        result = _converse(sim, npc, text, intent, medium="talk", player=p, forced=forced)
        result["accepted"] = ok
        if not ok:
            result["reason"] = {
                "not_familiar": "They barely know you.",
                "not_trusted": "Charm lands better with trust behind it.",
                "tense": "The mood isn't right for that.",
                "drained": "They don't have the energy for flirting.",
            }.get(why, "Not now.")
            sim.adjust_rel(npc.id, "player", tension=1.0, affinity=-1.5)
            sim.adjust_rel("player", npc.id, tension=1.0, affinity=-1.5)
        return result

    if intent == "apology":
        rel = sim.rel(npc.id, "player")
        ok = rel.get("tension", 0) >= 10 or int(rel.get("conflicts", 0)) > 0
        forced = list(line_pool("apology_yes" if ok else "apology_no", npc.archetype)) or [
            "Thanks — I appreciate that." if ok else "You don't need to apologize."
        ]
        result = _converse(sim, npc, text, intent, medium="talk", player=p, forced=forced)
        result["accepted"] = ok
        if ok:
            rel = sim.rel(npc.id, "player")
            sim.adjust_rel(npc.id, "player", tension=-6, trust=3, affinity=2)
            sim.adjust_rel("player", npc.id, tension=-6, trust=3, affinity=2)
            if rel.get("tension", 0) < 30 and "rival" in rel.get("flags", []):
                sim.set_rel_flag(npc.id, "player", "rival", False)
                sim.set_rel_flag("player", npc.id, "rival", False)
                sim.set_rel_flag(npc.id, "player", "reconciled", True)
                sim.note("Reconciled", f"{npc.first} accepted your apology. The air is clearer.", kind="story")
        return result

    if intent == "gossip":
        belief = next((b for b in npc.beliefs if b.confidence >= 0.4), None)
        hook = None
        if belief:
            from blxverse.content.dialogue_content import RUMOR_OPENERS
            hook = RUMOR_OPENERS[len(npc.beliefs) % len(RUMOR_OPENERS)].format(claim=belief.claim)
            p.flags.setdefault("known_rumors", [])
            if belief.rumor_id not in p.flags["known_rumors"]:
                p.flags["known_rumors"].append(belief.rumor_id)
        result = _converse(sim, npc, text, intent, medium="talk", player=p, forced=forced, context=hook)
        result["heard_rumor"] = bool(hook)
        return result

    result = _converse(sim, npc, text, intent, medium="talk", player=p)
    if intent == "insult":
        sim.note("Harsh words", f"You insulted {npc.first}. People notice these things.", kind="alert")
    return result


def _converse(sim, npc, text: str, intent: str, *, medium: str, player,
              forced=None, context: str | None = None) -> dict:
    conversation.hydrate(sim, npc)
    meeting = npc.flags.get('meeting', {})
    if medium == 'talk' and meeting.get('status') == 'waiting':
        meeting['status'] = 'met'
        npc.flags.pop('block_key', None)
    rule = conversation.request_plan(sim, npc, text) if not forced else None
    if rule:
        forced = [rule]
    elif intent == 'invite' and not forced:
        forced = ["Where and when should we meet? Give me a place and time so we can actually arrange it."]
    rel = sim._rel_obj(npc.id)
    if medium == 'talk':
        if not civic.engaged(sim, npc):
            civic.begin_talk(sim, npc)
        npc.flags['engaged_until'] = sim.minute + 12
    result = compose_reply(
        npc=npc, player=player, rel=rel, text=text, intent=intent, hub=sim.hub,
        location_names=sim.location_names, forced_lines=forced, context_hook=context,
    )
    npc.flags.setdefault("dialogue_cursors", {})[intent] = result["dialogue_cursor"]
    local = conversation.offline(npc, text, medium) if not forced else None
    if local:
        result['text'] = local
    effects = result["effects"]
    # Hearing a refusal is not a way to farm attraction. Both typed and quick
    # flirting use the same pre-conversation eligibility checks.
    if (intent == 'flirt' and not _flirt_eligible(sim, npc)[0]) or (intent == 'ask_date' and not _date_eligible(sim, npc)[0]):
        effects['romance'] = 0
    # Calls are a little less intimate per turn; texts least of all.
    scale = {"talk": 1.0, "call": 0.65, "text": 0.55}.get(medium, 1.0)
    if scale != 1.0:
        effects = {k: round(v * scale, 2) for k, v in effects.items()}
    _apply_effects(sim, npc, effects)
    npc.mood.social_energy = clamp(npc.mood.social_energy - 1.2, 0, 100)
    npc.mood.valence = clamp(npc.mood.valence + effects.get("affinity", 0) * 0.9, -100, 100)
    if intent == "insult":
        npc.mood.irritation = clamp(npc.mood.irritation + 14, 0, 100)
        player.reputation = clamp(player.reputation - 1.5, 0, 100)
        sim.adjust_rel(npc.id, "player", affinity=effects.get("affinity", 0) * 0.4,
                       tension=effects.get("tension", 0) * 0.5, conflicts=1)
        sim.metrics["conflicts"] = sim.metrics.get("conflicts", 0) + 1

    left = medium == 'talk' and (sim.rel(npc.id, 'player').get('tension', 0) >= 75 or npc.mood.irritation >= 70 or npc.mood.stress >= 90)
    if left:
        result['text'] = "No. I need some space. We are done talking for now."
        civic.end_talk(sim, npc_id=npc.id, reason='leave')
        civic.speak(sim, npc, "I need some space.", kind='conflict')
    elif medium == 'talk' and intent == 'goodbye':
        civic.end_talk(sim, npc_id=npc.id)
    remote = None
    # Forced consent/date/rule answers are authoritative, never AI-rephrased.
    if not left and not forced and intent not in ('ask_date', 'invite', 'goodbye') and llm.is_enabled():
        remote = llm.context(npc=npc, player=player, intent=intent, player_text=text,
            relationship=_rel_payload(sim, npc.id).get('label', 'acquaintance'),
            memory=conversation.recall(npc, text), medium=medium,
            venue=sim.location_names.get(npc.location_id, 'the block'))

    summary = f"You {QUICK_LABELS.get(intent, 'talked with')} {npc.first}."
    _record_talk(sim, npc, intent, summary,
                 importance=0.5 if intent in ("deep", "apology", "ask_date", "flirt", "insult") else 0.25,
                 valence=effects.get("affinity", 0) / 12.0,
                 kind="call" if medium == "call" else "talk")
    sim.player_memory(f"{summary} {npc.first} said: \"{result['text'][:110]}\"",
                      kind="call" if medium == "call" else "talk",
                      valence=effects.get("affinity", 0) / 20.0)
    sim.metrics["dialogue_turns"] = sim.metrics.get("dialogue_turns", 0) + 1

    # being seen together in public is social information
    if medium == "talk" and npc.location_id not in ("home", ""):
        for other in sim.npcs:
            if other.id != npc.id and other.location_id == npc.location_id and other.status != "sleeping":
                sim.remember(other, {
                    "id": f"seen_{new_id('evt')}", "minute": round(sim.minute, 2), "day": sim.day_number,
                    "kind": "seen_together", "actor": "player", "targets": [npc.id],
                    "location": npc.location_id, "facts": {}, "witnesses": [], "visibility": "public",
                    "summary": f"{player.name} and {npc.first} were talking at "
                               f"{sim.location_names.get(npc.location_id, 'the block')}.",
                }, importance=0.12, valence=0.1, source="witnessed")

    turn_id = conversation.record(sim, npc, text, result['text'], medium)
    return {
        "ok": True, "reply": result["text"], "intent": intent,
        "turn_id": turn_id, "npc_id": npc.id, "conversation_ended": bool(left or intent == 'goodbye'),
        "effects": effects, "effects_display": _effect_lines(effects),
        "npc": {"id": npc.id, "name": npc.name, "first": npc.first, "look": npc.look,
                "mood": npc.mood.label(), "voice": npc.voice},
        "relationship": _rel_payload(sim, npc.id),
        "heard_rumor": False, "_remote_dialogue": remote,
    }


def _pick_date_venue(sim, npc) -> str:
    """Choose a venue that fits the resident's tastes (deterministic per day)."""
    rng = sim.hub.stream(f"datevenue:{npc.id}:{sim.day_index}")
    prefs = []
    if "music" in npc.hobbies:
        prefs.append("studio")
    if "movies" in npc.hobbies:
        prefs.append("cinema")
    if "cooking" in npc.hobbies or "coffee" in npc.hobbies:
        prefs.append("cafe")
    if "art" in npc.hobbies or "photography" in npc.hobbies:
        prefs.append("gallery")
    prefs += ["restaurant", "park", "cafe"]
    valid = [v for v in prefs if v in LOCATION_BY_ID and LOCATION_BY_ID[v].get("kind") in
             ("cafe", "cinema", "studio", "park", "restaurant", "gallery")]
    return valid[rng.randrange(len(valid))] if valid else "cafe"


def _clock_short(minute: float) -> str:
    return clock_label_for(minute)


# ---------------------------------------------------------------------------
# gifts & shopping
# ---------------------------------------------------------------------------
def act_gift(sim, action: dict) -> dict:
    p = _player(sim)
    npc = _npc(sim, action.get("npc_id"))
    _require_near_npc(sim, npc)
    item_id = str(action.get("item_id", ""))
    if p.inventory.get(item_id, 0) <= 0:
        raise SimError("You don't have that in your bag.", "not_in_inventory", 422)
    item = buyable(item_id)
    if item is None:
        raise SimError("Unknown item.", "bad_item")
    if npc.id == "player":
        raise SimError("You can't gift yourself. Well — you can, but not here.", "bad_target")
    p.inventory[item_id] -= 1
    if p.inventory[item_id] <= 0:
        del p.inventory[item_id]

    rel = sim._rel_obj(npc.id)
    reaction = compose_gift_reaction(npc, rel, item, sim.hub)
    sim.adjust_rel(npc.id, "player", familiarity=2.0, affinity=reaction["affinity"],
                   trust=reaction["trust"], romance=reaction["romance"], count_interaction=True)
    sim.adjust_rel("player", npc.id, familiarity=2.0, affinity=reaction["affinity"],
                   trust=reaction["trust"], romance=reaction["romance"])
    rel_dict = sim.rel(npc.id, "player")
    rel_dict.setdefault("gifts", {})
    rel_dict["gifts"][item_id] = int(rel_dict["gifts"].get(item_id, 0)) + 1
    if reaction["mood"] == "love":
        npc.mood.valence = clamp(npc.mood.valence + 12, -100, 100)
    npc.mood.social_energy = clamp(npc.mood.social_energy + 4, 0, 100)
    _record_talk(sim, npc, "gift", f"You gave {npc.first} a {item['name']}.", importance=0.5,
                 valence=0.4, kind="gift")
    sim.metrics["gifts"] = sim.metrics.get("gifts", 0) + 1
    sim.note("Gift given", f"{npc.first} received your {item['name']}.", kind="gift")
    if reaction["mood"] == "love" and sim.hub.stream(f"giftpost:{npc.id}:{sim.day_index}").random() < 0.3:
        sim.push_feed(author_id=npc.id, text=f"Someone handed me a {item['name']} today for no reason. "
                                            "I'm not crying, the block is just dusty. 🥲",
                      mood="warm", tag="gifts", loc=npc.location_id)
    return {
        "ok": True, "reply": reaction["text"], "mood": reaction["mood"],
        "reasons": reaction.get("reasons", []), "repetition": reaction.get("repetition", 0),
        "effects_display": _effect_lines({"affinity": reaction["affinity"], "trust": reaction["trust"],
                                          "romance": reaction["romance"], "familiarity": 2.0}),
        "relationship": _rel_payload(sim, npc.id),
        "npc": {"id": npc.id, "name": npc.name, "first": npc.first, "look": npc.look},
    }


def act_buy(sim, action: dict) -> dict:
    p = _player(sim)
    item = buyable(str(action.get("item_id", "")))
    if item is None:
        raise SimError("Unknown item.", "bad_item")
    remote = bool(action.get("remote", True))
    price = int(item["price"]) + (math.ceil(item["price"] * config.REMOTE_ORDER_FEE) if remote else 0)
    sim.player_spend(price, "purchase", f"Bought {item['name']}", counterparty="business")
    p.inventory[item["id"]] = int(p.inventory.get(item["id"], 0)) + 1
    return {"ok": True, "item": item, "paid": price, "remote": remote,
            "wallet": p.wallet, "inventory": p.inventory,
            "consumable": item["id"] in CONSUMABLES,
            "text": f"{(item.get('icon') + ' ') if item.get('icon') else ''}{item['name']} bought for {price} BLX"
                    + (" (includes delivery)." if remote else ".")}


def act_use_item(sim, action: dict) -> dict:
    p = _player(sim)
    item_id = str(action.get("item_id", ""))
    consumable = CONSUMABLES.get(item_id)
    if consumable is None:
        raise SimError("You can't use that.", "bad_item")
    if p.inventory.get(item_id, 0) <= 0:
        raise SimError("You don't have that.", "not_in_inventory", 422)
    p.inventory[item_id] -= 1
    if p.inventory[item_id] <= 0:
        del p.inventory[item_id]
    p.energy = clamp(p.energy + consumable.get("energy", 0), 0, 100)
    p.mood.valence = clamp(p.mood.valence + consumable.get("mood", 0), -100, 100)
    p.mood.stress = clamp(p.mood.stress - consumable.get("stress", 0), 0, 100)
    sim.player_memory(f"You {consumable['verb']} a {consumable['name']}.", kind="rest", valence=0.3)
    return {"ok": True, "text": consumable["text"], "energy": round(p.energy, 1),
            "effects_display": [f"energy +{consumable.get('energy', 0)}", f"mood +{consumable.get('mood', 0)}"]}


# ---------------------------------------------------------------------------
# activities, work, sleep
# ---------------------------------------------------------------------------
def act_activity(sim, action: dict) -> dict:
    loc = LOCATION_BY_ID.get(str(action.get("location_id", "")))
    if loc is None:
        raise SimError("That place doesn't exist.", "bad_destination", 404)
    _require_near_loc(sim, loc["id"], pad=config.INTERACT_PAD)
    if not _is_open(sim, loc):
        raise SimError(f"{loc['name']} is closed right now.", "closed", 422)
    activity = next((a for a in loc["activities"] if a["id"] == action.get("activity_id")), None)
    if activity is None:
        raise SimError("That activity isn't available here.", "not_found", 404)
    if activity.get("civic_op"):
        return civic.action(sim,{"op":activity["civic_op"]})
    p = _player(sim)
    cost = int(activity.get("cost", 0))
    if cost:
        sim.player_spend(cost, "activity", f"{activity['label']} at {loc['name']}", counterparty=loc["id"])
    p.energy = clamp(p.energy + float(activity.get("energy", 0)) - 2.0, 0, 100)
    p.mood.valence = clamp(p.mood.valence + float(activity.get("mood", 2)) * 1.4, -100, 100)
    p.mood.social_energy = clamp(p.mood.social_energy + float(activity.get("social", 2)) * 0.8, 0, 100)
    p.mood.stress = clamp(p.mood.stress - float(activity.get("stress", 2)), 0, 100)
    present = [n for n in sim.npcs if n.location_id == loc["id"] and n.status != "sleeping"]
    for other in present[:5]:
        sim.adjust_rel(other.id, "player", familiarity=0.6, affinity=0.3)
    sim.player_memory(f"{activity['label']} at {loc['name']}.", kind="activity", valence=0.4)
    skipped = sim.skip_minutes(int(activity.get("minutes", 30)))
    return {"ok": True, "text": f"{activity['label']} at {loc['name']}. Time passes pleasantly.",
            "cost": cost, "wallet": p.wallet, "energy": round(p.energy, 1),
            "minutes": activity.get("minutes", 30), "notices": skipped,
            "people_here": [n.first for n in present[:6]],
            "clock": sim.clock_payload()}


def act_work(sim, action: dict) -> dict:
    p = _player(sim)
    loc_id = str(action.get("location_id") or p.flags.get("workplace") or "cafe")
    loc = LOCATION_BY_ID.get(loc_id)
    if loc is None:
        raise SimError("That place doesn't exist.", "bad_destination", 404)
    _require_near_loc(sim, loc["id"], pad=config.INTERACT_PAD)
    if not _is_open(sim, loc):
        raise SimError(f"{loc['name']} is closed right now.", "closed", 422)
    if p.energy < config.SHIFT_ENERGY_COST:
        raise SimError("You're too exhausted for a shift. Eat something or sleep first.", "exhausted", 422)
    rng = sim.hub.stream(f"wage:{loc['id']}:{sim.day_index}")
    pay = int(config.WAGE_BASE + rng.random() * config.WAGE_VARIANCE + p.reputation / 10)
    sim.player_earn(pay, "wage", f"Shift at {loc['name']}", counterparty=loc["id"])
    p.energy = clamp(p.energy - config.SHIFT_ENERGY_COST, 0, 100)
    p.mood.stress = clamp(p.mood.stress + 6, 0, 100)
    if p.occupation == "newcomer":
        p.occupation = "shift worker"
    sim.player_memory(f"Worked a shift at {loc['name']} and earned {pay} BLX.", kind="work", valence=0.3)
    sim.add_event(kind="shift", actor="player", targets=[], location=loc["id"], facts={"pay": pay},
                  witnesses=[], visibility="public", summary=f"You worked a shift at {loc['name']}.")
    sim.stop_player()
    skipped = sim.skip_minutes(config.SHIFT_HOURS * 60)
    p.flags["busy"] = {"kind":"work", "label":f"Finishing your shift at {loc['name']}", "until":time.time()+5}
    return {"ok": True, "pay": pay, "wallet": p.wallet, "energy": round(p.energy, 1),
            "text": f"You worked a {config.SHIFT_HOURS}-hour shift and earned {pay} BLX.",
            "notices": skipped, "clock": sim.clock_payload()}


def act_sleep(sim, action: dict) -> dict:
    p = _player(sim)
    now = sim.hour_of_day
    if 7.0 <= now < 21.0:
        raise SimError("It's the middle of the day — you're not sleepy.", "not_tired", 422)
    minutes = ((7.0 - now) % 24) * 60
    if minutes < 60:
        minutes += 24 * 60
    skipped = sim.skip_minutes(minutes)
    p.energy = 100.0
    p.mood.stress = clamp(p.mood.stress - 22, 0, 100)
    p.mood.valence = clamp(p.mood.valence + 7, -100, 100)
    sim.player_memory("Slept through the night and woke up refreshed.", kind="rest", valence=0.5)
    return {"ok": True, "text": "You slept. The block kept living without you — check the feed.",
            "minutes": round(minutes), "energy": 100.0,
            "notices": skipped, "clock": sim.clock_payload()}


# ---------------------------------------------------------------------------
# social network
# ---------------------------------------------------------------------------
def act_post(sim, action: dict) -> dict:
    p = _player(sim)
    text = _sanitize(action.get("text"), config.MAX_POST_LENGTH)
    if len(text) < 2:
        raise SimError("That's a little short for a post.", "too_short", 422)
    post = sim.push_feed(author_id="player", text=text, mood=p.mood.label(), tag="resident",
                         loc="")
    p.reputation = clamp(p.reputation + 0.6, 0, 100)
    sim.player_memory(f"You posted: \"{text[:100]}\"", kind="post", valence=0.2)
    # NPC reactions use real relationships, not vanity metrics
    reactions = []
    for npc in sim.npcs:
        rel = sim.rel(npc.id, "player")
        if rel.get("familiarity", 0) >= 10 and sim.hub.stream(f"like:{npc.id}:{post.id}").random() < 0.35:
            post.likes.append(npc.id)
            reactions.append(npc.first)
    if reactions:
        sim.note("Your post got attention", f"{', '.join(reactions[:4])} liked your post.", kind="info")
    return {"ok": True, "post": post.to_dict(), "likes": len(post.likes),
            "text": "Posted to the block." if not reactions else f"Posted. {len(reactions)} residents reacted."}


def _find_post(sim, post_id: str) -> Post:
    post = next((x for x in sim.posts if x.id == post_id), None)
    if post is None:
        raise SimError("That post is gone.", "not_found", 404)
    return post


def act_like(sim, action: dict) -> dict:
    post = _find_post(sim, str(action.get("post_id", "")))
    if "player" in post.likes:
        post.likes.remove("player")
        return {"ok": True, "liked": False, "likes": len(post.likes)}
    post.likes.append("player")
    if post.author_id != "player":
        author = sim.npc(post.author_id)
        if author:
            sim.adjust_rel(author.id, "player", familiarity=0.8, affinity=0.5)
            author.mood.valence = clamp(author.mood.valence + 1.2, -100, 100)
    return {"ok": True, "liked": True, "likes": len(post.likes)}


def act_comment(sim, action: dict) -> dict:
    _player(sim)
    post = _find_post(sim, str(action.get("post_id", "")))
    text = _sanitize(action.get("text"), config.MAX_COMMENT_LENGTH)
    from blxverse.engine.models import Comment
    post.comments.append(Comment(id=new_id("cmt"), author_id="player", text=text, minute=sim.minute))
    post.comments = post.comments[-40:]
    if post.author_id != "player":
        author = sim.npc(post.author_id)
        if author:
            sim.adjust_rel(author.id, "player", familiarity=1.2, affinity=0.8, count_interaction=True)
            if sim.hub.stream(f"cmtreply:{post.id}").random() < 0.5:
                sim.send_npc_message(author.id, "Ha — saw your comment on my post. "
                                                "You're funnier than you look.")
    return {"ok": True, "text": "Comment added.", "comments": len(post.comments)}


def act_message(sim, action: dict) -> dict:
    _player(sim)
    npc = _npc(sim, action.get("npc_id"))
    text = _sanitize(action.get("text"), config.MAX_CHAT_LENGTH)
    if npc.flags.get("banned_from") and npc.location_id == "home":
        raise SimError(f"{npc.first} has gone quiet for a bit. Try later.", "unavailable", 422)
    thread = sim.threads.get(npc.id) or Thread(npc_id=npc.id)
    sim.threads[npc.id] = thread
    thread.messages.append(Message(id=new_id("msg"), sender="player", text=text, minute=sim.minute,
                                   read=True, kind="text"))
    thread.messages = thread.messages[-60:]
    turn_id = conversation.record(sim, npc, text, medium='text', turn_id=thread.messages[-1].id)
    sim.player_memory(f"Texted {npc.first}: \"{text[:90]}\"", kind="message", valence=0.1)
    delay = config.MESSAGE_REPLY_MIN_DELAY + sim.hub.stream(f"msgdelay:{npc.id}").random() * (
        config.MESSAGE_REPLY_MAX_DELAY - config.MESSAGE_REPLY_MIN_DELAY)
    if npc.status == "sleeping":
        delay += 240
    queue = sim.world_flags.setdefault("pending_messages", [])
    queue.append({"id": new_id("pending"), "npc_id": npc.id, "text": text,
                  "due": sim.minute + delay, "turn_id": turn_id})
    sim.world_flags["pending_messages"] = queue[-30:]
    return {"ok": True, "scheduled": True,
            "text": f"Message sent. {npc.first} will reply in a few minutes of game time."}


def act_read_thread(sim, action: dict) -> dict:
    npc = _npc(sim, action.get("npc_id"))
    thread = sim.threads.get(npc.id)
    if thread:
        for m in thread.messages:
            if m.sender != "player":
                m.read = True
    return {"ok": True, "thread": thread.to_dict() if thread else {"npc_id": npc.id, "messages": []}}


# ---------------------------------------------------------------------------
# calls
# ---------------------------------------------------------------------------
def act_call_start(sim, action: dict) -> dict:
    p = _player(sim)
    npc = _npc(sim, action.get("npc_id"))
    rel = sim.rel(npc.id, "player")
    if rel.get("familiarity", 0) < config.CALL_MIN_FAMILIARITY:
        raise SimError(f"You don't know {npc.first} well enough to call yet. Talk in person first.",
                       "not_familiar", 422)
    if npc.status == "sleeping":
        raise SimError(f"{npc.first} is asleep and their phone is face-down.", "asleep", 422)
    if rel.get("tension", 0) >= 72:
        raise SimError(f"{npc.first} isn't picking up. The tension is too high.", "declined", 422)
    if npc.mood.social_energy < 12:
        raise SimError(f"{npc.first} is too drained for a call right now.", "drained", 422)
    call_id = new_id("call")
    from blxverse.content.dialogue_content import line_pool
    pool = list(line_pool("call_greeting", npc.archetype)) or ["Hey, you."]
    greeting = pool[sim.hub.stream(f"callgreet:{npc.id}").randrange(len(pool))].replace("{player}", p.name)
    sim.calls[call_id] = {"npc_id": npc.id, "start": sim.minute, "turns": 0, "active": True}
    npc.flags["on_call_with"] = "player"
    sim.metrics["calls"] = sim.metrics.get("calls", 0) + 1
    sim.player_memory(f"Called {npc.first}.", kind="call", valence=0.3)
    return {"ok": True, "call_id": call_id, "npc_id": npc.id, "greeting": greeting,
            "voice": npc.voice, "look": npc.look,
            "npc": {"id": npc.id, "name": npc.name, "first": npc.first, "occupation": npc.occupation,
                    "mood": npc.mood.label(), "archetype": npc.archetype}}


def act_call_turn(sim, action: dict) -> dict:
    call = sim.calls.get(str(action.get("call_id", "")))
    if not call or not call.get("active"):
        raise SimError("That call already ended.", "ended", 409)
    npc = sim.npc(call["npc_id"])
    if npc is None:
        raise SimError("Caller not found.", "not_found", 404)
    text = _sanitize(action.get("text"))
    intent = classify_intent(text) or "smalltalk"
    p = _player(sim)
    forced = None
    if intent == 'ask_date':
        forced = ["Let's talk about making that plan when we see each other in person."]
    elif intent == 'flirt' and not _flirt_eligible(sim, npc)[0]:
        forced = ["Let's slow down. I'd rather get to know you first."]
    result = _converse(sim, npc, text, intent, medium='call', player=p, forced=forced)
    call['turns'] = int(call.get('turns', 0)) + 1
    sim.metrics['call_turns'] = sim.metrics.get('call_turns', 0) + 1
    result['turns'] = call['turns']
    return result


def act_call_end(sim, action: dict) -> dict:
    call_id = str(action.get("call_id", ""))
    call = sim.calls.pop(call_id, None)
    if not call:
        return {"ok": True, "text": "Call already over."}
    npc = sim.npc(call["npc_id"])
    seconds = max(0, min(int(action.get("duration_s", 0) or 0), 60 * 60))
    minutes = max(0.5, min(30.0, seconds / 60.0))
    turns = int(call.get("turns", 0))
    if npc:
        npc.flags.pop("on_call_with", None)
        bonus = 1.0 + min(4.0, minutes / 6)
        sim.adjust_rel(npc.id, "player", familiarity=bonus, affinity=0.6, count_interaction=True)
        sim.adjust_rel("player", npc.id, familiarity=bonus, affinity=0.6)
        npc.mood.social_energy = clamp(npc.mood.social_energy - 3, 0, 100)
        summary = f"You ended a call with {npc.first} after {turns} turns."
        ev = sim.add_event(kind="call", actor="player", targets=[npc.id], location=npc.location_id,
                           facts={"turns": turns, "seconds": seconds}, witnesses=[], visibility="private",
                           summary=summary)
        sim.remember(npc, ev, importance=0.3 + min(0.3, turns * 0.05), valence=0.3, source="participated")
        sim.player_memory(summary, kind="call", valence=0.3)
        sim.metrics["call_minutes"] = round(sim.metrics.get("call_minutes", 0) + minutes, 1)
        return {"ok": True, "turns": turns, "duration_s": seconds,
                "reply": f"Call ended after {turns} turns. {npc.first} sounded glad you called.",
                "relationship": _rel_payload(sim, npc.id)}
    return {"ok": True, "turns": turns, "duration_s": seconds, "reply": "Call ended."}


def act_answer_call(sim, action: dict) -> dict:
    pending = sim.world_flags.get("pending_call")
    if not pending:
        raise SimError("No incoming call.", "no_call", 409)
    if action.get("call_id") and action["call_id"] != pending["call_id"]:
        raise SimError("That call is no longer ringing.", "no_call", 409)
    if sim.minute > pending.get("expires", 0):
        sim.world_flags["pending_call"] = None
        raise SimError("You missed the call.", "missed", 409)
    npc = _npc(sim, pending["npc_id"])
    sim.world_flags["pending_call"] = None
    call_id = pending["call_id"]
    from blxverse.content.dialogue_content import line_pool
    pool = list(line_pool("call_greeting", npc.archetype)) or ["Hey."]
    greeting = pool[sim.hub.stream(f"ans:{npc.id}").randrange(len(pool))].replace("{player}", sim.player.name)
    sim.calls[call_id] = {"npc_id": npc.id, "start": sim.minute, "turns": 0, "active": True}
    npc.flags["on_call_with"] = "player"
    return {"ok": True, "call_id": call_id, "npc_id": npc.id, "greeting": greeting,
            "voice": npc.voice, "look": npc.look,
            "npc": {"id": npc.id, "name": npc.name, "first": npc.first,
                    "occupation": npc.occupation, "mood": npc.mood.label()}}


def act_decline_call(sim, action: dict) -> dict:
    pending = sim.world_flags.get("pending_call")
    if not pending:
        raise SimError("No incoming call.", "no_call", 409)
    npc = sim.npc(pending["npc_id"])
    sim.world_flags["pending_call"] = None
    if npc:
        sim.adjust_rel(npc.id, "player", affinity=-1.5)
        sim.adjust_rel("player", npc.id, affinity=-1.5)
        thread = sim.threads.get(npc.id) or Thread(npc_id=npc.id)
        sim.threads[npc.id] = thread
        thread.messages.append(Message(id=new_id("msg"), sender=npc.id, kind="missed_call",
                                       minute=sim.minute, read=False,
                                       text=f"Missed call from {npc.first}"))
        sim.note("Missed call", f"{npc.first} called and you didn't pick up.", kind="call")
    return {"ok": True, "text": "You let it ring. They'll notice."}


# ---------------------------------------------------------------------------
# dates
# ---------------------------------------------------------------------------
def act_date_go(sim, action: dict) -> dict:
    p = _player(sim)
    offer_id = str(action.get("offer_id", ""))
    offers = sim.world_flags.setdefault("date_offers", [])
    offer = next((d for d in offers if d["id"] == offer_id), None)
    if offer is None:
        raise SimError("That date isn't on your calendar anymore.", "not_found", 404)
    if offer["status"] != "accepted":
        raise SimError("That date has already happened.", "consumed", 422)
    if sim.minute < offer["due"] - 45:
        raise SimError(f"It's too early — {offer['npc_first']} isn't there yet.", "too_early", 422)
    if sim.minute > offer["expires"]:
        offer["status"] = "missed"
        npc = sim.npc(offer["npc_id"])
        if npc:
            sim.adjust_rel(npc.id, "player", affinity=-3, trust=-2)
            sim.note("You missed a date", f"{npc.first} waited at {offer['venue_name']}.", kind="date")
        raise SimError("You missed the date window.", "missed_date", 422)
    npc = _npc(sim, offer["npc_id"])
    if sim.rel(npc.id, "player").get("tension", 0) >= 62:
        raise SimError(f"{npc.first} changed their mind — things feel too tense.", "canceled", 422)
    _require_near_loc(sim, offer["venue"], pad=config.INTERACT_PAD)
    cost = int(offer.get("cost", config.DATE_DEFAULT_COST))
    if p.wallet < cost:
        raise SimError(f"You need {cost} BLX for this date.", "insufficient_funds", 422)
    sim.player_spend(cost, "activity", f"Date with {npc.first} at {offer['venue_name']}", counterparty=npc.id)
    sim.force_move(npc, offer["venue"])
    sim.adjust_rel(npc.id, "player", familiarity=5, affinity=6, trust=4, romance=8, dates=1,
                   tension=-2, count_interaction=True)
    sim.adjust_rel("player", npc.id, familiarity=5, affinity=6, trust=4, romance=8, dates=1, tension=-2)
    npc.mood.valence = clamp(npc.mood.valence + 20, -100, 100)
    p.mood.valence = clamp(p.mood.valence + 14, -100, 100)
    offer["status"] = "done"
    ev = sim.add_event(kind="date", actor="player", targets=[npc.id], location=offer["venue"],
                       facts={"cost": cost}, witnesses=[], visibility="public",
                       summary=f"You and {npc.first} had a date at {offer['venue_name']}.")
    sim.remember(npc, ev, importance=0.8, valence=0.8, source="participated")
    sim.player_memory(f"Date with {npc.first} at {offer['venue_name']}.", kind="date", valence=0.8)
    sim.metrics["dates"] = sim.metrics.get("dates", 0) + 1

    relationship = sim.rel(npc.id, "player")
    became_partner = False
    if (relationship.get("romance", 0) >= 45 and relationship.get("affinity", 0) >= 35
            and "dating" not in relationship.get("flags", [])):
        sim.set_rel_flag(npc.id, "player", "dating", True)
        sim.set_rel_flag("player", npc.id, "dating", True)
        sim.set_rel_flag(npc.id, "player", "crush", False)
        became_partner = True
        sim.note("You're dating", f"You and {npc.first} are officially seeing each other.", kind="story")
        sim.push_feed(author_id=npc.id, text="Some things are worth keeping a little private. But also: "
                                            "I'm smiling at my phone. 💛", mood="warm", tag="love",
                      loc=offer["venue"])
    skipped = sim.skip_minutes(75)
    return {"ok": True, "text": f"A lovely evening at {offer['venue_name']} with {npc.first}.",
            "cost": cost, "wallet": p.wallet, "became_partner": became_partner,
            "relationship": _rel_payload(sim, npc.id), "notices": skipped,
            "clock": sim.clock_payload()}


# ---------------------------------------------------------------------------
# cases & investigation
# ---------------------------------------------------------------------------
EVIDENCE_BY_LOCATION = {
    "studio": "The equipment locker was reorganized this week — the mic case is empty, but there's a cable box wedged in front of it.",
    "music_store": "There's a repair intake receipt for the studio's brass mic dated Tuesday afternoon. Signed by the studio, not by Daniel.",
    "cafe": "The barista remembers Daniel at the cafe until 23:00 on Tuesday. The studio closes at 22:00 — he couldn't have been at the locker after closing.",
}


def act_investigate(sim, action: dict) -> dict:
    p = _player(sim)
    loc = LOCATION_BY_ID.get(str(action.get("location_id", "")))
    if loc is None:
        raise SimError("That place doesn't exist.", "bad_destination", 404)
    _require_near_loc(sim, loc["id"], pad=config.INTERACT_PAD)
    case = next((c for c in sim.cases if c.status == "open"), None)
    if case is None:
        raise SimError("There's no open case to investigate.", "no_case", 422)
    sites = {token.split(":")[0] for token in case.helpful_evidence}
    if loc["id"] not in sites:
        raise SimError(f"Nothing useful at {loc['name']} for this case.", "nothing_here", 422)
    if any(token.startswith(loc["id"] + ":") for token in case.found_evidence):
        raise SimError("You already found everything here.", "already", 422)
    token = f"{loc['id']}: {EVIDENCE_BY_LOCATION.get(loc['id'], 'You find a small, useful detail.')}"
    case.found_evidence.append(token)
    sim.player_memory(f"Found evidence at {loc['name']}.", kind="investigation", valence=0.4)
    sim.add_event(kind="investigation", actor="player", targets=[], location=loc["id"],
                  facts={"case": case.id}, witnesses=[], visibility="private",
                  summary=f"You investigated {loc['name']} and found a clue.")
    sim.note("Clue found", token[:150], kind="case")
    p.reputation = clamp(p.reputation + 1.5, 0, 100)
    remaining = max(0, 2 - len(case.found_evidence))
    return {"ok": True, "evidence": token, "found": len(case.found_evidence),
            "enough": len(case.found_evidence) >= 2,
            "text": token + ("\n\nYou have enough evidence to clear them. Open the case and present it."
                             if len(case.found_evidence) >= 2
                             else f"\n\n{remaining} more clue{'s' if remaining != 1 else ''} needed.")}


def act_present_case(sim, action: dict) -> dict:
    p = _player(sim)
    case = next((c for c in sim.cases if c.id == action.get("case_id")), None)
    if case is None:
        raise SimError("Case not found.", "not_found", 404)
    if case.status != "open":
        raise SimError("This case is already closed.", "closed_case", 422)
    if len(case.found_evidence) < 2:
        raise SimError("You need at least two pieces of evidence first.", "not_enough", 422)
    accused = sim.npc(case.accused)
    sim.resolve_case(case, by="player", evidence=list(case.found_evidence))
    p.reputation = clamp(p.reputation + 6, 0, 100)
    summary = f"You presented evidence and cleared {accused.first if accused else 'the accused'}."
    sim.player_memory(summary, kind="case", valence=0.9)
    # truth reaches everyone who believed the false claim
    for npc in sim.npcs:
        for belief in list(npc.beliefs):
            if belief.truth == "false" and belief.subject_id == case.accused and belief.confidence >= 0.2:
                belief.confidence = clamp(belief.confidence - 0.55, 0, 1)
                belief.evidence.append("cleared by evidence presented on the block")
                if belief.confidence < 0.2:
                    npc.beliefs.remove(belief)
    if accused:
        sim.adjust_rel(accused.id, "player", trust=6, affinity=6, familiarity=2)
        sim.adjust_rel("player", accused.id, trust=6, affinity=6)
    return {"ok": True, "text": "You presented the evidence. The story collapses. "
                                f"{accused.first if accused else 'The accused'} is cleared.",
            "case": case.to_dict(), "reputation": round(p.reputation, 1)}


def act_challenge_rumor(sim, action: dict) -> dict:
    _player(sim)
    npc = _npc(sim, action.get("npc_id"))
    claim = str(action.get("claim", ""))[:200]
    if not claim:
        raise SimError("Nothing to challenge.", "bad_request")
    belief = next((b for b in npc.beliefs if claim.lower() in b.claim.lower()), None)
    if belief is None:
        raise SimError(f"{npc.first} doesn't seem to believe that.", "not_found", 404)
    rel = sim.rel(npc.id, "player")
    strength = 0.18 + (0.3 if rel.get("trust", 0) >= 35 else 0.0) + (0.2 if rel.get("familiarity", 0) >= 30 else 0.0)
    belief.confidence = clamp(belief.confidence - strength, 0, 1)
    belief.challenged_by.append("player")
    if belief.confidence <= 0.15:
        npc.beliefs.remove(belief)
        text = f"{npc.first} frowns. \"…Huh. Maybe I got that wrong.\""
    else:
        text = f"{npc.first} shrugs it off, but the certainty is gone from their face."
    sim.adjust_rel(npc.id, "player", trust=1.5, familiarity=1.0, count_interaction=True)
    return {"ok": True, "text": text, "confidence": round(belief.confidence, 2),
            "remaining": belief.confidence > 0.15}


# ---------------------------------------------------------------------------
# business & mischief
# ---------------------------------------------------------------------------
def act_start_business(sim, action: dict) -> dict:
    p = _player(sim)
    if p.flags.get("cart_owned"):
        raise SimError("You already run a cart at the square.", "exists", 422)
    _require_near_loc(sim, "square", pad=config.INTERACT_PAD)
    sim.player_spend(config.STREET_CART_COST, "business", "Street cart licence and setup", counterparty="city")
    p.flags["cart_owned"] = True
    p.flags["cart_opened"] = sim.day_number
    p.occupation = "street vendor"
    p.reputation = clamp(p.reputation + 4, 0, 100)
    sim.player_memory("Opened a street cart at BlaxkVille Square.", kind="business", valence=0.9)
    ev = sim.add_event(kind="business", actor="player", targets=[], location="square",
                       facts={"cost": config.STREET_CART_COST}, witnesses=[], visibility="public",
                       summary="You set up a street cart at BlaxkVille Square.")
    for npc in sim.npcs:
        if npc.location_id == "square" and npc.status != "sleeping":
            sim.remember(npc, ev, importance=0.3, valence=0.4, source="witnessed")
    sim.push_feed(author_id="player", text="So I run a cart at the square now. Come by. I'll pretend not to be nervous. 🛒",
                  mood="hopeful", tag="business", loc="square")
    sim.note("Cart open", "Your cart is at BlaxkVille Square. It earns a little every day at 18:00.", kind="story")
    return {"ok": True, "text": f"You set up a street cart for {config.STREET_CART_COST} BLX. "
                                "It'll earn daily income at 18:00.", "wallet": p.wallet}


def act_stir(sim, action: dict) -> dict:
    p = _player(sim)
    target = _npc(sim, action.get("npc_id"))
    _require_near_npc(sim, target, radius=config.INTERACT_RADIUS + 40)
    others = [n for n in sim.npcs
              if n.id != target.id and n.location_id == target.location_id and n.status != "sleeping"]
    if not others:
        raise SimError("There's nobody else here to stir up anything with.", "no_target", 422)
    from blxverse.content.dialogue_content import STIR_CLAIMS

    subject = others[0]
    sim.adjust_rel(target.id, subject.id, tension=7, familiarity=1)
    sim.adjust_rel(subject.id, target.id, tension=3)
    p.reputation = clamp(p.reputation - 1.0, 0, 100)

    # The whisper becomes a real rumor. The person you told is the visible
    # origin; the ledger of who planted it stays on the rumor itself, which is
    # what makes provenance worth having.
    rng = sim.hub.stream(f"stir:{target.id}:{int(sim.minute)}")
    claim = STIR_CLAIMS[rng.randrange(len(STIR_CLAIMS))].format(subject=subject.first)
    rumor = sim.add_rumor(
        claim=claim, subject_id=subject.id, truth="false", origin_id=target.id,
        confidence=0.55, location=target.location_id or "square",
    )
    rumor["planted_by"] = "player"

    sim.player_memory(f"You whispered something to {target.first} about {subject.first}.", kind="mischief",
                      valence=-0.2)
    sim.note("Pot, stirred", f"{target.first} is repeating something about {subject.first}. "
                             "You know exactly why.", kind="alert")
    sim.metrics["stirs"] = sim.metrics.get("stirs", 0) + 1
    return {"ok": True, "text": f"You plant a seed with {target.first} about {subject.first}. "
                                f"“{claim}” — they're already repeating it.",
            "rumor": {"id": rumor["id"], "claim": claim, "subject": subject.first}}


def act_dismiss_notifications(sim, action: dict) -> dict:
    _player(sim)
    for n in sim.notifications:
        n["read"] = True
    for thread in sim.threads.values():
        for m in thread.messages:
            m.read = True
    return {"ok": True, "text": "Notifications cleared."}


def act_journal(sim, action: dict) -> dict:
    p = _player(sim)
    return {"ok": True, "journal": list(reversed(p.flags.get("journal", [])[-60:]))}


def act_talk_begin(sim, action):
    npc = _npc(sim, action.get('npc_id'))
    _require_near_npc(sim, npc)
    lease = civic.begin_talk(sim, npc, action.get('session_id'))
    if not action.get('session_id'):
        conversation.hydrate(sim, npc)
        lease['history'] = npc.flags['conversation_history'][-8:]
    return lease


def act_talk_end(sim, action):
    ended = civic.end_talk(sim, session_id=action.get('session_id'), npc_id=action.get('npc_id'))
    return {'ok': True, 'ended': ended}


ACTIONS = {
    'talk_begin': act_talk_begin,
    'talk_keepalive': act_talk_begin,
    'talk_end': act_talk_end,
    'civic': civic.action,
    "move": act_move,
    "stop": act_stop,
    "speed": act_speed,
    "talk": act_talk,
    "intent": act_intent,
    "gift": act_gift,
    "buy": act_buy,
    "use_item": act_use_item,
    "activity": act_activity,
    "work": act_work,
    "sleep": act_sleep,
    "post": act_post,
    "like": act_like,
    "comment": act_comment,
    "message": act_message,
    "read_thread": act_read_thread,
    "call_start": act_call_start,
    "call_turn": act_call_turn,
    "call_end": act_call_end,
    "answer_call": act_answer_call,
    "decline_call": act_decline_call,
    "date_go": act_date_go,
    "investigate": act_investigate,
    "present_case": act_present_case,
    "challenge_rumor": act_challenge_rumor,
    "start_business": act_start_business,
    "stir": act_stir,
    "dismiss_notifications": act_dismiss_notifications,
}


def handle_action(sim, action: dict) -> dict:
    kind = str(action.get("type", "")).strip()
    if civic.busy(sim) and kind not in ('talk_end', 'dismiss_notifications'):
        raise SimError('Your shift is still finishing. Wait a few seconds.', 'busy', 423)
    if kind in ('move', 'work', 'sleep', 'call_start'):
        civic.end_talk(sim)
    handler = ACTIONS.get(kind)
    if handler is None:
        raise SimError(f"Unknown action '{kind}'.", "bad_action", 404)
    payload = {k: v for k, v in action.items() if k != "type"}
    result = handler(sim, payload)
    result.setdefault("ok", True)
    if kind in ('talk', 'intent', 'call_turn'):
        intent = result.get('intent', '')
        if result.get('accepted') is False:
            result['coaching'] = 'They declined. Accept it without arguing; give them space rather than repeating the same request.'
        elif result.get('accepted') and intent == 'ask_date':
            result['coaching'] = 'You both agreed to a date. Check your calendar, make time, and show up.'
        else:
            result['coaching'] = {
                'compliment': 'Keep compliments specific and sincere. Follow up with curiosity, not a string of praise.',
                'flirt': 'Pay attention to whether the warmth is mutual. Give them room to set the pace.',
                'deep': 'Make space for their answer, and share a little about yourself too.',
                'insult': 'Disrespect damages trust. If you crossed a line, own it without demanding forgiveness.',
                'apology': 'An apology is a start. Changed behaviour matters more than saying it repeatedly.',
                'gossip': 'Rumours are not facts. Respect privacy and check claims before repeating them.',
            }.get(intent, 'Listen for one thing in their reply and ask a genuine follow-up. Conversation works both ways.')
    result["action"] = kind
    return result
