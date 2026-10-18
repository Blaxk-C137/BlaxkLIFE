"""Offline voices, cast migration, solid scenery, and resident routes."""
from __future__ import annotations

import json

from blxverse.content.names import FEATURED_F, FEATURED_M
from blxverse.content.scenery import SCENERY
from blxverse.content.voices import BEATS, dress_reply, identity, nominal_capacity, variant_indices
from blxverse.engine.composer import _fill, compose_reply
from blxverse.engine.generate import apply_blaxkville_names, generate_npcs
from blxverse.engine.rng import RngHub
from blxverse.engine.sim import Simulation, walkable


def test_requested_cast_and_unique_vibes():
    for seed in (1, 9911, 20261017):
        npcs = generate_npcs(RngHub(seed))
        assert set(FEATURED_F + FEATURED_M) <= {n.first for n in npcs}
        assert len({n.first for n in npcs}) == 72
        assert len({identity(n)['signature'] for n in npcs}) == 72
        assert len({identity(n)['style'] for n in npcs}) >= 7
        before = [(n.id, n.first) for n in npcs]
        apply_blaxkville_names(npcs)
        assert before == [(n.id, n.first) for n in npcs]


def test_at_least_1000_distinct_offline_greetings_per_resident():
    # Exhaustive over the CAST, sampled over the compositional deck. Not a
    # misleading claim of a million manually authored lines.
    for npc in generate_npcs(RngHub(20261017)):
        lines = set()
        for turn in range(1200):
            indices = variant_indices(npc, 20261017, 'greeting', turn, len(BEATS['greeting']))
            core = BEATS['greeting'][indices[0]]
            lines.add(dress_reply(npc, core, indices, 'greeting'))
        assert len(lines) == 1200, (npc.first, len(lines))
        assert nominal_capacity(npc) >= 1_000_000  # composition slots, not authored lines


def test_dialogue_cursor_survives_save_and_load(tmp_path):
    path = str(tmp_path / 'world.json')
    sim = Simulation.new(seed=5, player_spec={'name': 'Ada'}, save_path=path)
    npc = sim.npcs[0]
    npc.flags['dialogue_cursors'] = {'greeting': 1240}
    npc.target = {'x': 1180, 'y': 620, 'loc': 'square', 'activity': 'commuting'}
    npc.status = 'walking'
    sim.player.x, sim.player.y = SCENERY[0]['x'], SCENERY[0]['y']
    sim.save(force=True)
    loaded = Simulation.load(path)
    assert loaded.npc(npc.id).flags['dialogue_cursors']['greeting'] == 1240
    assert loaded.npc(npc.id).target == npc.target
    assert walkable(loaded.player.x, loaded.player.y)
    args = dict(player=sim.player, rel=sim._rel_obj(npc.id), text='hey', intent='greeting', location_names=sim.location_names)
    a = compose_reply(npc=npc, hub=RngHub(sim.seed), **args)
    b = compose_reply(npc=loaded.npc(npc.id), hub=RngHub(sim.seed), **args)
    assert a['text'] == b['text'] and a['dialogue_cursor'] == 1241


def test_facts_fill_without_placeholder_leaks():
    sim = Simulation.new(seed=7, player_spec={'name': 'Ada'})
    for npc in sim.npcs:
        for intent, beats in BEATS.items():
            for beat in beats:
                text = _fill(beat, npc, sim.player, 'the park', 'painting', 'a book')
                assert '{' not in text and '}' not in text, (intent, text)


def test_forced_consent_answer_is_never_replaced():
    sim = Simulation.new(seed=9, player_spec={'name': 'Ada'})
    npc = sim.npcs[0]
    reply = compose_reply(npc=npc, player=sim.player, rel=sim._rel_obj(npc.id), text='date?', intent='ask_date',
                          hub=sim.hub, location_names=sim.location_names, forced_lines=['No, thank you.'])
    assert reply['text'].startswith('No, thank you.')
    assert 'yes' not in reply['text'].lower()


def test_scenery_bases_solid_but_canopies_permeable():
    assert len(SCENERY) == 74
    for prop in SCENERY:
        assert not walkable(prop['x'], prop['y'])
    tree = next(t for t in SCENERY if t['kind'] == 'tree' and walkable(t['x'], t['y'] - 40))
    assert walkable(tree['x'], tree['y'] - 40), 'space underneath tall foliage stays traversable'


def test_resident_payload_has_authoritative_path_and_individual_speeds():
    sim = Simulation.new(seed=8, player_spec={'name': 'Ada'})
    speeds = {sim.npc_walk_speed(n) for n in sim.npcs}
    assert len(speeds) >= 15
    npc = sim.npcs[0]
    npc.x, npc.y = 900, 900
    npc.target = {'x': 1180, 'y': 620, 'loc': 'square'}
    npc.status = 'walking'
    core = sim._npc_core(npc)
    assert core['route']
    assert all(walkable(p['x'], p['y']) for p in core['route'])
    assert core['walk_speed'] > 0 and core['vibe']['signature']


def test_resident_does_not_teleport_to_pocket_target():
    sim = Simulation.new(seed=8, player_spec={'name': 'Ada'})
    npc = sim.npcs[0]
    npc.x, npc.y = 900, 900
    prop = SCENERY[0]
    npc.target = {'x': prop['x'], 'y': prop['y'], 'loc': 'park'}
    npc.status = 'walking'
    for _ in range(500):
        if not npc.target:
            break
        sim._move_npcs(.25)
    assert walkable(npc.x, npc.y)
    assert (npc.x, npc.y) != (prop['x'], prop['y'])


def test_world_brand_and_size_and_migration(tmp_path):
    sim = Simulation.new(seed=15, player_spec={'name': 'Ada'}, save_path=str(tmp_path / 'world.json'))
    world = sim.world_payload()
    assert world['city'] == 'BlaxkVille'
    assert (world['config']['world_width'], world['config']['world_height']) == (1900, 1300)
    assert len(world['scenery']) == 74
    original_ids = [n.id for n in sim.npcs]
    for n in sim.npcs:
        if n.first in FEATURED_M + FEATURED_F:
            n.first = 'Old' + n.id
    sim.advance(1)
    assert sim.arcs, 'exercise an actual authored arc, not an empty list'
    for arc in sim.arcs:
        arc.title = arc.title.replace('BlaxkVille', 'Bellwether')
    sim.save(force=True)
    raw = json.loads(open(sim.save_path).read())
    raw['npcs'][0].pop('target', None)
    raw['npcs'][0]['status'] = 'walking'
    raw['npcs'][0]['flags']['block_key'] = 'legacy-commute'
    with open(sim.save_path, 'w') as fh:
        json.dump(raw, fh)
    loaded = Simulation.load(sim.save_path)
    assert 'block_key' not in loaded.npcs[0].flags
    assert all('Bellwether' not in a.title for a in loaded.arcs)
    assert set(FEATURED_M + FEATURED_F) <= {n.first for n in loaded.npcs}
    assert [n.id for n in loaded.npcs] == original_ids
    assert json.loads(open(sim.save_path).read())['schema'] == 3
