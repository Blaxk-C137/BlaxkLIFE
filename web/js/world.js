/* =========================================================================
   World renderer & camera
   Canvas 2D, procedural static base layer + animated residents & effects.
   ========================================================================= */
import { buildStaticWorld, drawSprite, avatarUrl } from './art.js';

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

export class WorldView {
  constructor(canvas, cb = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.cb = cb;
    this.world = null;
    this.staticLayer = null;
    this.locations = [];
    this.homes = [];
    this.loc = {};
    this.npcs = new Map();
    this.player = null;
    this.clock = { hour: 7, weather: 'clear skies' };
    this.camera = { x: 900, y: 800, zoom: 0.92, targetZoom: 0.92 };
    this.display = new Map();
    this.playerDisplay = { x: 900, y: 800 };
    // The player walks the server's A* route, waypoint by waypoint. Never a
    // straight line to the clicked point: that crossed buildings and fought
    // the authoritative position every poll.
    this.walk = { route: [], dest: null, facing: 1, speed: 230, moving: false,
                  arrived: false, reconcile: null, stable: null };
    this.hover = null;
    this.marker = null;
    this.chaos = [];
    this.particles = [];
    this.keys = new Set();
    this.lastMoveSent = 0;
    this.raf = null;
    this.t = 0;
    this.lastFrame = performance.now();
    this.dpr = 1;
    this.dimmed = false;

    this._bind();
    this.resize();
    this._loop = this._loop.bind(this);
    this.raf = requestAnimationFrame(this._loop);
  }

  load(world) {
    this.world = world;
    this.locations = world.locations || [];
    this.homes = world.homes || [];
    this.loc = Object.fromEntries(this.locations.map(l => [l.id, l]));
    this.staticLayer = buildStaticWorld(world);
    this.npcs.clear();
    this.display.clear();
    for (const n of world.npcs || []) {
      this.npcs.set(n.id, n);
      this.display.set(n.id, { x: n.x, y: n.y });
    }
    if (this.player) {
      this.camera.x = this.player.x;
      this.camera.y = this.player.y;
    }
    this.seedParticles();
  }

  setState(state) {
    if (!state || state.setup) return;
    const prev = this.player;
    this.player = { ...state.player, isPlayer: true };
    const pd = this.playerDisplay;

    const serverRoute = Array.isArray(this.player.route) ? this.player.route : [];
    const dest = this.player.dest || null;
    const destChanged = !this.walk.dest || !dest ||
      Math.hypot(dest.x - this.walk.dest.x, dest.y - this.walk.dest.y) > 6;

    // Adopt the authoritative route when we have none, when the destination
    // changed, or when the server's first waypoint is nowhere near us (it
    // replanned around something). Otherwise keep walking ours so the sprite
    // never restarts mid-stride on every poll.
    // The poll is up to POLL_FAST old, so the server report *lags* the sprite
    // we already drew. Trusting it blindly is what dragged the sprite backwards
    // at the end of every walk ("moves forward and back"). Once we have
    // painted the destination we consider the walk done and ignore stale
    // routes that still point there.
    const sameDest = !!(dest && this.walk.dest && !destChanged);
    const first = serverRoute[0];
    const farFromRoute = first && Math.hypot(first.x - pd.x, first.y - pd.y) > 120;
    const adopt = serverRoute.length && !this.walk.arrived &&
      (!this.walk.route.length || destChanged || farFromRoute);
    if (adopt) {
      this.walk.route = serverRoute.map(p => ({ x: p.x, y: p.y }));
      this.walk.dest = dest;
      this.walk.arrived = false;
      this.walk.reconcile = null;
    } else if (!serverRoute.length && !this.player.moving) {
      this.walk.route = [];
      if (sameDest) this.walk.arrived = true;
      else { this.walk.dest = null; this.walk.arrived = false; }
    }

    // Reconciliation only ever *glides*, never snaps, and only once the
    // server has reported the same resting position on two consecutive polls
    // — i.e. it has genuinely stopped. Two identical positions in a row is
    // the cheap proof that the snapshot is not simply stale.
    const err = Math.hypot(pd.x - this.player.x, pd.y - this.player.y);
    const still = this.walk.stable &&
      Math.hypot(this.player.x - this.walk.stable.x, this.player.y - this.walk.stable.y) < 1;
    this.walk.stable = { x: this.player.x, y: this.player.y };
    if (!this.walk.route.length && !this.player.moving && still && err > 6) {
      this.walk.reconcile = { x: this.player.x, y: this.player.y };
    }
    if (err > 420 && !this.walk.route.length) {
      pd.x = this.player.x; pd.y = this.player.y;
      this.walk.reconcile = null;
    }
    if (prev && Math.abs((this.player.x || 0) - (prev.x || 0)) > 0.2) {
      this.walk.facing = this.player.x > prev.x ? 1 : -1;
    }
    for (const npc of state.npcs || []) {
      const cached = this.npcs.get(npc.id);
      if (cached) Object.assign(cached, npc);
      else this.npcs.set(npc.id, npc);
      let d = this.display.get(npc.id);
      if (!d) { d = { x: npc.x, y: npc.y }; this.display.set(npc.id, d); }
      d.tx = npc.x; d.ty = npc.y;
    }
    this.clock = state.clock || this.clock;
    this.dimmed = !!state.setup;
  }

