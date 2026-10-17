"""The scripted five-day chain, rumor mechanics and story integrity."""

from __future__ import annotations

from blxverse.engine import director


def _to_wednesday(sim):
    # Monday 07:30 -> Wednesday 11:00
    sim.advance(60 * 24 * 2 + 60 * 3.5)


def test_chain_starts_on_day_one(sim):
    sim.advance(30)
    chain = sim.world_flags["chain"]
    assert chain["started"] is True
    assert chain["stage"] >= 1
    arc = next(a for a in sim.arcs if a.kind == "chain")
    assert arc.stage == 0
    zara = sim.npc_by_first("Zara")
    landlord = sim.npc_by_flag("landlord")
    assert sim.rel(zara.id, landlord.id)["tension"] > 0
    assert any(e["kind"] == "landlord_dispute" for e in sim.events)


def test_chain_advances_into_a_false_rumor_and_case(sim):
    _to_wednesday(sim)
    chain = sim.world_flags["chain"]
    assert chain["stage"] >= 3
    rumor = next((r for r in sim.rumors if r["truth"] == "false"), None)
    assert rumor is not None
    assert rumor["subject"] == sim.npc_by_first("Daniel").id
    assert rumor["origin"] != rumor["subject"]
    case = next((c for c in sim.cases if c.accused == rumor["subject"]), None)
    assert case is not None and case.status == "open"
    assert len(case.helpful_evidence) >= 2
    # belief is not fact: the accuser holds a belief marked as coming from a rumor
    holder = next((n for n in sim.npcs if any(b.rumor_id == rumor["id"] for b in n.beliefs)), None)
    assert holder is not None
    belief = next(b for b in holder.beliefs if b.rumor_id == rumor["id"])
    assert belief.truth in ("unknown", "false")


def test_rumor_spreads_through_the_block(sim):
    _to_wednesday(sim)
    before = sum(1 for n in sim.npcs if n.beliefs)
    sim.advance(60 * 24 * 2)
    after = sum(1 for n in sim.npcs if n.beliefs)
    assert after > before + 4, "a rumor should travel through social ties over days"
    assert sim.metrics["rumor_spreads"] > 4


def test_rumor_does_not_reach_everyone_instantly(sim):
    _to_wednesday(sim)
    believers = sum(1 for n in sim.npcs if n.beliefs)
    assert believers < len(sim.npcs) / 2


def test_world_resolves_the_case_without_the_player(sim):
    _to_wednesday(sim)
    case = next(c for c in sim.cases if c.status == "open")
    # run through Saturday; the world should not leave the story dangling forever
    sim.advance(60 * 24 * 4)
    assert case.status in ("cleared", "unsolved")
    chain = sim.world_flags["chain"]
    assert chain["stage"] >= 6
    arc = next(a for a in sim.arcs if a.kind == "chain")
    assert arc.status in ("resolved", "faded")


def test_chain_has_consequences_for_zara_opinion(sim):
    _to_wednesday(sim)
    zara = sim.npc_by_first("Zara")
    graph_before = {oid: round(r.get("affinity", 0), 1) for oid, r in sim.outgoing_rels(zara.id)}
    accuser = sim.world_flags["chain"].get("accuser") or ""
    sim.advance(60 * 24 * 4)
    graph_after = {oid: round(r.get("affinity", 0), 1) for oid, r in sim.outgoing_rels(zara.id)}
    assert graph_before != graph_after, "Zara's opinion map should visibly shift after the chain"
    if accuser:
        assert sim.rel(zara.id, accuser)["affinity"] != graph_before.get(accuser, 0)


def test_director_gates_respect_in_game_time(sim):
    # calling the chain advance early must not skip Monday
    sim.advance(10)
    director.advance_chain(sim)
    assert sim.world_flags["chain"]["stage"] <= 2


def test_no_identity_based_mobs_or_violence(sim):
    sim.advance(60 * 24 * 6)
    for event in sim.events:
        text = event.get("summary", "").lower()
        assert "kill" not in text
        assert "mob" not in text
        if event["kind"] == "slapstick":
            assert event["facts"].get("non_graphic") is True
