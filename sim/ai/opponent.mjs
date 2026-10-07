// T045-T047: the opponent policy `decomp-ai` — the game's own trainer AI driving p2 in a live
// Showdown battle. Wiring only; the ported logic is in choose.mjs (moves), switch.mjs (switching
// and post-KO replacement) and items.mjs (Full Restore, PickCommand order).
//
// Per battle (state kept in a WeakMap keyed by the Showdown Battle):
//   - adapter over the live battle (adapter.mjs), game party order = trainer party order
//     (side.pokemon sorted by platsimSlot, set by team.mjs fixupSide);
//   - the AI RNG stream (choose.mjs AIRng, seeded from battle.prngSeed);
//   - AI_CONTEXT persistent memory: battlerMoves / battlerAbilities / battlerHeldItems
//     (ai_context.h:27-29), trainerItems / trainerItemCounts (InitAI);
//   - engine state the adapter does not expose, rebuilt from the Showdown log (see processLog):
//     battleCtx->moveHit[4] / moveHitBattler[4] and battleCtx->speedRand[4].
//
// Decision flow for a 'move' request (battle_controller_player.c:312-460 command selection):
//   1. Battler_CanPickCommand (battle_lib.c:6224-6236) false (recharge / thrash / uproar / locked)
//      -> no AI runs; Showdown's forced move is sent. Showdown's getLockedMove() decides here.
//   2. TrainerAI_PickCommand (TAI:3989): ShouldSwitch -> party; ShouldUseItem -> item; else fight.
//   3. FIGHT: all moves invalid (STRUGGLING_ALL) -> Struggle; Encore -> the encored move; else
//      TrainerAI_Main (choose.mjs). No AI move choice runs under Encore or Struggle.
// For a 'switch' request (post-KO replacement or U-turn): BattleAI_SwitchedSlot (6) ->
// BattleAI_PostKOSwitchIn -> party-menu fallback (battle_display.c:4543-4557).
//
// Quick Claw / speedRand. battleCtx->speedRand[b] (battle_context.h:293) is drawn for all four
// battlers by BattleContext_InitCounters at battle start (battle_lib.c:2024) and again in the
// pre-move phase of every turn (PRE_MOVE_ACTION_STATE_SPEED_RNG, battle_controller_player.c:853-856),
// i.e. after both sides chose their commands. The AI's speed compare (op 36, Quick Claw check
// battle_lib.c:1279) therefore reads the values drawn before the previous turn's moves (or at battle
// start on turn 1). Here: 4 draws from the AI stream when the state is created, then 4 more in
// afterTurn() after every turn in which p2 had a 'move' request (= a turn that reached the pre-move
// phase). Showdown's real Quick Claw activation uses its own PRNG; only the AI's estimate uses these.
//
// Showdown divergences that cannot be expressed are counted in st.stats (never silent):
//   invalidChoice  the AI picked a slot Showdown refuses (e.g. a 0-score tie that includes a
//                  taunted/0-PP move: the game would select it and fail); the enabled move with the
//                  highest score (lowest slot on ties) is sent instead.
//   trappedSwitch  ShouldSwitch said switch but Showdown's request says trapped; FIGHT is used.
//   lockMismatch   the game's Battler_CanPickCommand and Showdown's lock disagree.
import { createAdapter } from './adapter.mjs';
import { AIRng, aiProgram, aiSeedFromBattleSeed, checkInvalidMoves, newKnowledge, speedValuesNow, thinkingMaskOf, trainerAIMain } from './choose.mjs';
import { replacementSlot } from './switch.mjs';
import { initTrainerItems, pickCommand } from './items.mjs';
import { FULL_RESTORE_MOVE } from './patches.mjs';

export const DECOMP_AI = 'decomp-ai';
const NO_SLOT = 6;
const BATTLER_NONE = 0xff; // include/constants/battle.h:99
const toID = (s) => String(s ?? '').toLowerCase().replace(/[^a-z0-9]/g, '');

const states = new WeakMap();

// Process-wide totals of st.stats (for the 200-gauntlet run and reports).
export const AGGREGATE = {};
function bump(st, k) {
  st.stats[k]++;
  AGGREGATE[k] = (AGGREGATE[k] ?? 0) + 1;
}

/**
 * Creates the AI state for `battle`. opts: { trainer (trainers.json entry: ai_flags, bag_items),
 * aiSide ('p2'), rng (AIRng; default seeded from battle.prngSeed) }.
 */
