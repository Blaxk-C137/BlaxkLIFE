"""Player action layer: conversation, gifts, calls, dates, feed, work."""

from __future__ import annotations

import pytest

from blxverse import config
from blxverse.engine.sim import SimError


def test_talk_requires_proximity(sim, run):
    npc = sim.npc_by_first("Zara")
    sim.player.x, sim.player.y = npc.x + 900, npc.y + 900
    with pytest.raises(SimError) as err:
        run("talk", npc_id=npc.id, text="Hi there")
    assert err.value.code == "too_far"


def test_talk_changes_relationship_and_memory(sim, run, near):
    npc = near("Zara")
    before = sim.rel(npc.id, "player")["familiarity"]
    res = run("talk", npc_id=npc.id, text="Hey Zara, how's the new place treating you?")
    assert res["reply"]
    assert res["intent"] == "greeting"
    assert sim.rel(npc.id, "player")["familiarity"] > before
    assert any(m.kind == "talk" for m in npc.memory)
    assert any("Zara" in j["summary"] for j in sim.player.flags["journal"])


def test_mood_and_relationship_are_reported(sim, run, near):
    npc = near("Zara")
    res = run("talk", npc_id=npc.id, text="That jacket is excellent.")
    assert res["npc"]["mood"]
    assert {"label", "familiarity", "trust", "affinity"} <= set(res["relationship"])
    assert any("familiarity" in line for line in res["effects_display"])


def test_quick_intents_and_romance_gating(sim, run, near):
    npc = near("Zara")
    with pytest.raises(SimError):
        run("intent", npc_id=npc.id, intent="not_a_real_intent")
    res = run("intent", npc_id=npc.id, intent="flirt")
    assert res["ok"] is True
    assert res["reply"]
    # a date with a near-stranger must be declined, respectfully
    res = run("intent", npc_id=npc.id, intent="ask_date")
    assert res["accepted"] is False
    assert res["reason"]


def test_flirt_then_date_flow(sim, run, near):
    npc = near("Zara")
    for i in range(14):
        near(npc)
        run("intent", npc_id=npc.id, intent="flirt" if i % 2 else "compliment")
    near(npc)
    res = run("intent", npc_id=npc.id, intent="ask_date")
    assert res["accepted"] is True, res.get("reason")
    offer = res["date_offer"]
    assert offer["venue"] in {"cafe", "cinema", "park", "studio", "restaurant", "gallery"}
    sim.advance(max(0.0, offer["due"] - sim.minute) + 2)
    from blxverse.content.locations import LOCATION_BY_ID
    loc = LOCATION_BY_ID[offer["venue"]]
    sim.player.x = loc["x"] + loc["w"] / 2
    sim.player.y = loc["y"] + loc["h"] + 20
    out = run("date_go", offer_id=offer["id"])
    assert out["ok"] is True
    assert sim.rel(npc.id, "player")["dates"] == 1


def test_gift_reactions_are_recipient_specific_and_diminishing(sim, run, near):
    from blxverse.content.items import ITEM_BY_ID
    npc = near("Zara")
    sim.player.inventory["vinyl_record"] = 3
    first = run("gift", npc_id=npc.id, item_id="vinyl_record")
    second = run("gift", npc_id=npc.id, item_id="vinyl_record")
    assert first["mood"] in {"love", "like", "meh"}
    assert "vinyl_record" in ITEM_BY_ID
    assert sim.rel(npc.id, "player")["gifts"]["vinyl_record"] == 2
    assert second["repetition"] >= 1
    assert second["reply"]
    with pytest.raises(SimError) as err:
        run("gift", npc_id=npc.id, item_id="mystery_box")
    assert err.value.code == "not_in_inventory"


def test_work_pays_and_costs_energy(sim, run, at_venue):
    at_venue("cafe")
    sim.player.energy = 100
    sim.player.reputation = 50
    res = run("work", location_id="cafe")
    assert 70 <= res["pay"] <= 116 + 5
    assert res["energy"] <= 100 - config.SHIFT_ENERGY_COST + 1
    assert any(t["category"] == "wage" for t in sim.player.ledger)


