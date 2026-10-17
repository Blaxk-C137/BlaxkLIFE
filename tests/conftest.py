"""Shared fixtures for the BLXVERSE test suite."""

from __future__ import annotations

import pytest

from blxverse import config
from blxverse.content.locations import LOCATION_BY_ID
from blxverse.engine import actions
from blxverse.engine.sim import SimError, Simulation


@pytest.fixture()
def sim(tmp_path):
    return Simulation.new(
        seed=20261017,
        player_spec={"name": "Ada", "gender": "female", "age": 27, "look": {}},
        save_path=str(tmp_path / "world.json"),
    )


@pytest.fixture()
def run(sim):
    """Call an action, returning its payload; domain errors raise SimError."""
    def _run(kind: str, **kwargs):
        return actions.handle_action(sim, {"type": kind, **kwargs})
    return _run


@pytest.fixture()
def near(sim):
    """Move the player right next to a resident and return that resident."""
    def _near(npc_or_first, dx: float = 24.0, dy: float = 6.0):
        npc = sim.npc_by_first(npc_or_first) if isinstance(npc_or_first, str) else npc_or_first
        assert npc is not None, f"no resident named {npc_or_first}"
        sim.player.x = npc.x + dx
        sim.player.y = npc.y + dy
        return npc
    return _near


@pytest.fixture()
def at_venue(sim):
    def _at(loc_id: str):
        loc = LOCATION_BY_ID[loc_id]
        sim.player.x = loc["x"] + loc["w"] / 2
        sim.player.y = loc["y"] + loc["h"] + 20
        return loc
    return _at


@pytest.fixture()
def advance(sim):
    def _advance(minutes: float):
        sim.advance(minutes)
    return _advance


__all__ = ["SimError", "config", "actions"]
