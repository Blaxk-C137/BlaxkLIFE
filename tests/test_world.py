"""World generation, schedules, determinism and cast invariants."""

from __future__ import annotations

from blxverse import config
from blxverse.content.locations import HOMES, LOCATION_BY_ID, LOCATIONS
from blxverse.engine.generate import generate_npcs
from blxverse.engine.rng import RngHub
from blxverse.engine.sim import Simulation

EXPECTED_LOCATIONS = {
    "square", "cafe", "studio", "gym", "park", "grocery",
    "music_store", "clothing", "salon", "cinema", "restaurant",
}


def test_generation_is_deterministic():
    a = generate_npcs(RngHub(9911))
    b = generate_npcs(RngHub(9911))
    assert [(n.first, n.last, n.gender, n.age, n.occupation) for n in a] == \
           [(n.first, n.last, n.gender, n.age, n.occupation) for n in b]
    assert [n.look for n in a] == [n.look for n in b]
    assert [n.schedule for n in a] == [n.schedule for n in b]


def test_population_and_cast():
    sim = Simulation.new(seed=20261017, player_spec={"name": "Ada"})
    assert len(sim.npcs) == config.NPC_COUNT
    assert len({n.first for n in sim.npcs}) == config.NPC_COUNT, "first names must be unique"
    assert sum(1 for n in sim.npcs if n.spotlight) == config.SPOTLIGHT_COUNT
    zara, daniel, landlord = sim.npc_by_first("Zara"), sim.npc_by_first("Daniel"), sim.npc_by_flag("landlord")
    assert zara and daniel and landlord
    assert zara.occupation == "musician" and zara.spotlight
    assert daniel.occupation == "graphic designer"
    assert landlord.flags.get("landlord") is True
    assert all(config.NPC_AGE_RANGE[0] <= n.age <= config.NPC_AGE_RANGE[1] for n in sim.npcs)
    assert all(n.home_id == zara.home_id for n in (zara, landlord))


def test_locations_and_homes():
    assert EXPECTED_LOCATIONS <= set(LOCATION_BY_ID)
    assert len(HOMES) == 20
    for loc in LOCATIONS:
        assert loc["x"] >= 0 and loc["y"] >= 0
        assert loc["x"] + loc["w"] <= config.WORLD_WIDTH + 1
        assert loc["y"] + loc["h"] <= config.WORLD_HEIGHT + 1
        assert loc["activities"], f"{loc['id']} should offer activities"


def test_every_resident_has_a_full_day_schedule():
    sim = Simulation.new(seed=20261017, player_spec={"name": "Ada"})
    for npc in sim.npcs:
        for key in ("weekday", "weekend"):
            blocks = npc.schedule[key]
            assert blocks and blocks[0]["start"] == 0
            assert blocks[-1]["end"] == 24
            for prev, nxt in zip(blocks, blocks[1:], strict=False):
                assert prev["end"] <= nxt["start"] + 0.01, f"overlap in {npc.id} {key}"
        assert npc.schedule["weekday"][0]["kind"] == "sleep"


def test_relationship_fabric_is_two_sided_and_plausible():
    sim = Simulation.new(seed=20261017, player_spec={"name": "Ada"})
    for npc in sim.npcs:
        rel = sim.rel(npc.id, "player")
        for key in ("familiarity", "trust", "affinity", "romance", "tension"):
            assert key in rel
        assert rel["trust"] >= 0
    zara = sim.npc_by_first("Zara")
    landlord = sim.npc_by_flag("landlord")
    assert sim.rel(zara.id, landlord.id)["tension"] > 40
    assert "landlord" in sim.rel(zara.id, landlord.id)["flags"]


def test_simulation_clock_and_tiers():
    sim = Simulation.new(seed=20261017, player_spec={"name": "Ada"})
    clock = sim.clock_payload()
    assert clock["day"] == 1 and clock["weekday"] == "Mon"
    assert (clock["hour"], clock["minute_of_hour"]) == (7, 30)
    payload = sim.state_payload()
    tiers = payload["tiers"]
    assert tiers["foreground"] + tiers["nearby"] + tiers["background"] == len(sim.npcs)
    assert payload["player"]["wallet"] == config.STARTING_BALANCE


def test_residents_move_over_a_day():
    sim = Simulation.new(seed=20261017, player_spec={"name": "Ada"})
    start = {n.id: (n.location_id, round(n.x), round(n.y)) for n in sim.npcs}
    sim.advance(60 * 10)
    moved = sum(1 for n in sim.npcs if (n.location_id, round(n.x), round(n.y)) != start[n.id])
    assert moved > len(sim.npcs) // 2, "the block should be alive even without the player"


