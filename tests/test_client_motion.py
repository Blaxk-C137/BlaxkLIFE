"""Run the DOM-free route playback module with Node, without browser packages."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which('node') is None, reason='Node is optional for client module tests')
def test_motion_is_continuous_and_turns_corners_without_wall_chords():
    root = Path(__file__).resolve().parents[1]
    code = '''
      import assert from 'node:assert/strict';
      import { MotionTrack, routeBetween, alongRoute } from './web/js/motion.js';
      const a={x:0,y:0,route:[{x:100,y:0},{x:100,y:100}],at:0,speed:100};
      const b={x:100,y:100,at:2000};
      const path=routeBetween(a,b);
      assert.deepEqual(alongRoute(path,100),{x:100,y:0});
      assert.deepEqual(alongRoute(path,150),{x:100,y:50});
      const track=new MotionTrack(800);
      for(let t=0;t<=3600;t+=600) track.push({x:t/10,y:0,route:[{x:600,y:0}],walk_speed:100},t);
      let prev=null, steps=[];
      for(let now=1400;now<4300;now+=1000/60){
        const p=track.sample(now);
        if(prev)steps.push(p.x-prev.x);
        prev=p;
      }
      assert.ok(Math.min(...steps)>1.5,'must not stall between snapshots');
      assert.ok(Math.max(...steps)<1.8,'must not lurch on a snapshot');
      const late=track.sample(10000);
      assert.ok(late.x<=480.01,'never extrapolate more than 1.2 seconds');
      const noRoute=new MotionTrack();
      noRoute.push({x:5,y:5},0);
      assert.deepEqual(noRoute.sample(10000),{x:5,y:5});
      console.log('client motion: PASS');
    '''
    result = subprocess.run(['node', '--experimental-default-type=module', '--input-type=module', '-e', code],
                            cwd=root, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
