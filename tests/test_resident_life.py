"""Regression for actual autonomous life, not one manufactured moving sprite."""
from __future__ import annotations

import json
import math
import random
import subprocess
from pathlib import Path

from blxverse import config
from blxverse.content.scenery import hits_scenery
from blxverse.engine.sim import BUILDING_RECTS, Simulation, _circle_hits_rect, home_xy, walkable


def test_all_outdoor_cast_keeps_moving_between_commutes(sim):
    sim.minute = 2 * 1440 + 10 * 60 + 15
    sim._place_npcs_at_schedule()
    sim.advance(30)  # Finish initial journeys: do not measure commute startup.
    start = {n.id: (n.x, n.y) for n in sim.npcs}
    eligible = {n.id for n in sim.npcs if not sim._indoors(n) and n.energy > 12}
    moved = set()
    close_pairs = 0
    for _ in range(120):
        sim.tick(.25)
        for n in sim.npcs:
            if math.dist(start[n.id], (n.x, n.y)) > 8:
                moved.add(n.id)
            assert walkable(n.x, n.y)
        outside = [n for n in sim.npcs if not sim._indoors(n)]
        close_pairs += sum(math.dist((a.x, a.y), (b.x, b.y)) < 22
                           for i, a in enumerate(outside) for b in outside[i + 1:])
    assert len(moved & eligible) >= len(eligible) * .85, (len(moved), len(eligible))
    assert sum(not sim.npc(n).spotlight for n in moved) >= 30
    assert close_pairs == 0, close_pairs


def test_home_residents_are_inside_not_roaming_the_lawn(sim):
    sim.minute = 21 * 60 + 30
    sim._place_npcs_at_schedule()
    home = [n for n in sim.npcs if n.location_id == 'home']
    assert len(home) > 50
    start = {n.id: (n.x, n.y) for n in home}
    sim.advance(20)
    for n in home:
        assert sim._npc_core(n)['indoors']
        assert start[n.id] == (n.x, n.y)
        assert not n.target


def test_sleep_walks_home_then_despawns_at_door_and_leaves_next_day(sim):
    npc = sim.npcs[0]
    sim.minute = 23 * 60 + 1
    sim.force_move(npc, 'square')
    npc.flags.pop('block_key', None)
    sim._npc_think(npc)
    assert npc.status == 'walking' and npc.target['loc'] == 'home'
    assert not sim._npc_core(npc)['indoors']
    for _ in range(400):
        sim.minute += .25
        sim._move_npcs(.25)
        if npc.status == 'sleeping':
            break
    assert npc.status == 'sleeping'
    assert math.dist((npc.x, npc.y), home_xy(npc.home_id)) < 45
    assert sim._npc_core(npc)['indoors']
    sim.minute = 1440 + 10 * 60
    npc.flags.pop('block_key', None)
    sim._npc_think(npc)
    assert npc.status == 'walking'
    assert not sim._npc_core(npc)['indoors']


def test_save_resume_has_more_adult_women_without_replacing_existing_ids(sim, tmp_path):
    # Simulate an old, live 60-resident save.
    sim.npcs = sim.npcs[:60]
    sim.by_id = {n.id: n for n in sim.npcs}
    sim.world_flags.pop('blaxkville_cast_v2', None)
    sim.npcs[0].flags['dialogue_cursors'] = {'greeting': 900}
    before = {n.id: (n.gender, n.home_id, n.wallet) for n in sim.npcs}
    sim.save_path = str(tmp_path / 'legacy.json')
    sim.save(force=True)
    loaded = Simulation.load(sim.save_path)
    assert len(loaded.npcs) == config.NPC_COUNT == 72
    assert len({n.first for n in loaded.npcs}) == 72
    assert {n.id: (n.gender, n.home_id, n.wallet) for n in loaded.npcs[:60]} == before
    assert all(n.gender == 'female' and n.age >= 22 for n in loaded.npcs[60:])
    assert {'Zayyan', 'Bashir', 'Dominion'} <= {n.first for n in loaded.npcs}
    assert loaded.npcs[0].flags['dialogue_cursors']['greeting'] == 900
    loaded.save(force=True)
    twice = Simulation.load(loaded.save_path)
    assert [(n.id, n.first) for n in twice.npcs] == [(n.id, n.first) for n in loaded.npcs]


def test_spatial_broadphase_matches_exact_map_collision():
    rng = random.Random(51)
    for _ in range(5000):
        x, y, radius = rng.uniform(0, 1900), rng.uniform(0, 1300), rng.choice([8, 16, 18, 32, 55])
        exact = (30 <= x <= 1870 and 60 <= y <= 1270 and
                 not any(_circle_hits_rect(x, y, radius, rect) for rect in BUILDING_RECTS)
                 and not hits_scenery(x, y, radius))
        assert walkable(x, y, radius) == exact


