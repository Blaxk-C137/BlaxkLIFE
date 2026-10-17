"""World Director & Story Director.

Creates and advances causal story material from real world state:
- the scripted five-day chain from the design brief (section 6)
- emergent arcs: friendships, business plans, birthdays, rivalries, romance
- ambient neighborhood life (open mic nights, markets, movie nights)

Constraints enforced here:
- prerequisites must be satisfied before an event fires
- knowledge is limited to witnesses / communication / evidence
- identical conflicts are not repeated constantly
- peaceful and joyful events are scheduled too, not only drama
"""

from __future__ import annotations

from blxverse import config
from blxverse.engine.chaos import trigger_clash
from blxverse.engine.models import Arc, Case, new_id
from blxverse.engine.rng import clamp

CHAIN_STAGES = [
    "A new resident arrives",
    "An unexpected friendship",
    "A rumor takes hold",
    "The square gets loud",
    "The truth comes out",
]


# ---------------------------------------------------------------------------
# Five-day chain (design section 6)
# ---------------------------------------------------------------------------
def _chain(sim) -> dict:
    return sim.world_flags.setdefault("chain", {"started": False, "day": -1, "stage": 0})


def advance_chain(sim) -> None:
    chain = _chain(sim)
    day = sim.day_index
    chain["day"] = day
    if not chain.get("started"):
        if day < 0:
            return
        _chain_day0(sim, chain)
        return
    hour = sim.hour_of_day
    if chain.get("stage", 0) < 2 and (day > 1 or (day == 1 and hour >= 10.0)):
        _chain_day1(sim, chain)
    if chain.get("stage", 0) < 3 and (day > 2 or (day == 2 and hour >= 10.0)):
        _chain_day2(sim, chain)
    if chain.get("stage", 0) < 4 and (day > 3 or (day == 3 and hour >= 18.0)):
        _chain_day3(sim, chain)
    if chain.get("stage", 0) < 5 and (day > 4 or (day == 4 and hour >= 16.0)):
        _chain_day4(sim, chain)
    if chain.get("stage", 0) < 6 and (day > 5 or (day == 5 and hour >= 12.0)):
        _chain_day5(sim, chain)


def _arc(sim) -> Arc | None:
    return next((a for a in sim.arcs if a.kind == "chain"), None)


def _ensure_arc(sim, title: str) -> Arc:
    arc = _arc(sim)
    if arc is None:
        arc = Arc(
            id=new_id("arc"), kind="chain", title=title,
            summary="Zara moves to Bellwether, meets Daniel, and gets caught in a false accusation that the whole block has an opinion about.",
            actors=[], stages=CHAIN_STAGES, created=sim.minute, last_minute=sim.minute,
        )
        sim.arcs.append(arc)
    return arc


def _chain_day0(sim, chain: dict) -> None:
    zara = sim.npc_by_first("Zara")
    landlord = sim.npc_by_flag("landlord")
    if not zara or not landlord:
        return
    chain["started"] = True
    chain["stage"] = 1
    arc = _ensure_arc(sim, "A New Note in Bellwether")
    arc.actors = [zara.id, landlord.id]
    arc.stage = 0

    sim.force_move(zara, "home")
    event = sim.add_event(
        kind="landlord_dispute", actor=landlord.id, targets=[zara.id],
        location="home", facts={"cause": "an overdue rent increase and a leaking ceiling",
                                "newcomer": True},
        witnesses=[], visibility="participants",
        summary="Femi confronted Zara about rent while the ceiling dripped into a bucket.",
    )
    sim.remember(zara, event, importance=0.9, valence=-0.8, source="participated")
    sim.remember(landlord, event, importance=0.6, valence=-0.3, source="participated")
    sim.adjust_rel(zara.id, landlord.id, tension=6, trust=-4)
    sim.adjust_rel(landlord.id, zara.id, tension=5, trust=-3)
    zara.mood.stress = clamp(zara.mood.stress + 18, 0, 100)
    zara.mood.valence = clamp(zara.mood.valence - 14, -100, 100)

    sim.push_feed(
        author_id=zara.id,
        text="Day one in Bellwether: my ceiling is leaking, my landlord communicates in sighs, and a pigeon watched the whole conversation. 5/10, would move again. 🎹",
        mood="tired", tag="life", loc="home",
    )
    sim.add_notice(
        kind="alert", title="Rent dispute on Juniper Row",
        body="A new resident and a landlord disagree about repairs and an upcoming rent increase. No one was hurt; the bucket is doing its best.",
        location="home",
    )
    sim.note("New neighbor", "Zara Adeyemi just moved in. The whole block is curious.", kind="story")
    sim.log_metric("chain_day0", {"zara": zara.id, "landlord": landlord.id})


