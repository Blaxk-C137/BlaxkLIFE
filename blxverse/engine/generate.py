"""Procedural neighborhood generation.

Everything is a pure function of the world seed: same seed -> same residents,
homes, schedules, relationships and seed story. No network, no LLM.
"""

from __future__ import annotations

import math
import random

from blxverse import config
from blxverse.content import traits as T
from blxverse.content.dialogue_content import ARCHETYPES, PERSONALITY_QUIRKS
from blxverse.content.locations import HOMES, LOCATIONS, WORKPLACE_BY_OCCUPATION
from blxverse.content.names import FIRST_NAMES_F, FIRST_NAMES_M, FIRST_NAMES_N, SURNAMES
from blxverse.engine.models import NPC, Mood
from blxverse.engine.rng import RngHub, stable_hash

SKIN_TONES = ["#f6d7c3", "#eec3a0", "#d9a066", "#b97a4e", "#8a5a3b", "#6b4226", "#4c2f21", "#f1cbb3"]
HAIR_COLORS = ["#241a15", "#3b2417", "#5a3825", "#7a4b2b", "#1b1b1b", "#8c6239", "#b07d4a", "#d9c2a3"]
HAIR_STYLES = ["short", "curly", "braids", "bun", "wave", "locs", "buzz", "ponytail"]
OUTFIT_COLORS = ["#e0663b", "#3b82a0", "#c9902f", "#7c5cbf", "#4f9a6a", "#c2547f", "#3f6bc4", "#d9a441", "#5a6b7d", "#b5502f"]
ACCESSORIES = ["none", "glasses", "earrings", "cap", "headband", "watch", "chain", "scarf"]
HOUSEHOLD_ROLES = ["head", "partner", "sibling", "roommate", "adult child", "cousin"]


def h(*parts: str) -> int:
    return stable_hash(*parts)


# ---------------------------------------------------------------------------
# Personality -> derived stats -> archetype
# ---------------------------------------------------------------------------
def _build_archetype(stats: dict[str, float], traits: list[str]) -> str:
    tset = set(traits)
    best, best_score = "spark", -99.0
    for aid, a in ARCHETYPES.items():
        score = sum(2.0 for tag in a["tags"] if tag in tset)
        score += {
            "spark": stats["chatter"] + stats["warmth"] * 0.5,
            "storm": stats["vanity"] + stats["energy"] * 0.4,
            "zen": (1.0 - stats["energy"]) + stats["warmth"] * 0.6,
            "gear": stats["curiosity"] * 1.2,
            "flame": stats["discipline"] * 1.2,
            "sprite": stats["humor"] * 0.3 + stats["curiosity"] * 0.8,
            "tank": stats["warmth"] * 0.7 + stats["energy"] * 0.5,
            "trickster": stats["risk"] * 0.8 + stats["humor"] * 0.4,
        }.get(aid, 0.0)
        if score > best_score:
            best, best_score = aid, score
    return best


def _stats_from_traits(traits: list[str], hub: RngHub, key: str) -> dict[str, float]:
    base = {k: 0.5 for k in ("warmth", "energy", "directness", "risk", "chatter", "forgive",
                             "jealous", "generosity", "discipline", "curiosity", "humor", "vanity")}
    for tid in traits:
        tdef = T.TRAITS[tid]
        for f in base:
            base[f] += getattr(tdef, f) * 0.45
    rng = hub.stream(f"stats:{key}")
    for k in base:
        base[k] = max(0.05, min(0.98, base[k] + rng.uniform(-0.08, 0.08)))
    return {k: round(v, 3) for k, v in base.items()}


