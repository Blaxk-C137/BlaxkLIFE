"""Bounded neighbourhood encounters, social leases and persistent consequences.

All crime is fictional/abstract; no real weapons/drug instructions. Targets are
selected by proximity/disputes, never demographics. Death is permanent, including
story actors. Presentation actors are distinct from the resident population.
"""

from __future__ import annotations

import math
import time

from blxverse.engine.models import new_id

SITES = {"hospital", "graveyard", "police", "barracks", "black_market"}
CHAT = {
    "music": [
        ("That song is stuck in my head again.", "Same. The chorus gets me every time."),
        ("Vinyl Corner got anything good?", "A few gems. We should have a look."),
    ],
    "food": [
        ("Have you eaten yet?", "Not yet. I could absolutely go for something warm."),
        ("Coffee or actual lunch?", "Actual lunch. Coffee cannot keep winning."),
    ],
    "work": [
        ("Long shift today?", "A little. I am claiming the sofa afterwards."),
        ("How is work going?", "Busy, but at least the playlist is decent."),
    ],
    "weather": [("This breeze is saving my afternoon.", "Right? Finally a reason to walk the long way.")],
    "community": [("See you around the square later?", "Probably. Save me a seat if you get there first.")],
    "sports": [("Did you catch the match?", "Only the end. Apparently I missed everything.")],
    "gossip": [("Anything new around here?", "Just the usual. I am trying to mind my business today.")],
}


def state(sim):
    c = sim.world_flags.setdefault("civic", {})
    c.setdefault("version", 1)
    c.setdefault("memorials", [])
    c.setdefault("incidents", [])
    c.setdefault("actors", [])
    c.setdefault("businesses", {})
    c.setdefault("heat", 0)
    c.setdefault("next_crime", sim.minute + 240)
    c.setdefault("next_raid", sim.minute + 1440)
    c.setdefault("next_dispute", sim.minute + 90)
    c.setdefault("last_social", -1)
    return c


def init(sim):
    c = state(sim)
    if not c.get("patrols_seeded"):
        for kind, site, color in [("police", "police", "#3468a6"), ("soldier", "barracks", "#61784c")]:
            for i in range(2):
                c["actors"].append(actor(sim, kind, site, i, color))
        c["patrols_seeded"] = True
    # A dead resident must never return through an old cast migration.
    dead = {m["id"] for m in c["memorials"]}
    sim.npcs = [n for n in sim.npcs if n.id not in dead]
    for nid in dead:
        sim.by_id.pop(nid, None)


def actor(sim, kind, site, index=0, color="#44475a"):
    from blxverse.content.locations import LOCATION_BY_ID
    from blxverse.engine.sim import nearest_walkable

    loc = LOCATION_BY_ID[site]
    x, y = nearest_walkable(loc["x"] + 40 + index * 44, loc["y"] + loc["h"] + 36)
    return {
        "id": new_id(kind),
        "kind": kind,
        "first": {"police": "Officer", "soldier": "Soldier", "bandit": "Bandit", "thief": "Thief"}[kind],
        "x": x,
        "y": y,
        "route": [],
        "site": site,
        "armed": kind in ("bandit", "soldier", "police"),
        "status": "at",
        "next_patrol": sim.minute + 8,
        "look": {
            "skin": "#b77b54",
            "hair": "#241a15",
            "outfit": color,
            "accent": "#ced5df",
            "hairStyle": "short",
            "accessory": "cap",
            "height": 1,
        },
    }


def engaged(sim, npc):
    s = sim.world_flags.get("conversation")
    return bool(s and s["npc_id"] == npc.id and s["expires"] > time.time())


def held(sim, npc):
    return (
        engaged(sim, npc)
        or (
            npc.flags.get("ambient_hold", 0) > time.time()
            and npc.flags.get("ambient_game_until", 0) > sim.minute
        )
        or npc.flags.get("hospital_until", 0) > sim.minute
    )