def _chain_day1(sim, chain: dict) -> None:
    zara = sim.npc_by_first("Zara")
    daniel = sim.npc_by_first("Daniel")
    if not zara or not daniel:
        return
    if chain.get("stage", 0) < 2:
        chain["stage"] = 2
        arc = _ensure_arc(sim, "A New Note in Bellwether")
        arc.stage = 1
        arc.last_minute = sim.minute
        arc.actors = sorted(set(arc.actors + [zara.id, daniel.id]))
        sim.force_move(zara, "cafe")
        sim.force_move(daniel, "cafe")
        event = sim.add_event(
            kind="friendship", actor=zara.id, targets=[daniel.id], location="cafe",
            facts={"topic": "music and design", "spontaneous": True},
            witnesses=[], visibility="public",
            summary="Zara and Daniel met at Two Rivers Cafe and discovered a shared love of music.",
        )
        sim.remember(zara, event, importance=0.7, valence=0.7, source="participated")
        sim.remember(daniel, event, importance=0.6, valence=0.6, source="participated")
        sim.adjust_rel(zara.id, daniel.id, familiarity=26, affinity=24, trust=10)
        sim.adjust_rel(daniel.id, zara.id, familiarity=24, affinity=22, trust=9)
        sim.set_rel_flag(zara.id, daniel.id, "friend", True)
        sim.set_rel_flag(daniel.id, zara.id, "friend", True)
        zara.mood.valence = clamp(zara.mood.valence + 20, -100, 100)
        daniel.mood.valence = clamp(daniel.mood.valence + 12, -100, 100)
        sim.push_feed(
            author_id=zara.id,
            text="Met a designer at Two Rivers who knows more about Highlife records than I do. We talked for two hours. My coffee went cold. Worth it. ☕🎶",
            mood="hopeful", tag="friends", loc="cafe",
        )
        sim.note("A new friendship", "Zara and Daniel hit it off at the cafe.", kind="story")
        sim.log_metric("chain_day1", {"zara": zara.id, "daniel": daniel.id})