def test_client_culls_offscreen_faraway_and_indoor_actors():
    module = (Path(__file__).parents[1] / 'web/js/visibility.js').as_uri()
    script = f"""import {{residentOpacity as opacity}} from {json.dumps(module)};
    const camera={{x:900,y:700,zoom:1}}, player={{x:900,y:700}};
    const at=(x,y,n={{}})=>opacity(n,{{x,y}},player,camera,800,600);
    if(at(900,700)!==1 || at(900,700,{{indoors:true}})!==0 || at(900,700,{{status:'sleeping'}})!==0) throw Error('indoor');
    if(at(1600,700)!==0 || at(900,1200)!==0) throw Error('offscreen');
    if(at(1420,700)!==0) throw Error('viewport cull');
    const a=opacity({{}},{{x:1430,y:700}},player,camera,1400,900);
    if(!(a>0 && a<1)) throw Error('approach fade');
    console.log('visibility pass');"""
    subprocess.run(['node', '--input-type=module', '-e', script], check=True, capture_output=True, text=True)


def test_conversation_pauses_commuter_without_despawning_them(sim):
    from blxverse.engine import actions
    npc = sim.npcs[1]
    # A person who has left home still has 'home' as their origin until arrival.
    npc.location_id = 'home'
    npc.target = {'x': 900, 'y': 800, 'loc': 'square', 'activity': 'commuting'}
    npc.status = 'walking'
    sim.player.x, sim.player.y = npc.x + 15, npc.y
    actions.handle_action(sim, {'type': 'talk', 'npc_id': npc.id, 'text': 'Hey, how are you?'})
    before = (npc.x, npc.y)
    sim._move_npcs(.25)
    core = sim._npc_core(npc)
    assert (npc.x, npc.y) == before
    assert npc.target and not core['indoors']
    assert core['route'] == [] and core['walk_speed'] == 0
    sim.minute += 13
    assert sim._npc_core(npc)['route'] == []  # explicit session now outlives the old timer
    actions.handle_action(sim, {'type':'talk_end', 'npc_id':npc.id})
    assert sim._npc_core(npc)['route']


def test_texting_and_calls_still_work_from_inside_home(sim):
    from blxverse.engine import actions
    npc = sim.npcs[0]
    sim.force_move(npc, 'home')
    assert sim._indoors(npc)
    text = actions.act_message(sim, {'npc_id': npc.id, 'text': 'How is your evening?'})
    assert text['scheduled']
    sim.adjust_rel(npc.id, 'player', familiarity=20)
    assert actions.act_call_start(sim, {'npc_id': npc.id})['call_id']


def test_route_cache_keeps_distinct_precise_goals(monkeypatch):
    from blxverse.engine import sim as engine
    monkeypatch.setattr(engine, '_PATH_CACHE', {})
    rng = random.Random(418)
    checked = 0
    for _ in range(100):
        x, y = rng.randrange(80, 1800, 30) + 1, rng.randrange(90, 1200, 30) + 1
        if not walkable(x, y, 18) or not walkable(x + 8, y, 18):
            continue
        engine._PATH_CACHE.clear()
        expected = engine.find_path(900, 900, x + 8, y)
        engine._PATH_CACHE.clear()
        engine.find_path(900, 900, x, y)
        actual = engine.find_path(900, 900, x + 8, y)
        assert actual and expected
        assert actual[-1] == expected[-1], (x, y, expected[-1], actual[-1])
        checked += 1
    assert checked >= 20


def test_body_aware_replan_does_not_smooth_through_a_stationary_resident():
    from blxverse.engine.sim import find_path
    source, goal, blocker = (500, 640), (700, 640), (600, 640)
    route = find_path(*source, *goal, blockers=(blocker,))
    assert route and route[-1] == goal
    for a, b in zip([source] + route, route, strict=False):
        dx, dy = b[0]-a[0], b[1]-a[1]
        t = max(0, min(1, ((blocker[0]-a[0])*dx + (blocker[1]-a[1])*dy)/(dx*dx+dy*dy or 1)))
        assert math.hypot(a[0]+t*dx-blocker[0], a[1]+t*dy-blocker[1]) >= 22.9


def test_narrow_doorstep_has_visible_connection_to_navigation_grid():
    from blxverse.engine.sim import _line_clear, find_path
    source = (1034, 1270)
    assert walkable(*source)
    route = find_path(*source, 900, 900)
    assert route
    assert _line_clear(*source, *route[0], margin=16)


def test_static_navigation_never_chords_through_a_tree_between_clear_grid_nodes():
    from blxverse.engine.sim import _line_clear, find_path, walkable
    start=(1245.0,560.0)
    goal=(1096.0,994.0)
    assert walkable(*start) and walkable(*goal)
    path=find_path(*start,*goal)
    assert path
    for a,b in zip([start,*path],path, strict=False):
        assert _line_clear(*a,*b,margin=16), (a,b)


def test_sleep_block_recovers_after_a_midnight_story_move(sim):
    npc=sim.npcs[1]
    sim.minute=4*60
    sim._place_npcs_at_schedule()
    assert npc.status=='sleeping'
    sim.force_move(npc,'park')
    sim._npc_think(npc)
    assert npc.target and npc.target['loc']=='home'
    assert npc.target['arrival_status']=='sleeping'
