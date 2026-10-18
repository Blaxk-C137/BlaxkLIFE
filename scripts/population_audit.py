"""Measure the whole population in ordinary gameplay; preserve live saves."""
from __future__ import annotations

import json
import math
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blxverse.engine.sim import Simulation, walkable  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def measure(sim, label):
    starts = {n.id: (n.x, n.y) for n in sim.npcs}
    eligible = {n.id for n in sim.npcs if not sim._indoors(n) and n.energy > 12}
    moved, peak_walkers, close_pairs, bad_positions = set(), 0, 0, 0
    start = time.perf_counter()
    for _ in range(120):
        sim.tick(.25)
        for n in sim.npcs:
            if math.dist(starts[n.id], (n.x, n.y)) > 8:
                moved.add(n.id)
            bad_positions += not walkable(n.x, n.y)
        outside = [n for n in sim.npcs if not sim._indoors(n)]
        peak_walkers = max(peak_walkers, sum(n.status == 'walking' for n in outside))
        close_pairs += sum(math.dist((a.x, a.y), (b.x, b.y)) < 22 for i, a in enumerate(outside) for b in outside[i+1:])
    assert bad_positions == 0
    assert close_pairs == 0, (label, close_pairs)
    if eligible:
        assert len(moved & eligible) >= .85 * len(eligible), (label, len(moved), len(eligible))
    return {'scenario': label, 'residents': len(sim.npcs), 'initial_outdoors_eligible': len(eligible),
            'moved_over_8px': len(moved), 'eligible_moved': len(moved & eligible),
            'non_spotlight_moved': sum(not sim.npc(n).spotlight for n in moved),
            'ending_indoors': sum(sim._indoors(n) for n in sim.npcs), 'peak_walkers': peak_walkers,
            'close_pair_frames_under_22px': close_pairs, 'blocked_position_frames': bad_positions,
            'simulation_seconds_for_30_game_minutes': round(time.perf_counter()-start, 3)}


def run():
    rows = []
    with tempfile.TemporaryDirectory(prefix='blx-population-') as temp:
        for label, minute, settle in [('fresh morning', 450, 0),
                                      ('settled weekday mid-block', 2*1440+615, 30),
                                      ('asleep indoors', 1390, 0),
                                      ('next-day morning departure', 1440+450, 0)]:
            sim = Simulation.new(seed=20261017, player_spec={'name': 'Audit'}, save_path=f'{temp}/new.json')
            sim.minute = minute
            sim._place_npcs_at_schedule()
            sim.advance(settle)
            rows.append(measure(sim, label))
        live = ROOT / 'data/saves/world.json'
        if live.exists():
            copy = Path(temp) / 'copied-live-save.json'
            shutil.copy2(live, copy)
            sim = Simulation.load(str(copy))
            rows.append(measure(sim, 'copy of saved world, no reset'))
    report = {'result': 'PASS', 'window_game_minutes': 30, 'samples_per_scenario': 120, 'scenarios': rows,
              'note': 'Homes/sleepers are intentionally stationary indoors; outdoor residents keep schedules offscreen. Live save never modified.'}
    text = json.dumps(report, indent=2)
    (ROOT / 'docs/population-audit.json').write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    run()
