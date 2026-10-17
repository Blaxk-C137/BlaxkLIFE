/* =========================================================================
   BLXVERSE art engine
   All characters and the entire neighborhood are drawn procedurally.
   No external images, fonts or assets — the preview stays fully self-contained.
   ========================================================================= */

const SKINS_DARK = ['#6b4226', '#4c2f21', '#8a5a3b'];
const avatarCache = new Map();
const HAIR_STYLES = ['short', 'curly', 'braids', 'bun', 'wave', 'locs', 'buzz', 'ponytail'];

export const LOOK_OPTIONS = {
  skin: ['#f6d7c3', '#f1cbb3', '#eec3a0', '#d9a066', '#b97a4e', '#8a5a3b', '#6b4226', '#4c2f21'],
  hair: ['#241a15', '#3b2417', '#5a3825', '#7a4b2b', '#1b1b1b', '#8c6239', '#b07d4a', '#d9c2a3'],
  hairStyle: HAIR_STYLES,
  outfit: ['#e0663b', '#3b82a0', '#c9902f', '#7c5cbf', '#4f9a6a', '#c2547f', '#3f6bc4', '#d9a441', '#5a6b7d', '#b5502f'],
  accessory: ['none', 'glasses', 'earrings', 'cap', 'headband', 'watch', 'chain', 'scarf'],
  accent: ['#ffffff', '#1f2937', '#f2c14e', '#7fd1b9', '#ffb454', '#b7a4ff'],
};