def _chain_day2(sim, chain: dict) -> None:
    if chain.get("stage", 0) >= 3:
        return
    zara = sim.npc_by_first("Zara")
    daniel = sim.npc_by_first("Daniel")
    if not zara or not daniel:
        return
    accuser = sim.pick_gossip_npc(exclude={zara.id, daniel.id})
    if not accuser:
        return
    chain["stage"] = 3
    chain["accuser"] = accuser.id
    arc = _ensure_arc(sim, "A New Note in Bellwether")
    arc.stage = 2
    arc.last_minute = sim.minute
    arc.actors = sorted(set(arc.actors + [accuser.id]))

    claim = "Daniel was seen walking off with the studio's brass microphone after hours"
    rumor = sim.add_rumor(
        claim=claim, subject_id=daniel.id, truth="false", origin_id=accuser.id,
        confidence=0.72, location="studio",
    )
    case = Case(
        id=new_id("case"), title="The Missing Brass Mic",
        description=(
            "The studio's brass microphone vanished after Tuesday night. A neighborhood claim points at "
            "Daniel, but there is no evidence yet — only a confident rumor and a very loud group chat."
        ),
        accuser=accuser.id, accused=daniel.id, item="the brass studio microphone",
        location="studio", status="open", created=sim.minute,
        helpful_evidence=[
            "studio: check the equipment locker and ask who closed up",
            "music_store: look for a repair intake receipt",
            "cafe: ask about Tuesday evening's orders",
        ],
    )
    sim.cases.append(case)
    daniel.mood.valence = clamp(daniel.mood.valence - 28, -100, 100)
    daniel.mood.stress = clamp(daniel.mood.stress + 30, 0, 100)
    daniel.mood.irritation = clamp(daniel.mood.irritation + 22, 0, 100)
    accuser.mood.excitement = clamp(accuser.mood.excitement + 15, 0, 100)

    sim.push_feed(
        author_id=accuser.id,
        text="I'm not saying anything. I'm just saying the studio's brass mic is missing and I saw who left last. Ask questions. 👀🎙️",
        mood="suspicious", tag="rumor", loc="studio",
    )
    sim.push_feed(
        author_id=zara.id,
        text="Everyone is suddenly a detective and nobody has receipts. Daniel literally helped me find my bus stop yesterday. That's my entire evidence file.",
        mood="protective", tag="friends", loc="cafe",
    )
    sim.add_notice(
        kind="alert", title="Studio equipment missing",
        body="A brass microphone is missing from Golden Hour Studio. Residents are asked to share information, not accusations. Neighborhood security has opened a file.",
        location="studio",
    )
    sim.note("A rumor spreads", f"{accuser.first} is telling anyone who'll listen that Daniel took studio equipment. No evidence — just confidence.", kind="story")
    sim.log_metric("chain_day2", {"accuser": accuser.id, "rumor": rumor["id"], "case": case.id})


def _chain_day3(sim, chain: dict) -> None:
    if chain.get("stage", 0) >= 4:
        return
    daniel = sim.npc_by_first("Daniel")
    zara = sim.npc_by_first("Zara")
    accuser = sim.npc(chain.get("accuser", "")) if chain.get("accuser") else None
    if not daniel or not accuser or not zara:
        return
    chain["stage"] = 4
    arc = _ensure_arc(sim, "A New Note in Bellwether")
    arc.stage = 3
    arc.last_minute = sim.minute
    case = next((c for c in sim.cases if c.accused == daniel.id), None)
    sim.force_move(daniel, "square")
    sim.force_move(accuser, "square")

    if case and case.status == "cleared":
        event = sim.add_event(
            kind="public_apology", actor=accuser.id, targets=[daniel.id], location="square",
            facts={"reason": "false accusation", "witnesses": "crowd"},
            witnesses=[zara.id], visibility="public",
            summary=f"{accuser.first} publicly apologized to Daniel at the square after the evidence cleared him.",
        )
        sim.remember(daniel, event, importance=0.8, valence=0.5, source="participated")
        sim.remember(accuser, event, importance=0.7, valence=-0.4, source="participated")
        sim.remember(zara, event, importance=0.7, valence=0.7, source="witnessed")
        sim.adjust_rel(daniel.id, accuser.id, tension=-16, trust=4)
        sim.adjust_rel(accuser.id, daniel.id, tension=-12)
        sim.push_feed(
            author_id=accuser.id,
            text="I was wrong about Daniel. Publicly, loudly, in front of the fountain. The mic was in the locker the whole time. I've apologized and I'm buying the coffee for a month.",
            mood="sheepish", tag="accountability", loc="square",
        )
        sim.add_notice(kind="news", title="Apology at the square",
                       body=f"{accuser.first} publicly apologized to Daniel. The block applauded and pretended it wasn't emotional.",
                       location="square")
        sim.note("A public apology", f"{accuser.first} cleared things up at the square. The block noticed.", kind="story")
    else:
        event = trigger_clash(
            sim, daniel, accuser, cause="a false accusation about a missing microphone",
            loc_label="Bellwether Square",
        )
        sim.force_move(zara, "square")
        sim.remember(zara, event, importance=0.8, valence=-0.3, source="witnessed")
        sim.push_feed(
            author_id=zara.id,
            text="A microphone is missing, but apparently the whole square is a courtroom now. The dust cloud had more evidence than the accusers. 🌀",
            mood="furious", tag="chaos", loc="square",
        )
        sim.note("The square gets loud", "Daniel and the accuser turned the square into a cartoon dust cloud. Security intervened.", kind="story")
    chain["stage"] = 4