# ---------------------------------------------------------------------------
# Schedules: non-overlapping, per-resident variation
# ---------------------------------------------------------------------------
def _make_schedule(rng: random.Random, npc_seed: dict) -> dict[str, list]:
    shift_start = rng.choice([8, 9, 10, 12, 14, 16])
    shift_len = 4.0
    work_loc = npc_seed["workplace"]
    social_a = npc_seed["social_a"]
    social_b = npc_seed["social_b"]
    hobby_a = npc_seed["hobby_a"]
    occupation = npc_seed["occupation"]

    def block(start: float, end: float, loc: str, activity: str, kind: str) -> dict:
        return {"start": round(start, 2), "end": round(end, 2), "loc": loc, "activity": activity, "kind": kind}

    weekday: list[dict] = [block(0, 6.5, "home", "sleeping", "sleep"), block(6.5, 7.5, "home", "morning routine", "routine")]
    if shift_start <= 9:
        weekday.append(block(7.5, shift_start, "cafe", "a quick coffee", "meal"))
    else:
        weekday.append(block(7.5, shift_start, social_a, hobby_a, "leisure"))
    weekday.append(block(shift_start, shift_start + shift_len, work_loc, f"working as {occupation}", "work"))
    lunch = shift_start + shift_len
    weekday.append(block(lunch, lunch + 1.0, rng.choice(["cafe", "grocery", work_loc]), "lunch", "meal"))
    afternoon_end = min(18.0, lunch + 3.0)
    weekday.append(block(lunch + 1.0, afternoon_end, social_a, hobby_a, "leisure"))
    if afternoon_end < 18.0:
        weekday.append(block(afternoon_end, 18.5, "square", "passing through the square", "idle"))
    if rng.random() < 0.55:
        weekday.append(block(18.5, 21.0, social_b, "evening hangout", "social"))
        weekday.append(block(21.0, 23.0, "home", "evening at home", "rest"))
    else:
        weekday.append(block(18.5, 23.0, "home", "evening at home", "rest"))
    weekday.append(block(23.0, 24.0, "home", "sleeping", "sleep"))

    weekend = [
        block(0, 8.0, "home", "sleeping in", "sleep"),
        block(8.0, 10.0, "home", "slow morning", "routine"),
        block(10.0, 12.5, rng.choice(["grocery", "park", "cafe", "square"]), "weekend errands", "errand"),
        block(12.5, 13.5, rng.choice(["cafe", "restaurant"]), "weekend lunch", "meal"),
        block(13.5, 16.5, social_a, hobby_a, "leisure"),
        block(16.5, 19.0, social_b, "afternoon socializing", "social"),
        block(19.0, 21.5, rng.choice(["restaurant", "cinema", "square", "studio"]), "weekend night out", "social"),
        block(21.5, 24.0, "home", "night wind-down", "rest"),
    ]

    def add_drift(blocks: list[dict]) -> None:
        for b in blocks:
            if b["kind"] in ("leisure", "social", "errand"):
                d = rng.choice([-0.25, 0, 0, 0.25])
                b["start"] = max(0.0, b["start"] + d)
                b["end"] = min(24.0, b["end"] + d)
        for i in range(len(blocks) - 1):
            if blocks[i]["end"] > blocks[i + 1]["start"]:
                blocks[i]["end"] = blocks[i + 1]["start"]

    add_drift(weekday)
    add_drift(weekend)
    return {"weekday": weekday, "weekend": weekend}