def test_sleep_only_at_night_and_wakes_at_seven(sim, run):
    with pytest.raises(SimError):
        run("sleep")
    sim.advance(60 * 15)  # 22:30
    res = run("sleep")
    assert res["energy"] == 100
    assert 6.9 <= sim.hour_of_day <= 7.2


def test_feed_post_like_comment(sim, run):
    post = run("post", text="The fountain is objectively the best fountain.")
    assert post["post"]["text"]
    pid = post["post"]["id"]
    assert run("like", post_id=pid)["liked"] is True
    assert run("like", post_id=pid)["liked"] is False
    assert run("comment", post_id=pid, text="Strong agree.")["comments"] == 1


def test_moderation_rejects_targeted_harassment(sim, run):
    with pytest.raises(SimError) as err:
        run("post", text="they should be deported")
    assert err.value.code == "harassment"


def test_message_schedules_a_later_reply(sim, run):
    npc = sim.npc_by_first("Zara")
    res = run("message", npc_id=npc.id, text="Coffee tomorrow?")
    assert res["scheduled"] is True
    assert sim.world_flags["pending_messages"]
    sim.advance(30)
    thread = sim.threads[npc.id]
    assert len(thread.messages) >= 2
    assert any(m.sender == npc.id for m in thread.messages)


def test_call_requires_familiarity_then_works(sim, run, near):
    npc = near("Daniel")
    with pytest.raises(SimError) as err:
        run("call_start", npc_id=npc.id)
    assert err.value.code == "not_familiar"
    sim.adjust_rel(npc.id, "player", familiarity=config.CALL_MIN_FAMILIARITY + 2)
    call = run("call_start", npc_id=npc.id)
    assert call["greeting"]
    turn = run("call_turn", call_id=call["call_id"], text="Hey, is this a good time?")
    assert turn["reply"]
    end = run("call_end", call_id=call["call_id"], duration_s=42)
    assert end["ok"] is True and end["turns"] == 1
    assert call["call_id"] not in sim.calls


def test_investigation_and_case_resolution(sim, run, advance):
    advance(60 * 24 * 2 + 60 * 3.5)  # Wednesday 11:00
    case = next((c for c in sim.cases if c.status == "open"), None)
    assert case is not None, "the Wednesday rumor should open a case"
    from blxverse.content.locations import LOCATION_BY_ID
    for loc_id in ("studio", "music_store"):
        loc = LOCATION_BY_ID[loc_id]
        sim.player.x, sim.player.y = loc["x"] + loc["w"] / 2, loc["y"] + loc["h"] + 20
        res = run("investigate", location_id=loc_id)
        assert res["found"] >= 1
    out = run("present_case", case_id=case.id)
    assert "cleared" in out["text"]
    assert case.status == "cleared"


def test_beliefs_can_be_challenged(sim, run, advance):
    advance(60 * 24 * 2 + 60 * 4)
    holder = next((n for n in sim.npcs if n.beliefs), None)
    assert holder is not None, "the rumor should have reached at least one resident"
    belief = holder.beliefs[0]
    res = run("challenge_rumor", npc_id=holder.id, claim=belief.claim)
    assert res["ok"] is True
    assert res["confidence"] <= belief.confidence + 0.001


def test_stir_raises_tension_between_residents(sim, run, near, advance):
    sim.advance(60 * 2)  # mid-morning, people out
    npc = sim.npc_by_first("Zara")
    # find a venue with at least two awake residents
    from collections import Counter
    counts = Counter(n.location_id for n in sim.npcs if n.status != "sleeping")
    loc = max((lid for lid in counts if lid != "home"), key=counts.get)
    crew = [n for n in sim.npcs if n.location_id == loc and n.status != "sleeping"]
    target, other = crew[0], crew[1]
    sim.player.x, sim.player.y = target.x + 10, target.y + 5
    before = sim.rel(target.id, other.id)["tension"]
    run("stir", npc_id=target.id)
    assert sim.rel(target.id, other.id)["tension"] > before
    assert npc is not None


def test_unknown_action_is_structured_error(sim, run):
    with pytest.raises(SimError) as err:
        run("teleport_to_moon")
    assert err.value.code == "bad_action"


