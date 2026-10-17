"""Deterministic dialogue composer.

Turns player text + NPC state into an in-character reply and a set of
simulation effects. It is deliberately provider-agnostic: the same interface
can be backed by a remote LLM (see providers.py) without touching game rules.

The composer never edits wallets, inventory or locations. It only *proposes*
conversational intent; the Simulation validates and applies effects.
"""

from __future__ import annotations

import re

from blxverse.content.dialogue_content import ARCHETYPES, MOOD_LINES, line_pool
from blxverse.content.names import TOPICS
from blxverse.engine.models import NPC, Player, Relationship
from blxverse.engine.rng import RngHub

INTENTS = [
    "insult", "apology", "ask_date", "flirt", "gift", "gossip", "invite", "compliment",
    "joke", "how_are_you", "deep", "smalltalk", "greeting", "goodbye", "ask_about", "fallback",
]

KEYWORDS: dict[str, tuple[str, ...]] = {
    "insult": ("idiot", "stupid", "shut up", "hate you", "ugly", "loser", "trash", "annoying",
               "pathetic", "dumb", "worthless", "get lost", "nobody likes you"),
    "apology": ("sorry", "apologize", "apologise", "my bad", "i was wrong", "forgive me",
                "didn't mean", "did not mean", "regret"),
    "ask_date": ("date", "dinner with me", "go out with me", "coffee with me", "movie with me",
                 "take you out", "be my", "go on a date", "romantic evening"),
    "flirt": ("flirt", "cute", "gorgeous", "beautiful", "handsome", "pretty", "charming", "kiss",
              "romantic", "i like you", "crush", "sweet talk", "your eyes", "smile", "love you"),
    "gift": ("gift", "present", "i got you", "bought you", "here's a", "here is a", "for you"),
    "gossip": ("heard", "rumor", "rumour", "gossip", "apparently", "they say", "did you know",
               "word is", "someone said", "supposedly"),
    "invite": ("come with", "join me", "party", "hang out", "hangout", "invite", "meet me",
               "want to go", "let's go", "lets go", "come along"),
    "compliment": ("amazing", "great", "talented", "smart", "brilliant", "love your", "look nice",
                   "look great", "you look", "impressive", "admire", "respect you", "good at"),
    "joke": ("joke", "funny", "haha", "lol", "kidding", "laugh", "😂", "😄", "lmfao"),
    "how_are_you": ("how are you", "how're you", "how you doing", "how's it going", "hows it going",
                    "what's up", "whats up", "how was your day", "you good", "how do you feel"),
    "deep": ("dream", "afraid", "scared", "lonely", "life", "future", "worried", "secret",
             "feel about", "what matters", "meaning", "regret", "hope", "vulnerable", "trust"),
    "greeting": ("hi", "hello", "hey", "yo", "morning", "evening", "afternoon", "good day", "sup"),
    "goodbye": ("bye", "see you", "later", "gotta go", "goodnight", "good night", "i'm off"),
    "ask_about": ("tell me about", "what do you do", "your job", "your hobby", "your music",
                  "your family", "where are you from", "your dream", "about yourself"),
}

ORDER = ["insult", "apology", "ask_date", "gift", "flirt", "gossip", "invite", "compliment",
         "joke", "how_are_you", "deep", "greeting", "goodbye", "ask_about"]


_KW_RE: dict[str, re.Pattern[str]] = {}


def _kw_match(kw: str, text: str) -> bool:
    """Whole-word (or whole-phrase) match so "hi" never fires inside "right"."""
    pattern = _KW_RE.get(kw)
    if pattern is None:
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])")
        _KW_RE[kw] = pattern
    return pattern.search(text) is not None


def classify_intent(text: str) -> str:
    t = " " + re.sub(r"\s+", " ", text.lower().strip()) + " "
    best, best_score = "fallback", 0
    for intent in ORDER:
        score = 0
        for kw in KEYWORDS[intent]:
            if _kw_match(kw, t):
                score += 2 if len(kw) > 4 else 1
                if t.strip().startswith(kw) or t.strip().endswith(kw):
                    score += 1
        # 'date' inside 'update' should not count
        if intent == "ask_date" and re.search(r"\bdate\b", t) and "update" not in t:
            score += 2
        if score > best_score:
            best, best_score = intent, score
    if best_score == 0 and len(t) > 60 and "?" not in t:
        return "smalltalk"
    return best