def _chain_day4(sim, chain: dict) -> None:
    if chain.get("stage", 0) >= 5:
        return
    daniel = sim.npc_by_first("Daniel")
    zara = sim.npc_by_first("Zara")
    if not daniel or not zara:
        return
    chain["stage"] = 5
    arc = _ensure_arc(sim, "A New Note in Bellwether")
    arc.stage = 4
    arc.last_minute = sim.minute
    case = next((c for c in sim.cases if c.accused == daniel.id), None)
    if case and case.status == "cleared":
        arc.status = "resolved"
        arc.summary = "The rumor against Daniel collapsed under evidence. Zara's opinion of the block shifted — for better and for worse."
        sim.push_feed(
            author_id=daniel.id,
            text="The mic turned up. It was in the locker the whole time. I want to say thank you to the people who asked questions instead of repeating answers. That's the whole post.",
            mood="relieved", tag="accountability", loc="cafe",
        )
        sim.add_notice(kind="news", title="Case closed: the brass mic",
                       body="The microphone was recovered from the studio's own equipment locker. The accusation was false. The block is talking about how quickly a story can travel.",
                       location="studio")
        _shift_zara_opinion(sim, zara, cleared=True)
        sim.note("The truth comes out", "Daniel has been cleared. Zara's opinion of the neighborhood has changed.", kind="story")
    else:
        sim.note("The story is still open", "The rumor about Daniel is still spreading. If someone found evidence and shared it, the ending could change.", kind="story")
        arc.summary = "The rumor about Daniel is spreading faster than the truth. Someone should do something."
    sim.log_metric("chain_day4", {"cleared": bool(case and case.status == "cleared")})


def _chain_day5(sim, chain: dict) -> None:
    if chain.get("stage", 0) >= 6:
        return
    chain["stage"] = 6
    daniel = sim.npc_by_first("Daniel")
    zara = sim.npc_by_first("Zara")
    arc = _arc(sim)
    if not daniel or not zara or not arc:
        return
    case = next((c for c in sim.cases if c.accused == daniel.id), None)
    if case and case.status == "open":
        # The world does not wait for the player: a witness comes forward.
        sim.resolve_case(case, by="witness", evidence=["studio: the shopkeeper found the mic in the locker"])
        sim.push_feed(
            author_id=daniel.id,
            text="A witness came forward and the mic was in the studio locker. Six days of side-eyes for a clerical error. I'm going to go lie down in the park.",
            mood="tired", tag="accountability", loc="park",
        )
        sim.add_notice(kind="news", title="Mic found in studio locker",
                       body="A studio volunteer found the missing microphone behind a spare cable box. Daniel is cleared. The neighborhood is now debating who owes him a coffee.",
                       location="studio")
        arc.status = "resolved"
        arc.stage = 4
        arc.last_minute = sim.minute
        arc.summary = "The truth came out eventually — but only after Daniel spent a week being talked about."
        _shift_zara_opinion(sim, zara, cleared=False)
        sim.note("Case closed — eventually", "The truth came out without you. Daniel has been cleared.", kind="story")
    else:
        arc.status = "resolved" if case and case.status == "cleared" else arc.status


def _shift_zara_opinion(sim, zara, *, cleared: bool) -> None:
    """After the chain, Zara's view of several residents changes observably."""
    accuser_id = sim.world_flags.get("chain", {}).get("accuser")
    believers = []
    for rumor in sim.rumors:
        if rumor.get("truth") == "false":
            believers = [s["npc"] for s in rumor.get("spread", [])][:6]
    if cleared:
        for npc_id in believers:
            if npc_id in (zara.id, "player"):
                continue
            sim.adjust_rel(zara.id, npc_id, affinity=-6, trust=-4, familiarity=2)
        if accuser_id:
            sim.adjust_rel(zara.id, accuser_id, affinity=-14, trust=-10, tension=10)
        zara.mood.valence = clamp(zara.mood.valence + 10, -100, 100)
        zara.mood.stress = clamp(zara.mood.stress - 12, 0, 100)
        sim.push_feed(author_id=zara.id,
                      text="Updated map of this neighborhood: most people are better than the story they repeat. A few owe Daniel a very loud apology.",
                      mood="reflective", tag="community", loc="cafe")
    else:
        for npc_id in believers:
            if npc_id in (zara.id, "player"):
                continue
            sim.adjust_rel(zara.id, npc_id, affinity=-4, trust=-6, familiarity=2)
        zara.mood.valence = clamp(zara.mood.valence - 12, -100, 100)
        zara.mood.stress = clamp(zara.mood.stress + 12, 0, 100)
        zara.flags["disillusioned"] = True
        sim.push_feed(author_id=zara.id,
                      text="A week of watching people pick a story over a person. I still like it here. I'm just updating my notes.",
                      mood="tired", tag="community", loc="home")