def test_questions_are_answered_from_npc_state(sim, run, near):
    """Asking a concrete question must produce a state-grounded answer, not a
    generic line: residents always know where they are and what's next."""
    zara = near("Zara")
    sim.force_move(zara, "cafe")
    sim.player.x, sim.player.y = zara.x + 20, zara.y + 20

    where = run("talk", npc_id=zara.id, text="Where are you right now?")
    assert "Two Rivers Cafe" in where["reply"]

    plans = run("talk", npc_id=zara.id, text="What are you up to later?")
    assert plans["reply"].strip()
    assert plans["intent"] in ("fallback", "smalltalk", "goodbye", "greeting", "how_are_you", "ask_about")


def test_greeting_keyword_does_not_match_inside_words(sim, near):
    """"hi" inside "right" used to misclassify sentences as greetings."""
    from blxverse.engine.composer import classify_intent

    assert classify_intent("You are right about the fountain") != "greeting"
    assert classify_intent("Hi there") == "greeting"


def test_relationship_flags_never_duplicate(sim, run, near):
    """_apply_rel_flags runs on every relationship tick; repeated 'crush'
    entries broke labels and profile chips before de-duplication."""
    zara = near("Zara")
    for _ in range(12):
        run("intent", npc_id=zara.id, intent="flirt")
    for _ in range(8):
        run("intent", npc_id=zara.id, intent="compliment")
    flags = sim.rel(zara.id, "player")["flags"]
    assert len(flags) == len(set(flags)), flags
    assert all(isinstance(f, str) for f in flags)


def test_date_offer_lands_on_calendar_and_pays_out(sim, run, near):
    from blxverse.content.locations import LOCATION_BY_ID

    zara = near("Zara")
    for _ in range(12):
        run("intent", npc_id=zara.id, intent="flirt")
    for _ in range(6):
        run("intent", npc_id=zara.id, intent="compliment")
    result = run("intent", npc_id=zara.id, intent="ask_date")
    assert result["accepted"] is True, result.get("reason")
    offer = result["date_offer"]

    upcoming = sim.journal_payload()["upcoming"]
    assert any(item["kind"] == "date" for item in upcoming)

    sim.advance(offer["due"] - sim.minute + 5)
    loc = LOCATION_BY_ID[offer["venue"]]
    sim.player.x = loc["x"] + loc["w"] / 2
    sim.player.y = loc["y"] + loc["h"] + 40
    sim.force_move(zara, offer["venue"])

    done = run("date_go", offer_id=offer["id"])
    assert done["ok"] and "Zara" in done["text"]
    rel = sim.rel(zara.id, "player")
    assert rel["dates"] == 1 and "dating" in rel["flags"]
    # the date is gone from the calendar; the weekly fixtures stay
    after = sim.journal_payload()["upcoming"]
    assert not [u for u in after if u["kind"] == "date"], "date should leave the calendar once paid out"
    assert [u for u in after if u["kind"] == "event"], "block fixtures remain on the calendar"


def test_stir_creates_a_challengeable_rumor(sim, run):
    """Whispering must actually enter the belief system, not just nudge tension."""
    target = sim.npcs[3]
    others = [n for n in sim.npcs if n.id != target.id and n.location_id == target.location_id]
    assert others, "expected a shared venue for this fixture"
    sim.player.x, sim.player.y = target.x + 10, target.y + 10

    stirred = run("stir", npc_id=target.id)
    assert stirred["ok"] and stirred["rumor"]["claim"]
    belief = next((b for b in target.beliefs if b.rumor_id == stirred["rumor"]["id"]), None)
    assert belief is not None, "the whisper never became a belief"

    # provenance: the target is the visible origin, the player is recorded as the planter
    rumor = next(r for r in sim.rumors if r["id"] == stirred["rumor"]["id"])
    assert rumor["origin"] == target.id and rumor.get("planted_by") == "player"

    challenged = run("challenge_rumor", npc_id=target.id, claim=belief.claim)
    assert challenged["ok"]
    assert belief.confidence < 0.55

    held = {b.id for b in sim.npcs[0].beliefs}
    assert isinstance(held, set)
