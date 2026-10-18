"""Cross-channel persistence, provider grounding, and real casual meetups."""
from __future__ import annotations

import json

import pytest

from blxverse.engine import actions, conversation, llm
from blxverse.engine.sim import Simulation


@pytest.fixture()
def friend(sim, monkeypatch):
    monkeypatch.setenv('BLXVERSE_LLM_DISABLED', '1')
    npc = sim.npcs[12]
    npc.schedule = {'weekday': [], 'weekend': []}
    sim.force_move(npc, 'square')
    sim.adjust_rel(npc.id, 'player', familiarity=40, trust=40, tension=-100)
    npc.mood.social_energy = 90
    return npc


def test_text_is_remembered_face_to_face_and_on_call(sim, friend, near):
    actions.act_message(sim, {'npc_id': friend.id, 'text': 'My sister is called Amara and she has an interview on Friday.'})
    sim.world_flags['pending_messages'][0]['due'] = sim.minute
    sim._deliver_pending_messages()
    near(friend)
    reply = actions.act_talk(sim, {'npc_id': friend.id, 'text': 'Do you remember my sister and the interview?'})
    assert 'Amara' in reply['reply'] and 'text' in reply['reply']
    call = actions.act_call_start(sim, {'npc_id': friend.id})
    reply = actions.act_call_turn(sim, {'call_id': call['call_id'], 'text': 'What did I tell you about my sister?'})
    assert 'Amara' in reply['reply']
    assert any(t['medium'] == 'call' for t in friend.flags['conversation_history'])


def test_call_disclosure_survives_save_and_is_recalled_in_person(sim, friend, near):
    call = actions.act_call_start(sim, {'npc_id': friend.id})
    result = actions.act_call_turn(sim, {'call_id': call['call_id'], 'text': 'I work at Zenith and my interview is tomorrow.'})
    assert result['turn_id']
    sim.save(force=True)
    loaded = Simulation.load(sim.save_path)
    npc = loaded.npc(friend.id)
    loaded.player.x, loaded.player.y = npc.x+24, npc.y+6
    out = actions.act_talk(loaded, {'npc_id': npc.id, 'text': 'Where do I work? Remember what I told you?'})
    assert 'Zenith' in out['reply']


def test_retrieval_keeps_disclosures_beyond_rolling_transcript(sim, friend):
    conversation.record(sim, friend, 'My dog is called Bobo.', 'Nice!', 'text')
    for i in range(110):
        conversation.record(sim, friend, f'ordinary conversation number {i}', 'Okay', 'call')
    assert len(friend.flags['conversation_history']) == 80
    assert 'Bobo' in conversation.recall(friend, 'What is my dog called?')
    assert 'Bobo' in conversation.offline(friend, 'Do you remember my dog?', 'talk')


def test_memory_is_private_to_the_resident(sim, friend):
    conversation.record(sim, friend, 'My secret code word is plantain.', 'Okay', 'text')
    assert 'plantain' not in conversation.recall(sim.npcs[15], 'secret code word')


def test_legacy_thread_hydrates_once_without_duplicates(sim, friend):
    sim.send_npc_message(friend.id, 'The old conversation is still here.')
    friend.flags.pop('conversation_version', None)
    friend.flags['conversation_history'] = []
    conversation.hydrate(sim, friend)
    count = len(friend.flags['conversation_history'])
    conversation.hydrate(sim, friend)
    assert count == len(friend.flags['conversation_history']) == 1


def test_empty_memory_does_not_invent_shared_history(sim, friend):
    assert "don't remember" in conversation.offline(friend, 'Remember our trip to London?', 'talk')


def test_gemini_receives_cross_channel_memory_and_nigerian_channel_style(sim, friend, near, monkeypatch):
    monkeypatch.setenv('BLXVERSE_LLM_DISABLED', '0')
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key-not-real')
    actions.act_message(sim, {'npc_id': friend.id, 'text': 'My sister Amara is visiting on Friday.'})
    near(friend)
    out = actions.act_talk(sim, {'npc_id': friend.id, 'text': 'Remember Amara?'})
    ctx = out['_remote_dialogue']
    assert 'Amara' in ctx['memory'] and '[text' in ctx['memory'] and ctx['medium'] == 'talk'
    assert 'Nigerian English' in llm.SYSTEM_PROMPT and 'WhatsApp' in llm.SYSTEM_PROMPT


