// T010: opponent Full Restore as an injected pseudo-move.
// Game rule being modelled: TrainerAI_ShouldUseItem (pokeplatinum/src/battle/trainer_ai/trainer_ai.c:4056)
// uses Full Restore when 0 < hp < maxhp/4; item use resolves before moves.
// Cases: (1) basic: heals to full, cures poison, acts before p1's Extreme Speed (+1);
//        (2) under Taunt; (3) under Torment, used on two consecutive turns.
// In the game none of Taunt/Torment can stop a trainer's bag item, so (2) and (3) must succeed.
import { Battle, Dex } from '../showdown.mjs';
import { loadTrainerTeam, seedFor } from './common.mjs';

// Must happen before any Dex.*.get() of this id.
Dex.mod('gen4').data.Moves.trainerfullrestore = {
  num: -1001, name: 'Trainer Full Restore', accuracy: true, basePower: 0, category: 'Status',
  pp: 64, noPPBoosts: true, priority: 7, flags: {}, target: 'self', type: '???',
  onHit(pokemon) {
    pokemon.sethp(pokemon.maxhp);
    pokemon.cureStatus();
    pokemon.removeVolatile('confusion');
    this.add('-heal', pokemon, pokemon.getHealth, '[from] item: Full Restore');
  },
};

const cynthia = loadTrainerTeam('champion_cynthia');
const lucario = cynthia[3]; // has Extreme Speed (slot 2)

function useFullRestore(battle, side) {
  const mon = side.active[0];
  const move = battle.dex.moves.get('trainerfullrestore');
  mon.moveSlots.push({ move: move.name, id: move.id, pp: move.pp, maxpp: move.pp, target: move.target,
    disabled: false, used: false, virtual: true });
  return `move ${mon.moveSlots.length}`;
}
const removePseudo = (mon) => { mon.moveSlots = mon.moveSlots.filter((s) => s.id !== 'trainerfullrestore'); };

function setup(extraP1Moves) {
  const battle = new Battle({
    formatid: 'gen4customgame', seed: seedFor(7),
    p1: { name: 'P', team: [{ ...lucario, moves: extraP1Moves }] },
    p2: { name: 'C', team: [cynthia[4]] }, // Milotic
  });
  return battle;
}

const results = {};

// Case 1: basic.
{
  const b = setup(['extremespeed']);
  const foe = b.p2.active[0];
  foe.sethp(Math.floor(foe.maxhp * 0.2)); foe.setStatus('psn');
  const before = { hp: foe.hp, status: foe.status };
  b.makeChoices('move 1', useFullRestore(b, b.p2));
  removePseudo(foe);
  const lines = b.log.filter((l) => /\|move\||-heal|-damage/.test(l)).slice(-6);
  const healIdx = lines.findIndex((l) => l.includes('Trainer Full Restore'));
  const esIdx = lines.findIndex((l) => l.includes('Extreme Speed'));
  const healedLine = lines.find((l) => l.includes('-heal') && l.includes(`${foe.maxhp}/${foe.maxhp}`));
  results.basic = { before, after: { hp: foe.hp, maxhp: foe.maxhp, status: foe.status },
    healedToFullBeforeBeingHit: !!healedLine,
    actedBeforeExtremeSpeed: healIdx !== -1 && esIdx !== -1 && healIdx < esIdx,
    cured: foe.status === '', lines };
}

// Case 2: under Taunt.
{
  const b = setup(['taunt']);
  b.makeChoices('move 1', 'move 1'); // p1 Taunts Milotic
  const foe = b.p2.active[0];
  foe.sethp(Math.floor(foe.maxhp * 0.2));
  let error = null;
  try { b.makeChoices('move 1', useFullRestore(b, b.p2)); } catch (e) { error = String(e.message).slice(0, 160); }
  removePseudo(foe);
  results.taunt = { tauntActive: !!foe.volatiles.taunt, healedToFull: foe.hp === foe.maxhp, error,
    turnLog: b.log.slice(b.log.lastIndexOf('|turn|2') + 1).filter((l) => !l.startsWith('|split')) };
}

// Case 3: under Torment, two consecutive uses.
{
  const b = setup(['torment']);
  b.makeChoices('move 1', 'move 1');
  const foe = b.p2.active[0];
  const outcomes = [];
  for (let t = 0; t < 2; t++) {
    foe.sethp(Math.floor(foe.maxhp * 0.2));
    let error = null;
    try { b.makeChoices('move 1', useFullRestore(b, b.p2)); } catch (e) { error = String(e.message).slice(0, 160); }
    removePseudo(foe);
    outcomes.push({ healedToFull: foe.hp === foe.maxhp, error });
  }
  results.torment = { tormentActive: !!foe.volatiles.torment, outcomes };
}

console.log(JSON.stringify(results, null, 1));
const ok = results.basic.healedToFullBeforeBeingHit && results.basic.cured
  && results.basic.actedBeforeExtremeSpeed;
process.exit(ok ? 0 : 1);