# ---------------------------------------------------------------------------
# NPC generation
# ---------------------------------------------------------------------------
def generate_npcs(hub: RngHub, count: int = config.NPC_COUNT) -> list[NPC]:
    rng = hub.stream("generation")
    f_names = FIRST_NAMES_F[:]
    m_names = FIRST_NAMES_M[:]
    n_names = FIRST_NAMES_N[:]
    rng.shuffle(f_names)
    rng.shuffle(m_names)
    rng.shuffle(n_names)
    surnames = SURNAMES[:]
    rng.shuffle(surnames)

    plan = ["female"] * 30 + ["male"] * 27 + ["nonbinary"] * 3
    rng.shuffle(plan)
    count = min(count, 60)
    plan = plan[:count]

    npcs: list[NPC] = []
    used: set[str] = set()
    idx = {"female": 0, "male": 0, "nonbinary": 0}
    pools = {"female": f_names, "male": m_names, "nonbinary": n_names}

    for i in range(count):
        g = plan[i]
        first = pools[g][idx[g] % len(pools[g])]
        idx[g] += 1
        last = surnames[i % len(surnames)]
        attempts = 0
        while f"{first} {last}" in used and attempts < 20:
            last = surnames[(i + attempts * 3 + 1) % len(surnames)]
            attempts += 1
        used.add(f"{first} {last}")

        pairs = T.TRAIT_PAIRS[:]
        rng.shuffle(pairs)
        trait_ids = [a if rng.random() < 0.58 else b for a, b in pairs[: rng.choice([4, 5, 5, 6])]]
        stats = _stats_from_traits(trait_ids, hub, f"{first}{last}")
        archetype = _build_archetype(stats, trait_ids)

        occ, base_salary = rng.choices(T.OCCUPATIONS, weights=[1] * len(T.OCCUPATIONS))[0]
        salary = int(base_salary * rng.uniform(0.85, 1.25))
        workplace = WORKPLACE_BY_OCCUPATION.get(occ, "square")

        age = rng.randint(*config.NPC_AGE_RANGE)
        if occ == "student":
            age = rng.randint(22, 29)
        bracket = "young adult" if age < 30 else ("adult" if age < 45 else ("midlife" if age < 58 else "senior"))

        hobbies = rng.sample(list(T.HOBBIES.keys()), rng.choice([2, 3, 3]))
        hobby_a = hobbies[0]
        hobby_locs = [loc for loc in T.HOBBIES[hobby_a]["venues"] if loc != "home"] or ["park"]
        social_a = hobby_locs[0]
        social_b = rng.choice(["square", "cafe", "park", "restaurant", "cinema", "studio", "music_store"])
        if social_b == social_a:
            social_b = rng.choice(["square", "park", "cafe"])

        home_id = i % len(HOMES)
        hx, hy = HOMES[home_id][0], HOMES[home_id][1]
        household_id = i % 20
        role = "head" if i < 20 else HOUSEHOLD_ROLES[1 + (i % (len(HOUSEHOLD_ROLES) - 1))]

        look = {
            "skin": rng.choice(SKIN_TONES), "hair": rng.choice(HAIR_COLORS),
            "hairStyle": rng.choice(HAIR_STYLES), "outfit": rng.choice(OUTFIT_COLORS),
            "accent": rng.choice(["#ffffff", "#1f2937", "#f2c14e", "#7fd1b9"]),
            "accessory": rng.choice(ACCESSORIES), "height": round(rng.uniform(0.92, 1.08), 3),
        }
        voice = {
            "pitch": round(rng.uniform(0.75, 1.3), 3),
            "rate": round(rng.uniform(0.88, 1.12), 3),
            "warmth": round(stats["warmth"], 3),
        }
        schedule = _make_schedule(rng, {
            "workplace": workplace, "occupation": occ, "social_a": social_a,
            "social_b": social_b, "hobby_a": hobby_a,
        })

        mood = Mood(
            valence=rng.uniform(-6, 22), stress=rng.uniform(4, 24),
            excitement=rng.uniform(20, 52), irritation=rng.uniform(0, 10),
            social_energy=rng.uniform(55, 95),
        )

        npcs.append(NPC(
            id=f"npc_{i + 1:03d}",
            first=first, last=last, gender=g,
            pronouns={"female": "she/her", "male": "he/him", "nonbinary": "they/them"}[g],
            age=age, age_bracket=bracket, occupation=occ, salary=salary, workplace=workplace,
            home_id=home_id, household_id=household_id, household_role=role,
            archetype=archetype, traits=trait_ids, stats=stats, voice=voice, look=look,
            schedule=schedule, hobbies=hobbies, favorite_music=rng.choice(T.MUSIC_GENRES),
            favorite_food=rng.choice(T.FOODS), favorite_color=rng.choice(T.COLORS),
            values=rng.sample([v for v, _ in T.VALUES], 3),
            boundaries=rng.sample(T.BOUNDARIES, 2),
            goal_short=rng.choice([
                "get through a busy week", "plan a small get-together", "finish a personal project",
                "save up for something nice", "patch things up with someone", "learn a new skill",
                "find a better work rhythm", "make one new friend this month",
            ]),
            goal_long=rng.choice(T.ASPIRATIONS),
            secret=dict(zip(("id", "hint"), rng.choice(T.SECRETS), strict=True)),
            quirk=rng.choice(PERSONALITY_QUIRKS[archetype]),
            wallet=int(rng.triangular(90, 900, 260)),
            bills_due=6 + rng.randint(0, 12),
            spending_habit=rng.choice(["frugal", "balanced", "impulsive", "generous"]),
            mood=mood, energy=rng.uniform(62, 100),
            x=hx + rng.uniform(-30, 30), y=hy + 30 + rng.uniform(-10, 20),
            home_xy=(float(hx), float(hy + 40)),
        ))

    _guarantee_doc_characters(npcs)
    _ensure_unique_first_names(npcs)
    for n in npcs:
        n.flags.setdefault("birthday_in", 3 + (stable_hash("bday", n.id) % 48))
    return npcs