def test_wait_request_creates_walkable_trip_then_holds_and_expires(sim, friend):
    reply = conversation.request_plan(sim, friend, 'Abeg wait for me at the park for 10 minutes')
    assert "I'll meet you" in reply
    plan = friend.flags['meeting']
    start = friend.x, friend.y
    for _ in range(90):
        sim._npc_think(friend)
        sim._move_npcs(.5)
        if plan['status'] == 'waiting':
            break
    assert (friend.x, friend.y) != start
    assert plan['status'] == 'waiting'
    position = friend.x, friend.y
    for _ in range(10):
        sim._npc_think(friend)
        sim._move_npcs(.5)
    assert (friend.x, friend.y) == position
    sim.force_move(friend, 'cafe')
    assert (friend.x, friend.y) == position
    sim.minute = plan['wait_until']+.1
    sim._npc_think(friend)
    assert plan['status'] == 'finished'


def test_meetup_text_is_authoritative_and_persists(sim, friend):
    actions.act_message(sim, {'npc_id': friend.id, 'text': 'Meet me at the park in 20 minutes'})
    sim.world_flags['pending_messages'][0]['due'] = sim.minute
    sim._deliver_pending_messages()
    assert friend.flags['meeting']['due'] == sim.minute+20
    sim.save(force=True)
    loaded = Simulation.load(sim.save_path)
    assert loaded.npc(friend.id).flags['meeting']['status'] == 'scheduled'
    assert "I'll meet you" in loaded.threads[friend.id].messages[-1].text


@pytest.mark.parametrize('text', ['Wait for me somewhere', 'Meet me at the park later', 'Meet me at the park at 5', 'Meet me at the cafe or park'])
def test_ambiguous_plan_asks_a_question_without_creating_plan(sim, friend, text):
    assert '?' in conversation.request_plan(sim, friend, text)
    assert not friend.flags.get('meeting')


def test_work_and_relationship_can_decline_meetup(sim, friend):
    friend.schedule['weekday'] = [{'start': 0, 'end': 24, 'loc': 'cafe', 'activity': 'working', 'kind': 'work'}]
    assert "can't" in conversation.request_plan(sim, friend, 'Meet me at the park')
    assert not friend.flags.get('meeting')
    friend.schedule['weekday'] = []
    sim.adjust_rel(friend.id, 'player', tension=90)
    assert 'Not this time' in conversation.request_plan(sim, friend, 'Meet me at the park')


def test_explicit_cancellation_releases_plan(sim, friend):
    conversation.request_plan(sim, friend, 'Meet me at the park')
    sim._npc_think(friend)
    assert friend.target
    conversation.request_plan(sim, friend, 'Cancel our meeting')
    assert friend.flags['meeting']['status'] == 'cancelled'
    assert friend.target is None


def test_meeting_on_call_uses_same_authority(sim, friend):
    call = actions.act_call_start(sim, {'npc_id': friend.id})
    result = actions.act_call_turn(sim, {'call_id': call['call_id'], 'text': 'Wait for me at the park'})
    assert friend.flags['meeting']['status'] == 'scheduled'
    assert result['_remote_dialogue'] is None
    assert "I'll meet you" in result['reply']


def test_call_history_has_updateable_provider_turn_id(sim, friend):
    call = actions.act_call_start(sim, {'npc_id': friend.id})
    result = actions.act_call_turn(sim, {'call_id': call['call_id'], 'text': 'How far?'})
    row = next(t for t in friend.flags['conversation_history'] if t['id'] == result['turn_id'])
    assert row['user'] == 'How far?' and row['medium'] == 'call'
    assert 'dey' in row['reply']
    assert len(json.dumps(sim.state_payload())) < 300000
