// The `gauntlet` op (T035, contracts/worker-protocol.md ops 2 and 4).
//
// Runs the requested trainers in order with one persistent player party state:
//   - between battles HP, status and fainted members are restored (every battle is a fresh
//     Showdown Battle, so this is automatic); PP carries over unless
//     availability.json `pp_restore_between_battles` is true (T026; default false) (FR-012);
//     levels and exp persist; a consumed held item (berry eaten, etc.) stays consumed;
//   - turn limit or draw (Showdown tie) counts as a loss (spec Edge Cases);
//   - `stop_on_loss` (default true) stops at the first loss;
//   - `start_state` {levels, exp, pp, items} overrides the builds' starting values (op 4);
//   - with `log` "summary" or "full", each battle carries `state_before` (start_state shape).
//
// Seeds: battle i of a request uses deriveSeed(request.seed, 0, i) (sim/seeds.mjs), unless the
// request passes `seeds` (one per trainer). Every battle's seed is echoed in the result.
//
// Policies. The decomp trainer AI (T045-T047) and expectimax2-v1 (T050) do not exist yet; the
// player may request `greedy-v1` (T049, sim/policy/greedy.mjs). Both sides default to
// `placeholder-default`, which sends Showdown's `default` choice (first legal move / first legal
// switch). It is NOT the game AI and NOT a player policy; its name is reported in every result
// (`player_policy`, `opponent_policy`) so no result produced with it can be mistaken for a real
// evaluation. Later tasks register real policies with registerPlayerPolicy / registerOpponentPolicy.
//   policy = { name, choose(ctx) -> Showdown choice string, afterTurn?(ctx) }
//   ctx = { gd, battle, side, request, trainer, bag (opponent bag items, mutable), members }
import { createHash } from 'node:crypto';
import { deriveSeed } from './seeds.mjs';
import { ExpTracker } from './exp.mjs';
import { InvalidTeam, P1_NAME, newBattle, opponentMembers, playerMember } from './team.mjs';
import { greedy } from './policy/greedy.mjs';

export const PLACEHOLDER = 'placeholder-default';
const placeholder = { name: PLACEHOLDER, choose: () => 'default' };
export const PLAYER_POLICIES = new Map([[PLACEHOLDER, placeholder]]);
export const OPPONENT_POLICIES = new Map([[PLACEHOLDER, placeholder]]);
export const registerPlayerPolicy = (p) => PLAYER_POLICIES.set(p.name, p);
export const registerOpponentPolicy = (p) => OPPONENT_POLICIES.set(p.name, p);
registerPlayerPolicy(greedy); // `greedy-v1` (T049, sim/policy/greedy.mjs)

export const DEFAULT_TURN_LIMIT = 1000; // Showdown's own hard limit (pokemon-showdown/sim/battle.ts:1843)

export class RequestError extends Error {
  constructor(kind, msg) { super(msg); this.kind = kind; }
}

function findTrainer(gd, name) {
  const n = String(name).toLowerCase();
  const t = gd.trainers.find((x) => x.key === n || x.name.toLowerCase() === n);
  if (!t) throw new RequestError('invalid_team', `unknown trainer ${name}`);
  return t;
}

export const stripTimestamps = (lines) => lines.filter((l) => !l.startsWith('|t:|'));
const hashLog = (lines) => `sha256:${createHash('sha256').update(stripTimestamps(lines).join('\n')).digest('hex')}`;

function snapshot(party) {
  return {
    levels: party.map((m) => m.level),
    exp: party.map((m) => m.exp),
    pp: party.map((m) => [...m.pp]),
    items: party.map((m) => m.itemRec?.key ?? null),
  };
}

// Read PP and held item back from the finished battle into the party state.
function collect(gd, battle, party) {
  for (const p of battle.sides[0].pokemon) {
    const m = party[p.platsimSlot];
    m.pp = p.baseMoveSlots.map((s) => s.pp);
    // A held item Showdown knows that is gone at the end (eaten berry, used Focus Sash, Fling)
    // is consumed. A knocked-off item comes back after the battle in gen 4 (Showdown
    // `itemKnockedOff`). No League mon has Thief/Covet/Trick/Knock Off/Pluck/Bug Bite
    // (trainers.json), so the player cannot lose an item to the opponent.
    const sdItem = m.itemRec ? gd.sdItem.get(m.itemRec.key) : undefined;
    if (sdItem && !p.item && !p.itemKnockedOff) m.itemRec = null;
  }
}