def _ensure_unique_first_names(npcs: list[NPC]) -> None:
    used = set()
    pools = {"female": FIRST_NAMES_F[:], "male": FIRST_NAMES_M[:], "nonbinary": FIRST_NAMES_N[:]}
    for n in npcs:
        if n.first in used:
            for name in pools.get(n.gender, FIRST_NAMES_F):
                if name not in used:
                    n.first = name
                    break
        used.add(n.first)


def _guarantee_doc_characters(npcs: list[NPC]) -> None:
    """The design doc's example chain needs a Zara, a Daniel and a landlord."""
    for other in npcs[1:]:
        if other.first in ("Zara", "Daniel", "Femi"):
            replacement = next(nm for nm in (FIRST_NAMES_F if other.gender == "female" else
                                             FIRST_NAMES_M if other.gender == "male" else FIRST_NAMES_N)
                               if nm not in {o.first for o in npcs})
            other.first = replacement
    zara = npcs[0]
    zara.first, zara.last = "Zara", "Adeyemi"
    zara.gender, zara.pronouns = "female", "she/her"
    zara.age = 27
    zara.occupation, zara.salary, zara.workplace = "musician", 74, "studio"
    zara.archetype = "sprite"
    zara.traits = ["artsy", "romantic", "shy", "laidback", "kind"]
    zara.hobbies = ["music", "art", "coffee"]
    zara.goal_short = "survive the move and find a stage"
    zara.goal_long = "headline the neighborhood festival"
    zara.secret = {"id": "song", "hint": "is writing songs but is terrified to perform"}
    zara.mood = Mood(valence=-6, stress=44, excitement=28, irritation=22, social_energy=58)
    zara.wallet = 64
    zara.spotlight = True
    zara.flags["newcomer"] = True
    zara.flags["landlord"] = False
    zara.quirk = "hums in three keys"
    zara.look["outfit"] = "#7c5cbf"

    daniel = next((n for n in npcs if n.gender == "male" and n.id != zara.id), npcs[1])
    daniel.first, daniel.last = "Daniel", "Okafor"
    daniel.gender, daniel.pronouns = "male", "he/him"
    daniel.age = 31
    daniel.occupation, daniel.salary, daniel.workplace = "graphic designer", 132, "cafe"
    daniel.archetype = "gear"
    daniel.traits = ["nerdy", "kind", "calm", "artsy", "practical"]
    daniel.hobbies = ["music", "reading", "gaming"]
    daniel.goal_long = "open a small design studio"
    daniel.spotlight = True
    daniel.quirk = "takes notes in a tiny notebook"
    daniel.look["outfit"] = "#3b82a0"

    landlord = next((n for n in npcs if n.gender == "male" and n.id not in (zara.id, daniel.id) and n.age > 45), npcs[2])
    landlord.first, landlord.last = "Femi", "Balogun"
    landlord.gender, landlord.pronouns = "male", "he/him"
    landlord.age = 54
    landlord.occupation, landlord.salary, landlord.workplace = "carpenter", 140, "gym"
    landlord.archetype = "storm"
    landlord.traits = ["bold", "proud", "grumpy", "practical", "ambitious"]
    landlord.goal_short = "keep the buildings standing"
    landlord.goal_long = "own the whole block"
    landlord.spotlight = True
    landlord.flags["landlord"] = True
    landlord.quirk = "gestures with their whole body"
    landlord.home_id = zara.home_id

    by_arch: dict[str, list[NPC]] = {}
    for n in npcs:
        if not n.spotlight:
            by_arch.setdefault(n.archetype, []).append(n)
    order = ["spark", "tank", "zen", "flame", "trickster", "gear", "storm", "sprite"]
    picks = 0
    while picks < config.SPOTLIGHT_COUNT - 3:
        progressed = False
        for aid in order:
            pool = by_arch.get(aid, [])
            if pool and picks < config.SPOTLIGHT_COUNT - 3:
                pool.pop(0).spotlight = True
                picks += 1
                progressed = True
        if not progressed:
            break