def begin_talk(sim, npc, session_id=None):
    from blxverse.engine.sim import SimError

    if npc.flags.get("refused_until", 0) > sim.minute:
        raise SimError(f"{npc.first} needs space. They are not ready to talk.", "needs_space", 422)
    old = sim.world_flags.get("conversation")
    if session_id and (
        not old or old["expires"] <= time.time() or old["id"] != session_id or old["npc_id"] != npc.id
    ):
        raise SimError("That conversation has ended.", "session_ended", 409)
    if old and old["npc_id"] != npc.id:
        end_talk(sim, session_id=old["id"])
    if not old or old["expires"] <= time.time() or old["npc_id"] != npc.id:
        old = {"id": new_id("conversation"), "npc_id": npc.id, "started": sim.minute}
    old["expires"] = time.time() + 20
    sim.world_flags["conversation"] = old
    npc.flags.pop("ambient_hold", None)
    sim.stop_player()
    return {"ok": True, "session_id": old["id"], "npc_id": npc.id}


def end_talk(sim, session_id=None, npc_id=None, reason="goodbye"):
    s = sim.world_flags.get("conversation")
    if s and (not session_id or s["id"] == session_id) and (not npc_id or s["npc_id"] == npc_id):
        sim.world_flags.pop("conversation", None)
        npc = sim.npc(s["npc_id"])
        if npc:
            npc.flags.pop("engaged_until", None)
            npc.flags.pop("ambient_hold", None)
            if reason == "leave":
                npc.flags["refused_until"] = sim.minute + 60
                npc.flags["flee_until"] = sim.minute + 12
                from blxverse.engine.sim import home_xy

                x, y = home_xy(npc.home_id)
                npc.target = {
                    "x": x,
                    "y": y,
                    "loc": "home",
                    "activity": "taking some space",
                    "arrival_status": "at",
                    "kind": "enter_home",
                }
                npc.status = "walking"
                sim._npc_paths.pop(npc.id, None)
        return True
    return False


def speak(sim, npc, text, *, delay=0, duration=3.2, kind="chatter"):
    now = time.time()
    npc.flags["speech"] = {
        "id": new_id("speech"),
        "npc_id": npc.id,
        "text": str(text)[:104],
        "starts": now + delay,
        "expires": now + delay + duration,
        "kind": kind,
    }


def pair_chat(sim, a, b, topic="work"):
    if any(held(sim, n) or sim._indoors(n) for n in (a, b)) or math.hypot(a.x - b.x, a.y - b.y) > 115:
        return False
    lines = sim.hub.stream("street-chatter").choice(CHAT.get(topic, CHAT["work"]))
    speak(sim, a, lines[0])
    speak(sim, b, lines[1], delay=3.3)
    until = time.time() + 6.6
    a.flags["ambient_hold"] = b.flags["ambient_hold"] = until
    a.flags["ambient_game_until"] = b.flags["ambient_game_until"] = sim.minute + 6.6 * max(1, sim.speed)
    return True


def realtime(sim):
    s = sim.world_flags.get("conversation")
    if s and (s["expires"] <= time.time() or not sim.npc(s["npc_id"])):
        end_talk(sim)
    p = sim.player
    if not p:
        return
    c = state(sim)
    if time.time() < c.get("greet_after", 0):
        return
    for n in sim.npcs:
        dist = math.hypot(n.x - p.x, n.y - p.y)
        was = n.flags.get("greeting_in_range", False)
        n.flags["greeting_in_range"] = dist < 160
        if dist >= 160 or was or sim._indoors(n) or held(sim, n):
            continue
        r = sim.rel(n.id, "player")
        if (
            p.reputation >= 45
            and r.get("trust", 0) >= 30
            and r.get("affinity", 0) >= 12
            and r.get("familiarity", 0) >= 8
            and r.get("tension", 0) < 35
            and time.time() >= n.flags.get("greet_after", 0)
        ):
            name = p.name.split()[0]
            line = sim.hub.stream("passby").choice(
                [
                    f"Hey {name}! Good seeing you.",
                    f"{name}! Hope your day is treating you well.",
                    f"Looking well, {name}. Catch you later!",
                    f"Hey {name}—take care out there.",
                ]
            )
            speak(sim, n, line, kind="greeting")
            n.flags["greet_after"] = time.time() + 90
            c["greet_after"] = time.time() + 8
            break