def test_no_schedule_gap_makes_residents_sleep_in_the_daytime(sim):
    """Regression: _block_for fell back to the last block (bedtime) during
    schedule gaps, so half the block read as 'sleeping' at 6 pm."""
    sim.advance((18 * 60 + 5) - sim.minute)
    sleepers = [n.first for n in sim.npcs if n.status == "sleeping"]
    assert sleepers == [], f"residents asleep at 18:05: {sleepers[:5]}"

    sim.advance((23 * 60 + 30) - sim.minute)
    asleep = sum(1 for n in sim.npcs if n.status == "sleeping")
    assert asleep >= 50, f"only {asleep} residents asleep at 23:30"


def test_crowded_venues_do_not_stack_residents(sim):
    """Venue placement used to snap everyone inside a building onto the same
    ground strip, stacking residents (and their nameplates) on one pixel."""
    import math

    sim.advance((12 * 60) - sim.minute)  # midday, venues are busy
    stacked = []
    for i, a in enumerate(sim.npcs):
        for b in sim.npcs[i + 1:]:
            if a.location_id != b.location_id or a.location_id == "home":
                continue
            if math.hypot(a.x - b.x, a.y - b.y) < 12:
                stacked.append((a.first, b.first, a.location_id))
    assert stacked == [], f"residents stacked at the same venue spot: {stacked[:5]}"


def test_player_route_is_walkable_and_never_stalls():
    """Click-to-walk regression.

    Three separate bugs used to freeze the sprite mid-street: the walker gave
    up when a corner pinched its radius, A* treated a destination as
    unreachable when the *grid cell centre* under it was blocked, and a pocket
    destination could bounce the replan loop forever. Every destination here
    must now be reached, on walkable ground, without stalling.
    """
    import math

    from blxverse.engine.sim import walkable

    sim = Simulation.new(seed=20261017, player_spec={"name": "Ada"})
    spots = [(1500, 1130), (1620, 240), (900, 1050), (600, 1000),
             (1250, 320), (150, 150), (1750, 1200), (80, 700), (1000, 60)]
    for tx, ty in spots:
        sim.player.x, sim.player.y = 900.0, 900.0
        sim.set_player_destination(tx, ty)
        goal = sim._player_dest
        assert goal, f"no destination set for {(tx, ty)}"
        still = best = 0
        for _ in range(400):
            if sim._player_dest is None:
                break
            before = (sim.player.x, sim.player.y)
            sim._move_player(0.25)
            after = (sim.player.x, sim.player.y)
            assert walkable(*after), f"player left walkable ground at {after} heading to {goal}"
            still = still + 1 if math.hypot(after[0] - before[0], after[1] - before[1]) < 0.01 else 0
            best = max(best, still)
        assert best <= 2, f"player stalled {best} ticks heading to {goal}"
        assert math.hypot(sim.player.x - goal[0], sim.player.y - goal[1]) < 2.0, "walk did not finish"
        assert sim._player_dest is None and not sim._player_path


def test_random_walks_always_terminate_on_walkable_ground():
    """Fuzz the walker: 60 random destinations, no stalls, no wall clipping.

    Some clicks land in a courtyard the nav grid cannot enter; those end at the
    last reachable point instead of looping, so only the *median* error is held
    to a tight bound.
    """
    import math
    import random
    import statistics

    from blxverse.engine.sim import walkable

    sim = Simulation.new(seed=20261017, player_spec={"name": "Ada"})
    rng = random.Random(4242)
    errors = []
    for _ in range(60):
        tx, ty = rng.uniform(60, 1840), rng.uniform(90, 1240)
        sim.player.x, sim.player.y = 900.0, 900.0
        sim.set_player_destination(tx, ty)
        goal = sim._player_dest
        ticks = 0
        while sim._player_dest is not None and ticks < 900:
            sim._move_player(0.25)
            ticks += 1
            assert walkable(sim.player.x, sim.player.y), "walked through a building"
        assert ticks < 900, f"walk to {(tx, ty)} never terminated"
        errors.append(math.hypot(sim.player.x - goal[0], sim.player.y - goal[1]))
    assert statistics.median(errors) < 2.0, f"median arrival error {statistics.median(errors):.1f}px"
    assert sum(1 for e in errors if e < 2.0) >= 55, "too many walks stop short of open ground"


def test_player_route_payload_matches_the_waypoints_walked():
    sim = Simulation.new(seed=20261017, player_spec={"name": "Ada"})
    sim.player.x, sim.player.y = 900.0, 900.0
    sim.set_player_destination(1500, 1130)
    payload = sim.player_route_payload()
    assert payload["dest"] is not None
    assert 1 <= len(payload["route"]) <= 48
    assert payload["route"][-1]["x"] == payload["dest"]["x"]
    assert payload["route"][-1]["y"] == payload["dest"]["y"]
    state = sim.state_payload()["player"]
    assert state["route"] and state["dest"] == payload["dest"]
