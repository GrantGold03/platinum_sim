// T047: runtime patches to Showdown's gen4 Dex data for the opponent's Full Restore
// (research R5 "Spike results"). Nothing under pokemon-showdown/ is edited: these functions
// mutate Dex.mod('gen4').data in memory and are applied by sim/gamedata.mjs prepareDex(), i.e.
// before the first Dex.*.get() (Showdown caches got objects; research R4).
//
// Game behaviour being reproduced. A trainer's bag item is an action of its own, not a move:
// BattleControllerPlayer_ItemCommand (battle_controller_player.c:1903-1968) runs
// subscript_use_full_restore.s (status := NONE, confusion off) then subscript_use_potion.s (HP
// restore, no Heal Block check), and then goes to MOVE_END. No move is executed, so no PP is used,
// movePrevByBattler / Encore / Disable / Mirror Move / Copycat state is untouched, and none of the
// "before move" checks (sleep, freeze, paralysis, confusion, attraction, Taunt, flinch) can stop it.
//
// Showdown has no bag-item action, so the opponent selects the project pseudo-move
// `trainerfullrestore` (registered by gamedata.mjs, priority 7). The pseudo-move's work is done
// in `beforeTurnCallback`, which Showdown runs as a 'beforeTurnMove' action at the start of the
// turn (pokemon-showdown/sim/battle-queue.ts:205-211, sim/battle.ts:2734-2741) without any
// BeforeMove event; the callback then removes the pseudo-move's own 'move' action from the queue
// (BattleQueue.cancelMove, sim/battle-queue.ts:345-353), so runMove never runs for it:
//   - no BeforeMove handlers (Taunt, sleep, freeze, paralysis, confusion, attract, flinch, Truant),
//   - no OverrideAction (Encore), no PP deduction (Pressure), no moveUsed()/lastMove (Encore,
//     Disable, Mirror Move, Copycat, Torment, Choice lock), no battle.lastMove (Copycat),
//   - the foe's Sucker Punch sees no queued move and fails, as in the game where
//     Battler_SelectedMove of an item user is MOVE_NONE (battle_script.c:7385-7400, battle_lib.c:2858).
//   - Heal Block: sethp() is not a heal event, and the game's potion subscript has no Heal Block check.
// The pseudo-move's onHit is replaced by a throw: if Showdown ever ran it as a move, that is a bug.
//
// Belt and braces (the request-time checks): Taunt and Encore disable moves through
// onDisableMove when Showdown builds a request. The pseudo-move slot is added after that, but the
// two conditions are still patched so the slot can never be disabled or overridden by them.
export const FULL_RESTORE_MOVE = 'trainerfullrestore'; // must equal gamedata.mjs FULL_RESTORE_MOVE

const PATCHED = Symbol.for('platsim.aiDexPatched');

function reenableFullRestore(pokemon) {
  for (const s of pokemon.moveSlots) {
    if (s.id === FULL_RESTORE_MOVE && s.disabled) {
      s.disabled = false;
      s.disabledSource = '';
    }
  }
}

export function applyAiDexPatches(data) {
  if (data[PATCHED]) return data[PATCHED];
  const applied = [];

  const fr = data.Moves[FULL_RESTORE_MOVE];
  if (!fr) throw new Error(`patches: ${FULL_RESTORE_MOVE} must be registered before applyAiDexPatches`);
  fr.beforeTurnCallback = function fullRestoreBeforeTurn(pokemon) {
    this.queue.cancelMove(pokemon);
    // subscript_use_full_restore.s: BATTLEMON_STATUS := MON_CONDITION_NONE, confusion off;
    // subscript_use_potion.s: restore HP (Full Restore restores all of it).
    pokemon.cureStatus();
    pokemon.removeVolatile('confusion');
    pokemon.sethp(pokemon.maxhp);
    this.add('-heal', pokemon, pokemon.getHealth, '[from] item: Full Restore');
  };
  fr.onHit = function fullRestoreOnHit() {
    throw new Error('trainerfullrestore ran as a move; its beforeTurnCallback should have cancelled it');
  };
  applied.push('trainerfullrestore: beforeTurnCallback + cancelMove');

  // Taunt (pokemon-showdown/data/mods/gen4/moves.ts:1397-1425)
  const taunt = data.Moves.taunt?.condition;
  if (!taunt?.onDisableMove || !taunt?.onBeforeMove) throw new Error('patches: gen4 Taunt condition shape changed');
  const tauntDisable = taunt.onDisableMove;
  taunt.onDisableMove = function (pokemon) {
    tauntDisable.call(this, pokemon);
    reenableFullRestore(pokemon);
  };
  const tauntBefore = taunt.onBeforeMove;
  taunt.onBeforeMove = function (attacker, defender, move) {
    if (move.id === FULL_RESTORE_MOVE) return;
    return tauntBefore.call(this, attacker, defender, move);
  };
  applied.push('taunt: trainerfullrestore exempt');

  // Encore (pokemon-showdown/data/mods/gen4/moves.ts encore.condition)
  const encore = data.Moves.encore?.condition;
  if (!encore?.onDisableMove || !encore?.onOverrideAction) throw new Error('patches: gen4 Encore condition shape changed');
  const encoreDisable = encore.onDisableMove;
  encore.onDisableMove = function (pokemon) {
    encoreDisable.call(this, pokemon);
    reenableFullRestore(pokemon);
  };
  const encoreOverride = encore.onOverrideAction;
  encore.onOverrideAction = function (pokemon, target, move) {
    if (move.id === FULL_RESTORE_MOVE) return;
    return encoreOverride.call(this, pokemon, target, move);
  };
  applied.push('encore: trainerfullrestore exempt');

  Object.defineProperty(data, PATCHED, { value: applied, enumerable: false });
  return applied;
}