QUESTION_PATTERNS = (
    ("plans", re.compile(r"\b(what|wat|whatcha|what're|what are)\b.*\b(you|u)\b.*\b(up to|doing|later|tonight|today|weekend|plan)", re.I)),
    ("plans", re.compile(r"\b(any plans|what's next|whats next|what now|got plans)\b", re.I)),
    ("where", re.compile(r"\bwhere\b.*\b(you|u|are we|is)\b|\bwhereabouts\b", re.I)),
    ("how_feel", re.compile(r"\bhow (are|r) (you|u)|\bhow's it going|\bhows it going|\byou good\b", re.I)),
    ("work", re.compile(r"\b(work|job|shift|boss|coworker|office)\b", re.I)),
    ("who", re.compile(r"\bwho\b.*\b(you|u)\b|\bwho's|\bwhos", re.I)),
    ("why", re.compile(r"^\s*why\b|\bwhy (did|do|are|would|is)\b", re.I)),
    ("food", re.compile(r"\b(food|eat|hungry|lunch|dinner|coffee|snack)\b", re.I)),
    ("yesno", re.compile(r"^\s*(do|are|did|can|could|would|will|have|has|is|was|should)\s+(you|u)\b", re.I)),
    ("music", re.compile(r"\b(music|song|band|album|gig|playlist)\b", re.I)),
)


def _sentence(text: str) -> str:
    """Capitalise sentence starts so interpolated state reads like prose."""
    text = text.strip()
    if not text:
        return text
    out = text[0].upper() + text[1:]
    return re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)


def _clean_activity(npc: NPC) -> str:
    for candidate in (npc.schedule_activity, npc.activity):
        text = (candidate or "").strip()
        if not text:
            continue
        lowered = text.lower()
        for prefix in ("arriving at ", "heading to ", "walking to "):
            if lowered.startswith(prefix):
                place = text[len(prefix):].strip()
                return f"on my way to {place}" if place else "on my way somewhere"
        return text
    return "loitering with intent"


def _next_plan(npc: NPC, location_names: dict[str, str]) -> str | None:
    plans = [p for p in npc.plans if not p.get("done")]
    if not plans:
        return None
    plan = plans[-1]
    title = plan.get("title") or plan.get("kind") or "something"
    venue = location_names.get(plan.get("venue", ""), "")
    return f"{title}{' at ' + venue if venue else ''}"


