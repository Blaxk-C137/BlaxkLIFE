"""Consequences, street chatter and explicit conversations, without live API calls."""

from __future__ import annotations

import io
import json
import math
import time

import pytest

from blxverse.content.locations import LOCATION_BY_ID
from blxverse.engine import actions, civic, llm
from blxverse.engine.sim import SimError, Simulation, nearest_walkable, walkable


def outdoors(sim, index=1, x=500, y=640):
    n = sim.npcs[index]
    n.x, n.y = nearest_walkable(x, y)
    n.status, n.location_id, n.target = "at", "square", None
    n.flags.pop("hospital_until", None)
    sim.player.x, sim.player.y = n.x + 20, n.y
    return n


def test_overhead_conversation_is_short_local_and_alternates(sim):
    a = outdoors(sim, 1)
    b = outdoors(sim, 2, 550, 640)
    assert civic.pair_chat(sim, a, b, "food")
    p = civic.payload(sim)["bubbles"]
    assert len(p) == 2
    assert p[0]["starts_in"] <= 0 < p[1]["starts_in"]
    assert all(len(b["text"]) <= 104 for b in p)
    assert all(civic.held(sim, n) for n in (a, b))
    sim.minute += 8
    assert not any(civic.held(sim, n) for n in (a, b)), (
        "fast-forward must not freeze an entire day for a six-second chat"
    )


def test_street_chatter_does_not_reach_across_town_or_interrupt_player(sim):
    a = outdoors(sim, 1)
    b = outdoors(sim, 2, 950, 640)
    assert not civic.pair_chat(sim, a, b)
    b.x, b.y = 550, 640
    civic.begin_talk(sim, a)
    assert not civic.pair_chat(sim, a, b)


def test_respected_known_resident_greets_on_passby_not_every_tick(sim):
    n = outdoors(sim)
    sim.adjust_rel(n.id, "player", familiarity=20, trust=20, affinity=25)
    civic.realtime(sim)
    bubbles = civic.payload(sim)["bubbles"]
    assert len(bubbles) == 1 and bubbles[0]["kind"] == "greeting"
    assert "Ada" in bubbles[0]["text"]
    first = bubbles[0]["id"]
    civic.state(sim)["greet_after"] = 0
    civic.realtime(sim)
    assert civic.payload(sim)["bubbles"][0]["id"] == first


def test_strangers_or_disrespectful_relationships_do_not_greet(sim):
    outdoors(sim)
    civic.realtime(sim)
    assert not civic.payload(sim)["bubbles"]


def test_explicit_talk_holds_route_across_schedule_change_and_director_move(sim):
    n = outdoors(sim)
    n.target = {"x": 700, "y": 640, "loc": "cafe", "activity": "commuting"}
    n.status = "walking"
    lease = actions.handle_action(sim, {"type": "talk_begin", "npc_id": n.id})
    before = n.x, n.y
    sim.minute = 23 * 60
    sim._npc_think(n)
    sim._move_npcs(0.5)
    sim.force_move(n, "home")
    assert (n.x, n.y) == before and n.target
    assert sim._npc_core(n)["engaged"] and not sim._npc_core(n)["route"]
    actions.handle_action(sim, {"type": "talk_end", "session_id": lease["session_id"]})
    assert not civic.engaged(sim, n)
    assert sim._npc_core(n)["route"]


def test_session_tokens_cannot_release_a_different_conversation(sim):
    a = outdoors(sim, 1)
    b = outdoors(sim, 2, 550, 640)
    first = civic.begin_talk(sim, a)
    second = civic.begin_talk(sim, b)
    assert not civic.end_talk(sim, session_id=first["session_id"])
    assert civic.engaged(sim, b)
    assert civic.end_talk(sim, session_id=second["session_id"])


def test_abandoned_session_expires_and_cannot_renew_old_token(sim):
    n = outdoors(sim)
    lease = civic.begin_talk(sim, n)
    sim.world_flags["conversation"]["expires"] = time.time() - 1
    assert not civic.engaged(sim, n)
    with pytest.raises(SimError, match="ended"):
        civic.begin_talk(sim, n, lease["session_id"])
    civic.realtime(sim)
    assert "conversation" not in sim.world_flags


