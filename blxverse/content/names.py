"""Curated name pools for procedural residents and businesses."""

FIRST_NAMES_F = [
    "Amara", "Zara", "Nia", "Adaeze", "Sade", "Ifeoma", "Tara", "Lola", "Maya", "Rina",
    "Lina", "Elif", "Sofia", "Naomi", "Chiara", "Yara", "Nadia", "Imani", "Aisha", "Keira",
    "Bisi", "Halima", "Mila", "Anaya", "Ines", "Dalia", "Nkechi", "Fola", "Imade", "Layla",
    "Thea", "June", "Rae", "Petra",
]
FIRST_NAMES_M = [
    "Daniel", "Kofi", "Tunde", "Jide", "Femi", "Emeka", "Ikenna", "Seyi", "Rafi", "Omar",
    "Yusuf", "Andre", "Luca", "Mateo", "Kenji", "Arjun", "Tobi", "Kunle", "Chidi", "Ayo",
    "Bode", "Hassan", "Malik", "Noah", "Leo", "Elias", "Samir", "Idris", "Kaveh", "Jonas",
    "Rui", "Temi", "Bruno", "Kai",
]
FIRST_NAMES_N = ["Alex", "Juno", "River", "Sky", "Onyx", "Noor", "Wren", "Sage"]

SURNAMES = [
    "Adeyemi", "Okafor", "Bello", "Mensah", "Rivera", "Santos", "Kimura", "Chen", "Osei", "Novak",
    "Haddad", "Silva", "Ueda", "Diallo", "Ferreira", "Petrov", "Bianchi", "Yun", "Achebe", "Larsson",
    "Moreau", "Balogun", "Cabrera", "Obi", "Mensah", "Abara", "Sow", "Park", "Rossi", "Kaur",
    "Mbeki", "Hughes", "Nwosu", "Toure", "Vega", "Sato", "Mensah", "Eze", "Oduya", "Bakare",
]

BUSINESS_NAMES = [
    "Mango & Ink", "The Daily Grind", "Bloom Room", "Vinyl Corner", "Sundae Best", "Paper Planes",
    "The Corner Booth", "Golden Hour Studio", "Little Spoon", "Neon Threads", "Juniper Books",
    "Two Rivers Cafe", "Cloud Nine Bakes", "The Junkyard Gym", "Citrus & Sage",
]

TOPICS = {
    "music": ["new Afrobeats drops", "that festival lineup", "learning guitar", "the amapiano wave", "vinyl digging"],
    "food": ["jollof recipes", "the new suya spot", "breakfast debates", "late-night noodles", "mango season"],
    "fitness": ["morning runs", "the gym playlist", "recovery days", "marathon plans", "stretching routines"],
    "movies": ["the new sci-fi release", "cinema snack prices", "that twist ending", "documentaries", "binge-watching"],
    "books": ["the bookshop sale", "fantasy sagas", "poetry nights", "book club picks", "slow reading"],
    "gossip": ["who is dating who", "the neighbor's new car", "the cafe's mystery regular", "the festival committee drama"],
    "work": ["the new shift rota", "crazy customers", "side hustles", "asking for a raise", "commute traffic"],
    "weather": ["the heat wave", "that surprise rain", "perfect evening air", "the dusty harmattan wind"],
    "sports": ["the weekend match", "the local league", "the park court", "tournament brackets"],
    "community": ["the neighborhood clean-up", "the festival planning", "the new playground idea", "market day"],
    "dating": ["dating in this town", "first-date disasters", "good date spots", "romantic playlists"],
    "arts": ["the mural project", "open-mic night", "pottery class", "street photography"],
    "tech": ["the new phone launch", "gadget reviews", "AI in games", "that glitchy app"],
}

COMPLIMENT_TARGETS = ["style", "sense of humor", "energy", "kindness", "ambition", "taste in music"]


# Guaranteed residents in every full-size BlaxkVille cast; story anchors stay.
FEATURED_M = ["Abdullahi", "Smarty", "Musty", "Legend", "Eboh", "Joski", "Ofucks", "Ysmanny", "Samban", "Ibrahim", "Dami", "Chuks", "Zayyan", "Bashir", "Dominion"]
FEATURED_F = ["Fati", "Jenny", "Omonu", "Elvina", "Zainab", "Amina", "Chiamaka", "Zuri", "Ene", "Adaeze", "Amara", "Aisha", "Halima", "Ifeoma", "Sade", "Imani", "Naomi", "Layla", "Nadia", "Nkechi", "Maya", "Bisi", "Lola", "Yara", "Khadija", "Rahma", "Nneka", "Uchechi", "Chinaza", "Tomi", "Damilola", "Hauwa", "Maryam", "Simi", "Teni", "Bisola"]
FIRST_NAMES_M.extend(n for n in FEATURED_M if n not in FIRST_NAMES_M)
FIRST_NAMES_F.extend(n for n in FEATURED_F if n not in FIRST_NAMES_F)