def _grounded_answer(
    *, npc: NPC, player: Player, text: str, venue: str, hub: RngHub,
    location_names: dict[str, str],
) -> str | None:
    """Answer what was actually asked using the NPC's own simulated state.

    The deterministic composer has no world model of its own, but the NPC does:
    their schedule, plans, mood, friends and goals are real simulation data, so
    questions can be answered truthfully instead of with a generic line.
    """
    lowered = text.strip()
    kind = None
    for name, pattern in QUESTION_PATTERNS:
        if pattern.search(lowered):
            kind = name
            break
    if kind is None and "?" not in lowered:
        return None
    rng = hub.stream(f"answer:{npc.id}")
    activity = _clean_activity(npc)
    plan = _next_plan(npc, location_names)
    friend = "anyone at the square"

    if kind == "plans":
        options = [
            f"Later? {activity}, probably. {('Then ' + plan + '.') if plan else 'Nothing heroic planned.'}",
            f"I've got {activity} on the books. {('After that: ' + plan + '.') if plan else 'The rest is unclaimed.'}",
            f"Honestly, {plan + '.' if plan else activity + '. Maybe nothing. Maybe everything.'}",
        ]
    elif kind == "where":
        options = [
            f"Right here at {venue}, clearly. You found me.",
            f"{venue}. That's the whole itinerary for the next hour.",
            f"Wherever the day puts me. Right now: {venue}.",
        ]
    elif kind == "how_feel":
        options = [
            f"{npc.mood.label().capitalize()}, honestly. {npc.goal_short.capitalize()} is the current project.",
            f"Running on {npc.mood.label()} and a decent amount of stubbornness. You?",
            "Better than this morning. Worse than after dinner. Normal, then.",
        ]
    elif kind == "work":
        options = [
            f"{npc.occupation.capitalize()} work. {activity} right now, which is either exciting or a crime.",
            f"I'm a {npc.occupation}. Today has been peak {activity}. Make of that what you will.",
        ]
    elif kind == "who":
        options = [
            f"Who am I? {npc.first}, resident {npc.age}, professional {npc.occupation}. Ask {friend} — they've got opinions.",
            f"Just a {npc.occupation} who knows too many people at {venue}. {npc.first}. Ask around.",
        ]
    elif kind == "why":
        options = [
            f"Because {npc.goal_short} is more fun than it sounds. And because I'm stubborn.",
            f"Habit, mostly. And the goal: {npc.goal_short}. Ask me again in a week.",
        ]
    elif kind == "food":
        options = [
            f"Cafe food at {venue} is underrated. The sandwich is structural.",
            f"I'd kill for something warm. Also, {npc.occupation} schedules and lunch don't mix.",
        ]
    elif kind == "yesno":
        options = [
            "Yeah, mostly. Good coffee, strange neighbors, decent music. No complaints worth filing.",
            f"Honestly? More than I expected. Ask me again after {plan or 'the next thing'}.",
            "Tentatively yes. This block grows on you, like a very loud houseplant.",
        ]
    elif kind == "music":
        options = [
            f"Music is the whole personality. {activity} was originally set to a tempo.",
            "Always. First thing on, last thing off. Ask me about the good stuff sometime.",
        ]
    else:  # generic question with '?'
        options = [
            f"Fair question. Short version: {activity}, then {plan or 'see how the day goes'}.",
            f"Depends. Today's answer is {npc.mood.label()} and {activity}.",
            f"Probably. It's been that kind of week — {npc.goal_short}, all of it.",
        ]
    return _sentence(options[rng.randrange(len(options))]) if options else None


def _fill(template: str, npc: NPC, player: Player, venue_name: str, topic: str, item_name: str) -> str:
    return (template
            .replace("{player}", player.name)
            .replace("{name}", npc.first)
            .replace("{venue}", venue_name)
            .replace("{topic}", topic)
            .replace("{item}", item_name)
            .replace("{job}", npc.occupation))


def _venue_label(location_id: str, location_names: dict[str, str]) -> str:
    if location_id in location_names:
        return location_names[location_id]
    return "the neighborhood"


def _topic_for(npc: NPC, hub: RngHub) -> str:
    """Pick a topic this NPC actually cares about (hobby -> topic pool)."""
    hobby_to_topic = {
        "music": "music", "cooking": "food", "fitness": "fitness", "movies": "movies",
        "reading": "books", "gaming": "tech", "art": "arts", "gardening": "community",
        "fashion": "arts", "coffee": "food", "photography": "arts", "boardgames": "community",
        "dancing": "music", "volunteering": "community", "tech": "tech", "sports": "sports",
    }
    key = hobby_to_topic.get(npc.hobbies[0], "community")
    pool = TOPICS.get(key, TOPICS["community"])
    return pool[hub.stream(f"topic:{npc.id}").randrange(len(pool))]


MOOD_IRRITATED_PREFIX = [
    "Look, I'm going to be honest with you —",
    "Okay, I'm a little heated today, so bear with me.",
    "I'll say this once, because my patience is a small cup today:",
]