export function createAIState(battle, { trainer, aiSide = 'p2', rng } = {}) {
  const order = (side) => {
    const mons = side.pokemon.slice();
    if (mons.every((p) => Number.isInteger(p.platsimSlot))) mons.sort((a, b) => a.platsimSlot - b.platsimSlot);
    return mons;
  };
  const partyOrder = { p1: order(battle.p1), p2: order(battle.p2) };
  const st = {
    battle, aiSide,
    prog: aiProgram(),
    rng: rng ?? new AIRng(aiSeedFromBattleSeed(battle.prngSeed)),
    knowledge: newKnowledge(),
    speedRand: [0, 0, 0, 0], // u16 battleCtx->speedRand[4]
    moveHit: [0, 0, 0, 0], // u16 battleCtx->moveHit[4]
    moveHitBattler: [BATTLER_NONE, BATTLER_NONE, BATTLER_NONE, BATTLER_NONE],
    aiSwitchedPartySlot: [NO_SLOT, NO_SLOT, NO_SLOT, NO_SLOT],
    logIndex: 0, splitSkip: 0,
    pendingPreMove: false,
    frMon: null,
    stats: { decisions: 0, moves: 0, switches: 0, replacements: 0, items: 0, locked: 0, struggle: 0, encore: 0,
      invalidChoice: 0, trappedSwitch: 0, lockMismatch: 0 },
    last: null,
  };
  st.ai = createAdapter(battle, { aiSide, partyOrder, speedRand: (b) => st.speedRand[b] });
  st.thinkingMask = thinkingMaskOf(st.prog, trainer.ai_flags);
  st.items = initTrainerItems(st.ai, trainer.bag_items);
  // BattleContext_InitCounters (battle_lib.c:2018-2025): speedRand for battlers 0..3 at battle start.
  for (let i = 0; i < 4; i++) st.speedRand[i] = st.rng.next();
  return st;
}

export function stateFor(battle) { return states.get(battle); }

// ---------------------------------------------------------------------------------------------
// Showdown log -> AI memory and engine fields
//
// Mapping (UNVERIFIED against the cartridge, OPCODES.md trap 5):
//   |switch| / |drag| / |faint|  -> BattleAI_ClearKnown{Moves,Ability,Item} and moveHit := NONE
//       (switch-in init battle_lib.c:2121-2122, 2151-2153; CleanupFaintedMon :2199-2200, 2223-2225)
//   |move|A|M|T  (attack message shown) -> moveHit[T] = M, moveHitBattler[T] = A when T is the other
//       battler (UpdateFlagsWhenHit, battle_controller_player.c:4495-4502); then MoveEnd's ClearFlags
//       sets moveHit[A] = NONE (:4389)
//   |cant|A, and the AI's own Full Restore (an item action, also ending in MOVE_END) -> moveHit[A] = NONE
//   |-ability|X|Ab, "ability: Ab" in a line -> BattleAI_SetAbility (BattleMessage_AbilityTag,
//       battle_script.c:11795-11807; UpdateMonData BATTLEMON_ABILITY :3073-3075, 3402-3404)
//   |-item|X|It, "[from] item: It" -> BattleAI_SetHeldItem (BattleMessage_ItemTag :11726-11743)
//   |-enditem|X|It -> item announced and gone: BattleMon_CopyToParty clears it (battle_lib.c:1819-1823)
//   The owner of a "[from] ..." effect is the "[of]" Pokemon when present, else the line's subject.
export function processLog(st) {
  const log = st.battle.log;
  const { ai } = st;
  const K = st.knowledge;
  const who = (ident) => {
    const m = /^(p[12])[a-d]?(?::|$)/.exec(ident ?? '');
    if (!m) return -1;
    return m[1] === st.aiSide ? 1 : 0;
  };
  const clear = (b) => {
    K.battlerMoves[b] = [0, 0, 0, 0];
    K.battlerAbilities[b] = 0;
    K.battlerHeldItems[b] = 0;
    st.moveHit[b] = 0;
    st.moveHitBattler[b] = BATTLER_NONE;
  };
  const setAbility = (b, name) => { if (b >= 0) K.battlerAbilities[b] = ai.map.ability(toID(name)) & 0xff; };
  const setItem = (b, name) => { if (b >= 0) K.battlerHeldItems[b] = ai.map.item(toID(name)) & 0xffff; };
  for (; st.logIndex < log.length; st.logIndex++) {
    const line = log[st.logIndex];
    if (st.splitSkip === 1) { st.splitSkip = 2; } else if (st.splitSkip === 2) { st.splitSkip = 0; continue; }
    const parts = line.split('|');
    const type = parts[1];
    if (type === 'split') { st.splitSkip = 1; continue; }
    const from = parts.find((p) => p.startsWith('[from] '))?.slice(7);
    const of = parts.find((p) => p.startsWith('[of] '))?.slice(5);
    const subject = who(parts[2]);
    switch (type) {
      case 'switch': case 'drag': case 'faint':
        if (subject >= 0) clear(subject);
        continue;
      case 'move': {
        const target = who(parts[4]);
        const move = ai.map.move(toID(parts[3]));
        if (target >= 0 && target !== subject) {
          st.moveHit[target] = move;
          st.moveHitBattler[target] = subject;
        }
        if (subject >= 0) st.moveHit[subject] = 0;
        break;
      }
      case 'cant':
        if (subject >= 0) st.moveHit[subject] = 0;
        break;
      case '-ability':
        setAbility(subject, parts[3]);
        continue; // its own [from] (e.g. Trace) belongs to the subject, already recorded
      case '-item':
        setItem(subject, parts[3]);
        break;
      case '-enditem':
        if (subject >= 0) K.battlerHeldItems[subject] = 0;
        break;
      default:
        break;
    }
    // Generic "[from] ability: X" / "[from] item: X" / "|-activate|X|ability: Y".
    const owner = of ? who(of) : subject;
    if (from?.startsWith('ability: ')) setAbility(owner, from.slice(9));
    if (type === '-activate' && parts[3]?.startsWith('ability: ')) setAbility(subject, parts[3].slice(9));
    if (from?.startsWith('item: ') && type !== '-item' && type !== '-enditem') {
      const item = from.slice(6);
      if (item === 'Full Restore' && type === '-heal' && !of) {
        if (subject >= 0) st.moveHit[subject] = 0; // the AI's item action ended (MOVE_END)
      } else {
        setItem(owner, item);
      }
    }
  }
}

