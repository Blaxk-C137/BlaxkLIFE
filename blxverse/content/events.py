"""The block's weekly calendar: recurring events, birthdays, and what's next.

Everything here is deterministic. A weekday is 0 = Monday (matching
``sim.WEEKDAYS``), and every time is an absolute game minute
(``day * 1440 + clock``), so the calendar advances with the simulation instead
of the wall clock.

The player-facing payoff is the journal's "Coming up" list and the phone's
Calendar tab: neighbours actually turn up to these, so showing up too is the
point.
"""

from __future__ import annotations

from dataclasses import dataclass

from blxverse.content.locations import LOCATION_BY_ID
from blxverse.engine.rng import stable_hash

# ---------------------------------------------------------------------------
# Weekly fixtures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeeklyEvent:
    id: str
    title: str
    venue: str
    weekday: int          # 0 = Monday
    start: int            # minutes after midnight
    duration: int         # minutes
    icon: str
    host: str             # first name of the resident who runs it
    tags: tuple[str, ...]  # hobbies that pull residents in
    blurb: str


WEEKLY_EVENTS: tuple[WeeklyEvent, ...] = (
    WeeklyEvent(
        "sunrise_run", "Sunrise Run", "park", 0, 6 * 60 + 30, 60, "🌅", "Tobi",
        ("fitness", "sport"), "Three laps, one thermos of tea, everyone pretending they are not out of breath.",
    ),
    WeeklyEvent(
        "quiz_night", "Quiz Night", "cafe", 1, 19 * 60, 120, "🧠", "Layla",
        ("trivia", "books", "coffee"), "Six rounds, one disputed answer, a prize nobody has ever claimed.",
    ),
    WeeklyEvent(
        "open_studio", "Open Studio", "studio", 2, 17 * 60, 180, "🎨", "Naomi",
        ("art", "photography", "design"), "The studio props its door open and the whole block wanders through.",
    ),
    WeeklyEvent(
        "open_mic", "Open Mic Night", "music_store", 3, 19 * 60 + 30, 150, "🎤", "Zara",
        ("music", "poetry"), "Half the block performs, the other half claims they came for the snacks.",
    ),
    WeeklyEvent(
        "film_club", "Late Film Club", "cinema", 4, 20 * 60, 135, "🎬", "Samir",
        ("film", "art"), "One cult classic, one argument in the lobby afterwards.",
    ),
    WeeklyEvent(
        "market_day", "Market Day", "square", 5, 9 * 60, 300, "🧺", "Aisha",
        ("cooking", "coffee", "fitness"), "Stalls, samples, and a queue that exists mostly to gossip in.",
    ),
    WeeklyEvent(
        "flea_market", "Flea Market", "clothing", 6, 10 * 60, 240, "🧥", "Kofi",
        ("fashion", "art", "music"), "Clothes, old records, and one lamp that has changed hands four times.",
    ),
    WeeklyEvent(
        "sunday_roast", "Sunday Roast", "restaurant", 6, 13 * 60, 150, "🍲", "Verity",
        ("cooking", "food"), "A long table, too much food, and the landlord doing a speech.",
    ),
)

EVENT_BY_ID = {ev.id: ev for ev in WEEKLY_EVENTS}

# Birthdays happen at 18:00 on a resident's own weekday.
BIRTHDAY_CLOCK = 18 * 60


# ---------------------------------------------------------------------------
# Time helpers (absolute game minutes)
# ---------------------------------------------------------------------------


def day_of(minute: float) -> int:
    return int(minute // 1440)


def weekday_of(minute: float) -> int:
    return day_of(minute) % 7


def next_occurrence(weekday: int, start: int, now: float) -> int:
    """Absolute minute of the next time ``weekday @ start`` comes around."""
    today = day_of(now)
    clock = now - today * 1440
    delta = (weekday - today % 7) % 7
    due = (today + delta) * 1440 + start
    if delta == 0 and clock >= start:
        due += 7 * 1440
    return due


def birthday_weekday(npc_id: str) -> int:
    """Every resident has a stable birthday slot somewhere in the week."""
    return stable_hash("birthday", npc_id) % 7


def next_birthday(npc_id: str, now: float) -> int:
    return next_occurrence(birthday_weekday(npc_id), BIRTHDAY_CLOCK, now)


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------


def occurrence_payload(ev: WeeklyEvent, due: int) -> dict:
    loc = LOCATION_BY_ID.get(ev.venue, {})
    return {
        "kind": "event",
        "id": ev.id,
        "title": ev.title,
        "icon": ev.icon,
        "where": loc.get("name", ev.venue),
        "venue": ev.venue,
        "due": due,
        "ends": due + ev.duration,
        "host": ev.host,
        "tags": list(ev.tags),
        "blurb": ev.blurb,
        "detail": f"{ev.duration} min · hosted by {ev.host}",
    }


def upcoming_events(now: float, horizon_minutes: int = 7 * 1440) -> list[dict]:
    """Next occurrence of every fixture, sorted by when it starts."""
    out = [occurrence_payload(ev, next_occurrence(ev.weekday, ev.start, now)) for ev in WEEKLY_EVENTS]
    out.sort(key=lambda e: e["due"])
    return [e for e in out if e["due"] - now <= horizon_minutes]


def live_events(now: float) -> list[dict]:
    """Fixtures happening right now."""
    today = day_of(now)
    out = []
    for ev in WEEKLY_EVENTS:
        for offset in (0, 1):  # a fixture can still be running from yesterday
            day = today - offset
            if day % 7 != ev.weekday:
                continue
            start = day * 1440 + ev.start
            if start <= now < start + ev.duration:
                out.append(occurrence_payload(ev, start))
    out.sort(key=lambda e: e["due"])
    return out


def events_for_day(now: float, day_offset: int = 0) -> list[dict]:
    """Everything on the calendar for one day (today + offset)."""
    day = day_of(now) + day_offset
    out = []
    for ev in WEEKLY_EVENTS:
        if ev.weekday != day % 7:
            continue
        out.append(occurrence_payload(ev, day * 1440 + ev.start))
    out.sort(key=lambda e: e["due"])
    return out
