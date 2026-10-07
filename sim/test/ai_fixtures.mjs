// Shared fixtures for the trainer-AI tests (T048). Not a test file (no .test.mjs suffix).
// Builds real League battles (data/generated/trainers.json via team.mjs) and an AI state whose RNG
// is a scripted stub, so every random draw in a fixture is known and can be walked through by hand.
import { loadGameData } from '../gamedata.mjs';
import { newBattle, opponentMembers, playerMember } from '../team.mjs';
import { createAIState } from '../ai/opponent.mjs';

export const gd = loadGameData();

export const B = (species, level, moves, ability, held_item = null, extra = {}) =>
  ({ species, start_level: level, moves, ability, held_item, nature: 'Hardy', ...extra });

export function trainerByKey(key) {
  const t = gd.trainers.find((x) => x.key === key);
  if (!t) throw new Error(`no trainer ${key}`);
  return t;
}

/**
 * Scripted RNG. `values` are returned in order (u16); after they run out, `fill` is returned.
 * `draws` counts calls, like AIRng.
 */
export function stubRng(values = [], fill = 0) {
  const q = [...values];
  return {
    draws: 0,
    next() { this.draws++; return (q.length ? q.shift() : fill) & 0xffff; },
    clone() { throw new Error('stub rng is not clonable'); },
  };
}

/** A real League battle (both sides fixed up by team.mjs) + AI state for p2. */
export function leagueBattle(trainerKey, playerBuilds, { seed = 'sodium,' + '1'.repeat(32), rng = stubRng() } = {}) {
  const trainer = trainerByKey(trainerKey);
  const player = playerBuilds.map((b, i) => playerMember(gd, b, i));
  const opponent = opponentMembers(gd, trainer);
  const battle = newBattle(gd, { seed, player, opponent });
  battle.makeRequest();
  const st = createAIState(battle, { trainer, rng });
  return { battle, trainer, st, p1: battle.sides[0], p2: battle.sides[1] };
}

/** Puts the AI party member with game slot `slot` in as p2's active mon (Showdown switchIn). */
export function sendIn(battle, side, slot) {
  const mon = side.pokemon.find((p) => p.platsimSlot === slot);
  battle.actions.switchIn(mon, 0);
  return mon;
}

export const setHP = (mon, hp) => { mon.hp = hp; };
/** Marks `moveId` as `mon`'s last successful move (battleCtx->movePrevByBattler). */
export function setLastMove(battle, mon, moveId) {
  mon.lastMove = battle.dex.getActiveMove(moveId);
  mon.moveLastTurnResult = true;
}