  seedParticles() {
    this.particles = [];
    const rnd = (a, b) => a + Math.random() * (b - a);
    for (let i = 0; i < 46; i++) {
      this.particles.push({ x: rnd(0, 1900), y: rnd(0, 1300), r: rnd(1, 2.6), s: rnd(6, 20), ph: rnd(0, 6.28), kind: i % 3 === 0 ? 'leaf' : 'dust' });
    }
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    this.dpr = Math.min(2, window.devicePixelRatio || 1);
    this.canvas.width = Math.max(2, Math.floor(rect.width * this.dpr));
    this.canvas.height = Math.max(2, Math.floor(rect.height * this.dpr));
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.viewW = rect.width;
    this.viewH = rect.height;
  }

  /* ------------------------------------------------------------- camera */
  /** Walk a list of {x,y} waypoints (the server's computed path). */
  setRoute(points, dest = null) {
    this.walk.route = (points || []).map(p => ({ x: p.x, y: p.y }));
    this.walk.dest = dest || (this.walk.route.length ? this.walk.route[this.walk.route.length - 1] : null);
    this.walk.moving = this.walk.route.length > 0;
    this.walk.arrived = false;
    this.walk.reconcile = null;
  }

  clearRoute() {
    this.walk.route = [];
    this.walk.dest = null;
    this.walk.moving = false;
    this.walk.arrived = false;
    this.walk.reconcile = null;
  }

  get isWalking() { return this.walk.route.length > 0; }

  centerOnPlayer() {
    if (!this.player) return;
    this.camera.x = this.player.x;
    this.camera.y = this.player.y;
  }

  setZoom(delta) {
    this.camera.targetZoom = clamp(this.camera.targetZoom + delta, 0.62, 2.0);
  }

  zoomTo(z) { this.camera.targetZoom = clamp(z, 0.62, 2.0); }

  screenToWorld(sx, sy) {
    const c = this.camera;
    return {
      x: c.x + (sx - this.viewW / 2) / c.zoom,
      y: c.y + (sy - this.viewH / 2) / c.zoom,
    };
  }

  worldToScreen(wx, wy) {
    const c = this.camera;
    return {
      x: (wx - c.x) * c.zoom + this.viewW / 2,
      y: (wy - c.y) * c.zoom + this.viewH / 2,
    };
  }