def test_npc_can_end_the_conversation_and_walk_away(sim):
    n = outdoors(sim)
    civic.begin_talk(sim, n)
    n.mood.irritation = 85
    reply = actions.handle_action(sim, {"type": "talk", "npc_id": n.id, "text": "You are being rude."})
    assert reply["conversation_ended"] and reply["_remote_dialogue"] is None
    assert not civic.engaged(sim, n) and n.target and n.flags["refused_until"] > sim.minute
    with pytest.raises(SimError) as e:
        civic.begin_talk(sim, n)
    assert e.value.code == "needs_space"


def test_goodbye_releases_the_resident(sim):
    n = outdoors(sim)
    civic.begin_talk(sim, n)
    reply = actions.handle_action(sim, {"type": "intent", "npc_id": n.id, "intent": "goodbye"})
    assert reply["conversation_ended"] and not civic.engaged(sim, n)


def test_wounded_resident_enters_hospital_and_recovers_on_game_clock(sim):
    n = outdoors(sim)
    assert civic.injure(sim, n, 45, "a dispute") == "hospital"
    assert sim._indoors(n) and n.status == "recovering"
    assert civic.payload(sim)["patients"][0]["id"] == n.id
    sim.minute += 181
    civic.step(sim, 0)
    assert civic.health(n) == 100 and not sim._indoors(n)
    assert not civic.payload(sim)["patients"]


def test_death_is_permanent_cancels_dates_calls_and_survives_restart(sim):
    n = outdoors(sim)
    nid = n.id
    sim.world_flags["date_offers"] = [{"npc_id": nid, "status": "accepted"}]
    sim.world_flags["pending_messages"] = [{"npc_id": nid, "text": "Hi", "due": sim.minute + 2}]
    sim.calls["call_test"] = {"npc_id": nid, "status": "active"}
    partner = sim.npcs[3]
    sim.set_rel_flag(partner.id, nid, "dating", True)
    old_rel = dict(sim.rel(nid, "player"))
    assert civic.injure(sim, n, 110, "an armed raid") == "deceased"
    assert sim.npc(nid) is None and len(sim.npcs) == 71
    assert sim.calls["call_test"]["status"] == "ended"
    assert sim.world_flags["date_offers"][0]["status"] == "cancelled"
    assert not sim.world_flags["pending_messages"]
    sim.save(force=True)
    loaded = Simulation.load(sim.save_path)
    assert loaded.npc(nid) is None and len(loaded.npcs) == 71
    assert loaded.rel(nid, "player") == old_rel
    assert "dating" not in loaded.rel(partner.id, nid)["flags"]
    assert "bereaved" in loaded.rel(partner.id, nid)["flags"]
    assert civic.payload(loaded)["memorials"][0]["name"] == n.name
    assert "resident" not in civic.payload(loaded)["memorials"][0]


def test_named_story_resident_can_die_and_story_closes_honestly(sim):
    n = sim.npc_by_first("Zara")
    assert n
    civic.injure(sim, n, 110, "a dispute")
    assert sim.npc_by_first("Zara") is None
    assert sim.world_flags["chain"]["ended_by_death"] == n.id
    assert sim.world_flags["chain"]["stage"] == 6
    assert all(a.status != "active" for a in sim.arcs if a.kind == "chain")


def test_raid_has_four_armed_distinct_square_formation_slots(sim):
    inc = civic.start_incident(sim, "raid")
    squad = [a for a in civic.state(sim)["actors"] if a.get("incident") == inc["id"]]
    assert len(squad) == 4 and all(a["armed"] for a in squad)
    assert {a["formation_slot"] for a in squad} == {0, 1, 2, 3}
    assert all(walkable(a["x"], a["y"]) for a in squad)
    assert all(
        math.hypot(a["x"] - b["x"], a["y"] - b["y"]) >= 40
        for i, a in enumerate(squad)
        for b in squad[i + 1 :]
    )
    assert all(a["route"] for a in squad)
    assert civic.start_incident(sim, "raid") is None


def test_raid_walks_to_site_before_fighting_and_eventually_resolves(sim):
    inc = civic.start_incident(sim, "raid")
    phases = set()
    for _ in range(90):
        sim.minute += 0.75
        civic.step(sim, 0.75)
        phases.add(inc["phase"])
    assert "confrontation" in phases, phases
    assert inc["phase"] == "resolved"
    assert len([a for a in civic.state(sim)["actors"] if a["kind"] == "bandit"]) == 0
    assert any(e["kind"] == "raid" for e in sim.events)