# ---------------------------------------------------------------------------
# Social fabric
# ---------------------------------------------------------------------------
def seed_relationships(npcs: list[NPC]) -> dict[str, dict]:
    from blxverse.engine.models import Relationship  # noqa: F401  (schema parity)

    rels: dict[str, dict] = {}

    def key(a: str, b: str) -> str:
        return f"{a}|{b}"

    def get(a: str, b: str) -> dict:
        return rels.setdefault(key(a, b), {})

    def set_rel(a: str, b: str, *, familiarity: float, trust: float, affinity: float,
                romance: float = 0.0, tension: float = 0.0, flags: list[str] | None = None) -> None:
        flags = flags or []
        for src, dst in ((a, b), (b, a)):
            r = get(src, dst)
            r.update({
                "familiarity": familiarity, "trust": trust, "affinity": affinity,
                "romance": romance, "tension": tension, "flags": list(flags),
            })

    homes: dict[int, list[NPC]] = {}
    for n in npcs:
        homes.setdefault(n.home_id, []).append(n)
    for members in homes.values():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                set_rel(a.id, b.id, familiarity=78, trust=72, affinity=48, tension=6,
                        flags=["family", "housemate"])

    workplaces: dict[str, list[NPC]] = {}
    for n in npcs:
        workplaces.setdefault(n.workplace, []).append(n)
    for crew in workplaces.values():
        for i, a in enumerate(crew):
            for b in crew[i + 1:]:
                if a.household_id == b.household_id:
                    continue
                f = 18.0 + h("coworker", a.id, b.id) % 24
                set_rel(a.id, b.id, familiarity=f, trust=44, affinity=12, flags=["coworker"])

    for i, a in enumerate(npcs):
        for b in npcs[i + 1:]:
            if a.home_id == b.home_id:
                continue
            if a.home_id // 5 == b.home_id // 5 and h("neighbor", a.id, b.id) % 100 < 60:
                set_rel(a.id, b.id, familiarity=8.0 + h("nf", a.id, b.id) % 22,
                        trust=28, affinity=6, flags=["neighbor"])

    for npc in npcs:
        candidates = [o for o in npcs if o.id != npc.id and o.home_id != npc.home_id]
        candidates.sort(key=lambda o: h("pick", npc.id, o.id))
        added = 0
        for other in candidates:
            if added >= 3:
                break
            if "friend" in get(npc.id, other.id).get("flags", []):
                continue
            if h("friend", npc.id, other.id) % 100 < 34:
                f = 40.0 + h("fam", npc.id, other.id) % 35
                aff = 34.0 + h("aff", npc.id, other.id) % 32
                set_rel(npc.id, other.id, familiarity=f, trust=58, affinity=aff, flags=["friend"])
                added += 1

    # two pre-existing couples
    pool = [n for n in npcs if not n.flags.get("landlord")]
    plus_rels = [n for n in npcs if n.first == "Zara"]
    couples = 0
    for i in range(len(pool)):
        if couples >= 2:
            break
        a = pool[i]
        if a in plus_rels:
            continue
        for j in range(i + 1, len(pool)):
            b = pool[j]
            if b.home_id == a.home_id or b.workplace == a.workplace or b in plus_rels:
                continue
            if h("couple", a.id, b.id) % 100 < 2:
                set_rel(a.id, b.id, familiarity=62, trust=66, affinity=64, romance=64, flags=["dating"])
                couples += 1
                break

    exes = 0
    for i in range(len(pool)):
        if exes >= 3:
            break
        a = pool[i]
        for j in range(i + 3, len(pool)):
            b = pool[j]
            if b.home_id == a.home_id:
                continue
            if h("ex", a.id, b.id) % 100 < 3:
                set_rel(a.id, b.id, familiarity=48, trust=34, affinity=8, romance=14, tension=28, flags=["ex"])
                exes += 1
                break

    rival_causes = [
        "a parking spot ownership dispute", "a borrowed ladder that was never returned",
        "competing food stall ambitions", "a painfully loud late-night playlist",
        "a spilled coffee and zero apology", "a group project that went badly",
        "a disputed interpretation of the festival rules",
    ]
    seeds = [(npcs[3], npcs[11]), (npcs[7], npcs[21]), (npcs[16], npcs[34]), (npcs[25], npcs[44])]
    for i, (a, b) in enumerate(seeds):
        if a.id == b.id:
            continue
        set_rel(a.id, b.id, familiarity=52, trust=18, affinity=-26, tension=64, flags=["rival"])
        a.flags["rival_cause"] = rival_causes[i % len(rival_causes)]

    zara = next(n for n in npcs if n.first == "Zara")
    landlord = next(n for n in npcs if n.flags.get("landlord"))
    set_rel(zara.id, landlord.id, familiarity=34, trust=14, affinity=-24, tension=62, flags=["landlord", "rival"])
    # tenant/landlord flags differ per direction
    rels[key(zara.id, landlord.id)]["flags"] = ["landlord", "rival"]
    rels[key(landlord.id, zara.id)]["flags"] = ["tenant", "rival"]
    rels[key(zara.id, landlord.id)]["cause"] = "an overdue rent increase and a leaking ceiling"

    for n in npcs:
        get(n.id, "player").update({"familiarity": 0.0, "trust": 20.0, "affinity": 0.0,
                                    "romance": 0.0, "tension": 0.0, "flags": []})
        get("player", n.id).update({"familiarity": 0.0, "trust": 20.0, "affinity": 0.0,
                                    "romance": 0.0, "tension": 0.0, "flags": []})

    for r in rels.values():
        r.setdefault("interactions", 0)
        r.setdefault("last", -9999.0)
        r.setdefault("gifts", {})
        r.setdefault("dates", 0)
        r.setdefault("conflicts", 0)
    return rels


