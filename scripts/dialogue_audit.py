"""Sample the actual offline composer for EVERY resident; no provider calls.

python3 scripts/dialogue_audit.py --samples 1200 --output docs/dialogue-audit.json
Capacity numbers are composition slots, not manually authored conversations.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blxverse.content.voices import identity, nominal_capacity  # noqa: E402
from blxverse.engine.composer import compose_reply  # noqa: E402
from blxverse.engine.sim import Simulation  # noqa: E402


def audit(samples=1200):
    started = time.perf_counter()
    rows = []
    with tempfile.TemporaryDirectory(prefix='blax-voices-') as temp:
        sim = Simulation.new(seed=20261017, player_spec={'name': 'Neighbour'}, save_path=str(Path(temp) / 'world.json'))
        for npc in sim.npcs:
            seen = set()
            rel = sim._rel_obj(npc.id)
            example = ''
            for _ in range(samples):
                out = compose_reply(npc=npc, player=sim.player, rel=rel, text='hey', intent='greeting',
                                    hub=sim.hub, location_names=sim.location_names)
                npc.flags.setdefault('dialogue_cursors', {})['greeting'] = out['dialogue_cursor']
                assert '{' not in out['text'] and '}' not in out['text']
                seen.add(out['text'])
                example = example or out['text']
            assert len(seen) == samples, (npc.first, samples, len(seen))
            rows.append({'name': npc.first, 'id': npc.id, 'vibe': identity(npc)['label'],
                         'sampled_distinct_greetings': len(seen), 'nominal_composition_slots': nominal_capacity(npc),
                         'example': example})
    return {'result': 'PASS', 'seed': 20261017, 'residents': len(rows),
            'sampled_replies': sum(r['sampled_distinct_greetings'] for r in rows),
            'minimum_distinct_greetings_per_resident': min(r['sampled_distinct_greetings'] for r in rows),
            'nominal_slots_per_resident': rows[0]['nominal_composition_slots'],
            'elapsed_seconds': round(time.perf_counter()-started, 2),
            'note': 'Nominal slots combine authored fragments. Not a million independently authored stories; grounded questions and safety/consent intentionally constrain replies.',
            'cast': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=1200)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    result = audit(args.samples)
    text = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(json.dumps({k: v for k, v in result.items() if k != 'cast'}, indent=2))


if __name__ == '__main__':
    main()
