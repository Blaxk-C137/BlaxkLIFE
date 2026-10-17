"""Save/load round-trips and schema safety."""

from __future__ import annotations

import json

import pytest

from blxverse import config
from blxverse.engine.sim import SimError, Simulation


def test_round_trip_preserves_the_world(sim, run, near, tmp_path):
    npc = near("Zara")
    run("talk", npc_id=npc.id, text="Hey Zara — welcome to the block.")
    run("buy", item_id="house_plant")
    run("gift", npc_id=npc.id, item_id="house_plant")
    run("message", npc_id=npc.id, text="Also: your song is stuck in my head.")
    sim.advance(60 * 5)
    sim.advance(60 * 24 * 2)

    path = tmp_path / "world.json"
    sim.save_path = str(path)
    sim.save(force=True)
    assert path.exists()

    loaded = Simulation.load(str(path))
    assert loaded.minute == pytest.approx(sim.minute, abs=0.01)
    assert loaded.day_index == sim.day_index
    assert loaded.player.name == sim.player.name
    assert loaded.player.wallet == sim.player.wallet
    assert len(loaded.npcs) == len(sim.npcs)
    assert len(loaded.rels) == len(sim.rels)
    assert len(loaded.posts) == len(sim.posts)
    assert len(loaded.cases) == len(sim.cases)
    assert len(loaded.arcs) == len(sim.arcs)
    assert sum(len(n.memory) for n in loaded.npcs) == sum(len(n.memory) for n in sim.npcs)
    assert sum(len(n.beliefs) for n in loaded.npcs) == sum(len(n.beliefs) for n in sim.npcs)
    thread_a = sim.threads.get(npc.id)
    thread_b = loaded.threads.get(npc.id)
    assert thread_a and thread_b
    assert [m.text for m in thread_a.messages] == [m.text for m in thread_b.messages]
    assert loaded.npc(npc.id).first == npc.first
    assert loaded.rel(npc.id, "player")["familiarity"] == pytest.approx(
        sim.rel(npc.id, "player")["familiarity"], abs=0.01)


def test_save_is_atomic_and_keeps_a_backup(sim, tmp_path):
    sim.save_path = str(tmp_path / "world.json")
    sim.save(force=True)
    sim.advance(60)
    sim.save(force=True)
    assert (tmp_path / "world.json").exists()
    assert (tmp_path / "world.json.bak").exists()
    assert not (tmp_path / "world.json.tmp").exists()


def test_bad_save_is_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"format": "other", "schema": 1}), encoding="utf-8")
    with pytest.raises(SimError) as err:
        Simulation.load(str(bad))
    assert err.value.code in ("bad_save", "schema_mismatch")


def test_schema_mismatch_is_rejected(sim, tmp_path):
    path = tmp_path / "world.json"
    sim.save_path = str(path)
    sim.save(force=True)
    data = json.loads(path.read_text())
    assert data["format"] == config.SAVE_FORMAT
    data["schema"] = config.SCHEMA_VERSION + 1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SimError) as err:
        Simulation.load(str(path))
    assert err.value.code == "schema_mismatch"


def test_default_save_path_is_not_none():
    fresh = Simulation.new(seed=1, player_spec={"name": "Test"})
    assert fresh.save_path
    assert fresh.save_path.endswith("world.json")