def test_theft_changes_victims_wallet_when_no_police_arrive(sim):
    n = outdoors(sim)
    for other in sim.npcs:
        if other is not n:
            other.status = "sleeping"
    for a in civic.state(sim)["actors"]:
        a["x"], a["y"] = 60, 60
    n.wallet = 100
    inc = {
        "id": "test_theft",
        "kind": "theft",
        "location": "square",
        "phase": "confrontation",
        "x": n.x,
        "y": n.y,
        "victims": [],
    }
    civic._resolve_incident(sim, inc)
    assert n.wallet < 100 and inc["stolen"] == 100 - n.wallet


def test_business_money_flows_and_closed_business_does_not_generate_income(sim):
    site = LOCATION_BY_ID["black_market"]
    sim.player.x, sim.player.y = site["x"] + 40, site["y"] + site["h"] + 35
    civic.action(sim, {"op": "business_start", "category": "drugs"})
    assert sim.player.wallet == 160
    biz = civic.state(sim)["businesses"]["drugs"]
    sim.hub.stream("black-market-risk").random = lambda: 0.99
    sim.minute = biz["next_income"]
    civic.step(sim, 0)
    assert biz["balance"] == 45
    civic.action(sim, {"op": "business_collect", "category": "drugs"})
    assert sim.player.wallet == 205 and biz["balance"] == 0
    civic.action(sim, {"op": "business_close", "category": "drugs"})
    sim.minute += 500
    civic.step(sim, 0)
    assert biz["status"] == "closed" and biz["balance"] == 0


def test_black_market_can_be_seized_and_does_not_refund_stake(sim):
    site = LOCATION_BY_ID["black_market"]
    sim.player.x, sim.player.y = site["x"] + 40, site["y"] + site["h"] + 35
    civic.action(sim, {"op": "business_start", "category": "drugs"})
    sim.hub.stream("black-market-risk").random = lambda: 0
    biz = civic.state(sim)["businesses"]["drugs"]
    sim.minute = biz["next_income"]
    civic.step(sim, 0)
    assert biz["status"] == "seized" and sim.player.wallet == 160


def test_busy_lock_blocks_gameplay_and_movement_until_wall_clock_finishes(sim):
    sim.player.flags["busy"] = {"kind": "work", "until": time.time() + 5, "label": "Shift"}
    sim.set_player_destination(700, 640)
    before = sim.player.x, sim.player.y
    sim.tick(0.25)
    assert (sim.player.x, sim.player.y) == before
    for kind in ("move", "talk", "work", "buy", "civic", "speed"):
        with pytest.raises(SimError) as e:
            actions.handle_action(sim, {"type": kind})
        assert e.value.code == "busy"
    sim.player.flags["busy"]["until"] = time.time() - 1
    assert civic.busy(sim) is None
    assert actions.handle_action(sim, {"type": "speed", "speed": 1})["ok"]


def test_gemini_fast_model_recent_history_minimal_thinking_and_local_budget(sim, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-05-history-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("BLXVERSE_LLM_DISABLED", raising=False)
    monkeypatch.setenv("GEMINI_LOCAL_RPM", "1")
    n = outdoors(sim)
    n.flags["conversation_history"] = [{"user": "I like jazz", "reply": "Same, especially live sets."}]
    calls = []

    def fake(req, timeout):
        body = json.loads(req.data)
        calls.append(body)
        assert "jazz" in body["systemInstruction"]["parts"][0]["text"]
        assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}
        return io.BytesIO(
            json.dumps(
                {
                    "candidates": [
                        {"content": {"parts": [{"text": "There is a tiny jazz set at the studio tonight."}]}}
                    ]
                }
            ).encode()
        )

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    args = {
        "npc": n,
        "player": sim.player,
        "intent": "smalltalk",
        "player_text": "What about live music?",
        "relationship": "friend",
        "memory": "",
        "venue": "square",
    }
    assert llm.generate_reply(**args)
    assert llm.generate_reply(**args) is None
    assert len(calls) == 1 and llm._settings()[2] == "gemini-3.5-flash-lite"
