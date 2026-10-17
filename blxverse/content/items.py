"""Gift & shop catalog. Prices are fictional BLX with a 1 BLX ≈ 1 USD internal reference."""

ITEMS = [
    {"id": "coffee_voucher", "name": "coffee voucher", "price": 6, "tags": ["coffee", "food"],
     "icon": "☕", "shop": ["cafe"], "blurb": "A little card for a warm drink. Universally welcome."},
    {"id": "cupcakes", "name": "box of cupcakes", "price": 12, "tags": ["food", "sweet"],
     "icon": "🧁", "shop": ["restaurant", "cafe"], "blurb": "Six cupcakes. Sharing optional but noticed."},
    {"id": "house_plant", "name": "house plant", "price": 22, "tags": ["plants", "cozy"],
     "icon": "🪴", "shop": ["park"], "blurb": "A stubborn little plant that survives almost anything."},
    {"id": "vinyl_record", "name": "vinyl record", "price": 28, "tags": ["music", "arts"],
     "icon": "💿", "shop": ["music_store"], "blurb": "Warm crackle, big cover art, instant personality."},
    {"id": "novel", "name": "paperback novel", "price": 20, "tags": ["books", "quiet"],
     "icon": "📖", "shop": ["music_store", "grocery"], "blurb": "A story worth losing an evening to."},
    {"id": "sneakers", "name": "fresh sneakers", "price": 65, "tags": ["sport", "style"],
     "icon": "👟", "shop": ["clothing"], "blurb": "The kind of shoes that make you take the long way home."},
    {"id": "scarf", "name": "silk scarf", "price": 30, "tags": ["style", "cozy"],
     "icon": "🧣", "shop": ["clothing"], "blurb": "Practically a personality upgrade."},
    {"id": "spicy_sauce", "name": "house hot sauce", "price": 9, "tags": ["food", "spicy"],
     "icon": "🌶️", "shop": ["grocery"], "blurb": "Small bottle. Large consequences."},
    {"id": "postcard_print", "name": "framed art postcard", "price": 14, "tags": ["arts"],
     "icon": "🖼️", "shop": ["studio"], "blurb": "A tiny print of the fountain at golden hour."},
    {"id": "keychain", "name": "telescope keychain", "price": 18, "tags": ["tech", "cozy"],
     "icon": "🔭", "shop": ["grocery", "music_store"], "blurb": "For looking up, literally."},
    {"id": "guitar_picks", "name": "set of guitar picks", "price": 12, "tags": ["music"],
     "icon": "🎸", "shop": ["music_store"], "blurb": "The good thickness. Musicians are picky about this."},
    {"id": "board_game", "name": "board game", "price": 26, "tags": ["games", "social"],
     "icon": "🎲", "shop": ["grocery"], "blurb": "Guaranteed friendship stress-test in one box."},
    {"id": "spa_candle", "name": "spa candle", "price": 24, "tags": ["cozy", "style"],
     "icon": "🕯️", "shop": ["salon"], "blurb": "Smells like calm, low stakes and expensive blankets."},
    {"id": "headphones", "name": "headphones", "price": 75, "tags": ["tech", "music"],
     "icon": "🎧", "shop": ["music_store"], "blurb": "Noise cancellation for a loud neighborhood."},
    {"id": "picnic_basket", "name": "picnic basket", "price": 35, "tags": ["food", "social", "outdoorsy"],
     "icon": "🧺", "shop": ["grocery", "park"], "blurb": "Everything you need to sit on grass with intent."},
    {"id": "camera_film", "name": "camera film roll", "price": 20, "tags": ["tech", "arts"],
     "icon": "📷", "shop": ["studio"], "blurb": "36 chances to be sentimental."},
    {"id": "cookbook", "name": "neighborhood cookbook", "price": 24, "tags": ["food", "books"],
     "icon": "🍲", "shop": ["grocery", "music_store"], "blurb": "Recipes collected from every kitchen on the block."},
    {"id": "football", "name": "worn football", "price": 30, "tags": ["sport", "social"],
     "icon": "⚽", "shop": ["gym"], "blurb": "Perfectly scuffed. Perfectly balanced."},
    {"id": "fountain_pen", "name": "fountain pen", "price": 26, "tags": ["books", "style"],
     "icon": "🖋️", "shop": ["music_store"], "blurb": "For people who write things down and mean it."},
    {"id": "mystery_box", "name": "mystery box", "price": 16, "tags": ["games", "wild"],
     "icon": "🎁", "shop": ["grocery"], "blurb": "Contents unknown. Confidence required."},
]

ITEM_BY_ID = {i["id"]: i for i in ITEMS}

# Player-usable consumables (not giftable)
CONSUMABLES = {
    "sandwich": {
        "id": "sandwich", "name": "sandwich", "price": 8, "energy": 22, "mood": 2, "stress": 1,
        "icon": "🥪", "shop": ["cafe", "grocery"],
        "blurb": "The cafe's counter sandwich. Structural, reliable, slightly too much mustard.",
        "verb": "ate", "text": "You eat the sandwich on the steps. Energy returns, dignity optional.",
        "tags": ["food"],
    },
    "iced_coffee": {
        "id": "iced_coffee", "name": "iced coffee", "price": 5, "energy": 12, "mood": 2, "stress": 0,
        "icon": "🧋", "shop": ["cafe"],
        "blurb": "Cold, loud, and exactly what the afternoon asked for.",
        "verb": "drank", "text": "You drink the iced coffee. Your thoughts acquire a marching band.",
        "tags": ["food", "coffee"],
    },
    "smoothie": {
        "id": "smoothie", "name": "smoothie", "price": 7, "energy": 16, "mood": 3, "stress": 2,
        "icon": "🥤", "shop": ["cafe", "grocery"],
        "blurb": "Fruit blended with the confidence of a wellness influencer.",
        "verb": "drank", "text": "You drink the smoothie. Somewhere, a blender feels proud.",
        "tags": ["food"],
    },
}

CONSUMABLE_IDS = frozenset(CONSUMABLES)
CONSUMABLES_LIST = [
    {k: v[k] for k in ("id", "name", "price", "icon", "blurb", "energy", "mood", "shop", "tags")}
    for v in CONSUMABLES.values()
]


def buyable(item_id: str) -> dict | None:
    """Gift catalog first, then the cafe counter menu."""
    item = ITEM_BY_ID.get(item_id)
    if item is not None:
        return item
    food = CONSUMABLES.get(item_id)
    if food is not None:
        return {**food, "shop": list(food.get("shop", [])), "blurb": food.get("blurb", "")}
    return None


def gift_score_hint(item: dict, npc: dict) -> str:
    """Coarse, spoiler-light hint shown in the gift dialog."""
    hobby_tags = " ".join(npc.get("hobbies", []))
    tags = " ".join(item.get("tags", []))
    pool = []
    if any(t in hobby_tags for t in ("music", "cooking", "fitness", "movies", "reading", "gaming", "art", "gardening", "fashion", "coffee", "photography", "boardgames", "dancing", "volunteering", "tech", "sports")):
        pool.append("hobby")
    if any(k in tags for k in ("food", "music", "books", "sport", "style", "arts", "tech", "plants", "games", "cozy", "social")):
        pool.append("tag")
    return "hobby" if pool else "unknown"
