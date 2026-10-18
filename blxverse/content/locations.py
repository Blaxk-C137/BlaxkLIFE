"""Locations and venue data for the BlaxkVille neighborhood.

Coordinates are world-space pixels. The client renders from this same payload,
so the map and the simulation can never disagree.
"""

from __future__ import annotations

LOCATIONS = [
    {
        "id": "cafe", "name": "Two Rivers Cafe", "kind": "cafe", "icon": "☕",
        "x": 260, "y": 300, "w": 210, "h": 150, "color": "#b9673d",
        "desc": "Warm light, loud espresso machine, and the best mango cake in BlaxkVille.",
        "hours": [7, 22], "role": "social",
        "activities": [
            {"id": "coffee", "label": "Order a coffee", "cost": 6, "minutes": 20, "mood": 3, "social": 4},
            {"id": "cake", "label": "Mango cake & people-watching", "cost": 10, "minutes": 25, "mood": 5, "social": 4},
            {"id": "chat_barista", "label": "Chat with the barista", "cost": 0, "minutes": 15, "mood": 2, "social": 6},
        ],
    },
    {
        "id": "park", "name": "Juniper Park", "kind": "park", "icon": "🌳",
        "x": 640, "y": 220, "w": 280, "h": 190, "color": "#5f9a5b",
        "desc": "Old trees, a creaky swing set, and enough space for a picnic or a chase scene.",
        "hours": [6, 23], "role": "social",
        "activities": [
            {"id": "stroll", "label": "Take a stroll", "cost": 0, "minutes": 20, "mood": 4, "social": 2},
            {"id": "picnic", "label": "Picnic blanket moment", "cost": 12, "minutes": 40, "mood": 7, "social": 6},
            {"id": "swings", "label": "Hit the swings", "cost": 0, "minutes": 15, "mood": 6, "social": 3},
        ],
    },
    {
        "id": "grocery", "name": "BlaxkVille Market", "kind": "market", "icon": "🧺",
        "x": 1080, "y": 240, "w": 220, "h": 150, "color": "#c9892f",
        "desc": "Fresh produce, loud bargaining, and gossip exchanged over tomatoes.",
        "hours": [7, 21], "role": "shop",
        "activities": [
            {"id": "browse", "label": "Browse the stalls", "cost": 0, "minutes": 15, "mood": 3, "social": 3},
            {"id": "groceries", "label": "Buy groceries", "cost": 22, "minutes": 20, "mood": 2, "social": 1},
        ],
    },
    {
        "id": "gym", "name": "The Junkyard Gym", "kind": "gym", "icon": "🏋️",
        "x": 1460, "y": 250, "w": 200, "h": 140, "color": "#6b7280",
        "desc": "Chalk dust, a boombox, and a punching bag named Gerald.",
        "hours": [5, 22], "role": "activity",
        "activities": [
            {"id": "workout", "label": "Work out", "cost": 15, "minutes": 45, "mood": 5, "social": 2, "energy": -18},
            {"id": "spar", "label": "Light sparring", "cost": 10, "minutes": 30, "mood": 4, "social": 5, "energy": -14},
        ],
    },
    {
        "id": "cinema", "name": "Starlite Cinema", "kind": "cinema", "icon": "🎬",
        "x": 330, "y": 700, "w": 230, "h": 150, "color": "#7c3aed",
        "desc": "One screen, red velvet seats, and popcorn with suspiciously generous butter.",
        "hours": [11, 23], "role": "date",
        "activities": [
            {"id": "movie", "label": "Catch a movie", "cost": 18, "minutes": 110, "mood": 7, "social": 5},
            {"id": "popcorn", "label": "Popcorn & debating the trailer", "cost": 9, "minutes": 25, "mood": 4, "social": 4},
        ],
    },
    {
        "id": "restaurant", "name": "Saffron & Smoke", "kind": "restaurant", "icon": "🍲",
        "x": 780, "y": 640, "w": 220, "h": 150, "color": "#a16207",
        "desc": "Dinner dates, birthday dinners, and at least one dramatic public scene per week.",
        "hours": [11, 23], "role": "date",
        "activities": [
            {"id": "dinner", "label": "Dinner", "cost": 42, "minutes": 70, "mood": 8, "social": 7},
            {"id": "dessert", "label": "Dessert only", "cost": 14, "minutes": 30, "mood": 5, "social": 4},
        ],
    },
    {
        "id": "studio", "name": "Golden Hour Studio", "kind": "studio", "icon": "🎙️",
        "x": 1210, "y": 690, "w": 220, "h": 150, "color": "#0f766e",
        "desc": "A converted garage with foam on the walls and big dreams in the booth.",
        "hours": [9, 23], "role": "activity",
        "activities": [
            {"id": "openmic", "label": "Open-mic night", "cost": 5, "minutes": 60, "mood": 8, "social": 8},
            {"id": "record", "label": "Record a demo", "cost": 25, "minutes": 60, "mood": 6, "social": 3},
        ],
    },
    {
        "id": "clothing", "name": "Neon Threads", "kind": "shop", "icon": "👕",
        "x": 150, "y": 1000, "w": 230, "h": 140, "color": "#be185d",
        "desc": "Thrift racks, tailoring in the back, and a mirror that has heard every opinion.",
        "hours": [9, 21], "role": "shop",
        "activities": [
            {"id": "browse", "label": "Try things on", "cost": 0, "minutes": 20, "mood": 5, "social": 2},
            {"id": "style", "label": "Get a style consult", "cost": 30, "minutes": 30, "mood": 6, "social": 3},
        ],
    },
    {
        "id": "music_store", "name": "Vinyl Corner", "kind": "shop", "icon": "💿",
        "x": 700, "y": 1020, "w": 210, "h": 140, "color": "#b45309",
        "desc": "Dusty crates, listening booths, and one cat who judges your taste.",
        "hours": [10, 21], "role": "shop",
        "activities": [
            {"id": "dig", "label": "Dig through crates", "cost": 0, "minutes": 25, "mood": 5, "social": 2},
            {"id": "listen", "label": "Listening booth session", "cost": 8, "minutes": 30, "mood": 6, "social": 1},
        ],
    },
    {
        "id": "salon", "name": "The Glow Room", "kind": "salon", "icon": "💇",
        "x": 1150, "y": 1010, "w": 210, "h": 140, "color": "#9333ea",
        "desc": "Where haircuts come with life advice, most of it unsolicited but accurate.",
        "hours": [9, 20], "role": "shop",
        "activities": [
            {"id": "cut", "label": "Fresh haircut", "cost": 30, "minutes": 45, "mood": 6, "social": 3},
            {"id": "gossip", "label": "Haircut + gossip hour", "cost": 34, "minutes": 60, "mood": 7, "social": 6},
        ],
    },
    {
        "id": "square", "name": "BlaxkVille Square", "kind": "square", "icon": "⛲",
        "x": 1560, "y": 650, "w": 250, "h": 190, "color": "#0e7490",
        "desc": "The fountain, the notice board, and the unofficial stage for every neighborhood scene.",
        "hours": [0, 24], "role": "social",
        "activities": [
            {"id": "peoplewatch", "label": "People-watch by the fountain", "cost": 0, "minutes": 20, "mood": 4, "social": 5},
            {"id": "noticeboard", "label": "Check the notice board", "cost": 0, "minutes": 10, "mood": 2, "social": 2},
        ],
    },
]