// ---------------------------------------------------------------------------------------------
// Decisions

function partyMon(st, side, gameSlot) {
  const mons = side.pokemon.slice();
  if (mons.every((p) => Number.isInteger(p.platsimSlot))) return mons.find((p) => p.platsimSlot === gameSlot);
  return st.ai.party(1)[gameSlot].pokemon;
}
function switchChoice(st, side, gameSlot) {
  const mon = partyMon(st, side, gameSlot);
  const idx = side.pokemon.indexOf(mon);
  if (!mon || idx < 0 || mon.fainted || mon.isActive) return null;
  return `switch ${idx + 1}`;
}

function injectFullRestore(battle, mon) {
  const move = battle.dex.moves.get(FULL_RESTORE_MOVE);
  mon.moveSlots.push({ move: move.name, id: move.id, pp: move.pp, maxpp: move.pp, target: move.target,
    disabled: false, used: false, virtual: true });
  return `move ${mon.moveSlots.length}`;
}

/**
 * One decision for the AI side's current request. Returns { choice, kind, detail }.
 * opts.trace: forwarded to trainerAIMain.
 */
export function decide(st, side, opts = {}) {
  const { ai } = st;
  processLog(st);
  bump(st, 'decisions');
  const mon = side.active[0];
  st.aiSwitchedPartySlot = [NO_SLOT, NO_SLOT, NO_SLOT, NO_SLOT]; // BattleContext_Init (battle_lib.c:2015)
  if (side.requestState === 'switch') {
    const trace = opts.trace ? [] : null;
    const slot = replacementSlot(st, 1, trace);
    bump(st, 'replacements');
    const choice = switchChoice(st, side, slot);
    if (!choice) throw new Error(`decomp-ai: post-KO replacement slot ${slot} is not a legal Showdown switch`);
    return (st.last = { choice, kind: 'replacement', detail: { slot, trace } });
  }
  if (side.requestState !== 'move') return (st.last = { choice: 'default', kind: 'other', detail: { requestState: side.requestState } });

  st.pendingPreMove = true;
  // 1. Battler_CanPickCommand (battle_lib.c:6224-6236)
  const K = (n) => ai.constants.get(n);
  const lockMask = K('VOLATILE_CONDITION_RECHARGING') | K('VOLATILE_CONDITION_THRASH') | K('VOLATILE_CONDITION_UPROAR') | K('VOLATILE_CONDITION_MOVE_LOCKED');
  const gameLocked = (ai.statusVolatile(1) & lockMask) !== 0;
  const sdLocked = !!mon.getLockedMove();
  if (gameLocked !== sdLocked) { bump(st, 'lockMismatch'); if (process.env.PLATSIM_AI_DEBUG) process.stderr.write(`lockMismatch game=${gameLocked} sd=${mon.getLockedMove()} vols=${Object.keys(mon.volatiles)}\n`); }
  if (sdLocked) {
    bump(st, 'locked');
    return (st.last = { choice: 'move 1', kind: 'locked', detail: { move: mon.getLockedMove() } });
  }

  // 2. TrainerAI_PickCommand
  st.monSpeedValues = speedValuesNow(ai);
  st.mem = { monSpeedValues: st.monSpeedValues };
  const cmd = pickCommand(st, 1);
  const request = mon.getMoveRequestData();
  if (cmd.command === 'party') {
    const choice = request.trapped ? null : switchChoice(st, side, cmd.slot);
    if (choice) {
      bump(st, 'switches');
      return (st.last = { choice, kind: 'switch', detail: { slot: cmd.slot } });
    }
    bump(st, 'trappedSwitch');
  } else if (cmd.command === 'item') {
    bump(st, 'items');
    st.frMon = mon;
    const choice = injectFullRestore(st.battle, mon);
    return (st.last = { choice, kind: 'item', detail: cmd.itemUse });
  }

  // 3. FIGHT (battle_controller_player.c:419-445)
  const sdMoves = request.moves;
  const enabled = (i) => sdMoves[i] && !sdMoves[i].disabled;
  const firstEnabled = () => { for (let i = 0; i < sdMoves.length; i++) if (enabled(i)) return i; return 0; };
  const STRUGGLING_ALL = 0xf; // include/constants/battle.h:137
  if ((checkInvalidMoves(ai, 1, 0, ~0) & STRUGGLING_ALL) === STRUGGLING_ALL) {
    bump(st, 'struggle');
    // Showdown offers a single Struggle entry when it agrees; otherwise count the disagreement.
    if (!enabled(0)) bump(st, 'invalidChoice');
    return (st.last = { choice: `move ${(enabled(0) ? 0 : firstEnabled()) + 1}`, kind: 'struggle', detail: {} });
  }
  const med = ai.moveEffectsData(1);
  if (med.encoredMove) {
    bump(st, 'encore');
    let slot = ai.moves(1).indexOf(med.encoredMove);
    if (slot < 0 || !enabled(slot)) { bump(st, 'invalidChoice'); slot = firstEnabled(); }
    return (st.last = { choice: `move ${slot + 1}`, kind: 'encore', detail: { slot } });
  }
  const res = trainerAIMain(st, 1, { trace: opts.trace });
  let slot = res.slot;
  if (!enabled(slot)) {
    bump(st, 'invalidChoice');
    let best = -1;
    for (let i = 0; i < 4; i++) if (enabled(i) && (best < 0 || res.scores[i] > res.scores[best])) best = i;
    slot = best;
  }
  bump(st, 'moves');
  return (st.last = { choice: `move ${slot + 1}`, kind: 'move', detail: { ...res, mem: undefined, chosen: slot } });
}

