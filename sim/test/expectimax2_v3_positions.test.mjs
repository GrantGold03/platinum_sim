// 007 T029 (SC-008): positive-control positions for status-move categories expectimax2 newly models.
// For each: a position where the reference player chooses the move and v2 does not, and a matching
// position where the move does not help and the reference does not choose it.
// Categories with no such position at the 2-ply reference are recorded as findings in
// specs/007-status-moves-items/validation-log.md (T029), not asserted here.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PLAYER_POLICIES } from '../gauntlet.mjs';
import { makeExpectimax2, V3_REF_OPTS } from '../policy/expectimax2.mjs';
import { B, gd, leagueBattle, sendIn } from './ai_fixtures.mjs';

const v2 = PLAYER_POLICIES.get('expectimax2-v2');
const ref = PLAYER_POLICIES.get('expectimax2-v3-ref');
// The 2-ply reference does not see a hazard's payoff; the hazard leaf term does (research R4.4).
const refHazards = makeExpectimax2('expectimax2-v3-ref', { ...V3_REF_OPTS, leafHazards: true });

function position(builds, { foeSlot = null, myHp = null, live } = {}) {
  const { battle, trainer, p1, p2 } = leagueBattle('champion_cynthia', builds);
  if (foeSlot !== null) sendIn(battle, p2, foeSlot);
  if (myHp !== null) p1.active[0].hp = Math.max(1, Math.floor(p1.active[0].maxhp * myHp));
  if (live) live(battle);
  battle.makeRequest();
  return { gd, battle, side: p1, request: p1.activeRequest, trainer };
}
const chosen = (pol, mk) => {
  const ctx = mk();
  const c = pol.choose(ctx);
  return c.startsWith('move') ? ctx.side.active[0].moveSlots[Number(c.split(' ')[1]) - 1].id : c;
};

const TORTERRA = [B('torterra', 58, ['leech_seed', 'body_slam', 'protect', 'synthesis'], 'ABILITY_OVERGROW')];
test('Leech Seed: chosen against Spiritomb (Body Slam cannot touch it); not against Grass-type Roserade', () => {
  const help = () => position(TORTERRA);
  assert.equal(chosen(ref, help), 'leechseed');
  assert.notEqual(chosen(v2, help), 'leechseed');
  assert.notEqual(chosen(ref, () => position(TORTERRA, { foeSlot: 1 })), 'leechseed');
});

const GENGAR = [B('gengar', 60, ['confuse_ray', 'shadow_ball', 'thunderbolt', 'focus_blast'], 'ABILITY_LEVITATE')];
test('Confuse Ray: chosen against a healthy Garchomp; not against one already confused', () => {
  const help = () => position(GENGAR, { foeSlot: 5 });
  assert.equal(chosen(ref, help), 'confuseray');
  assert.notEqual(chosen(v2, help), 'confuseray');
  const confused = () => position(GENGAR, { foeSlot: 5, live: (b) => { b.sides[1].active[0].volatiles.confusion = { id: 'confusion', duration: 4, time: 4 }; } });
  assert.notEqual(chosen(ref, confused), 'confuseray');
});

const NINJASK = [B('ninjask', 60, ['baton_pass', 'swords_dance', 'substitute', 'x_scissor'], 'ABILITY_SPEED_BOOST'),
  B('scizor', 60, ['bullet_punch', 'x_scissor', 'swords_dance', 'roost'], 'ABILITY_TECHNICIAN')];
test('Baton Pass: chosen to hand +4 Atk / +2 Spe from a 1-HP Ninjask to Scizor; not with no one to pass to', () => {
  const boosted = (b) => { const m = b.sides[0].active[0]; m.boosts.atk = 4; m.boosts.spe = 2; m.hp = 1; };
  const help = () => position(NINJASK, { live: boosted });
  assert.equal(chosen(ref, help), 'batonpass');
  assert.notEqual(chosen(v2, help), 'batonpass');
  // without boosts it still works like a switch to a better matchup, so the no-help case is no bench (it fails)
  assert.notEqual(chosen(ref, () => position(NINJASK.slice(0, 1), { live: boosted })), 'batonpass');
});

const SKARMORY = [B('skarmory', 60, ['spikes', 'stealth_rock', 'peck', 'roost'], 'ABILITY_KEEN_EYE')];
test('hazards (with the hazard leaf term): set against a full bench; not against the last foe', () => {
  const help = () => position(SKARMORY);
  assert.ok(['spikes', 'stealthrock'].includes(chosen(refHazards, help)));
  assert.ok(!['spikes', 'stealthrock'].includes(chosen(v2, help)));
  const last = () => position(SKARMORY, { foeSlot: 5, live: (b) => { for (const p of b.sides[1].pokemon) if (p !== b.sides[1].active[0]) p.hp = 0; } });
  assert.ok(!['spikes', 'stealthrock'].includes(chosen(refHazards, last)));
});