def make_player(hub: RngHub, name: str, gender: str, look: dict | None, age: int = 26) -> dict:
    rng = hub.stream("player")
    base_look = {
        "skin": rng.choice(SKIN_TONES), "hair": rng.choice(HAIR_COLORS),
        "hairStyle": rng.choice(HAIR_STYLES), "outfit": rng.choice(OUTFIT_COLORS),
        "accent": "#ffd166", "accessory": rng.choice(ACCESSORIES), "height": 1.0,
    }
    if look:
        for k in base_look:
            if k in look and isinstance(look[k], str):
                base_look[k] = look[k]
    home_id = 17
    hx, hy = HOMES[home_id][0], HOMES[home_id][1]
    return {
        "name": (name or "You").strip()[:24] or "You",
        "gender": gender if gender in ("male", "female", "nonbinary") else "female",
        "pronouns": {"male": "he/him", "female": "she/her", "nonbinary": "they/them"}.get(gender, "she/her"),
        "age": max(22, min(90, int(age))),
        "occupation": "newcomer",
        "look": base_look, "home_id": home_id,
        "wallet": config.STARTING_BALANCE, "energy": 100.0, "reputation": 50.0,
        "x": float(hx + 24), "y": float(hy + 96),
        "inventory": {}, "ledger": [],
        "flags": {"moved_in_day": 0, "cart_owned": False, "call_consent": False},
        "stats": {}, "created_at": 0.0, "last_active": 0.0,
    }


def initial_world_flags() -> dict:
    return {
        "last_rent_day": -1,
        "feed_seq": 0,
        "banned_until": 0.0,
        "chaos_last_minute": -9999.0,
        "next_npc_chat_minute": 40.0,
        "next_feed_minute": 60.0,
        "next_director_minute": 90.0,
        "next_ambient_minute": 30.0,
        "chain": {"started": False, "day": -1},
    }


def dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def location_xy(loc_id: str, home_xy: tuple[float, float] = (900.0, 800.0)) -> tuple[float, float]:
    if loc_id == "home":
        return float(home_xy[0]), float(home_xy[1])
    for loc in LOCATIONS:
        if loc["id"] == loc_id:
            return loc["x"] + loc["w"] / 2, loc["y"] + loc["h"] / 2
    return 900.0, 800.0