SPAWN_POINTS = {
    "cafe": (355, 452),
    "park": (770, 520),
    "grocery": (1180, 452),
    "gym": (1550, 448),
    "cinema": (438, 900),
    "restaurant": (880, 838),
    "studio": (1310, 888),
    "clothing": (258, 1180),
    "music_store": (800, 1200),
    "salon": (1248, 1188),
    "square": (1680, 890),
}

HOMES = [
    (120, 520, "#e2b07a"), (470, 470, "#a7c4a0"), (860, 460, "#d9a5b3"), (1300, 470, "#9fb8d9"),
    (1710, 410, "#d9c09f"), (250, 880, "#c5a3d9"), (600, 900, "#9fd3c7"), (1050, 900, "#e6c47a"),
    (1520, 940, "#d9a58f"), (420, 1160, "#a0b8c4"), (980, 1180, "#c9b2e0"), (1600, 1180, "#b0c99a"),
    (70, 720, "#e0c3a5"), (1780, 840, "#a9c9a0"), (300, 1180, "#d8a8a8"), (1320, 1210, "#a8b8d8"),
    (1820, 1100, "#c8b090"), (520, 1080, "#b0d0b0"), (120, 220, "#d8c8a0"), (900, 240, "#b8a8d0"),
]

WORKPLACE_BY_OCCUPATION = {
    "barista": "cafe", "line cook": "restaurant", "musician": "studio", "music teacher": "studio",
    "nurse": "salon", "electrician": "gym", "graphic designer": "cafe", "shopkeeper": "clothing",
    "baker": "restaurant", "bus driver": "square", "tailor": "clothing", "photographer": "park",
    "personal trainer": "gym", "accountant": "square", "carpenter": "music_store", "journalist": "cafe",
    "florist": "park", "software developer": "cafe", "dance instructor": "studio", "cafe owner": "cafe",
    "librarian": "music_store", "event planner": "square", "mechanic": "gym", "barber": "salon",
    "makeup artist": "salon", "security guard": "square", "farmer": "grocery", "radio host": "studio",
    "student": "cafe", "unemployed": "park", "social worker": "square", "physiotherapist": "gym",
}