  /* ------------------------------------------------------------- input */
  _bind() {
    const canvas = this.canvas;
    canvas.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
      const hit = this.hitTest(sx, sy);
      if (hit.type === 'npc') this.cb.onNpc?.(hit.id);
      else if (hit.type === 'location') this.cb.onLocation?.(hit.id);
      else if (hit.type === 'home') this.cb.onHome?.(hit.id);
      else {
        const w = this.screenToWorld(sx, sy);
        this.marker = { x: w.x, y: w.y, t: this.t };
        this.cb.onMove?.(w.x, w.y);
      }
    });
    canvas.addEventListener('pointermove', (e) => {
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
      const hit = this.hitTest(sx, sy);
      this.hover = hit;
      canvas.style.cursor = hit.type === 'ground' ? 'crosshair' : 'pointer';
      this.cb.onHover?.(hit, { x: sx, y: sy });
    });
    canvas.addEventListener('pointerleave', () => { this.hover = null; });
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.setZoom(e.deltaY > 0 ? -0.08 : 0.08);
    }, { passive: false });

    window.addEventListener('keydown', (e) => {
      if (e.target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
      const k = e.key.toLowerCase();
      if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(k)) {
        this.keys.add(k === 'arrowup' ? 'w' : k === 'arrowdown' ? 's' : k === 'arrowleft' ? 'a' : k === 'arrowright' ? 'd' : k);
      }
    });
    window.addEventListener('keyup', (e) => {
      const k = e.key.toLowerCase();
      this.keys.delete(k === 'arrowup' ? 'w' : k === 'arrowdown' ? 's' : k === 'arrowleft' ? 'a' : k === 'arrowright' ? 'd' : k);
    });
    window.addEventListener('blur', () => this.keys.clear());
  }

  hitTest(sx, sy) {
    const w = this.screenToWorld(sx, sy);
    let best = null, bestD = 1e9;
    for (const npc of this.npcs.values()) {
      const d = Math.hypot(npc.x - w.x, npc.y - w.y);
      const r = 20 / this.camera.zoom + 10;
      if (d < r && d < bestD) { best = { type: 'npc', id: npc.id }; bestD = d; }
    }
    if (this.player && Math.hypot(this.player.x - w.x, this.player.y - w.y) < 18 / this.camera.zoom + 6) {
      if (!best) best = { type: 'npc', id: 'player' };
    }
    if (best) return best;
    for (const l of this.locations) {
      if (w.x >= l.x && w.x <= l.x + l.w && w.y >= l.y && w.y <= l.y + l.h) {
        return { type: 'location', id: l.id };
      }
    }
    for (const h of this.homes) {
      if (w.x >= h.x && w.x <= h.x + 92 && w.y >= h.y - 8 && w.y <= h.y + 74) {
        return { type: 'home', id: h.id };
      }
    }
    return { type: 'ground', x: w.x, y: w.y };
  }

  /* ------------------------------------------------------------- effects */
  setDestinationMarker(x, y) {
    this.marker = { x, y, t: this.t };
  }

  playChaos(x, y, caption = 'BOING!') {
    this.chaos.push({ x, y, t: 0, caption, dur: 8 });
  }

  flashMarker(x, y) { this.marker = { x, y, t: this.t }; }

  /* ------------------------------------------------------------- loop */
  _loop(now) {
    const dt = Math.min(0.05, (now - this.lastFrame) / 1000);
    this.lastFrame = now;
    this.t += dt;
    try { this._update(dt); this._draw(); } catch (err) { console.error(err); }
    this.raf = requestAnimationFrame(this._loop);
  }

  _update(dt) {
    // smooth camera zoom
    const c = this.camera;
    c.zoom += (c.targetZoom - c.zoom) * Math.min(1, dt * 8);

    // player display + camera follow
    if (this.player) {
      const pd = this.playerDisplay;
      const route = this.walk.route;

      if (route.length) {
        // Walk exactly along the authoritative path at the server's speed,
        // easing in/out so starts and stops stop looking robotic.
        let budget = this.walk.speed * dt;
        let guard = 0;
        while (budget > 0 && route.length && guard++ < 8) {
          const wp = route[0];
          const dx = wp.x - pd.x, dy = wp.y - pd.y;
          const d = Math.hypot(dx, dy);
          if (d < 0.75) { route.shift(); continue; }
          const stepLen = Math.min(budget, d);
          pd.x += dx / d * stepLen;
          pd.y += dy / d * stepLen;
          if (Math.abs(dx) > 0.4) this.walk.facing = dx > 0 ? 1 : -1;
          budget -= stepLen;
        }
        if (!route.length) { this.walk.moving = false; this.walk.arrived = true; }
      } else {
        // Glide to a *confirmed* resting server position at a walking pace —
        // small corrections look like a sidestep, not a jitter.
        const rec = this.walk.reconcile;
        if (rec) {
          const dx = rec.x - pd.x, dy = rec.y - pd.y;
          const d = Math.hypot(dx, dy);
          if (d < 3) { pd.x = rec.x; pd.y = rec.y; this.walk.reconcile = null; }
          else {
            const step = Math.min(d, 95 * dt);
            pd.x += dx / d * step;
            pd.y += dy / d * step;
          }
        }
      }
      const targetX = clamp(pd.x, this.viewW / (2 * c.zoom) - 80, 1900 - this.viewW / (2 * c.zoom) + 80);
      const targetY = clamp(pd.y, this.viewH / (2 * c.zoom) - 60, 1300 - this.viewH / (2 * c.zoom) + 60);
      c.x += (targetX - c.x) * Math.min(1, dt * 4.2);
      c.y += (targetY - c.y) * Math.min(1, dt * 4.2);
      c.x = clamp(c.x, this.viewW / (2 * c.zoom) - 90, 1900 - this.viewW / (2 * c.zoom) + 90);
      c.y = clamp(c.y, this.viewH / (2 * c.zoom) - 70, 1300 - this.viewH / (2 * c.zoom) + 70);
    }

    // npc interpolation
    for (const [id, d] of this.display) {
      if (d.tx === undefined) continue;
      d.x += (d.tx - d.x) * Math.min(1, dt * 6.5);
      d.y += (d.ty - d.y) * Math.min(1, dt * 6.5);
    }

    // Keyboard steering: aim from where the sprite actually is (not the
    // lagging server position) and only re-issue when the direction changes
    // or the current route is running out. Re-sending every 160 ms from the
    // server position is what made held keys stutter.
    if (this.keys.size && this.player) {
      let dx = (this.keys.has('d') ? 1 : 0) - (this.keys.has('a') ? 1 : 0);
      let dy = (this.keys.has('s') ? 1 : 0) - (this.keys.has('w') ? 1 : 0);
      if (dx || dy) {
        const len = Math.hypot(dx, dy) || 1;
        dx /= len; dy /= len;
        this.keys.dir = `${dx.toFixed(2)},${dy.toFixed(2)}`;
        const pd = this.playerDisplay;
        const routeLeft = this.walk.route.length;
        const stale = performance.now() - this.lastMoveSent > 520;
        if (routeLeft < 2 || stale) {
          this.lastMoveSent = performance.now();
          this.cb.onMove?.(pd.x + dx * 300, pd.y + dy * 300, true);
        }
      }
    }

    // chaos animations
    for (const ch of this.chaos) ch.t += dt;
    this.chaos = this.chaos.filter(ch => ch.t < ch.dur);

    // particles drift
    for (const p of this.particles) {
      p.x += Math.sin(this.t * .6 + p.ph) * 4 * dt;
      p.y += p.s * dt * .3;
      if (p.y > 1320) { p.y = -10; p.x = Math.random() * 1900; }
    }
  }

  _draw() {
    if (!this.staticLayer) return;
    const ctx = this.ctx;
    const c = this.camera;
    ctx.save();
    ctx.clearRect(0, 0, this.viewW, this.viewH);
    ctx.translate(this.viewW / 2, this.viewH / 2);
    ctx.scale(c.zoom, c.zoom);
    ctx.translate(-c.x, -c.y);

    ctx.drawImage(this.staticLayer, 0, 0);

    this._drawFountain(ctx);
    this._drawMarker(ctx);

    // hover highlight on venues
    if (this.hover?.type === 'location') {
      const l = this.loc[this.hover.id];
      if (l) {
        ctx.strokeStyle = 'rgba(255,180,84,.8)';
        ctx.lineWidth = 2.5 / c.zoom;
        ctx.setLineDash([7, 5]);
        rrPath(ctx, l.x - 6, l.y - 6, l.w + 12, l.h + 12, 16);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
    if (this.hover?.type === 'home') {
      const h = this.homes.find(hh => hh.id === this.hover.id);
      if (h) {
        ctx.strokeStyle = 'rgba(127,209,185,.8)';
        ctx.lineWidth = 2.5 / c.zoom;
        rrPath(ctx, h.x - 6, h.y - 12, 104, 92, 12);
        ctx.stroke();
      }
    }

    // sprites sorted by y
    const list = [];
    for (const npc of this.npcs.values()) {
      const d = this.display.get(npc.id);
      if (!d) continue;
      list.push({ npc, x: d.x, y: d.y });
    }
    if (this.player) {
      const p = {
        ...this.player, id: 'player', isPlayer: true,
        status: this.isWalking ? 'walking' : (this.player.status || 'at'),
        facing: this.walk.facing,
      };
      list.push({ npc: p, x: this.playerDisplay.x, y: this.playerDisplay.y });
    }
    list.sort((a, b) => a.y - b.y);
    const labelRects = [];
    for (const item of list) {
      const npc = { ...item.npc, x: item.x, y: item.y };
      const isHover = this.hover?.type === 'npc' && this.hover.id === (npc.id || 'player');
      drawSprite(ctx, npc, this.t, { zoom: c.zoom, dim: this.dimmed, scale: isHover ? 1.05 : 1, labels: labelRects });
      if (isHover && !npc.isPlayer) {
        ctx.strokeStyle = 'rgba(255,180,84,.85)';
        ctx.lineWidth = 2 / c.zoom;
        ctx.beginPath(); ctx.ellipse(item.x, item.y, 22, 9, 0, 0, Math.PI * 2); ctx.stroke();
      }
    }

    // dust clouds
    for (const ch of this.chaos) this._drawChaos(ctx, ch);
    // weather particles
    this._drawWeather(ctx);
    ctx.restore();

    this._drawNightTint(ctx);
  }

  _drawFountain(ctx) {
    const sq = this.loc.square;
    if (!sq) return;
    const cx = sq.x + sq.w / 2, cy = sq.y + sq.h / 2;
    ctx.save();
    ctx.fillStyle = 'rgba(140,180,220,.22)';
    ctx.beginPath(); ctx.arc(cx, cy, 40, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(200,225,255,.5)';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(cx, cy, 40, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = 'rgba(180,220,255,.35)';
    ctx.beginPath(); ctx.arc(cx, cy, 30, 0, Math.PI * 2); ctx.fill();
    for (let i = 0; i < 5; i++) {
      const a = this.t * .7 + i * 1.256;
      const rx = cx + Math.cos(a) * 14;
      const ry = cy + Math.sin(a) * 5 - 34 - Math.sin(this.t * 2 + i) * 6;
      ctx.fillStyle = 'rgba(210,235,255,.6)';
      ctx.beginPath(); ctx.arc(rx, ry, 2.6, 0, Math.PI * 2); ctx.fill();
    }
    ctx.fillStyle = 'rgba(220,240,255,.55)';
    ctx.beginPath(); ctx.arc(cx, cy - 16, 5, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  _drawMarker(ctx) {
    // Active destination: a soft ring that breathes while you walk toward it.
    const dest = this.walk.dest;
    if (dest && this.walk.route.length) {
      const pulse = 1 + Math.sin(this.t * 3.4) * 0.12;
      ctx.save();
      ctx.strokeStyle = 'rgba(255,180,84,.5)';
      ctx.lineWidth = 1.6;
      ctx.setLineDash([6, 6]);
      ctx.lineDashOffset = -this.t * 14;
      ctx.beginPath(); ctx.ellipse(dest.x, dest.y, 17 * pulse, 8 * pulse, 0, 0, Math.PI * 2); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = 'rgba(255,180,84,.5)';
      ctx.beginPath(); ctx.ellipse(dest.x, dest.y, 3.2, 2.2, 0, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
    if (!this.marker) return;
    const age = this.t - this.marker.t;
    if (age > 1.6) { this.marker = null; return; }
    ctx.save();
    ctx.strokeStyle = `rgba(255,180,84,${.9 - age / 2})`;
    ctx.lineWidth = 2.2;
    const r = 10 + age * 16;
    ctx.beginPath(); ctx.arc(this.marker.x, this.marker.y, r, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(this.marker.x, this.marker.y, 3.5, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  _drawChaos(ctx, ch) {
    const p = ch.t / ch.dur;
    const x = ch.x, y = ch.y;
    ctx.save();
    ctx.globalAlpha = p < .85 ? 1 : (1 - p) / .15;
    // swirling cloud
    for (let i = 0; i < 9; i++) {
      const a = this.t * 3.2 + i * .7;
      const rr = 26 + i * 4 + Math.sin(this.t * 4 + i) * 6;
      const cx = x + Math.cos(a) * (18 + i * 3);
      const cy = y - 30 + Math.sin(a) * 10 - i * 1.4;
      ctx.fillStyle = i % 2 ? 'rgba(232,220,200,.55)' : 'rgba(196,180,158,.5)';
      ctx.beginPath(); ctx.arc(cx, cy, rr * .42, 0, Math.PI * 2); ctx.fill();
    }
    // stars
    for (let i = 0; i < 5; i++) {
      const a = this.t * 2 + i * 1.256;
      const sx = x + Math.cos(a) * 42, sy = y - 54 + Math.sin(a) * 18;
      this._star(ctx, sx, sy, 5 + Math.sin(this.t * 5 + i) * 2, 'rgba(255,220,130,.95)');
    }
    // caption
    if (p < .8) {
      ctx.font = '800 14px Inter, system-ui, sans-serif';
      ctx.textAlign = 'center';
      const wob = Math.sin(this.t * 10) * 1.6;
      ctx.save();
      ctx.translate(x, y - 96 + wob);
      ctx.rotate(Math.sin(this.t * 6) * .04);
      ctx.fillStyle = 'rgba(8,14,24,.8)';
      roundRect(ctx, -70, -14, 140, 26, 10); ctx.fill();
      ctx.fillStyle = '#ffd166';
      ctx.fillText(ch.caption.slice(0, 22), 0, 4);
      ctx.restore();
    }
    ctx.restore();
  }

  _star(ctx, x, y, r, color) {
    ctx.save();
    ctx.fillStyle = color;
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + i * Math.PI / 5;
      const rad = i % 2 ? r * .45 : r;
      const px = x + Math.cos(a) * rad, py = y + Math.sin(a) * rad;
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.closePath(); ctx.fill();
    ctx.restore();
  }

  _drawWeather(ctx) {
    const w = (this.clock?.weather || '').toLowerCase();
    const night = this._nightFactor() > .3;
    if (w.includes('rain') || w.includes('drizzle')) {
      ctx.save();
      ctx.strokeStyle = 'rgba(160,200,255,.35)';
      ctx.lineWidth = 1.2;
      for (let i = 0; i < 60; i++) {
        const x = ((i * 137 + this.t * 120) % 1980) - 40;
        const y = ((i * 89 + this.t * 420) % 1360) - 30;
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 3, y + 13); ctx.stroke();
      }
      ctx.restore();
    }
    if (night) {
      ctx.save();
      for (let i = 0; i < 20; i++) {
        const x = 300 + ((i * 71) % 1400);
        const y = 250 + ((i * 137) % 900);
        const a = .25 + .25 * Math.sin(this.t * 1.3 + i);
        ctx.fillStyle = `rgba(255,226,150,${a})`;
        ctx.beginPath(); ctx.arc(x + Math.sin(this.t + i) * 8, y + Math.cos(this.t * .7 + i) * 6, 1.8, 0, Math.PI * 2); ctx.fill();
      }
      ctx.restore();
    }
  }

  _nightFactor() {
    const h = this.clock?.hour ?? 8;
    const m = this.clock?.minute_of_hour ?? 0;
    const t = h + m / 60;
    if (t >= 6 && t < 17.5) return 0;
    if (t >= 17.5 && t < 20.5) return (t - 17.5) / 3 * .16;
    if (t >= 20.5 || t < 4.5) return .30;
    return .16 * (1 - (t - 4.5) / 1.5);
  }

  _drawNightTint(ctx) {
    const n = this._nightFactor();
    if (n <= 0.005) return;
    ctx.save();
    ctx.fillStyle = `rgba(12,24,52,${n})`;
    ctx.fillRect(0, 0, this.viewW, this.viewH);
    // warm window glow at night
    ctx.globalCompositeOperation = 'lighter';
    const pulse = .04 + .02 * Math.sin(this.t * .8);
    for (const l of this.locations) {
      const s = this.worldToScreen(l.x + l.w / 2, l.y + l.h * .55);
      const r = Math.max(l.w, l.h) * this.camera.zoom * .6;
      const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, r);
      g.addColorStop(0, `rgba(255,190,110,${.10 + pulse})`);
      g.addColorStop(1, 'rgba(255,190,110,0)');
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(s.x, s.y, r, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }

  avatarFor(npcId) {
    const npc = npcId === 'player' ? this.player : this.npcs.get(npcId);
    if (!npc) return '';
    return avatarUrl(npc.look, 96, 'bust', npc.mood);
  }
}

function rrPath(ctx, x, y, w, h, r) {
  const rad = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rad, y);
  ctx.arcTo(x + w, y, x + w, y + h, rad);
  ctx.arcTo(x + w, y + h, x, y + h, rad);
  ctx.arcTo(x, y + h, x, y, rad);
  ctx.arcTo(x, y, x + w, y, rad);
  ctx.closePath();
}
function roundRect(ctx, x, y, w, h, r) {
  rrPath(ctx, x, y, w, h, r);
}
