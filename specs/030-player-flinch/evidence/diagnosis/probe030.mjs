import { B, gd, leagueBattle } from '/home/grant/Desktop/platinum_sim/sim/test/ai_fixtures.mjs';
import { scoreActions, V4_OPTS, EXPECTIMAX2_V4 } from '/home/grant/Desktop/platinum_sim/sim/policy/expectimax2.mjs';
function pos() {
  const { battle, trainer, p1, p2 } = leagueBattle('champion_cynthia', [
    B('garchomp', 52, ['earthquake', 'dragon_claw', 'rock_slide', 'crunch'], 'ABILITY_SAND_VEIL', 'sitrus_berry'),
    B('infernape', 50, ['fire_blast', 'flamethrower', 'close_combat', 'grass_knot'], 'ABILITY_BLAZE', 'expert_belt'),
    B('staraptor', 50, ['return', 'aerial_ace', 'pluck', 'close_combat'], 'ABILITY_INTIMIDATE', 'sitrus_berry'),
    B('rotom', 50, ['thunderbolt', 'shadow_ball', 'charge_beam', 'thunder_shock'], 'ABILITY_LEVITATE', 'wise_glasses'),
    B('floatzel', 51, ['waterfall', 'ice_punch', 'crunch', 'focus_blast'], 'ABILITY_SWIFT_SWIM', 'sitrus_berry'),
    B('weavile', 53, ['ice_punch', 'night_slash', 'aerial_ace', 'brick_break'], 'ABILITY_PRESSURE', 'icicle_plate'),
  ]);
  battle.makeRequest();
  return { gd, battle, side: p1, request: p1.activeRequest, trainer };
}
for (const [name, opts] of [['flinch off', { ...V4_OPTS, flinch: false }], ['attack', { ...V4_OPTS, flinch: 'attack' }], ['both', V4_OPTS]]) {
  const r = scoreActions(pos(), opts, EXPECTIMAX2_V4);
  const rows = r.acts.map((a, i) => `${a.choice ?? a.kind}${a.id ? '(' + a.id + ')' : ''}:${Number.isFinite(r.scores[i]) ? r.scores[i].toFixed(4) : '-inf'}`);
  console.log(name.padEnd(10), rows.join('  '));
}