HOOK_TEMPLATES = {
    "gift": ["(Also, I'm still using that {item_hint}. It was a good call.)",
             "(Random: I told someone about that {item_hint} you gave me. They were impressed.)"],
    "date": ["(And yes, I'm still thinking about {venue_hint}. That was a good night.)"],
    "conflict": ["(We've had friction before, and I haven't forgotten. But I'm here.)"],
    "call": ["(Good talking to you on the phone, by the way.)"],
    "talk": ["(We keep bumping into each other. I don't hate it.)"],
    "rumor_belief": ["(Different subject: I heard {claim}. I'm still deciding what to think.)"],
}

EVENT_SUMMARY = {
    "gift": "You gave {player} {item}.",
    "date": "You spent a {date_kind} at {venue} with {player}.",
}


def compose_reply(
    *,
    npc: NPC,
    player: Player,
    rel: Relationship,
    text: str,
    intent: str,
    hub: RngHub,
    location_names: dict[str, str],
    item_name: str = "a small gift",
    forced_lines: list[str] | None = None,
    context_hook: str | None = None,
) -> dict:
    rng = hub.fork(f"compose:{npc.id}:{int(intent == 'fallback')}")
    venue = _venue_label(npc.location_id, location_names) if npc.location_id != "home" else "home"
    topic = _topic_for(npc, hub)
    arch = npc.archetype if npc.archetype in ARCHETYPES else "spark"

    # --- choose base line -------------------------------------------------
    if forced_lines:
        base = forced_lines[rng.randrange(len(forced_lines))]
    else:
        pool = line_pool(intent, arch) or line_pool("fallback", arch)
        # a moody NPC occasionally leads with snark, unless you're apologizing
        if npc.mood.irritation >= 62 and intent not in ("apology", "goodbye", "deep") and rng.random() < 0.45:
            prefix = MOOD_IRRITATED_PREFIX[rng.randrange(len(MOOD_IRRITATED_PREFIX))]
            base = f"{prefix} {pool[rng.randrange(len(pool))]}"
        else:
            base = pool[rng.randrange(len(pool))]

    reply = _fill(base, npc, player, venue, topic, item_name)

    # --- answer the actual question ---------------------------------------
    # A generic smalltalk line reads as non-responsive when the player asked
    # something concrete. Ground the answer in simulated state instead.
    social_intents = {"insult", "apology", "ask_date", "flirt", "gift", "gossip", "joke", "compliment"}
    asked = "?" in text or any(pattern.search(text) for _, pattern in QUESTION_PATTERNS)
    if intent not in social_intents and (asked or intent in ("fallback", "smalltalk", "how_are_you")):
        grounded = _grounded_answer(
            npc=npc, player=player, text=text, venue=venue, hub=hub,
            location_names=location_names,
        )
        if grounded:
            reply = grounded

    # --- continuity: recognise familiar faces -----------------------------
    if intent == "greeting" and rel.familiarity >= 30 and rng.random() < 0.5:
        warm_openers = [
            "Oh, it's you — good.", "There you are.", "My favorite interruption.",
            "Hey, look at that, the day improved.",
        ]
        reply = f"{warm_openers[rng.randrange(len(warm_openers))]} {reply}"

    # --- state-aware observation ------------------------------------------
    if rng.random() < 0.28 and player.mood.label() != "steady":
        mood_key = {"buzzing": "happy", "cheerful": "happy", "excited": "happy",
                    "low": "sad", "stressed": "angry", "irritated": "angry", "steady": "neutral"}[player.mood.label()]
        obs = MOOD_LINES[mood_key]
        reply += " " + obs[rng.randrange(len(obs))]

    # --- memory / belief hook --------------------------------------------
    if context_hook:
        reply += " " + context_hook
    elif rng.random() < 0.16:
        memories = [m for m in npc.memory if m.kind in ("gift", "date", "call", "talk", "conflict")]
        if memories:
            m = memories[-1]
            if m.kind == "gift":
                hint = m.summary.split(" gave ")[-1] if " gave " in m.summary else "that gift"
                tpl = HOOK_TEMPLATES["gift"][rng.randrange(len(HOOK_TEMPLATES["gift"]))]
                reply += " " + tpl.replace("{item_hint}", hint)
            elif m.kind in HOOK_TEMPLATES:
                reply += " " + HOOK_TEMPLATES[m.kind][rng.randrange(len(HOOK_TEMPLATES[m.kind]))].replace(
                    "{venue_hint}", _venue_label(m.location, location_names)
                )
        elif npc.beliefs:
            b = npc.beliefs[-1]
            if b.confidence >= 0.55:
                tpl = HOOK_TEMPLATES["rumor_belief"][rng.randrange(len(HOOK_TEMPLATES["rumor_belief"]))]
                reply += " " + tpl.replace("{claim}", b.claim)

    # --- effects ----------------------------------------------------------
    effects = compute_effects(npc, rel, intent, player, hub)
    memories = []
    if intent not in ("bad_greeting",):
        memories.append({
            "kind": "talk", "summary": f"You talked with {player.name} at {venue} ({intent}).",
            "importance": 0.28, "valence": effects["affinity"] / 10.0, "location": npc.location_id,
        })
    return {
        "npc_id": npc.id, "text": reply, "intent": intent, "topic": topic,
        "effects": effects, "memories": memories,
        "mood": npc.mood.label(), "archetype": arch,
    }