def health(npc):
    return int(npc.flags.get("health", 100))


def injure(sim, npc, amount, cause, location=None):
    if not sim.npc(npc.id):
        return "deceased"
    npc.flags["health"] = max(0, health(npc) - max(0, int(amount)))
    if health(npc) <= 0:
        die(sim, npc, cause, location or npc.location_id)
        return "deceased"
    if health(npc) < 65:
        if npc.flags.get('meeting', {}).get('status') in ('scheduled', 'travelling', 'waiting'):
            npc.flags['meeting']['status'] = 'cancelled for hospital care'
        end_talk(sim, npc_id=npc.id, reason="injury")
        npc.flags["hospital_until"] = sim.minute + 180
        npc.flags["injury_cause"] = cause
        npc.target = None
        sim._npc_paths.pop(npc.id, None)
        # Ambulance transfer is an explicit medical transport, not a walking route.
        from blxverse.content.locations import LOCATION_BY_ID
        from blxverse.engine.sim import nearest_walkable

        site = LOCATION_BY_ID["hospital"]
        npc.x, npc.y = nearest_walkable(site["x"] + site["w"] / 2, site["y"] + site["h"] + 24)
        npc.location_id, npc.status, npc.activity = "hospital", "recovering", "receiving treatment"
        sim.note("Hospital admission", f"{npc.first} is receiving treatment after {cause}.", "medical")
        return "hospital"
    return "wounded"


def die(sim, npc, cause, location):
    c = state(sim)
    if any(m["id"] == npc.id for m in c["memorials"]):
        return
    end_talk(sim, npc_id=npc.id, reason="death")
    npc.flags["health"], npc.flags["deceased"] = 0, True
    record = {
        "id": npc.id,
        "name": npc.name,
        "first": npc.first,
        "age": npc.age,
        "minute": sim.minute,
        "cause": str(cause)[:120],
        "location": location,
        "look": npc.look,
        "resident": sim._npc_save(npc),
    }
    c["memorials"].append(record)
    sim.npcs = [n for n in sim.npcs if n.id != npc.id]
    sim.by_id.pop(npc.id, None)
    sim._npc_paths.pop(npc.id, None)
    sim.world_flags["pending_messages"] = [
        m for m in sim.world_flags.get("pending_messages", []) if m["npc_id"] != npc.id
    ]
    for d in sim.world_flags.get("date_offers", []):
        if d["npc_id"] == npc.id and d["status"] == "accepted":
            d["status"] = "cancelled"
    for call in sim.calls.values():
        if call.get("npc_id") == npc.id:
            call["status"] = "ended"
    pending = sim.world_flags.get("pending_call")
    if pending and pending.get("npc_id") == npc.id:
        sim.world_flags["pending_call"] = None
    for key, relationship in sim.rels.items():
        if npc.id in key.split("|") and "dating" in relationship.get("flags", []):
            relationship["flags"] = [f for f in relationship["flags"] if f != "dating"] + ["bereaved"]
    for other in sim.npcs:
        for plan in other.plans:
            if plan.get("with") == npc.id and not plan.get("done"):
                plan.update(done=True, cancelled="death")
        if sim.rel(other.id, npc.id).get("affinity", 0) > 15:
            other.mood.valence = max(-100, other.mood.valence - 16)
    if npc.first in ("Zara", "Daniel", "Femi"):
        sim.world_flags.setdefault("chain", {}).update(stage=6, ended_by_death=npc.id, started=True)
        for arc in sim.arcs:
            if arc.kind == "chain":
                arc.status = "faded"
                arc.summary = (
                    f"This story ended after {npc.first} died. Their memorial remains at Juniper Rest."
                )
        for case in sim.cases:
            if case.status == "open":
                case.status = "unsolved"
    sim.add_event(
        kind="death",
        actor=npc.id,
        targets=[],
        location=location,
        facts={"cause": cause, "non_graphic": True},
        witnesses=[],
        visibility="public",
        summary=f"{npc.name} died after {cause}. A permanent memorial was placed at Juniper Rest.",
    )
    sim.note("A life remembered", f"{npc.name} has died. Visit Juniper Rest to pay respects.", "memorial")
    sim._dirty = True


