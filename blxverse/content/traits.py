"""Personality traits and derived character stats.

Traits are curated descriptors, not open-ended labels: every trait maps to
deterministic behavioural modifiers that the simulation reads directly. That
keeps personalities stable and auditable while dialogue stays generative.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TraitDef:
    id: str
    label: str
    opposite: str
    tags: tuple[str, ...]
    # behavioural modifiers in [-1, 1]
    warmth: float = 0.0
    energy: float = 0.0
    directness: float = 0.0
    risk: float = 0.0
    chatter: float = 0.0
    forgive: float = 0.0
    jealous: float = 0.0
    generosity: float = 0.0
    discipline: float = 0.0
    curiosity: float = 0.0
    humor: float = 0.0
    vanity: float = 0.0


TRAITS: dict[str, TraitDef] = {
    "warm": TraitDef("warm", "Warm", "cold", ("warm", "sweet"), warmth=0.8, generosity=0.4, forgive=0.4, chatter=0.3),
    "cold": TraitDef("cold", "Reserved", "warm", ("quiet", "snarky"), warmth=-0.6, chatter=-0.3, forgive=-0.2),
    "playful": TraitDef("playful", "Playful", "serious", ("playful", "joke"), humor=0.8, energy=0.4, chatter=0.4, risk=0.2),
    "serious": TraitDef("serious", "Serious", "playful", ("neat", "honest"), humor=-0.5, discipline=0.6, chatter=-0.2),
    "bold": TraitDef("bold", "Bold", "shy", ("bold", "loud"), energy=0.5, directness=0.6, risk=0.6),
    "shy": TraitDef("shy", "Shy", "bold", ("shy", "quiet"), energy=-0.3, directness=-0.6, chatter=-0.3),
    "anxious": TraitDef("anxious", "Anxious", "calm", ("anxious", "sweet"), energy=-0.2, risk=-0.5, forgive=0.1),
    "calm": TraitDef("calm", "Calm", "anxious", ("calm", "spiritual"), directness=-0.2, risk=-0.2, forgive=0.3),
    "kind": TraitDef("kind", "Kind", "snarky", ("kind", "sweet"), warmth=0.6, generosity=0.6, forgive=0.5),
    "snarky": TraitDef("snarky", "Snarky", "kind", ("snarky", "spicy"), humor=0.5, warmth=-0.4, directness=0.4),
    "grumpy": TraitDef("grumpy", "Grumpy", "sunny", ("grumpy", "spicy"), warmth=-0.5, forgive=-0.4, humor=-0.2),
    "sunny": TraitDef("sunny", "Sunny", "grumpy", ("warm", "playful"), warmth=0.6, energy=0.4, humor=0.3),
    "ambitious": TraitDef("ambitious", "Ambitious", "laidback", ("ambitious", "proud"), energy=0.5, discipline=0.7, vanity=0.2),
    "laidback": TraitDef("laidback", "Laid-back", "ambitious", ("lazy", "calm"), energy=-0.4, discipline=-0.4, risk=-0.1),
    "artsy": TraitDef("artsy", "Artsy", "practical", ("artsy", "musical", "stylish"), curiosity=0.6, warmth=0.2, vanity=0.2),
    "practical": TraitDef("practical", "Practical", "artsy", ("neat", "honest"), discipline=0.4, risk=-0.3, curiosity=-0.1),
    "gossipy": TraitDef("gossipy", "Gossipy", "private", ("gossipy", "loud"), chatter=0.7, curiosity=0.5, discipline=-0.2),
    "private": TraitDef("private", "Private", "gossipy", ("quiet", "honest"), chatter=-0.5, curiosity=-0.2, forgive=0.1),
    "romantic": TraitDef("romantic", "Romantic", "pragmatic", ("romantic", "sweet"), warmth=0.4, generosity=0.3, jealous=0.2, humor=0.1),
    "pragmatic": TraitDef("pragmatic", "Pragmatic", "romantic", ("neat", "honest"), discipline=0.4, risk=-0.2),
    "foodie": TraitDef("foodie", "Foodie", "fitness", ("foodie", "messy"), chatter=0.2, generosity=0.2, discipline=-0.1),
    "fitness": TraitDef("fitness", "Fitness Fanatic", "foodie", ("sporty", "outdoorsy"), energy=0.5, discipline=0.5),
    "sporty": TraitDef("sporty", "Sporty", "bookish", ("sporty", "outdoorsy"), energy=0.4, risk=0.2),
    "bookish": TraitDef("bookish", "Bookish", "sporty", ("bookish", "nerdy"), curiosity=0.5, energy=-0.2),
    "nerdy": TraitDef("nerdy", "Nerdy", "stylish", ("nerdy", "techy"), curiosity=0.7, humor=0.1),
    "stylish": TraitDef("stylish", "Stylish", "nerdy", ("stylish", "artsy"), vanity=0.6, energy=0.2),
    "wild": TraitDef("wild", "Wild", "orderly", ("wild", "chaotic"), risk=0.8, energy=0.5, discipline=-0.4),
    "orderly": TraitDef("orderly", "Orderly", "wild", ("neat", "honest"), discipline=0.6, risk=-0.4),
}

# The opposite pair table is used to build a balanced, non-contradictory identity.
TRAIT_PAIRS = [
    ("warm", "cold"), ("playful", "serious"), ("bold", "shy"), ("anxious", "calm"),
    ("kind", "snarky"), ("grumpy", "sunny"), ("ambitious", "laidback"), ("artsy", "practical"),
    ("gossipy", "private"), ("romantic", "pragmatic"), ("foodie", "fitness"), ("sporty", "bookish"),
    ("nerdy", "stylish"), ("wild", "orderly"),
]

HOBBIES: dict[str, dict] = {
    "music": {"label": "music", "tags": ("music", "artsy"), "venues": ("music_store", "studio", "park")},
    "cooking": {"label": "cooking", "tags": ("food", "foodie"), "venues": ("grocery", "home")},
    "fitness": {"label": "fitness", "tags": ("sport", "outdoorsy"), "venues": ("gym", "park")},
    "movies": {"label": "movies", "tags": ("movies", "artsy"), "venues": ("cinema",)},
    "reading": {"label": "reading", "tags": ("books", "quiet"), "venues": ("park", "cafe")},
    "gaming": {"label": "gaming", "tags": ("games", "techy"), "venues": ("home", "cafe")},
    "art": {"label": "art", "tags": ("arts", "artsy"), "venues": ("studio", "park")},
    "gardening": {"label": "gardening", "tags": ("plants", "outdoorsy"), "venues": ("park", "home")},
    "fashion": {"label": "fashion", "tags": ("style", "stylish"), "venues": ("clothing", "square")},
    "coffee": {"label": "coffee", "tags": ("coffee", "food"), "venues": ("cafe",)},
    "photography": {"label": "photography", "tags": ("arts", "techy"), "venues": ("park", "square")},
    "boardgames": {"label": "board games", "tags": ("games", "social"), "venues": ("cafe", "home")},
    "dancing": {"label": "dancing", "tags": ("music", "social"), "venues": ("studio", "square")},
    "volunteering": {"label": "volunteering", "tags": ("kind", "social"), "venues": ("park", "market")},
    "tech": {"label": "tinkering", "tags": ("techy", "games"), "venues": ("home", "cafe")},
    "sports": {"label": "sports", "tags": ("sport", "social"), "venues": ("gym", "park")},
}

MUSIC_GENRES = ["Afrobeats", "Highlife", "jazz", "lo-fi", "alt-rock", "amapiano", "soul", "indie pop", "classical", "hip-hop"]
FOODS = ["jollof rice", "suya", "pancakes", "sushi", "pizza", "grilled fish", "shawarma", "mango cake", "ramen", "tacos"]
COLORS = ["amber", "teal", "coral", "violet", "sky blue", "lime", "rose", "indigo", "gold", "mint"]

VALUES = [
    ("honesty", "honesty"), ("loyalty", "loyalty"), ("ambition", "ambition"), ("kindness", "kindness"),
    ("creativity", "creativity"), ("family", "family"), ("independence", "independence"),
    ("community", "community"), ("humor", "humor"), ("stability", "stability"), ("growth", "growth"),
]

BOUNDARIES = [
    "no gossip about my family",
    "no being late without a message",
    "no public arguments",
    "no flirting with my friends",
    "no borrowing money without asking",
    "no pranks that damage my things",
    "no talking over me",
    "no secrets about big plans",
]

SECRETS = [
    ("side_hustle", "is quietly building a side business after hours"),
    ("crush", "has a secret crush on someone in the neighborhood"),
    ("debt", "owes money and is hiding it from a friend"),
    ("song", "is writing songs but is terrified to perform"),
    ("quitting", "is planning to quit their job soon"),
    ("surprise", "is organizing a surprise party for a friend"),
    ("rejection", "got rejected for something big and told nobody"),
    ("move", "is considering moving away from the neighborhood"),
]

ASPIRATIONS = [
    "open a small business", "headline the neighborhood festival", "own a home by the river",
    "be known for generosity", "become a top chef", "coach the local kids' team",
    "write a book", "run for the neighborhood council", "build a community garden",
    "tour with a band", "launch a fashion line", "become the neighborhood's best barista",
]

OCCUPATIONS = [
    ("barista", 88), ("line cook", 96), ("musician", 74), ("music teacher", 102), ("nurse", 150),
    ("electrician", 145), ("graphic designer", 132), ("shopkeeper", 128), ("baker", 104),
    ("bus driver", 118), ("tailor", 106), ("photographer", 114), ("personal trainer", 120),
    ("accountant", 158), ("carpenter", 140), ("journalist", 136), ("florist", 98),
    ("software developer", 168), ("dance instructor", 108), ("cafe owner", 150),
    ("librarian", 100), ("event planner", 126), ("mechanic", 142), ("barber", 110),
    ("makeup artist", 116), ("security guard", 112), ("farmer", 94), ("radio host", 134),
    ("student", 74), ("unemployed", 74), ("social worker", 124), ("physiotherapist", 152),
]