def compute_effects(npc: NPC, rel: Relationship, intent: str, player: Player, hub: RngHub) -> dict:
    """Relationship deltas for a conversational beat. Bounded and diminishing."""
    base = {
        "greeting": (2.0, 1.0, 0.4, 0.0, -0.4),
        "how_are_you": (1.6, 1.6, 0.4, 0.0, -0.6),
        "smalltalk": (2.2, 1.2, 0.4, 0.0, -0.4),
        "joke": (2.0, 2.4, 0.6, 0.2, -1.2),
        "compliment": (1.2, 2.8, 0.6, 0.4, -0.2),
        "flirt": (1.6, 2.4, 0.8, 3.6, 0.0),
        "ask_date": (1.2, 1.4, 1.0, 2.0, 0.0),
        "gossip": (2.2, 0.6, 0.3, 0.0, 1.2),
        "invite": (1.8, 2.0, 0.8, 0.4, -0.4),
        "apology": (0.8, 1.2, 2.0, 0.0, -10.0),
        "insult": (0.0, -12.0, -7.0, -2.0, 17.0),
        "deep": (2.8, 2.2, 3.0, 0.8, -0.8),
        "goodbye": (1.0, 0.6, 0.2, 0.0, -0.3),
        "ask_about": (1.8, 1.2, 0.6, 0.2, 0.0),
        "fallback": (1.6, 0.9, 0.4, 0.0, -0.2),
    }.get(intent, (1.4, 0.8, 0.3, 0.0, 0.0))

    fam, aff, trust, romance, tension = base
    # personality modulation
    aff *= 0.75 + npc.stats["warmth"] * 0.5
    if intent == "joke":
        aff *= 0.6 + npc.stats["humor"] * 1.0
    if intent == "compliment":
        aff *= 0.7 + npc.stats["vanity"] * 0.8
    if intent == "apology":
        tension *= (1.6 - npc.stats["forgive"])
        trust *= (0.5 + npc.stats["forgive"])
    if intent == "flirt":
        romance *= 0.6 + npc.stats["warmth"] * 0.8
    if intent == "insult":
        tension *= (0.7 + npc.stats["directness"] * 0.7)

    # history modulation: familiarity makes warmth easier, tension makes it harder
    if aff > 0:
        aff *= (1.25 - rel.tension / 180.0) * (0.8 + min(rel.familiarity, 60) / 150.0)
    # repeated small talk in quick succession is less meaningful
    if intent in ("greeting", "smalltalk", "how_are_you") and rel.last_minute is not None:
        pass
    rng = hub.stream("effects")
    jitter = lambda x: x * rng.uniform(0.92, 1.08)  # noqa: E731
    return {
        "familiarity": round(jitter(fam), 2), "affinity": round(jitter(aff), 2),
        "trust": round(jitter(trust), 2), "romance": round(jitter(romance), 2),
        "tension": round(jitter(tension), 2),
    }