def fight(sim, a, b, *, cause="a heated dispute"):
    c = state(sim)
    if sim._indoors(a) or sim._indoors(b) or math.hypot(a.x - b.x, a.y - b.y) > 135:
        return None
    if any(n.flags.get("fight_after", 0) > sim.minute or held(sim, n) for n in (a, b)):
        return None
    for n in (a, b):
        n.flags["fight_after"] = sim.minute + 180
        n.flags["combat_until"] = time.time() + 5
        n.flags["ambient_hold"] = time.time() + 5
        n.flags["ambient_game_until"] = sim.minute + 5 * max(1, sim.speed)
        speak(sim, n, "Back off!" if n is a else "Enough. I am calling for help.", kind="conflict")
    ev = sim.add_event(
        kind="fight",
        actor=a.id,
        targets=[b.id],
        location=a.location_id,
        facts={"cause": cause, "non_graphic": True},
        witnesses=[],
        visibility="public",
        summary=f"{a.first} and {b.first} fought after {cause}. Police were alerted.",
    )
    rng = sim.hub.stream("civic-fights")
    victim = rng.choice([a, b])
    injure(sim, victim, 110 if rng.random() < 0.02 else rng.randint(20, 46), cause)
    c["incidents"].append(
        {
            "id": new_id("dispute"),
            "kind": "dispute",
            "location": a.location_id,
            "phase": "police responding",
            "started": sim.minute,
            "ends": sim.minute + 20,
            "x": a.x,
            "y": a.y,
            "victims": [a.id, b.id],
        }
    )
    c["incidents"] = c["incidents"][-12:]
    return ev


def _route(sim, a, x, y, blockers=()):
    from blxverse.engine.sim import find_path, nearest_walkable

    x, y = nearest_walkable(x, y)
    a["route"] = [list(p) for p in find_path(a["x"], a["y"], x, y, blockers=blockers)]
    a["status"] = "walking" if a["route"] else "at"
    a["goal"] = [x, y]


def _move_actors(sim, dt):
    from blxverse.engine.sim import walkable

    c = state(sim)
    live = [i for i in c["incidents"] if i["phase"] not in ("resolved", "retreated")]
    for a in c["actors"][:16]:
        if a["kind"] in ("police", "soldier") and live and sim.minute >= a.get("dispatch_after", 0):
            incident = live[-1]
            if a.get("responding") != incident["id"]:
                _route(sim, a, incident["x"] + (22 if a["kind"] == "police" else -22), incident["y"] + 100)
                a["responding"] = incident["id"]
        elif a["kind"] in ("police", "soldier") and not live and sim.minute >= a.get("next_patrol", 0):
            from blxverse.engine.sim import venue_spot

            n = sim.npcs[0] if sim.npcs else None
            if n:
                loc = sim.hub.stream("patrols").choice(["square", "grocery", "park", a["site"]])
                _route(sim, a, *venue_spot(n, loc))
            a["next_patrol"] = sim.minute + 60
            a.pop("responding", None)
        before = (a["x"], a["y"])
        budget = min(2, dt) * (75 if a["kind"] in ("bandit", "thief") else 85)
        while a["route"] and budget > 0:
            x, y = a["route"][0]
            dx, dy = x - a["x"], y - a["y"]
            dist = math.hypot(dx, dy)
            if dist < 0.01:
                a["route"].pop(0)
                continue
            step = min(5, budget, dist)
            nx, ny = a["x"] + dx / dist * step, a["y"] + dy / dist * step
            if not walkable(nx, ny):
                a["route"] = []
                break
            # Presentation actors yield to resident bodies too.
            if any(not sim._indoors(n) and math.hypot(n.x - nx, n.y - ny) < 23 for n in sim.npcs):
                break
            if any(o is not a and math.hypot(o["x"] - nx, o["y"] - ny) < 23 for o in c["actors"]):
                break
            a["x"], a["y"] = nx, ny
            budget -= step
        a["status"] = "walking" if a["route"] else "at"
        a["stalled"] = (
            a.get("stalled", 0) + dt if a["route"] and math.dist(before, (a["x"], a["y"])) < 0.1 else 0
        )
        if a["stalled"] >= 3 and a.get("goal"):
            blockers = tuple(
                (n.x, n.y)
                for n in sim.npcs
                if not sim._indoors(n) and math.hypot(n.x - a["x"], n.y - a["y"]) < 220
            )
            blockers += tuple(
                (o["x"], o["y"])
                for o in c["actors"]
                if o is not a and math.hypot(o["x"] - a["x"], o["y"] - a["y"]) < 220
            )
            _route(sim, a, *a["goal"], blockers=blockers)
            a["stalled"] = 0