# Civic facilities occupy the unused northern/perimeter lots; city dimensions stay fixed.
LOCATIONS += [
    {"id":"hospital", "name":"BlaxkVille General", "kind":"hospital", "icon":"🏥", "x":1070,"y":65,"w":210,"h":110,"color":"#447d80", "desc":"Emergency care, recovery wards and neighbours looking out for each other.","hours":[0,24],"role":"civic","activities":[]},
    {"id":"graveyard", "name":"Juniper Rest", "kind":"graveyard", "icon":"🕊️", "x":1430,"y":65,"w":280,"h":125,"color":"#52675b", "desc":"A quiet memorial garden. Deaths here are permanent; every name has a history.","hours":[0,24],"role":"civic","activities":[]},
    {"id":"police", "name":"Community Police", "kind":"police", "icon":"🚓", "x":70,"y":65,"w":190,"h":90,"color":"#345d8f", "desc":"Report thefts, disputes and raids. Officers patrol the neighbourhood.","hours":[0,24],"role":"civic","activities":[]},
    {"id":"barracks", "name":"Northgate Garrison", "kind":"barracks", "icon":"🛡️", "x":300,"y":65,"w":210,"h":110,"color":"#62724e", "desc":"A small soldier detachment responds to armed bandit squads.","hours":[0,24],"role":"civic","activities":[]},
    {"id":"black_market", "name":"The Backlot", "kind":"black_market", "icon":"🌑", "x":1740,"y":200,"w":120,"h":130,"color":"#4d4058", "desc":"Fictional gun and drug businesses. Abstract inventory, risky returns and police seizures—not real-world instructions.","hours":[0,24],"role":"civic","activities":[]},
]
for site in LOCATIONS:
    if site['role']=='civic':
        op={'hospital':'treatment','graveyard':'respects','police':'report','barracks':'report'}.get(site['id'])
        site['activities']=[{'id':op or 'ledger','label': {'treatment':'Get treatment','respects':'Pay respects','report':'Report an incident'}.get(op,'Review the abstract trading ledger'),'cost':0,'minutes':5,'mood':1,'social':0,**({'civic_op':op} if op else {})}]
SPAWN_POINTS.update({loc['id']:(loc['x']+loc['w']/2, loc['y']+loc['h']+36) for loc in LOCATIONS if loc['role']=='civic'})
WORKPLACE_BY_OCCUPATION['nurse'] = 'hospital'
LOCATION_BY_ID = {loc["id"]: loc for loc in LOCATIONS}


def venue_center(loc_id: str) -> tuple[float, float]:
    loc = LOCATION_BY_ID[loc_id]
    return loc["x"] + loc["w"] / 2, loc["y"] + loc["h"] / 2