def compose_message_reply(
    *, npc: NPC, player: Player, rel: Relationship, text: str, hub: RngHub,
    location_names: dict[str, str],
) -> str:
    intent = classify_intent(text)
    out = compose_reply(
        npc=npc, player=player, rel=rel, text=text, intent=intent, hub=hub,
        location_names=location_names,
    )
    opener = ["", "", "Hey! ", "Ooh. ", "Okay, so — ", "Ha. "][hub.stream(f"msg:{npc.id}").randrange(6)]
    return opener + out["text"]


def compose_gift_reaction(npc: NPC, rel: Relationship, item: dict, hub: RngHub) -> dict:
    """Recipient-specific gift meaning: tags vs hobbies, values, favourite things."""
    score = 0.0
    reasons = []
    hobby_tags: set[str] = set()
    hobby_map = {
        "music": {"music"}, "cooking": {"food"}, "fitness": {"sport"},
        "movies": {"movies", "arts"}, "reading": {"books"}, "gaming": {"games", "tech"},
        "art": {"arts"}, "gardening": {"plants", "outdoorsy"}, "fashion": {"style"},
        "coffee": {"coffee"}, "photography": {"arts", "tech"}, "boardgames": {"games"},
        "dancing": {"music", "social"}, "volunteering": {"kind", "social"},
        "tech": {"tech", "games"}, "sports": {"sport"},
    }
    for hobby in npc.hobbies:
        hobby_tags |= hobby_map.get(hobby, set())
    tags = set(item.get("tags", []))
    overlap = tags & hobby_tags
    if overlap:
        # A hobby match is the strongest signal, but a cheap token shouldn't
        # out-score a considered gift just because it happens to be edible.
        score += 0.34 + 0.10 * min(2, len(overlap))
        reasons.append("matches their hobbies")

    name = item.get("name", "").lower()
    if name and name in (npc.favorite_food.lower(), npc.favorite_music.lower()):
        score += 0.38
        reasons.append("it's literally their favorite")

    # Perceived thoughtfulness tracks price, but with sharply diminishing
    # returns: a 6 BLX coffee and a 75 BLX pair of headphones are not 12x
    # apart as gifts, and money can never carry a gift on its own.
    price = float(item.get("price", 0) or 0)
    value = min(0.30, price * 0.004)
    if price >= 25:
        reasons.append("it's a real spend")
    score += value

    # A bare food item is a snack, not a gesture, unless it matches something
    # they actually care about.
    if item.get("consumable") or item.get("energy"):
        score -= 0.12 if not overlap else 0.02

    if item.get("tag_color") and item.get("tag_color") == npc.favorite_color:
        score += 0.1
    score += (npc.stats["generosity"] - 0.5) * 0.2
    score += hub.stream(f"gift:{npc.id}").uniform(-0.18, 0.18)

    # saturation: repeated identical gifts lose meaning (design: gifts aren't a cheat code)
    item_id = item.get("id") or item.get("name", "gift")
    repeat = rel.gifts_week.get(item_id, 0)
    score -= repeat * 0.22

    if score >= 0.62:
        mood = "love"
        reaction = line_pool("gift_like", npc.archetype)
        aff, trust, romance = 7.0, 2.2, 1.2
    elif score >= 0.22:
        mood = "like"
        reaction = line_pool("gift_neutral", npc.archetype)
        aff, trust, romance = 3.5, 1.0, 0.4
    else:
        mood = "meh"
        reaction = line_pool("gift_dislike", npc.archetype)
        aff, trust, romance = 0.6, 0.3, 0.0
    if repeat >= 3:
        aff *= 0.45
        trust *= 0.5
    rng = hub.fork(f"giftline:{npc.id}")
    text = reaction[rng.randrange(len(reaction))].replace("{item}", item["name"]).replace("{player}", "you")
    return {
        "mood": mood, "text": text, "reasons": reasons, "affinity": round(aff, 2),
        "trust": round(trust, 2), "romance": round(romance, 2), "repetition": repeat,
        "score": round(score, 2), "value": round(value, 2),
    }