// After makeChoices: remove the pseudo-move slot; draw the pre-move speedRand values.
export function afterTurn(st) {
  if (st.frMon) {
    st.frMon.moveSlots = st.frMon.moveSlots.filter((s) => s.id !== FULL_RESTORE_MOVE);
    st.frMon = null;
  }
  if (st.pendingPreMove) {
    for (let i = 0; i < 4; i++) st.speedRand[i] = st.rng.next();
    st.pendingPreMove = false;
  }
}

export const decompAI = {
  name: DECOMP_AI,
  choose(ctx) {
    let st = states.get(ctx.battle);
    if (!st) {
      st = createAIState(ctx.battle, { trainer: ctx.trainer, aiSide: ctx.side.id });
      states.set(ctx.battle, st);
    }
    const r = decide(st, ctx.side);
    if (r.kind === 'item' && Array.isArray(ctx.bag)) {
      // keep the gauntlet's view of the bag in step with trainerItems
      const left = st.items.trainerItems.filter((x) => x).map((id) => ai_itemName(st, id));
      ctx.bag.length = 0;
      ctx.bag.push(...left);
    }
    return r.choice;
  },
  afterTurn(ctx) {
    const st = states.get(ctx.battle);
    if (st) afterTurn(st);
  },
};

function ai_itemName(st, id) {
  return st.ai.constants.nameOf('items', id) ?? `ITEM_${id}`;
}