export function runGauntlet(gd, req) {
  const playerPolicy = PLAYER_POLICIES.get(req.player_policy ?? PLACEHOLDER);
  if (!playerPolicy) throw new RequestError('internal', `unknown player_policy ${req.player_policy} (known: ${[...PLAYER_POLICIES.keys()]})`);
  const oppPolicy = OPPONENT_POLICIES.get(req.opponent_policy ?? PLACEHOLDER);
  if (!oppPolicy) throw new RequestError('internal', `unknown opponent_policy ${req.opponent_policy}`);
  if (!Array.isArray(req.team) || req.team.length < 1 || req.team.length > 6) {
    throw new RequestError('invalid_team', `team must have 1-6 members, got ${req.team?.length}`);
  }
  if (typeof req.seed !== 'string' && !Array.isArray(req.seeds)) throw new RequestError('internal', 'seed is required');
  const trainerNames = req.trainers ?? ['aaron', 'bertha', 'flint', 'lucian', 'cynthia'];
  const trainers = trainerNames.map((n) => findTrainer(gd, n));
  const logMode = req.log ?? 'none';
  const stopOnLoss = req.stop_on_loss ?? true;
  const turnLimit = req.turn_limit ?? DEFAULT_TURN_LIMIT;
  const ppRestore = gd.availability?.pp_restore_between_battles === true;

  const ss = req.start_state;
  let party;
  try {
    party = req.team.map((b, i) => playerMember(gd, b, i, ss ? {
      level: ss.levels?.[i], exp: ss.exp?.[i], pp: ss.pp?.[i], item: ss.items ? ss.items[i] : undefined,
    } : {}));
  } catch (e) {
    throw e instanceof InvalidTeam ? new RequestError('invalid_team', e.message) : e;
  }

  const battles = [];
  const expEvents = [];
  const fullLogs = [];
  let cleared = true;
  for (const [i, trainer] of trainers.entries()) {
    if (ppRestore && i > 0) for (const m of party) m.pp = m.moves.map((k) => gd.moves[k].pp);
    const seed = req.seeds?.[i] ?? deriveSeed(req.seed, 0, i);
    const before = snapshot(party);
    const opponent = opponentMembers(gd, trainer);
    const battle = newBattle(gd, { seed, player: party, opponent });
    // The turn-1 requests were built inside the Battle constructor, before fixupSide reset PP
    // (Showdown's 3 PP Ups, carried-over PP). Rebuild them from the live state so a policy that
    // reads `request` (pp, disabled) sees what Showdown will validate against. Found by T049:
    // with carried-over PP 0 the stale request offered a move Showdown then rejected.
    battle.makeRequest();
    new ExpTracker(gd, battle, party, { trainerBattle: true, battleIndex: i, events: expEvents });
    const bag = [...trainer.bag_items];
    const ctxFor = (side) => ({ gd, battle, side, request: side.activeRequest, trainer, bag,
      members: side === battle.sides[0] ? party : opponent });

    let end = null;
    while (!battle.ended) {
      if (battle.turn > turnLimit) { end = 'turn_limit'; break; }
      const [p1, p2] = battle.sides;
      const c1 = p1.requestState ? playerPolicy.choose(ctxFor(p1)) : '';
      const c2 = p2.requestState ? oppPolicy.choose(ctxFor(p2)) : '';
      battle.makeChoices(c1, c2);
      playerPolicy.afterTurn?.(ctxFor(p1));
      oppPolicy.afterTurn?.(ctxFor(p2));
    }
    if (!end) end = battle.winner === P1_NAME ? 'win' : battle.winner ? 'loss' : 'tie';
    const won = end === 'win';
    collect(gd, battle, party);
    const rec = { trainer: trainer.name.toLowerCase(), won, end, turns: battle.turn, seed, log_hash: hashLog(battle.log) };
    if (logMode === 'summary' || logMode === 'full') rec.state_before = before;
    battles.push(rec);
    if (logMode === 'full') fullLogs.push(stripTimestamps(battle.log));
    if (!won) {
      cleared = false;
      if (stopOnLoss) break;
    }
  }
  if (battles.length < trainers.length) cleared = false;

  const final = snapshot(party);
  return {
    cleared,
    battles,
    final_levels: final.levels,
    final_state: final,
    exp_events: expEvents,
    log: logMode === 'full' ? fullLogs : null,
    player_policy: playerPolicy.name,
    opponent_policy: oppPolicy.name,
    pp_restore_between_battles: ppRestore,
    turn_limit: turnLimit,
  };
}