/* ---------------------------------------------------------------- helpers */
function rr(ctx, x, y, w, h, r) {
  const rad = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rad, y);
  ctx.arcTo(x + w, y, x + w, y + h, rad);
  ctx.arcTo(x + w, y + h, x, y + h, rad);
  ctx.arcTo(x, y + h, x, y, rad);
  ctx.arcTo(x, y, x + w, y, rad);
  ctx.closePath();
}
function shade(hex, amt) {
  const h = hex.replace('#', '');
  const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h;
  const n = parseInt(full, 16);
  let r = (n >> 16) + amt, g = ((n >> 8) & 255) + amt, b = (n & 255) + amt;
  r = Math.max(0, Math.min(255, r)); g = Math.max(0, Math.min(255, g)); b = Math.max(0, Math.min(255, b));
  return `rgb(${r},${g},${b})`;
}
function hashStr(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0);
}
function mulberry(seed) {
  let t = seed >>> 0;
  return () => {
    t += 0x6D2B79F5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

/* ---------------------------------------------------------------- avatars */
export function drawAvatar(ctx, look = {}, W, H, opts = {}) {
  const {
    mood = 'steady', mode = 'bust', bob = 0, facing = 1, talking = false,
    ring = false,
  } = opts;
  const skin = look.skin || '#d9a066';
  const hair = look.hair || '#241a15';
  const hairStyle = HAIR_STYLES.includes(look.hairStyle) ? look.hairStyle : 'short';
  const outfit = look.outfit || '#e0663b';
  const accent = look.accent || '#f2c14e';
  const accessory = look.accessory || 'none';
  const smile = mood === 'buzzing' || mood === 'cheerful' || mood === 'excited';
  const sad = mood === 'low';
  const angry = mood === 'irritated' || mood === 'stressed';

  ctx.save();
  ctx.clearRect(0, 0, W, H);

  if (mode === 'head') {
    const s = Math.min(W, H) / 110;
    ctx.translate(W / 2, H / 2 + 2);
    ctx.scale(s, s);
    drawHead(ctx, 0, 0, skin, hair, hairStyle, smile, sad, angry, accessory, accent);
    ctx.restore();
    return;
  }

  // bust composition
  const s = Math.min(W / 300, H / 380) * 1.02;
  ctx.translate(W / 2, H * 0.52 + bob);
  ctx.scale(s, s);

  // backdrop arch
  ctx.save();
  const bg = ctx.createRadialGradient(0, -60, 20, 0, -40, 190);
  bg.addColorStop(0, 'rgba(255,180,84,.13)');
  bg.addColorStop(.55, 'rgba(127,209,185,.06)');
  bg.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = bg;
  ctx.beginPath(); ctx.arc(0, -10, 160, 0, Math.PI * 2); ctx.fill();
  ctx.restore();

  // floor shadow
  ctx.save();
  ctx.fillStyle = 'rgba(0,0,0,.28)';
  ctx.filter = 'blur(6px)';
  ctx.beginPath(); ctx.ellipse(0, 148, 82, 16, 0, 0, Math.PI * 2); ctx.fill();
  ctx.restore();

  // legs (subtle)
  ctx.fillStyle = '#1b2737';
  rr(ctx, -30, 92, 24, 58, 11); ctx.fill();
  rr(ctx, 8, 92, 24, 58, 11); ctx.fill();
  ctx.fillStyle = '#0e1622';
  rr(ctx, -33, 138, 30, 13, 6); ctx.fill();
  rr(ctx, 6, 138, 30, 13, 6); ctx.fill();

  // torso / outfit
  const bodyGrad = ctx.createLinearGradient(0, 10, 0, 120);
  bodyGrad.addColorStop(0, shade(outfit, 22));
  bodyGrad.addColorStop(1, shade(outfit, -28));
  ctx.fillStyle = bodyGrad;
  ctx.beginPath();
  ctx.moveTo(-52, 40);
  ctx.quadraticCurveTo(-58, 90, -44, 130);
  ctx.quadraticCurveTo(0, 142, 44, 130);
  ctx.quadraticCurveTo(58, 90, 52, 40);
  ctx.quadraticCurveTo(20, 22, 0, 22);
  ctx.quadraticCurveTo(-20, 22, -52, 40);
  ctx.closePath();
  ctx.fill();

  // collar
  ctx.fillStyle = 'rgba(255,255,255,.18)';
  ctx.beginPath();
  ctx.moveTo(-20, 30); ctx.quadraticCurveTo(0, 48, 20, 30);
  ctx.quadraticCurveTo(0, 38, -20, 30);
  ctx.fill();

  // arms
  ctx.fillStyle = shade(outfit, -18);
  rr(ctx, -62, 48, 18, 62, 9); ctx.fill();
  rr(ctx, 44, 48, 18, 62, 9); ctx.fill();
  ctx.fillStyle = skin;
  ctx.beginPath(); ctx.arc(-53, 114, 10, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(53, 114, 10, 0, Math.PI * 2); ctx.fill();

  // neck
  ctx.fillStyle = shade(skin, -22);
  rr(ctx, -15, 8, 30, 26, 10); ctx.fill();

  drawHead(ctx, 0, -38, skin, hair, hairStyle, smile, sad, angry, accessory, accent, facing);

  // scarf / chain drawn on chest
  if (accessory === 'scarf') {
    ctx.fillStyle = accent;
    ctx.beginPath();
    ctx.moveTo(-26, 26); ctx.quadraticCurveTo(0, 38, 26, 26);
    ctx.lineTo(30, 40); ctx.quadraticCurveTo(0, 54, -30, 40); ctx.closePath(); ctx.fill();
    ctx.fillStyle = shade(accent, -30);
    ctx.beginPath(); ctx.moveTo(10, 40); ctx.lineTo(22, 74); ctx.lineTo(10, 76); ctx.lineTo(2, 42); ctx.closePath(); ctx.fill();
  }
  if (accessory === 'chain') {
    ctx.strokeStyle = '#e9c46a'; ctx.lineWidth = 3.5;
    ctx.beginPath(); ctx.arc(0, 26, 22, 0.2, Math.PI - 0.2); ctx.stroke();
    ctx.fillStyle = '#ffd166';
    ctx.beginPath(); ctx.arc(0, 48, 4.4, 0, Math.PI * 2); ctx.fill();
  }
  if (accessory === 'watch') {
    ctx.fillStyle = '#d9c2a3'; rr(ctx, 47, 100, 14, 7, 3); ctx.fill();
  }

  if (ring) {
    ctx.strokeStyle = 'rgba(255,180,84,.9)';
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(0, 92, 118, 0, Math.PI * 2); ctx.stroke();
  }
  if (talking) {
    ctx.fillStyle = 'rgba(127,209,185,.9)';
    ctx.beginPath(); ctx.arc(46, -106, 5, 0, Math.PI * 2); ctx.fill();
  }
  ctx.restore();
}

function drawHead(ctx, cx, cy, skin, hair, style, smile, sad, angry, accessory, accent, facing = 1) {
  // head
  ctx.save();
  ctx.translate(cx, cy);
  const grad = ctx.createLinearGradient(0, -44, 0, 48);
  grad.addColorStop(0, shade(skin, 16));
  grad.addColorStop(1, shade(skin, -14));
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.ellipse(0, 0, 40, 46, 0, 0, Math.PI * 2);
  ctx.fill();

  // ears
  ctx.fillStyle = shade(skin, -8);
  ctx.beginPath(); ctx.ellipse(-40, 4, 7, 10, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(40, 4, 7, 10, 0, 0, Math.PI * 2); ctx.fill();
  if (accessory === 'earrings') {
    ctx.fillStyle = '#ffd166';
    ctx.beginPath(); ctx.arc(-40, 14, 4, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(40, 14, 4, 0, Math.PI * 2); ctx.fill();
  }

  // hair back layer
  ctx.fillStyle = hair;
  if (style === 'curly') {
    for (const [x, y, r] of [[-34, -26, 20], [0, -38, 24], [34, -26, 20], [-40, -2, 16], [40, -2, 16]]) {
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    }
  } else if (style === 'braids') {
    ctx.beginPath(); ctx.ellipse(0, -8, 46, 44, 0, Math.PI, 0); ctx.fill();
    ctx.fillStyle = shade(hair, 8);
    rr(ctx, -44, 8, 13, 62, 6); ctx.fill();
    rr(ctx, 31, 8, 13, 62, 6); ctx.fill();
    ctx.fillStyle = '#e9c46a';
    ctx.beginPath(); ctx.arc(-38, 68, 4, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(38, 68, 4, 0, Math.PI * 2); ctx.fill();
  } else if (style === 'locs') {
    ctx.beginPath(); ctx.ellipse(0, -10, 45, 42, 0, Math.PI, 0); ctx.fill();
    for (let i = 0; i < 5; i++) {
      const x = -36 + i * 18;
      ctx.fillStyle = i % 2 ? shade(hair, 10) : hair;
      rr(ctx, x, -18, 9, 60 + (i % 3) * 10, 5); ctx.fill();
    }
  } else if (style === 'ponytail') {
    ctx.beginPath(); ctx.ellipse(0, -12, 43, 38, 0, Math.PI, 0); ctx.fill();
    ctx.beginPath(); ctx.ellipse(52 * facing, 4, 17, 30, -.3 * facing, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = accent;
    rr(ctx, 38 * facing, -14, 10, 8, 4); ctx.fill();
  } else if (style === 'bun') {
    ctx.beginPath(); ctx.ellipse(0, -12, 42, 36, 0, Math.PI, 0); ctx.fill();
    ctx.beginPath(); ctx.arc(0, -54, 19, 0, Math.PI * 2); ctx.fill();
  } else if (style === 'wave') {
    ctx.beginPath(); ctx.ellipse(0, -14, 45, 38, 0, Math.PI, 0); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-44, -8); ctx.quadraticCurveTo(-30, 10, -16, -8);
    ctx.quadraticCurveTo(0, 10, 16, -8); ctx.quadraticCurveTo(30, 10, 44, -8);
    ctx.lineTo(44, -20); ctx.lineTo(-44, -20); ctx.closePath(); ctx.fill();
  } else if (style === 'buzz') {
    ctx.beginPath(); ctx.ellipse(0, -16, 40, 32, 0, Math.PI, 0); ctx.fill();
  } else {
    // short
    ctx.beginPath(); ctx.ellipse(0, -18, 43, 34, 0, Math.PI, 0); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-42, -12); ctx.quadraticCurveTo(-34, 2, -26, -12); ctx.closePath(); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(42, -12); ctx.quadraticCurveTo(34, 2, 26, -12); ctx.closePath(); ctx.fill();
  }

  // eyebrows
  ctx.strokeStyle = shade(hair, -10);
  ctx.lineWidth = 3.4;
  ctx.lineCap = 'round';
  const browY = angry ? -14 : -18;
  ctx.beginPath();
  if (angry) {
    ctx.moveTo(-25, browY - 2); ctx.lineTo(-11, browY + 3);
    ctx.moveTo(25, browY - 2); ctx.lineTo(11, browY + 3);
  } else {
    ctx.moveTo(-25, browY + 1); ctx.quadraticCurveTo(-18, browY - 3, -11, browY + 1);
    ctx.moveTo(25, browY + 1); ctx.quadraticCurveTo(18, browY - 3, 11, browY + 1);
  }
  ctx.stroke();

  // eyes
  const eyeY = -4;
  if (sad) {
    ctx.strokeStyle = '#2a1c14'; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(-17, eyeY, 6, Math.PI * .15, Math.PI * .85); ctx.stroke();
    ctx.beginPath(); ctx.arc(17, eyeY, 6, Math.PI * .15, Math.PI * .85); ctx.stroke();
  } else {
    ctx.fillStyle = '#241a15';
    ctx.beginPath(); ctx.ellipse(-17, eyeY, 5.6, 6.4, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(17, eyeY, 5.6, 6.4, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,.85)';
    ctx.beginPath(); ctx.arc(-15, eyeY - 2, 1.8, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(19, eyeY - 2, 1.8, 0, Math.PI * 2); ctx.fill();
  }

  // nose
  ctx.strokeStyle = shade(skin, -34);
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(0, 2); ctx.quadraticCurveTo(4, 9, -1, 11); ctx.stroke();

  // mouth
  ctx.strokeStyle = '#7c4a3a';
  ctx.lineWidth = 2.8;
  ctx.beginPath();
  if (smile) {
    ctx.arc(0, 16, 10, Math.PI * .15, Math.PI * .85);
  } else if (sad) {
    ctx.arc(0, 28, 9, Math.PI * 1.15, Math.PI * 1.85);
  } else {
    ctx.moveTo(-7, 20); ctx.quadraticCurveTo(0, 23, 7, 20);
  }
  ctx.stroke();

  // accessories on face
  if (accessory === 'glasses') {
    ctx.strokeStyle = 'rgba(30,40,54,.9)';
    ctx.lineWidth = 2.6;
    ctx.beginPath(); ctx.arc(-17, -4, 12, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(17, -4, 12, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-5, -4); ctx.lineTo(5, -4); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-29, -6); ctx.lineTo(-38, -10); ctx.moveTo(29, -6); ctx.lineTo(38, -10); ctx.stroke();
    ctx.fillStyle = 'rgba(180,220,255,.08)';
    ctx.beginPath(); ctx.arc(-17, -4, 11, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(17, -4, 11, 0, Math.PI * 2); ctx.fill();
  }
  if (accessory === 'cap') {
    ctx.fillStyle = accent;
    ctx.beginPath(); ctx.ellipse(0, -34, 42, 24, 0, Math.PI, 0); ctx.fill();
    ctx.beginPath(); ctx.ellipse(26 * facing, -24, 28, 8, 0, 0, Math.PI * 2); ctx.fill();
  }
  if (accessory === 'headband') {
    ctx.strokeStyle = accent;
    ctx.lineWidth = 7;
    ctx.beginPath(); ctx.arc(0, -6, 40, Math.PI * 1.12, Math.PI * 1.88); ctx.stroke();
  }
  ctx.restore();
}

/* cached avatar images for DOM use */
export function avatarUrl(look = {}, size = 96, mode = 'bust', mood = 'steady') {
  const key = `${size}:${mode}:${mood}:${JSON.stringify(look)}`;
  if (avatarCache.has(key)) return avatarCache.get(key);
  const canvas = document.createElement('canvas');
  canvas.width = size; canvas.height = size;
  const ctx = canvas.getContext('2d');
  drawAvatar(ctx, look, size, size, { mode, mood });
  const url = canvas.toDataURL('image/png');
  avatarCache.set(key, url);
  return url;
}

/* ---------------------------------------------------------------- world sprites */
export function drawSprite(ctx, npc, t, opts = {}) {
  const look = npc.look || {};
  const x = npc.x, y = npc.y;
  const walking = npc.status === 'walking';
  const bob = walking ? Math.sin(t * 9 + hashStr(npc.id) % 10) * 2.5 : Math.sin(t * 2 + hashStr(npc.id) % 7) * 1.1;
  const s = (look.height || 1) * 0.92;
  const skin = look.skin || '#d9a066';
  const hair = look.hair || '#241a15';
  const outfit = look.outfit || '#e0663b';
  const style = look.hairStyle || 'short';

  const facing = npc.facing === -1 ? -1 : 1;
  ctx.save();
  ctx.translate(x, y + bob * .35);
  ctx.scale(s * (opts.scale || 1), s * (opts.scale || 1));

  // shadow stays on the ground while the body bobs
  ctx.save();
  ctx.translate(0, -bob * .35);
  ctx.fillStyle = 'rgba(0,0,0,.34)';
  ctx.beginPath(); ctx.ellipse(0, 0, walking ? 16 : 15, 5.5, 0, 0, Math.PI * 2); ctx.fill();
  ctx.restore();

  // walking pivots from the feet, leaning into the direction of travel
  if (walking) ctx.rotate(facing * 0.035);

  // legs
  ctx.fillStyle = '#1a2534';
  const legSwing = walking ? Math.sin(t * 9 + hashStr(npc.id)) * 5 : 0;
  rr(ctx, -7, -16, 6, 16 + legSwing, 3); ctx.fill();
  rr(ctx, 1, -16, 6, 16 - legSwing, 3); ctx.fill();

  // body
  const g = ctx.createLinearGradient(0, -40, 0, -12);
  g.addColorStop(0, shade(outfit, 16));
  g.addColorStop(1, shade(outfit, -22));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.moveTo(-11, -38);
  ctx.quadraticCurveTo(-14, -24, -10, -13);
  ctx.quadraticCurveTo(0, -9, 10, -13);
  ctx.quadraticCurveTo(14, -24, 11, -38);
  ctx.quadraticCurveTo(0, -43, -11, -38);
  ctx.closePath(); ctx.fill();

  // arms
  ctx.fillStyle = shade(outfit, -14);
  const armSwing = walking ? Math.sin(t * 9 + 2 + hashStr(npc.id)) * 3 : 0;
  rr(ctx, -15, -35, 5, 20 + armSwing, 2.5); ctx.fill();
  rr(ctx, 10, -35, 5, 20 - armSwing, 2.5); ctx.fill();

  // head
  if (facing === -1) ctx.scale(-1, 1);
  ctx.fillStyle = skin;
  ctx.beginPath(); ctx.arc(0, -46 + bob, 11, 0, Math.PI * 2); ctx.fill();

  // hair
  ctx.fillStyle = hair;
  if (style === 'curly') {
    for (const [hx, hy, hr] of [[-8, -52, 6], [0, -56, 7], [8, -52, 6]]) {
      ctx.beginPath(); ctx.arc(hx, hy + bob, hr, 0, Math.PI * 2); ctx.fill();
    }
  } else if (style === 'bun') {
    ctx.beginPath(); ctx.arc(0, -55 + bob, 8, Math.PI, 0); ctx.fill();
    ctx.beginPath(); ctx.arc(0, -60 + bob, 4.5, 0, Math.PI * 2); ctx.fill();
  } else if (style === 'braids' || style === 'locs') {
    ctx.beginPath(); ctx.arc(0, -50 + bob, 11, Math.PI, 0); ctx.fill();
    ctx.fillStyle = shade(hair, 10);
    rr(ctx, -10, -48 + bob, 3.4, 16, 1.6); ctx.fill();
    rr(ctx, 6.6, -48 + bob, 3.4, 16, 1.6); ctx.fill();
  } else if (style === 'cap') {
    ctx.beginPath(); ctx.arc(0, -50 + bob, 11.5, Math.PI, 0); ctx.fill();
  } else {
    ctx.beginPath(); ctx.arc(0, -50 + bob, 11, Math.PI * 1.02, -0.02); ctx.fill();
    rr(ctx, -11, -52 + bob, 22, 5, 2); ctx.fill();
  }

  // face dots
  ctx.fillStyle = '#20150f';
  ctx.beginPath(); ctx.arc(-4, -45 + bob, 1.3, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(4, -45 + bob, 1.3, 0, Math.PI * 2); ctx.fill();

  // accessory hint
  if (look.accessory === 'cap') {
    ctx.fillStyle = look.accent || '#f2c14e';
    ctx.beginPath(); ctx.arc(0, -53 + bob, 10.5, Math.PI, 0); ctx.fill();
    ctx.beginPath(); ctx.ellipse(7, -51 + bob, 8, 2.4, 0, 0, Math.PI * 2); ctx.fill();
  }
  if (look.accessory === 'glasses') {
    ctx.strokeStyle = 'rgba(20,30,42,.9)'; ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.arc(-4, -45 + bob, 3.4, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(4, -45 + bob, 3.4, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(-0.6, -45 + bob); ctx.lineTo(0.6, -45 + bob); ctx.stroke();
  }

  // player ring
  if (npc.isPlayer) {
    ctx.strokeStyle = 'rgba(255,180,84,.85)';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 4]);
    ctx.lineDashOffset = -t * 18;
    ctx.beginPath(); ctx.ellipse(0, 0, 20, 8, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.restore();

  // nameplate (not scaled, stays readable)
  drawNameplate(ctx, npc, x, y, t, opts);
}

function drawNameplate(ctx, npc, x, y, t, opts) {
  const zoom = opts.zoom || 1;
  const fs = Math.max(10, 12 / Math.min(1.5, Math.max(.8, zoom)));
  ctx.save();
  ctx.font = `600 ${fs}px Inter, system-ui, sans-serif`;
  const label = npc.isPlayer ? `${npc.name} (you)` : npc.first;
  const w = ctx.measureText(label).width + 22;
  const h = fs + 12;
  let ty = y - 78 * (npc.look?.height || 1) * (opts.scale || 1);
  // Two residents can occupy almost the same pixel (crowded venue, walking
  // past each other). Stacked nameplates become unreadable, so lift a label
  // until it clears the ones already drawn this frame.
  const taken = opts.labels;
  if (taken) {
    for (let guard = 0; guard < 5; guard++) {
      const r = { x: x - w / 2 - 2, y: ty - h - 2, w: w + 4, h: h + 4 };
      const hit = taken.some(o => r.x < o.x + o.w && r.x + r.w > o.x && r.y < o.y + o.h && r.y + r.h > o.y);
      if (!hit) { taken.push(r); break; }
      ty -= h + 3;
    }
  }
  ctx.globalAlpha = opts.dim ? 0.55 : 1;
  const important = npc.isPlayer || npc.spotlight;
  ctx.fillStyle = important ? 'rgba(9,16,27,.82)' : 'rgba(9,16,27,.6)';
  rr(ctx, x - w / 2, ty - h, w, h, 8);
  ctx.fill();
  if (npc.isPlayer) {
    ctx.strokeStyle = 'rgba(255,180,84,.6)';
    ctx.lineWidth = 1;
    ctx.stroke();
  }
  // mood dot
  const moodColor = npc.mood === 'irritated' || npc.mood === 'stressed' ? '#ff7a59'
    : npc.mood === 'buzzing' || npc.mood === 'cheerful' || npc.mood === 'excited' ? '#7fd1b9'
    : npc.mood === 'low' ? '#8d9bb5' : '#ffb454';
  ctx.fillStyle = moodColor;
  ctx.beginPath(); ctx.arc(x - w / 2 + 8, ty - h / 2, 2.6, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = npc.isPlayer ? '#ffd08a' : (important ? '#eaf1f8' : 'rgba(234,241,248,.8)');
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(label, x + 4, ty - h / 2 + .5);
  // activity glyph
  if (npc.status === 'sleeping') {
    ctx.font = `700 ${fs}px Inter, sans-serif`;
    ctx.fillStyle = '#9fb0c6';
    ctx.fillText('z z', x + w / 2 + 12, ty - h / 2 + Math.sin(t * 2) * 2);
  }
  ctx.restore();
}

/* ---------------------------------------------------------------- static world */
export function buildStaticWorld(world) {
  const W = 1900, H = 1300;
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const rand = mulberry(90210);

  // ground base
  const ground = ctx.createLinearGradient(0, 0, W, H);
  ground.addColorStop(0, '#1c3128');
  ground.addColorStop(.45, '#22392d');
  ground.addColorStop(1, '#182a23');
  ctx.fillStyle = ground;
  ctx.fillRect(0, 0, W, H);

  // grass patches
  for (let i = 0; i < 2600; i++) {
    const x = rand() * W, y = rand() * H;
    const r = 1 + rand() * 3.2;
    ctx.fillStyle = rand() > .5 ? 'rgba(255,255,255,.025)' : 'rgba(0,0,0,.05)';
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  }
  for (let i = 0; i < 140; i++) {
    const x = rand() * W, y = rand() * H;
    ctx.strokeStyle = 'rgba(127,209,185,.06)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + 3, y - 7, x + 1, y - 12); ctx.stroke();
  }

  const loc = Object.fromEntries((world.locations || []).map(l => [l.id, l]));
  const homes = world.homes || [];

  // ---- roads -------------------------------------------------------------
  const roads = [
    [[-40, 640], [260, 640], [640, 625], [1030, 630], [1420, 640], [1720, 650], [1960, 660]],
    [[158, 60], [172, 640], [190, 980], [230, 1260]],
    [[620, 60], [635, 420], [640, 760], [660, 1010], [690, 1260]],
    [[1180, 60], [1165, 420], [1170, 750], [1180, 1010], [1190, 1260]],
    [[1580, 60], [1590, 420], [1610, 760], [1640, 1080], [1660, 1260]],
    [[260, 380], [640, 380], [1180, 390], [1600, 395]],
    [[300, 860], [700, 865], [1170, 860], [1620, 860]],
  ];
  for (const line of roads) {
    // outer edge
    ctx.strokeStyle = 'rgba(9,17,14,.5)';
    ctx.lineWidth = 66;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    line.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    ctx.stroke();
    // surface
    ctx.strokeStyle = '#6f6350';
    ctx.lineWidth = 56;
    ctx.beginPath();
    line.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    ctx.stroke();
    // inner highlight
    ctx.strokeStyle = 'rgba(190,170,138,.16)';
    ctx.lineWidth = 44;
    ctx.beginPath();
    line.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    ctx.stroke();
    // dashes
    ctx.strokeStyle = 'rgba(230,215,185,.22)';
    ctx.lineWidth = 2;
    ctx.setLineDash([12, 22]);
    ctx.beginPath();
    line.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // sidewalks around venues
  for (const l of Object.values(loc)) {
    ctx.fillStyle = 'rgba(205,190,160,.10)';
    rr(ctx, l.x - 18, l.y - 18, l.w + 36, l.h + 36, 22); ctx.fill();
  }

  // ---- plaza / park ground ----------------------------------------------
  if (loc.square) {
    const s = loc.square;
    ctx.fillStyle = '#8b7f68';
    rr(ctx, s.x, s.y, s.w, s.h, 30); ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,.07)';
    for (let i = 0; i < 6; i++) {
      ctx.beginPath(); ctx.arc(s.x + s.w / 2, s.y + s.h / 2, 26 + i * 16, 0, Math.PI * 2); ctx.stroke();
    }
  }
  if (loc.park) {
    const p = loc.park;
    ctx.fillStyle = '#2c4a35';
    rr(ctx, p.x, p.y, p.w, p.h, 34); ctx.fill();
    ctx.fillStyle = '#6c9a67';
    ctx.beginPath(); ctx.ellipse(p.x + p.w * .35, p.y + p.h * .62, 54, 26, -.3, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#7fb3ff';
    ctx.beginPath(); ctx.ellipse(p.x + p.w * .68, p.y + p.h * .7, 42, 22, .2, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,.14)';
    ctx.beginPath(); ctx.ellipse(p.x + p.w * .66, p.y + p.h * .68, 20, 8, .2, 0, Math.PI * 2); ctx.fill();
  }

  // ---- trees -------------------------------------------------------------
  const rects = Object.values(loc).map(l => ({ x: l.x - 24, y: l.y - 24, w: l.w + 48, h: l.h + 48 }))
    .concat(homes.map(h => ({ x: h.x - 18, y: h.y - 30, w: 128, h: 120 })));
  const inside = (x, y, pad = 0) => rects.some(r => x > r.x - pad && x < r.x + r.w + pad && y > r.y - pad && y < r.y + r.h + pad);
  const trees = [];
  let attempts = 0;
  while (trees.length < 74 && attempts < 900) {
    attempts++;
    const x = 40 + rand() * (W - 80), y = 90 + rand() * (H - 160);
    if (inside(x, y, 8)) continue;
    if (roads.some(line => line.some(([rx, ry]) => Math.hypot(rx - x, ry - y) < 70))) continue;
    if (trees.some(t => Math.hypot(t.x - x, t.y - y) < 58)) continue;
    trees.push({ x, y, r: 16 + rand() * 16, hue: rand() });
  }
  for (const t of trees) {
    // shadow
    ctx.fillStyle = 'rgba(0,0,0,.22)';
    ctx.beginPath(); ctx.ellipse(t.x + 6, t.y + 12, t.r * 1.2, t.r * .5, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#3a2a1c';
    rr(ctx, t.x - 3.5, t.y, 7, t.r * .9, 3); ctx.fill();
    const c1 = t.hue > .5 ? '#2f5e42' : '#376b4a';
    const c2 = t.hue > .5 ? '#4f8a63' : '#58956b';
    ctx.fillStyle = c1;
    ctx.beginPath(); ctx.arc(t.x, t.y - t.r * .25, t.r, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = c2;
    ctx.beginPath(); ctx.arc(t.x - t.r * .34, t.y - t.r * .5, t.r * .62, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(t.x + t.r * .4, t.y - t.r * .42, t.r * .5, 0, Math.PI * 2); ctx.fill();
  }

  // ---- buildings ---------------------------------------------------------
  const drawBuilding = (l) => {
    const { x, y, w, h } = l;
    // shadow
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,.34)';
    ctx.filter = 'blur(10px)';
    rr(ctx, x + 8, y + h - 6, w, 26, 16); ctx.fill();
    ctx.restore();

    const base = l.color || '#b9673d';
    // main volume
    const grad = ctx.createLinearGradient(x, y, x + w, y + h);
    grad.addColorStop(0, shade(base, 26));
    grad.addColorStop(.6, base);
    grad.addColorStop(1, shade(base, -30));
    ctx.fillStyle = grad;
    rr(ctx, x, y, w, h, 12); ctx.fill();
    // roof band
    ctx.fillStyle = 'rgba(255,255,255,.13)';
    rr(ctx, x, y, w, 16, 12); ctx.fill();
    ctx.fillStyle = 'rgba(0,0,0,.12)';
    rr(ctx, x, y + h - 14, w, 14, 12); ctx.fill();

    // storefront windows
    const winY = y + h * .44;
    ctx.fillStyle = 'rgba(255,214,145,.28)';
    const cols = Math.max(2, Math.floor(w / 72));
    const ww = (w - 36) / cols - 10;
    for (let i = 0; i < cols; i++) {
      rr(ctx, x + 18 + i * (ww + 10), winY, ww, h * .34, 6); ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,.18)';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    // door
    ctx.fillStyle = 'rgba(20,16,12,.5)';
    rr(ctx, x + w / 2 - 13, y + h - 34, 26, 34, 6); ctx.fill();
    ctx.fillStyle = 'rgba(255,214,145,.35)';
    rr(ctx, x + w / 2 - 9, y + h - 30, 18, 16, 4); ctx.fill();

    // kind-specific decorations
    if (l.kind === 'cafe') {
      // awning
      const stripes = Math.floor(w / 26);
      for (let i = 0; i < stripes; i++) {
        ctx.fillStyle = i % 2 ? '#f4e6d2' : '#c4543c';
        ctx.beginPath();
        ctx.moveTo(x + 6 + i * (w - 12) / stripes, y + 18);
        ctx.lineTo(x + 6 + (i + 1) * (w - 12) / stripes, y + 18);
        ctx.lineTo(x + 2 + (i + .5) * (w - 12) / stripes, y + 44);
        ctx.closePath(); ctx.fill();
      }
      // cup sign
      ctx.fillStyle = '#f4e6d2';
      ctx.beginPath(); ctx.arc(x + w - 30, y + h - 26, 12, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '#8a5a3b'; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(x + w - 24, y + h - 28, 5, -.8, .8); ctx.stroke();
    }
    if (l.kind === 'cinema') {
      ctx.fillStyle = '#1a1024';
      rr(ctx, x + 14, y + 22, w - 28, 26, 8); ctx.fill();
      for (let i = 0; i < 9; i++) {
        ctx.fillStyle = i % 2 ? '#ffd166' : '#fff3c4';
        ctx.beginPath(); ctx.arc(x + 28 + i * (w - 56) / 8, y + 35, 2.4, 0, Math.PI * 2); ctx.fill();
      }
    }
    if (l.kind === 'gym') {
      ctx.strokeStyle = 'rgba(255,255,255,.16)'; ctx.lineWidth = 2;
      for (let i = 0; i < 5; i++) {
        ctx.beginPath(); ctx.moveTo(x + 10, y + 30 + i * 12); ctx.lineTo(x + w - 10, y + 30 + i * 12); ctx.stroke();
      }
    }
    if (l.kind === 'studio') {
      ctx.fillStyle = 'rgba(127,209,185,.3)';
      for (let i = 0; i < 4; i++) {
        ctx.beginPath();
        ctx.arc(x + w * .3, y + h * .66, 12 + i * 9, -0.6, 0.6);
        ctx.lineWidth = 4;
        ctx.strokeStyle = `rgba(127,209,185,${.5 - i * .1})`;
        ctx.stroke();
      }
    }
    if (l.kind === 'market') {
      for (let i = 0; i < 3; i++) {
        const sx = x + 16 + i * (w - 32) / 3;
        ctx.fillStyle = i % 2 ? '#e3a13c' : '#d97c4a';
        ctx.beginPath();
        ctx.moveTo(sx, y + 44);
        ctx.lineTo(sx + (w - 32) / 3 - 6, y + 44);
        ctx.lineTo(sx + (w - 32) / 3 - 14, y + 62);
        ctx.lineTo(sx + 8, y + 62);
        ctx.closePath(); ctx.fill();
      }
    }
    if (l.kind === 'salon') {
      ctx.fillStyle = 'rgba(255,255,255,.18)';
      ctx.beginPath(); ctx.arc(x + 30, y + 34, 9, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(x + w - 30, y + 34, 9, 0, Math.PI * 2); ctx.fill();
    }
    if (l.kind === 'shop') {
      ctx.fillStyle = 'rgba(255,255,255,.12)';
      rr(ctx, x + 16, y + 24, w - 32, 10, 5); ctx.fill();
    }

    // sign
    const label = l.name;
    ctx.font = '700 15px Inter, system-ui, sans-serif';
    const tw = ctx.measureText(label).width + 26;
    const sx = x + w / 2 - tw / 2;
    const sy = y - 16;
    ctx.fillStyle = 'rgba(9,16,27,.9)';
    rr(ctx, sx, sy, tw, 28, 9); ctx.fill();
    ctx.strokeStyle = 'rgba(255,180,84,.35)';
    ctx.lineWidth = 1.2; ctx.stroke();
    ctx.fillStyle = '#f0e6d6';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, x + w / 2, sy + 14.5);

    // open/closed dot
    ctx.fillStyle = 'rgba(127,209,185,.9)';
    ctx.beginPath(); ctx.arc(sx + 9, sy + 14, 2.6, 0, Math.PI * 2); ctx.fill();
  };
  for (const l of Object.values(loc)) {
    if (l.kind === 'park') continue;
    drawBuilding(l);
  }

  // ---- park features -----------------------------------------------------
  if (loc.park) {
    const p = loc.park;
    // bench
    ctx.fillStyle = '#6b4b2f';
    rr(ctx, p.x + p.w * .18, p.y + p.h * .8, 54, 8, 4); ctx.fill();
    ctx.fillStyle = '#4e3622';
    rr(ctx, p.x + p.w * .18 + 6, p.y + p.h * .8 + 8, 6, 12, 3); ctx.fill();
    rr(ctx, p.x + p.w * .18 + 42, p.y + p.h * .8 + 8, 6, 12, 3); ctx.fill();
    // swing frame
    const swx = p.x + p.w * .72, swy = p.y + p.h * .3;
    ctx.strokeStyle = '#8a6b4a'; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.moveTo(swx - 34, swy + 42); ctx.lineTo(swx, swy); ctx.lineTo(swx + 34, swy + 42); ctx.stroke();
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(swx - 16, swy + 6); ctx.lineTo(swx - 16, swy + 34); ctx.moveTo(swx + 16, swy + 6); ctx.lineTo(swx + 16, swy + 34); ctx.stroke();
    ctx.fillStyle = '#c9902f';
    rr(ctx, swx - 24, swy + 34, 18, 5, 2); ctx.fill();
    rr(ctx, swx + 8, swy + 34, 18, 5, 2); ctx.fill();
  }

  // ---- homes -------------------------------------------------------------
  for (const [i, h] of homes.entries()) {
    const { x, y, color } = h;
    const w = 92, hh = 74;
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,.3)';
    ctx.filter = 'blur(8px)';
    rr(ctx, x + 6, y + hh - 8, w, 20, 10); ctx.fill();
    ctx.restore();
    // walls
    const g = ctx.createLinearGradient(x, y, x, y + hh);
    g.addColorStop(0, shade(color, 24));
    g.addColorStop(1, shade(color, -22));
    ctx.fillStyle = g;
    rr(ctx, x, y + 20, w, hh - 20, 8); ctx.fill();
    // roof
    ctx.fillStyle = shade(color, -42);
    ctx.beginPath();
    ctx.moveTo(x - 8, y + 24);
    ctx.lineTo(x + w / 2, y - 8);
    ctx.lineTo(x + w + 8, y + 24);
    ctx.closePath(); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,.09)';
    ctx.beginPath();
    ctx.moveTo(x - 8, y + 24);
    ctx.lineTo(x + w / 2, y - 8);
    ctx.lineTo(x + w / 2, y + 2);
    ctx.lineTo(x + 2, y + 24);
    ctx.closePath(); ctx.fill();
    // chimney
    ctx.fillStyle = shade(color, -50);
    rr(ctx, x + w - 26, y - 6, 10, 18, 2); ctx.fill();
    // door
    ctx.fillStyle = '#2b1c12';
    rr(ctx, x + w / 2 - 10, y + hh - 26, 20, 26, 4); ctx.fill();
    // windows
    ctx.fillStyle = 'rgba(255,214,145,.55)';
    rr(ctx, x + 12, y + 40, 18, 16, 3); ctx.fill();
    rr(ctx, x + w - 30, y + 40, 18, 16, 3); ctx.fill();
    ctx.strokeStyle = 'rgba(30,20,12,.4)'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(x + 21, y + 40); ctx.lineTo(x + 21, y + 56); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x + w - 21, y + 40); ctx.lineTo(x + w - 21, y + 56); ctx.stroke();
    // house number
    ctx.fillStyle = 'rgba(255,255,255,.55)';
    ctx.font = '700 9px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(String(i + 1), x + w / 2, y + hh - 30);
  }

  // ---- street lamps ------------------------------------------------------
  const lamps = [[300, 610], [900, 600], [1330, 610], [1750, 620], [640, 900], [1180, 900], [210, 300], [1620, 300]];
  for (const [lx, ly] of lamps) {
    ctx.fillStyle = '#2a2f36';
    rr(ctx, lx - 2, ly - 34, 4, 34, 2); ctx.fill();
    ctx.fillStyle = '#3a4149';
    rr(ctx, lx - 8, ly - 40, 16, 8, 4); ctx.fill();
    ctx.fillStyle = 'rgba(255,205,120,.35)';
    ctx.beginPath(); ctx.arc(lx, ly - 32, 14, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(255,235,180,.9)';
    ctx.beginPath(); ctx.arc(lx, ly - 32, 4, 0, Math.PI * 2); ctx.fill();
  }

  // ---- flower beds / props ------------------------------------------------
  for (let i = 0; i < 26; i++) {
    const x = 60 + rand() * (W - 120), y = 100 + rand() * (H - 200);
    if (inside(x, y, 24)) continue;
    const petals = ['#ffb454', '#ff7a59', '#b7a4ff', '#f2c14e', '#7fd1b9'];
    ctx.fillStyle = petals[Math.floor(rand() * petals.length)];
    for (let p = 0; p < 4; p++) {
      const a = p / 4 * Math.PI * 2;
      ctx.beginPath(); ctx.arc(x + Math.cos(a) * 3.4, y + Math.sin(a) * 3.4, 2.6, 0, Math.PI * 2); ctx.fill();
    }
    ctx.fillStyle = '#ffe9a8';
    ctx.beginPath(); ctx.arc(x, y, 1.8, 0, Math.PI * 2); ctx.fill();
  }

  return canvas;
}