# ---------------------------------------------------------------------------
# Emergent arcs
# ---------------------------------------------------------------------------
def _active_arc_kinds(sim) -> set[str]:
    return {a.kind for a in sim.arcs if a.status == "active"}


def _create_arc(sim, *, kind: str, title: str, summary: str, actors: list[str],
                stages: list[str], data: dict | None = None) -> Arc:
    arc = Arc(id=new_id("arc"), kind=kind, title=title, summary=summary, actors=actors,
              stages=stages, created=sim.minute, last_minute=sim.minute, data=data or {})
    sim.arcs.append(arc)
    return arc


def maybe_create_emergent(sim) -> None:
    rng = sim.hub.stream("director-emergent")
    active = [a for a in sim.arcs if a.status == "active"]
    if len(active) >= 4:
        return
    if rng.random() > 0.55:
        return

    options = []

    # 1. A friendship becomes a best-friendship
    if "friendship" not in _active_arc_kinds(sim):
        pairs = []
        for n in sim.npcs:
            if not n.spotlight:
                continue
            for other_id, r in sim.outgoing_rels(n.id):
                if other_id == "player":
                    continue
                if r.get("affinity", 0) >= 58 and "best friend" not in r.get("flags", []) and "dating" not in r.get("flags", []):
                    pairs.append((r["affinity"], n.id, other_id))
        if pairs:
            pairs.sort(reverse=True)
            _, a_id, b_id = pairs[0]
            a, b = sim.npc(a_id), sim.npc(b_id)
            if a and b:
                options.append(("friendship", a, b))

    # 2. A business dream starts
    if "business" not in _active_arc_kinds(sim) and sim.day_index >= 1:
        dreamers = [
            n for n in sim.npcs
            if n.spotlight and 120 < n.wallet < 340 and n.stats["discipline"] > 0.55
            and not n.flags.get("has_business") and not n.flags.get("business_arc")
        ]
        if dreamers:
            options.append(("business", rng.choice(dreamers), None))

    # 3. Birthday party for someone well-connected (at most one at a time)
    if "birthday" not in _active_arc_kinds(sim):
        birthday = next((n for n in sim.npcs
                         if n.spotlight and isinstance(n.flags.get("birthday_in"), int)
                         and n.flags.get("birthday_in") <= 0), None)
        if birthday:
            options.append(("birthday", birthday, None))

    # 4. Rivalry heat check
    if "rivalry" not in _active_arc_kinds(sim):
        hot = []
        for n in sim.npcs:
            for other_id, r in sim.outgoing_rels(n.id):
                if other_id == "player":
                    continue
                if r.get("tension", 0) >= 74 and r.get("conflicts", 0) == 0:
                    hot.append((r["tension"], n.id, other_id))
        if hot:
            hot.sort(reverse=True)
            _, a_id, b_id = hot[0]
            a, b = sim.npc(a_id), sim.npc(b_id)
            if a and b:
                options.append(("rivalry", a, b))

    if not options:
        return
    kind, a, b = options[rng.randrange(len(options))]

    if kind == "friendship":
        _create_arc(
            sim, kind="friendship", title=f"{a.first} & {b.first}, apparently",
            summary=f"{a.first} and {b.first} keep ending up in the same places. The block has noticed.",
            actors=[a.id, b.id], stages=["noticed", "inseparable", "official"],
        )
        sim.adjust_rel(a.id, b.id, familiarity=8, affinity=8, trust=4)
        sim.adjust_rel(b.id, a.id, familiarity=8, affinity=8, trust=4)
        sim.push_feed(
            author_id=a.id,
            text=f"Fine, public announcement: {b.first} is my favorite person to argue with about the correct way to eat mango. That's it. That's the post.",
            mood="warm", tag="friends", loc=a.location_id,
        )
        sim.note("A friendship deepens", f"{a.first} and {b.first} are becoming a package deal.", kind="story")

    elif kind == "business":
        a.flags["business_arc"] = True
        _create_arc(
            sim, kind="business", title=f"{a.first}'s big idea",
            summary=f"{a.first} is saving up to open something small and stubbornly theirs.",
            actors=[a.id], stages=["saving", "scouting", "opening"],
            data={"target": min(460, int(a.wallet) + 140), "created_day": sim.day_index},
        )
        a.goal_short = "save enough to open a small stall"
        a.plans.append({"id": new_id("plan"), "kind": "business", "title": "save for a stall",
                        "due": sim.minute + 3 * 1440, "done": False})
        sim.push_feed(
            author_id=a.id,
            text="Okay. I'm saying it out loud so it's real: I'm saving to open a tiny stall. If you see me buying iced coffee, remind me of this post. 💸",
            mood="determined", tag="business", loc=a.location_id,
        )
        sim.note("A business dream", f"{a.first} is saving up to open a stall.", kind="story")

    elif kind == "birthday":
        _create_arc(
            sim, kind="birthday", title=f"{a.first}'s birthday",
            summary=f"{a.first}'s birthday is coming up. A party is being quietly organized at Juniper Park.",
            actors=[a.id], stages=["planning", "party", "aftermath"],
        )
        sim.force_move(a, "park")
        a.flags["birthday_in"] = 30 + (hash_seed(a.id) % 30)
        sim.add_notice(kind="event", title="Birthday at Juniper Park",
                       body=f"A birthday picnic for {a.first} is happening at Juniper Park. Bring something small and kind.",
                       location="park")
        sim.push_feed(
            author_id=a.id,
            text="Apparently it's my birthday soon and I've been informed that 'we're doing something'. I have no further information. I've been told to just show up.",
            mood="suspicious", tag="celebrations", loc="park",
        )
        sim.note("A birthday", f"{a.first} has a birthday coming up at Juniper Park.", kind="story")

    elif kind == "rivalry":
        _create_arc(
            sim, kind="rivalry", title=f"Thin ice: {a.first} & {b.first}",
            summary=f"Old tension between {a.first} and {b.first} is close to the surface.",
            actors=[a.id, b.id], stages=["cold", "spark", "either way"],
        )
        sim.add_notice(kind="alert", title="Tension on the block",
                       body=f"Residents report raised voices between {a.first} and {b.first}. No incident yet. Nearby businesses are watching their fruit crates.",
                       location=a.location_id)
        sim.note("Tension rising", f"{a.first} and {b.first} are on thin ice.", kind="story")


