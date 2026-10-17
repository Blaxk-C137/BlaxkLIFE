"""The block calendar: weekly fixtures, live windows, birthdays."""

from __future__ import annotations

import math

from blxverse.content import events as cal
from blxverse.engine.sim import Simulation


def test_weekly_calendar_is_sorted_and_deterministic():
    a = cal.upcoming_events(7 * 60 + 30)
    b = cal.upcoming_events(7 * 60 + 30)
    assert a == b, "calendar must be deterministic"
    assert [e["due"] for e in a] == sorted(e["due"] for e in a)
    assert {e["id"] for e in a} == {ev.id for ev in cal.WEEKLY_EVENTS}
    for e in a:
        assert e["due"] > 7 * 60 + 30, "upcoming means in the future"
        assert e["ends"] > e["due"]
        assert e["where"], "every fixture needs a venue name"


def test_every_fixture_lands_on_its_weekday_once_a_week():
    now = 3 * 1440 + 10 * 60  # Thursday 10:00
    for ev in cal.WEEKLY_EVENTS:
        first = cal.next_occurrence(ev.weekday, ev.start, now)
        assert first % 1440 == ev.start
        assert (first // 1440) % 7 == ev.weekday
        second = cal.next_occurrence(ev.weekday, ev.start, first + 1)
        assert second - first == 7 * 1440, "fixtures repeat exactly weekly"


def test_live_window_only_covers_the_fixture():
    ev = cal.EVENT_BY_ID["open_mic"]
    start = cal.next_occurrence(ev.weekday, ev.start, 0)
    assert [e["id"] for e in cal.live_events(start)] == ["open_mic"]
    assert cal.live_events(start - 1) == []
    assert cal.live_events(start + ev.duration - 1)[0]["id"] == "open_mic"
    assert cal.live_events(start + ev.duration) == []


def test_birthdays_are_stable_and_within_one_week():
    a = cal.birthday_weekday("npc_001")
    assert a == cal.birthday_weekday("npc_001")
    assert 0 <= a <= 6
    now = 5 * 1440 + 9 * 60
    for npc_id in ("npc_001", "npc_017", "npc_042"):
        due = cal.next_birthday(npc_id, now)
        assert now < due <= now + 7 * 1440
        assert due % 1440 == cal.BIRTHDAY_CLOCK
    # and the population is spread across the week, not all on one day
    spread = {cal.birthday_weekday(f"npc_{i:03d}") for i in range(1, 40)}
    assert len(spread) >= 5


def test_journal_shows_the_week_ahead():
    sim = Simulation.new(seed=20261017, player_spec={"name": "Ada"})
    rows = sim.journal_payload()["upcoming"]
    assert rows, "coming-up list should never be empty"
    events = [r for r in rows if r["kind"] == "event"]
    assert events, "weekly fixtures should be listed"
    assert all(r["due"] >= sim.minute for r in events)
    assert all(r["icon"] for r in events)


def test_live_fixture_pulls_matching_residents_in():
    sim = Simulation.new(seed=20261017, player_spec={"name": "Ada"})
    # Wednesday 17:40 → Open Studio is live at Golden Hour Studio.
    sim.advance(2 * 1440 + 17 * 60 + 40 - sim.minute)
    live = sim.live_events()
    assert [e["id"] for e in live] == ["open_studio"]
    pulled = [n for n in sim.npcs if sim._event_pull(n)]
    assert pulled, "someone on the block should be tempted by a live fixture"
    assert any(n.location_id == "studio" for n in sim.npcs if n.spotlight), \
        "the host should be at their own event"
    # nobody is teleported into a wall
    for n in sim.npcs:
        assert math.isfinite(n.x) and math.isfinite(n.y)
