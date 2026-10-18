"""Canonical world-state data structures.

The simulation owns the truth. LLM-style dialogue never mutates these
directly; every change flows through engine actions which validate and log.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _round(d: dict[str, float], nd: int = 1) -> dict[str, float]:
    return {k: round(float(v), nd) for k, v in d.items()}


# ---------------------------------------------------------------------------
# Mood
# ---------------------------------------------------------------------------
@dataclass
class Mood:
    valence: float = 0.0        # -100 (awful) .. 100 (elated)
    stress: float = 12.0
    excitement: float = 35.0
    irritation: float = 0.0
    social_energy: float = 72.0

    def label(self) -> str:
        if self.irritation >= 62:
            return "irritated"
        if self.stress >= 62:
            return "stressed"
        if self.valence >= 34:
            return "buzzing"
        if self.valence >= 12:
            return "cheerful"
        if self.valence <= -30:
            return "low"
        if self.excitement >= 60:
            return "excited"
        return "steady"

    def to_dict(self) -> dict:
        return {
            "valence": round(self.valence, 1), "stress": round(self.stress, 1),
            "excitement": round(self.excitement, 1), "irritation": round(self.irritation, 1),
            "social_energy": round(self.social_energy, 1), "label": self.label(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Mood:
        return cls(
            valence=float(d.get("valence", 0)), stress=float(d.get("stress", 12)),
            excitement=float(d.get("excitement", 35)), irritation=float(d.get("irritation", 0)),
            social_energy=float(d.get("social_energy", 72)),
        )


# ---------------------------------------------------------------------------
# Memory & beliefs
# ---------------------------------------------------------------------------
@dataclass
class Memory:
    id: str
    minute: float
    day: int
    event_id: str
    kind: str
    summary: str
    importance: float
    valence: float
    source: str = "witnessed"     # witnessed | told | participated | inferred
    with_ids: list[str] = field(default_factory=list)
    location: str = ""
    tag: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "minute": round(self.minute, 2), "day": self.day,
            "event_id": self.event_id, "kind": self.kind, "summary": self.summary,
            "importance": round(self.importance, 2), "valence": round(self.valence, 2),
            "source": self.source, "with": list(self.with_ids), "location": self.location, "tag": self.tag,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Memory:
        return cls(
            id=d["id"], minute=float(d["minute"]), day=int(d["day"]), event_id=d["event_id"],
            kind=d["kind"], summary=d["summary"], importance=float(d["importance"]),
            valence=float(d["valence"]), source=d.get("source", "witnessed"),
            with_ids=list(d.get("with", [])), location=d.get("location", ""), tag=d.get("tag", ""),
        )


@dataclass
class Belief:
    id: str
    claim: str
    subject_id: str
    truth: str                     # true | false | unknown
    confidence: float              # 0..1
    source_id: str
    created_minute: float
    updated_minute: float
    rumor_id: str = ""
    evidence: list[str] = field(default_factory=list)
    challenged_by: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "claim": self.claim, "subject_id": self.subject_id, "truth": self.truth,
            "confidence": round(self.confidence, 3), "source_id": self.source_id,
            "created": round(self.created_minute, 1), "updated": round(self.updated_minute, 1),
            "rumor_id": self.rumor_id, "evidence": list(self.evidence),
            "challenged_by": list(self.challenged_by),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Belief:
        return cls(
            id=d["id"], claim=d["claim"], subject_id=d["subject_id"], truth=d.get("truth", "unknown"),
            confidence=float(d["confidence"]), source_id=d["source_id"],
            created_minute=float(d["created"]), updated_minute=float(d["updated"]),
            rumor_id=d.get("rumor_id", ""), evidence=list(d.get("evidence", [])),
            challenged_by=list(d.get("challenged_by", [])),
        )


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------
@dataclass
class Relationship:
    familiarity: float = 0.0
    trust: float = 18.0
    affinity: float = 0.0
    romance: float = 0.0
    tension: float = 0.0
    interactions: int = 0
    last_minute: float = -9999.0
    gifts_week: dict[str, int] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    # bonding history counts
    dates: int = 0
    conflicts: int = 0

    def label(self, npc_side: str = "friendly") -> str:
        if "ex" in self.flags:
            return "ex"
        if "dating" in self.flags:
            return "partner" if self.romance >= 60 else "dating"
        if "family" in self.flags:
            return "family"
        if "rival" in self.flags or self.tension >= 62:
            return "rival"
        if self.romance >= 45 and self.familiarity >= 40:
            return "crush"
        if self.affinity >= 52 and self.familiarity >= 45:
            return "close friend"
        if self.affinity >= 20:
            return "friend"
        if self.familiarity < 8:
            return "stranger"
        if self.tension >= 30:
            return "tense"
        return "acquaintance"

    def to_dict(self) -> dict:
        return {
            "familiarity": round(self.familiarity, 1), "trust": round(self.trust, 1),
            "affinity": round(self.affinity, 1), "romance": round(self.romance, 1),
            "tension": round(self.tension, 1), "interactions": self.interactions,
            "last": round(self.last_minute, 1), "gifts": dict(self.gifts_week),
            "flags": list(self.flags), "dates": self.dates, "conflicts": self.conflicts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Relationship:
        return cls(
            familiarity=float(d.get("familiarity", 0)), trust=float(d.get("trust", 18)),
            affinity=float(d.get("affinity", 0)), romance=float(d.get("romance", 0)),
            tension=float(d.get("tension", 0)), interactions=int(d.get("interactions", 0)),
            last_minute=float(d.get("last", -9999)), gifts_week=dict(d.get("gifts", {})),
            flags=list(d.get("flags", [])), dates=int(d.get("dates", 0)),
            conflicts=int(d.get("conflicts", 0)),
        )


# ---------------------------------------------------------------------------
# NPC
# ---------------------------------------------------------------------------
@dataclass
class NPC:
    id: str
    first: str
    last: str
    gender: str
    pronouns: str
    age: int
    age_bracket: str
    occupation: str
    salary: int
    workplace: str
    home_id: int
    household_id: int
    household_role: str
    archetype: str
    traits: list[str]
    stats: dict[str, float]
    voice: dict[str, float]
    look: dict[str, Any]
    schedule: dict[str, list]
    hobbies: list[str]
    favorite_music: str
    favorite_food: str
    favorite_color: str
    values: list[str]
    boundaries: list[str]
    goal_short: str
    goal_long: str
    secret: dict
    quirk: str
    wallet: int
    bills_due: int
    spending_habit: str
    mood: Mood
    energy: float
    x: float
    y: float
    home_xy: tuple[float, float]
    location_id: str = "home"
    status: str = "idle"
    activity: str = ""
    target: dict | None = None
    schedule_activity: str = ""
    memory: list[Memory] = field(default_factory=list)
    beliefs: list[Belief] = field(default_factory=list)
    plans: list[dict] = field(default_factory=list)
    spotlight: bool = False
    flags: dict[str, Any] = field(default_factory=dict)
    group_hint: str = ""
    # transient, not serialised: last decision minute
    next_decision: float = 0.0

    @property
    def name(self) -> str:
        return f"{self.first} {self.last}"

    def rel_state(self) -> str:
        return self.mood.label()

    def has_memory_of(self, event_id: str) -> bool:
        return any(m.event_id == event_id for m in self.memory)

    def remember(self, mem: Memory) -> None:
        self.memory.append(mem)
        if len(self.memory) > 90:
            # keep the most important & recent
            self.memory.sort(key=lambda m: (m.importance * 0.6 + m.minute / 100000.0), reverse=True)
            self.memory = self.memory[:90]

    def to_dict(self, include_memory: bool = True) -> dict:
        d = {
            "id": self.id, "first": self.first, "last": self.last, "name": self.name,
            "gender": self.gender, "pronouns": self.pronouns, "age": self.age,
            "age_bracket": self.age_bracket, "occupation": self.occupation, "salary": self.salary,
            "workplace": self.workplace, "home_id": self.home_id, "household_id": self.household_id,
            "household_role": self.household_role, "archetype": self.archetype, "traits": self.traits,
            "stats": _round(self.stats, 2), "voice": self.voice, "look": self.look,
            "schedule": self.schedule, "hobbies": self.hobbies, "music": self.favorite_music,
            "food": self.favorite_food, "color": self.favorite_color, "values": self.values,
            "boundaries": self.boundaries, "goal_short": self.goal_short, "goal_long": self.goal_long,
            "secret": {"id": self.secret.get("id"), "hint": self.secret.get("hint")},
            "quirk": self.quirk, "wallet": self.wallet, "bills_due": self.bills_due,
            "spending_habit": self.spending_habit, "mood": self.mood.to_dict(),
            "energy": round(self.energy, 1), "x": round(self.x, 1), "y": round(self.y, 1),
            "location": self.location_id, "status": self.status, "activity": self.activity,
            "target": self.target,
            "plans": self.plans, "spotlight": self.spotlight, "flags": self.flags,
            "group_hint": self.group_hint,
        }
        if include_memory:
            d["memory"] = [m.to_dict() for m in self.memory[-12:]]
            d["beliefs"] = [b.to_dict() for b in self.beliefs[-10:]]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> NPC:
        npc = cls(
            id=d["id"], first=d["first"], last=d["last"], gender=d["gender"],
            pronouns=d["pronouns"], age=int(d["age"]), age_bracket=d["age_bracket"],
            occupation=d["occupation"], salary=int(d["salary"]), workplace=d["workplace"],
            home_id=int(d["home_id"]), household_id=int(d["household_id"]),
            household_role=d["household_role"], archetype=d["archetype"], traits=list(d["traits"]),
            stats=dict(d["stats"]), voice=dict(d["voice"]), look=dict(d["look"]),
            schedule=dict(d["schedule"]), hobbies=list(d["hobbies"]), favorite_music=d["music"],
            favorite_food=d["food"], favorite_color=d["color"], values=list(d["values"]),
            boundaries=list(d["boundaries"]), goal_short=d["goal_short"], goal_long=d["goal_long"],
            secret=dict(d["secret"]), quirk=d.get("quirk", ""), wallet=int(d["wallet"]),
            bills_due=int(d["bills_due"]), spending_habit=d["spending_habit"],
            mood=Mood.from_dict(d["mood"]), energy=float(d["energy"]), x=float(d["x"]),
            y=float(d["y"]), home_xy=tuple(d["look"].get("home_xy", (0, 0))),
            location_id=d.get("location", "home"), status=d.get("status", "idle"),
            activity=d.get("activity", ""), target=d.get("target"), plans=list(d.get("plans", [])),
            spotlight=bool(d.get("spotlight")), flags=dict(d.get("flags", {})),
            group_hint=d.get("group_hint", ""),
        )
        npc.memory = [Memory.from_dict(m) for m in d.get("memory_full", [])]
        npc.beliefs = [Belief.from_dict(b) for b in d.get("beliefs_full", [])]
        return npc


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------
@dataclass
class Player:
    id: str
    name: str
    gender: str
    pronouns: str
    age: int
    occupation: str
    look: dict[str, Any]
    home_id: int
    wallet: int
    energy: float
    mood: Mood
    reputation: float
    x: float
    y: float
    inventory: dict[str, int] = field(default_factory=dict)
    ledger: list[dict] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    stats: dict[str, float] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "gender": self.gender, "pronouns": self.pronouns,
            "age": self.age, "occupation": self.occupation, "look": self.look,
            "home_id": self.home_id, "wallet": self.wallet, "energy": round(self.energy, 1),
            "mood": self.mood.to_dict(), "reputation": round(self.reputation, 1),
            "x": round(self.x, 1), "y": round(self.y, 1), "inventory": dict(self.inventory),
            "ledger": self.ledger[-60:], "flags": self.flags, "stats": self.stats,
            "created_at": self.created_at, "last_active": self.last_active,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Player:
        return cls(
            id=d["id"], name=d["name"], gender=d["gender"], pronouns=d["pronouns"],
            age=int(d.get("age", 26)), occupation=d.get("occupation", "newcomer"),
            look=dict(d.get("look", {})), home_id=int(d.get("home_id", 0)),
            wallet=int(d.get("wallet", 300)), energy=float(d.get("energy", 100)),
            mood=Mood.from_dict(d.get("mood", {})), reputation=float(d.get("reputation", 50)),
            x=float(d.get("x", 900)), y=float(d.get("y", 760)),
            inventory=dict(d.get("inventory", {})), ledger=list(d.get("ledger", [])),
            flags=dict(d.get("flags", {})), stats=dict(d.get("stats", {})),
            created_at=float(d.get("created_at", time.time())),
            last_active=float(d.get("last_active", time.time())),
        )


# ---------------------------------------------------------------------------
# Social feed
# ---------------------------------------------------------------------------
@dataclass
class Comment:
    id: str
    author_id: str
    text: str
    minute: float
    likes: int = 0

    def to_dict(self) -> dict:
        return {"id": self.id, "author": self.author_id, "text": self.text,
                "minute": round(self.minute, 1), "likes": self.likes}


@dataclass
class Post:
    id: str
    author_id: str
    text: str
    minute: float
    mood: str = ""
    likes: list[str] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    tag: str = ""
    loc: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "author": self.author_id, "text": self.text,
            "minute": round(self.minute, 1), "mood": self.mood, "likes": list(self.likes),
            "comments": [c.to_dict() for c in self.comments], "tag": self.tag, "loc": self.loc,
        }


@dataclass
class Message:
    id: str
    sender: str
    text: str
    minute: float
    read: bool = False
    kind: str = "text"        # text | missed_call | event | gift
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "sender": self.sender, "text": self.text,
                "minute": round(self.minute, 1), "read": self.read, "kind": self.kind,
                "meta": self.meta}


@dataclass
class Thread:
    npc_id: str
    messages: list[Message] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"npc_id": self.npc_id, "messages": [m.to_dict() for m in self.messages[-80:]]}


# ---------------------------------------------------------------------------
# Story structures
# ---------------------------------------------------------------------------
@dataclass
class Rivalry:
    id: str
    a: str
    b: str
    cause: str
    tension: float
    status: str = "simmering"      # simmering | watching | clashing | reconciling | resolved
    created: float = 0.0
    last_minute: float = 0.0
    clashes: int = 0
    witnesses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"id": self.id, "a": self.a, "b": self.b, "cause": self.cause,
                "tension": round(self.tension, 1), "status": self.status,
                "created": round(self.created, 1), "last": round(self.last_minute, 1),
                "clashes": self.clashes, "witnesses": self.witnesses[-6:]}


@dataclass
class Case:
    id: str
    title: str
    description: str
    accuser: str
    accused: str
    item: str
    location: str
    status: str = "open"           # open | cleared | unsolved
    created: float = 0.0
    min_trust: float = 0.0
    helpful_evidence: list[str] = field(default_factory=list)
    found_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "description": self.description,
                "accuser": self.accuser, "accused": self.accused, "item": self.item,
                "location": self.location, "status": self.status, "created": round(self.created, 1),
                "evidence": self.found_evidence, "helpful": self.helpful_evidence}


@dataclass
class Arc:
    id: str
    kind: str
    title: str
    summary: str
    actors: list[str]
    stage: int = 0
    stages: list[str] = field(default_factory=list)
    status: str = "active"         # active | resolved | faded
    created: float = 0.0
    last_minute: float = 0.0
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "title": self.title, "summary": self.summary,
                "actors": self.actors, "stage": self.stage, "stage_title": self.stage_title(),
                "status": self.status, "created": round(self.created, 1),
                "last": round(self.last_minute, 1), "data": self.data}

    def stage_title(self) -> str:
        if 0 <= self.stage < len(self.stages):
            return self.stages[self.stage]
        return ""