def advance_emergent(sim) -> None:
    for arc in sim.arcs:
        if arc.kind == "friendship" and arc.status == "active":
            a_id, b_id = arc.actors[0], arc.actors[1]
            r = sim.rel(a_id, b_id)
            if r.get("affinity", 0) >= 68 and arc.stage == 0:
                arc.stage = 1
                arc.last_minute = sim.minute
                sim.set_rel_flag(a_id, b_id, "best friend", True)
                sim.set_rel_flag(b_id, a_id, "best friend", True)
                b_first = sim.npc(b_id).first if sim.npc(b_id) else "someone"
                sim.push_feed(author_id=a_id, text=f"{b_first} and I have reached 'knows my coffee order' status. It's serious.",
                              mood="warm", tag="friends", loc="cafe")
            elif r.get("affinity", 0) < 20:
                arc.status = "faded"
            elif arc.stage == 1 and r.get("familiarity", 0) >= 70:
                arc.stage = 2
                arc.status = "resolved"
                arc.last_minute = sim.minute

        elif arc.kind == "business" and arc.status == "active":
            npc = sim.npc(arc.actors[0])
            if not npc:
                arc.status = "faded"
                continue
            target = arc.data.get("target", 420)
            created_day = arc.data.get("created_day", 0)
            matured = sim.day_index - created_day >= 2
            if matured and npc.wallet >= target:
                npc.flags["has_business"] = True
                npc.flags["business_type"] = npc.hobbies[0]
                arc.stage = 2
                arc.status = "resolved"
                arc.last_minute = sim.minute
                sim.add_notice(kind="event", title="New business opening",
                               body=f"{npc.first} just opened a small stall at the square. The block is showing up for moral support and free samples.",
                               location="square")
                sim.push_feed(author_id=npc.id, text="I did the thing. Small stall. Big nerves. If you're nearby, come pretend you're just walking by.",
                              mood="proud", tag="business", loc="square")
                sim.note("A business opens", f"{npc.first} opened a stall at the square.", kind="story")
            elif arc.stage == 0 and sim.day_index - created_day >= 1:
                arc.stage = 1
                arc.last_minute = sim.minute
                sim.note("Scouting a space", f"{npc.first} is asking around about an empty stall at the square.", kind="story")
            elif npc.wallet < 60:
                if sim.hour_of_day >= 19 and sim.hour_of_day < 20:
                    sim.send_npc_message(npc.id, "Okay, so the stall fund is looking tragic. I'm not asking for anything — just complaining into the void. The void being you. Hi.", kind="text")

        elif arc.kind == "birthday" and arc.status == "active":
            npc = sim.npc(arc.actors[0])
            if not npc:
                arc.status = "faded"
                continue
            if arc.stage == 0:
                arc.stage = 1
                arc.last_minute = sim.minute
                sim.force_move(npc, "park")
                guests = [n for n in sim.npcs if n.spotlight and n.id != npc.id][:6]
                for g in guests:
                    sim.force_move(g, "park")
                    sim.adjust_rel(g.id, npc.id, familiarity=6, affinity=6)
                    sim.remember(g, sim.add_event(
                        kind="party", actor=npc.id, targets=[g.id], location="park",
                        facts={"occasion": "birthday"}, witnesses=[], visibility="public",
                        summary=f"{g.first} came to {npc.first}'s birthday picnic.",
                    ), importance=0.5, valence=0.7, source="participated")
                npc.mood.valence = clamp(npc.mood.valence + 30, -100, 100)
                sim.push_feed(author_id=guests[0].id if guests else npc.id,
                              text=f"Birthday picnic for {npc.first} at the park. Someone brought a cake shaped like a cassette tape, so obviously I cried.",
                              mood="emotional", tag="celebrations", loc="park")
                sim.note("Birthday party", f"{npc.first}'s birthday picnic is happening at Juniper Park right now.", kind="story")
            elif arc.stage == 1 and sim.minute - arc.last_minute > 180:
                arc.stage = 2
                arc.status = "resolved"

        elif arc.kind == "rivalry" and arc.status == "active":
            a = sim.npc(arc.actors[0])
            b = sim.npc(arc.actors[1]) if len(arc.actors) > 1 else None
            if not a or not b:
                arc.status = "faded"
                continue
            tension = sim.rel(a.id, b.id).get("tension", 0)
            if tension >= 80 and a.location_id == b.location_id and arc.stage == 0:
                arc.stage = 1
                arc.last_minute = sim.minute
                sim.note("Rivalry heating up", f"{a.first} and {b.first} are in the same place and neither is blinking.", kind="story")
            elif tension < 40:
                arc.status = "resolved"
                arc.stage = 2
                arc.last_minute = sim.minute


