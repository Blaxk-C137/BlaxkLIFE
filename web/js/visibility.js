// Presentation culling, never deletion: off-screen residents keep their lives.
export function residentOpacity(npc, point, player, camera, width, height) {
  if (!point || npc.indoors || npc.status === 'sleeping') return 0;
  const halfW = width / (2 * camera.zoom), halfH = height / (2 * camera.zoom);
  if (Math.abs(point.x - camera.x) > halfW + 80 || Math.abs(point.y - camera.y) > halfH + 100) return 0;
  if (!player) return 1;
  const distance = Math.hypot(point.x - player.x, point.y - player.y);
  // Fade in well ahead of interaction distance, with no camera-centre chasing.
  return Math.max(0, Math.min(1, (580 - distance) / 100));
}
