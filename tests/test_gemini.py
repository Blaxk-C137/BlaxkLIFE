"""Native Gemini contract and failure paths. No real key / network required."""
from __future__ import annotations

import io
import json
from concurrent.futures import Future

import pytest

from blxverse.engine import actions, llm


@pytest.fixture(autouse=True)
def no_live_keys(monkeypatch):
    for name in ('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'BLXVERSE_LLM_API_KEY', 'BLXVERSE_LLM_DISABLED'):
        monkeypatch.delenv(name, raising=False)


def args(sim):
    n = sim.npcs[0]
    return dict(npc=n, player=sim.player, intent='smalltalk', player_text='What music do you love?',
                relationship='acquaintance', memory='Met at the cafe', venue='cafe')


def test_gemini_native_request_response_and_key_privacy(sim, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-secret-not-real')
    def fake_urlopen(request, timeout):
        assert request.full_url.endswith('/models/gemini-3.5-flash-lite:generateContent')
        assert 'test-secret' not in request.full_url
        assert request.get_header('X-goog-api-key') == 'test-secret-not-real'
        body = json.loads(request.data)
        assert body['contents'][0]['parts'][0]['text'].endswith('What music do you love?')
        assert 'Boundaries:' in body['systemInstruction']['parts'][0]['text']
        assert timeout <= 6
        return io.BytesIO(json.dumps({'candidates': [{'finishReason': 'STOP', 'content': {
            'parts': [{'text': 'I love Afrobeats. What have you been listening to?'}]}}]}).encode())
    monkeypatch.setattr(llm.urllib.request, 'urlopen', fake_urlopen)
    assert llm.generate_reply(**args(sim)).startswith('I love Afrobeats.')
    assert llm.status()['provider'] == 'gemini'
    assert 'test-secret' not in json.dumps(llm.status())


@pytest.mark.parametrize('response', [{}, {'candidates': []}, {'candidates': [{'finishReason': 'SAFETY'}]},
                                    {'candidates': [{'content': {'parts': []}}]}])
def test_empty_blocked_or_malformed_response_falls_back(sim, monkeypatch, response):
    monkeypatch.setenv('GOOGLE_API_KEY', 'fake-key')
    monkeypatch.setattr(llm.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(json.dumps(response).encode()))
    assert llm.generate_reply(**args(sim)) is None


def test_timeout_disabled_and_no_key_fallback(sim, monkeypatch):
    assert llm.generate_reply(**args(sim)) is None
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key')
    def timeout(*a, **k):
        raise TimeoutError()
    monkeypatch.setattr(llm.urllib.request, 'urlopen', timeout)
    assert llm.generate_reply(**args(sim)) is None
    monkeypatch.setenv('BLXVERSE_LLM_DISABLED', '1')
    assert not llm.is_enabled()


def test_talk_and_calls_snapshot_context_without_network_in_actions(sim, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key')
    def forbidden(*a, **k):
        raise AssertionError('Network attempted while mutating simulation')
    monkeypatch.setattr(llm, 'generate_reply', forbidden)
    npc = sim.npcs[0]
    sim.player.x, sim.player.y = npc.x, npc.y
    reply = actions.handle_action(sim, {'type': 'talk', 'npc_id': npc.id, 'text': 'What music do you like?'})
    assert reply['_remote_dialogue']['npc'] is not npc
    sim.adjust_rel(npc.id, 'player', familiarity=20)
    call = actions.act_call_start(sim, {'npc_id': npc.id})
    turn = actions.act_call_turn(sim, {'call_id': call['call_id'], 'text': 'How are you?'})
    assert turn['_remote_dialogue']['npc'] is not npc


def test_forced_consent_answers_never_remote_rephrased(sim, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key')
    npc = sim.npcs[0]
    sim.player.x, sim.player.y = npc.x, npc.y
    reply = actions.handle_action(sim, {'type': 'intent', 'npc_id': npc.id, 'intent': 'ask_date'})
    assert reply['accepted'] is False
    assert reply['_remote_dialogue'] is None


def test_pending_text_waits_for_worker_without_blocking_simulation(sim, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key')
    job = Future()
    monkeypatch.setattr(llm, 'submit_reply', lambda snapshot: job)
    npc = sim.npcs[0]
    sim.world_flags['pending_messages'] = [{'npc_id': npc.id, 'text': 'What is your favourite music?', 'due': sim.minute}]
    sim._deliver_pending_messages()
    assert len(sim.world_flags['pending_messages']) == 1
    minute = sim.minute
    sim.tick(.25)
    assert sim.minute > minute
    job.set_result('I am making an Afrobeats playlist. Any recommendations?')
    sim._deliver_pending_messages()
    assert not sim.world_flags['pending_messages']
    assert 'Afrobeats playlist' in sim.threads[npc.id].messages[-1].text
    sim.save(force=True)  # no Future objects in the JSON save


def test_typed_date_and_flirting_use_consent_rules(sim, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key')
    npc = sim.npcs[0]
    sim.player.x, sim.player.y = npc.x, npc.y
    declined = actions.handle_action(sim, {'type': 'talk', 'npc_id': npc.id, 'text': 'Will you go on a date with me?'})
    assert declined['accepted'] is False
    assert declined['_remote_dialogue'] is None
    assert 'declined' in declined['coaching']
    assert sim.rel(npc.id, 'player')['romance'] == 0
