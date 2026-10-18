/* Server-snapshot playback. No easing-to-a-dot, no speculative straight lines.
   A small jitter buffer lets every resident move continuously between polls. */
export function routeBetween(a, b) {
  const route = [a, ...(a.route || [])];
  if (route.length < 2) return [a, b];
  let best = { distance: Infinity, index: 0, x: a.x, y: a.y };
  for (let i = 0; i < route.length - 1; i++) {
    const p = route[i], q = route[i + 1];
    const dx = q.x - p.x, dy = q.y - p.y;
    const u = Math.max(0, Math.min(1, ((b.x-p.x)*dx+(b.y-p.y)*dy)/(dx*dx+dy*dy || 1)));
    const x = p.x+dx*u, y = p.y+dy*u;
    const distance = Math.hypot(b.x-x,b.y-y);
    if (distance < best.distance) best = { distance, index: i, x, y };
  }
  // A story teleport or destination change is not a route to interpolate through.
  if (best.distance > 45) return null;
  return [...route.slice(0,best.index+1), {x:best.x,y:best.y}, b];
}

export function alongRoute(points, distance) {
  if (!points.length) return null;
  for (let i=1; i<points.length; i++) {
    const a=points[i-1], b=points[i], length=Math.hypot(b.x-a.x,b.y-a.y);
    if (length && distance < length) {
      const u=Math.max(0,distance/length);
      return {x:a.x+(b.x-a.x)*u,y:a.y+(b.y-a.y)*u};
    }
    distance-=length;
  }
  const end=points[points.length-1];
  return {x:end.x,y:end.y};
}

export class MotionTrack {
  constructor(delay=800) { this.samples=[]; this.delay=delay; }
  push(npc, at) {
    this.samples.push({x:npc.x,y:npc.y,route:npc.route || [],at,speed:npc.walk_speed || 0});
    if (this.samples.length>8) this.samples.shift();
  }
  sample(now) {
    const s=this.samples, time=now-this.delay;
    if (!s.length) return null;
    if (time <= s[0].at) return {x:s[0].x,y:s[0].y};
    for (let i=1;i<s.length;i++) {
      const a=s[i-1],b=s[i];
      if (time>b.at) continue;
      const u=Math.max(0,Math.min(1,(time-a.at)/(b.at-a.at || 1)));
      if (Math.hypot(b.x-a.x,b.y-a.y) > a.speed*(b.at-a.at)/1000+90) return {x:a.x,y:a.y};
      const route=routeBetween(a,b);
      if (!route) return {x:a.x,y:a.y};
      const length=route.slice(1).reduce((n,p,j)=>n+Math.hypot(p.x-route[j].x,p.y-route[j].y),0);
      return alongRoute(route,length*u);
    }
    // A late poll can coast only on a known server route, then hold still.
    const a=s[s.length-1];
    return alongRoute([a,...a.route],Math.max(0,Math.min(1.2,(time-a.at)/1000))*a.speed);
  }
}