# ---------------------------------------------------------------------------
# Ambient life
# ---------------------------------------------------------------------------
AMBIENT_EVENTS = [
    {"id": "openmic", "title": "Open-mic night", "loc": "studio",
     "body": "Golden Hour Studio is hosting open-mic night. Sign-up sheet is full of handwriting that says 'I'm nervous' in different fonts.",
     "feed": "Open mic at Golden Hour tonight. I'm performing. I'm also pretending I'm not performing so nobody expects anything. 🎤"},
    {"id": "market", "title": "Market day", "loc": "grocery",
     "body": "The market has extra stalls today: fruit, secondhand books, questionable art, excellent conversation.",
     "feed": "Market day! There's a stall selling 'mystery jam'. I asked what's in it. The answer was 'jam'. I bought two. 🍓"},
    {"id": "movienight", "title": "Outdoor movie night", "loc": "park",
     "body": "A projector, a white sheet, and forty folding chairs at Juniper Park. Bring a blanket and strong opinions.",
     "feed": "Outdoor movie at the park tonight. The projector makes a sound like a small airplane. Bring a blanket. 🎬"},
    {"id": "festival_planning", "title": "Festival planning meeting", "loc": "square",
     "body": "The Lantern Festival committee needs volunteers, snacks, and someone willing to argue about the budget in public.",
     "feed": "Festival meeting at the square. I went in with zero opinions and left with a heated position on banner colours. 🏮"},
    {"id": "cleanup", "title": "Block clean-up", "loc": "park",
     "body": "Gloves, bags and music at the park. The goal: less litter, more civic pride, exactly one group photo.",
     "feed": "Block clean-up this morning. I found a spoon, a sock, and three new friends. Net win. 🧤"},
]