def start_incident(sim, kind="raid", location="square"):
    from blxverse.content.locations import LOCATION_BY_ID
    from blxverse.engine.sim import nearest_walkable

    c = state(sim)
    if any(i["phase"] not in ("resolved", "retreated") and i["kind"] == kind for i in c["incidents"]):
        return None
    site = LOCATION_BY_ID[location]
    x, y = nearest_walkable(site["x"] + site["w"] / 2, site["y"] + site["h"] + 38)
    incident = {
        "id": new_id(kind),
        "kind": kind,
        "location": location,
        "phase": "advancing",
        "started": sim.minute,
        "ends": sim.minute + 50,
        "x": x,
        "y": y,
        "victims": [],
        "actors": [],
    }
    for i in range(4 if kind == "raid" else 1):
        a = actor(sim, "bandit" if kind == "raid" else "thief", "black_market", i, "#584958")
        # Four armed raiders enter in a real 2x2 square formation, not one stacked dot.
        a["x"], a["y"] = nearest_walkable(1780 + (i % 2) * 44, 540 + (i // 2) * 44)
        a["incident"] = incident["id"]
        a["expires"] = sim.minute + 85
        a["formation_slot"] = i
        _route(sim, a, x + (i % 2) * 42 - 21, y + (i // 2) * 42 - 21)
        c["actors"].append(a)
        incident["actors"].append(a["id"])
    for a in c["actors"]:
        if a["kind"] in ("police", "soldier"):
            a["dispatch_after"] = sim.minute + (5 if kind == "raid" else 10)
    c["incidents"].append(incident)
    c["incidents"] = c["incidents"][-12:]
    sim.note(
        "Armed raid" if kind == "raid" else "Theft reported",
        f"{'A four-person armed squad is approaching' if kind == 'raid' else 'A thief was spotted near'} {site['name']}. Keep your distance or alert police.",
        "safety",
    )
    sim._dirty = True
    return incident


def _resolve_incident(sim, inc):
    c = state(sim)
    rng = sim.hub.stream("civic-crime")
    responders = [
        a
        for a in c["actors"]
        if a["kind"] in ("police", "soldier") and math.hypot(a["x"] - inc["x"], a["y"] - inc["y"]) < 180
    ]
    victims = [
        n
        for n in sim.npcs
        if not sim._indoors(n) and math.hypot(n.x - inc["x"], n.y - inc["y"]) < 220 and not engaged(sim, n)
    ]
    if inc["kind"] == "dispute":
        if inc.get("player_fault"):
            fine = min(35, sim.player.wallet)
            sim.player_spend(fine, "fine", "Police fine for a public fight")
            sim.note("Police response", f"You were fined {fine} BLX after the public fight.", "safety")
        inc["phase"] = "resolved"
        return
    if inc["kind"] == "theft" and victims:
        n = rng.choice(victims)
        if not responders:
            stolen = min(n.wallet, rng.randint(8, 24))
            n.wallet -= stolen
            inc["stolen"], inc["victim"] = stolen, n.id
            if rng.random() < 0.12:
                injure(sim, n, 110 if rng.random() < 0.03 else 40, "a theft dispute")
        inc["victims"] = [n.id]
    elif inc["kind"] == "raid":
        rng.shuffle(victims)
        for n in victims[: max(1, 3 - len(responders))]:
            fatal = rng.random() < (0.025 if responders else 0.10)
            result = injure(sim, n, 110 if fatal else rng.randint(20, 48), "an armed raid", inc["location"])
            inc["victims"].append(n.id)
            if result == "deceased":
                break  # Never mass-cull the town in one encounter.
    inc["phase"] = "retreating"
    inc["retreat_at"] = sim.minute + 18
    for a in c["actors"]:
        if a.get("incident") == inc["id"]:
            _route(
                sim,
                a,
                1840 + (a.get("formation_slot", 0) % 2) * 20,
                580 + (a.get("formation_slot", 0) // 2) * 44,
            )
            a["expires"] = sim.minute + 20
    sim.add_event(
        kind=inc["kind"],
        actor="bandits" if inc["kind"] == "raid" else "thief",
        targets=inc["victims"],
        location=inc["location"],
        facts={"non_graphic": True, "responders": len(responders)},
        witnesses=[],
        visibility="public",
        summary=f"{('Responders ended an armed raid' if responders else 'An armed squad withdrew') if inc['kind'] == 'raid' else ('Police interrupted a theft' if responders else 'A theft was reported')} at {sim.location_names[inc['location']]}.",
    )
    sim.note(
        "Incident update",
        f"{sim.location_names[inc['location']]}: responders are securing the area. Check the hospital for injuries.",
        "safety",
    )


def step(sim, dt):
    c = state(sim)
    for n in sim.npcs:
        until = n.flags.get("hospital_until")
        if until and sim.minute >= until:
            n.flags.pop("hospital_until", None)
            n.flags["health"] = 100
            n.flags.pop("block_key", None)
            n.flags.pop("ambient_hold", None)
            n.status, n.activity = "at", "leaving hospital"
    _move_actors(sim, dt)
    for inc in c["incidents"]:
        if inc["phase"] == "advancing":
            attackers = [a for a in c["actors"] if a["id"] in inc.get("actors", [])]
            if attackers and all(math.hypot(a["x"] - inc["x"], a["y"] - inc["y"]) < 95 for a in attackers):
                inc["phase"] = "confrontation"
                inc["ends"] = sim.minute + 8
                for a in attackers:
                    a["combat_until"] = sim.minute + 8
                session = sim.world_flags.get("conversation")
                partner = sim.npc(session["npc_id"]) if session else None
                if partner and math.hypot(partner.x - inc["x"], partner.y - inc["y"]) < 220:
                    speak(sim, partner, "We need to get somewhere safe. Now.", kind="conflict")
                    end_talk(sim, npc_id=partner.id, reason="leave")
            elif sim.minute >= inc["ends"]:
                # An unreachable raid aborts; never resolve violence remotely.
                inc["phase"] = "retreating"
                inc["retreat_at"] = sim.minute + 12
                for a in attackers:
                    _route(sim, a, 1840, 600 + a.get("formation_slot", 0) * 25)
                    a["expires"] = sim.minute + 14
        elif inc["phase"] in ("confrontation", "police responding") and sim.minute >= inc["ends"]:
            _resolve_incident(sim, inc)
        elif inc["phase"] == "retreating" and sim.minute >= inc["retreat_at"]:
            inc["phase"] = "resolved"
    c["actors"] = [a for a in c["actors"] if a.get("expires", float("inf")) > sim.minute]
    if sim.minute >= c["next_crime"]:
        if 7 <= sim.hour_of_day < 22:
            start_incident(sim, "theft", sim.hub.stream("crime-site").choice(["cafe", "grocery", "square"]))
        c["next_crime"] = sim.minute + sim.hub.stream("crime-cadence").uniform(600, 1000)
    if sim.minute >= c["next_raid"]:
        if 8 <= sim.hour_of_day < 21:
            start_incident(sim, "raid", "square")
        c["next_raid"] = sim.minute + sim.hub.stream("raid-cadence").uniform(1800, 3000)
    if sim.minute >= c["next_dispute"]:
        crew = [n for n in sim.npcs if not sim._indoors(n) and not held(sim, n)]
        for a in crew:
            b = next(
                (
                    b
                    for b in crew
                    if b is not a
                    and sim.rel(a.id, b.id).get("tension", 0) >= 65
                    and math.hypot(a.x - b.x, a.y - b.y) < 110
                ),
                None,
            )
            if b:
                fight(sim, a, b)
                break
        c["next_dispute"] = sim.minute + 120
    for key, biz in c["businesses"].items():
        if biz["status"] == "operating" and sim.minute >= biz["next_income"]:
            rng = sim.hub.stream("black-market-risk")
            if rng.random() < 0.18 + c["heat"] / 400:
                biz["status"] = "seized"
                biz["balance"] = 0
                sim.note(
                    "Police seizure",
                    f"The {key} business was shut down. Its stake and stock were confiscated.",
                    "safety",
                )
            elif biz["status"] == "operating":
                biz["balance"] += 45 if key == "drugs" else 38
                c["heat"] = min(100, c["heat"] + 8)
            biz["next_income"] = sim.minute + 480
    c["heat"] = max(0, c["heat"] - dt / 180)


def busy(sim):
    b = sim.player.flags.get("busy") if sim.player else None
    if b and b["until"] > time.time():
        return {**b, "remaining_seconds": round(b["until"] - time.time(), 2)}
    if b:
        sim.player.flags.pop("busy", None)
    return None


def action(sim, data):
    from blxverse.engine.actions import _require_near_loc, _require_near_npc
    from blxverse.engine.sim import SimError

    c = state(sim)
    op = str(data.get("op", ""))
    if op == "report":
        for inc in c["incidents"]:
            if inc["phase"] not in ("resolved", "retreated"):
                for a in c["actors"]:
                    if a["kind"] in ("police", "soldier"):
                        a["dispatch_after"] = sim.minute
        sim.player.reputation = min(
            100, sim.player.reputation + (1 if c.get("last_report", -999) + 60 < sim.minute else 0)
        )
        c["last_report"] = sim.minute
        return {"text": "Police dispatch received your report. Stay clear; units are responding."}
    if op == "treatment":
        _require_near_loc(sim, "hospital")
        cost = min(sim.player.wallet, 18)
        sim.player_spend(cost, "medical", "Hospital treatment")
        sim.player.flags["health"] = 100
        sim.player.energy = min(100, sim.player.energy + 30)
        return {"text": f"You received treatment for {cost} BLX. Health restored."}
    if op == "respects":
        _require_near_loc(sim, "graveyard")
        sim.player_memory("Paid respects at Juniper Rest.", kind="memorial", valence=-0.1)
        return {"text": "You spend a quiet moment remembering the people of BlaxkVille."}
    if op in ("business_start", "business_collect", "business_close"):
        _require_near_loc(sim, "black_market")
        category = data.get("category")
        if category not in ("guns", "drugs"):
            raise SimError("Choose a fictional business category.", "bad_request", 422)
        if op == "business_start":
            if c["businesses"].get(category, {}).get("status") == "operating":
                raise SimError("You already run that business.", "already_owned", 422)
            cost = 220 if category == "guns" else 160
            sim.player_spend(cost, "business", f"Fictional {category} business stake")
            c["businesses"][category] = {"status": "operating", "balance": 0, "next_income": sim.minute + 480}
            c["heat"] = min(100, c["heat"] + 15)
            return {
                "text": f"{category.title()} business opened. Abstract stock only; profit is risky, and police can seize it."
            }
        biz = c["businesses"].get(category)
        if not biz or biz["status"] != "operating":
            raise SimError("That business is not operating.", "unavailable", 422)
        pay = biz["balance"]
        biz["balance"] = 0
        if pay:
            sim.player_earn(pay, "business", f"Fictional {category} business proceeds")
        if op == "business_close":
            biz["status"] = "closed"
        return {
            "text": f"{pay} BLX collected."
            + (" Business closed; no stake refund." if op == "business_close" else "")
        }
    if op == "confront":
        npc = sim.npc(str(data.get("npc_id", "")))
        _require_near_npc(sim, npc)
        if npc.flags.get("fight_after", 0) > sim.minute:
            raise SimError("They have already left that dispute behind. Give them space.", "cooldown", 422)
        end_talk(sim, reason="conflict")
        npc.flags.pop("ambient_hold", None)
        npc.flags["combat_until"] = time.time() + 5
        npc.flags["fight_after"] = sim.minute + 180
        speak(sim, npc, "No. Back off! I am calling the police.", kind="conflict")
        rng = sim.hub.stream("player-dispute")
        injure(sim, npc, 110 if rng.random() < 0.015 else rng.randint(20, 42), "a dispute with the player")
        sim.player.flags["health"] = max(10, sim.player.flags.get("health", 100) - rng.randint(12, 30))
        sim.player.reputation = max(0, sim.player.reputation - 12)
        c["heat"] = min(100, c["heat"] + 30)
        c["incidents"].append(
            {
                "id": new_id("dispute"),
                "kind": "dispute",
                "location": npc.location_id,
                "phase": "police responding",
                "started": sim.minute,
                "ends": sim.minute + 20,
                "x": sim.player.x,
                "y": sim.player.y,
                "victims": [npc.id],
                "player_fault": True,
            }
        )
        c["incidents"] = c["incidents"][-12:]
        return {
            "text": "The dispute turned physical. You were wounded, lost reputation, and police are responding. There can be permanent consequences."
        }
    raise SimError("Unknown neighbourhood action.", "bad_action", 404)


def payload(sim):
    c = state(sim)
    now = time.time()
    bubbles = []
    for n in sim.npcs:
        b = n.flags.get("speech")
        if b and b["expires"] > now:
            bubbles.append(
                {k: b[k] for k in ("id", "npc_id", "text", "kind")}
                | {"starts_in": round(b["starts"] - now, 2), "remaining": round(b["expires"] - now, 2)}
            )
    s = sim.world_flags.get("conversation")
    return {
        "actors": [
            {k: v for k, v in a.items() if k != "route"}
            | {
                "route": [{"x": round(x, 1), "y": round(y, 1)} for x, y in a["route"][:48]],
                "walk_speed": (75 if a["kind"] in ("bandit", "thief") else 85) * sim.speed,
                "combat": a.get("combat_until", 0) > sim.minute,
                "indoors": False,
                "name": a["first"],
                "health": 100,
                "role": a["kind"],
            }
            for a in c["actors"][:16]
        ],
        "bubbles": bubbles[:6],
        "incidents": [{k: v for k, v in i.items() if k != "actors"} for i in c["incidents"][-8:]],
        "memorials": [{k: v for k, v in m.items() if k != "resident"} for m in c["memorials"]],
        "patients": [
            {
                "id": n.id,
                "first": n.first,
                "health": health(n),
                "remaining_minutes": round(n.flags["hospital_until"] - sim.minute),
            }
            for n in sim.npcs
            if n.flags.get("hospital_until", 0) > sim.minute
        ],
        "heat": round(c["heat"]),
        "businesses": c["businesses"],
        "busy": busy(sim),
        "conversation": {"npc_id": s["npc_id"], "session_id": s["id"]} if s and s["expires"] > now else None,
        "player_health": sim.player.flags.get("health", 100) if sim.player else 100,
        "dialogue": __import__("blxverse.engine.llm", fromlist=["status"]).status(),
    }