def run_ambient(sim) -> None:
    rng = sim.hub.stream("ambient")
    if rng.random() > 0.35:
        return
    history = sim.world_flags.setdefault("ambient_history", [])
    recent_ids = {h["event"] for h in history if sim.minute - h["minute"] < 2 * 1440}
    options = [e for e in AMBIENT_EVENTS if e["id"] not in recent_ids] or AMBIENT_EVENTS
    event = options[rng.randrange(len(options))]
    if history and history[-1]["event"] == event["id"]:
        return
    history.append({"event": event["id"], "minute": sim.minute})
    del history[:-12]
    sim.host_ambient(event)


def run_director(sim) -> None:
    advance_chain(sim)
    maybe_create_emergent(sim)
    advance_emergent(sim)
    # fade old resolved arcs
    for arc in sim.arcs:
        if arc.status == "resolved" and sim.minute - arc.last_minute > 3 * 1440:
            arc.status = "faded"
    for npc in sim.npcs:
        if not isinstance(npc.flags.get("birthday_in"), int):
            npc.flags["birthday_in"] = 3 + (hash_seed(npc.id) % 48)


def hash_seed(value: str) -> int:
    from blxverse.engine.rng import stable_hash
    return stable_hash("birthday", value)


def tick_days(sim) -> None:
    """Daily bookkeeping called once per in-game day at 00:05."""
    for npc in sim.npcs:
        bday = npc.flags.get("birthday_in")
        if isinstance(bday, int) and bday > 0:
            npc.flags["birthday_in"] = bday - 1
        # beliefs decay slowly: confidence erodes without reinforcement
        for belief in npc.beliefs:
            belief.confidence = clamp(belief.confidence - config.BELIEF_DECAY_PER_DAY, 0.0, 1.0)
        npc.beliefs = [b for b in npc.beliefs if b.confidence > 0.12]
        # weekly gift memory fades
        for k, v in list(sim.rels.get(f"{npc.id}|player", {}).get("gifts", {}).items()):
            if v > 0 and sim.day_index % 7 == 0:
                sim.rels[f"{npc.id}|player"]["gifts"][k] = 0
        # plans due
        for plan in npc.plans:
            if not plan.get("done") and plan.get("due", 0) < sim.minute:
                plan["done"] = True
                if plan.get("kind") == "reconcile":
                    other = sim.npc(plan.get("with", ""))
                    if other:
                        sim.adjust_rel(npc.id, other.id, tension=-8, trust=2)
    # reset player's weekly gift counts too
    if sim.day_index % 7 == 0:
        for k in list(sim.rels.keys()):
            if k.endswith("|player"):
                sim.rels[k]["gifts"] = {kk: 0 for kk in sim.rels[k].get("gifts", {})}
