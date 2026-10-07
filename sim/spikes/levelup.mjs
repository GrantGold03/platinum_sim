// T009: can a Showdown Pokemon level up mid-battle with stats recomputed?
// Same seed run twice: (A) p1 lead stays level 50; (B) after turn 1 the lead becomes level 70.
// Pass criteria:
//   1. After the change, B's lead has exactly the stats of a freshly built level-70 copy.
//   2. Current HP rose by exactly the max-HP increase (game behaviour, battle_script.c ~:9822).
//   3. The battles diverge after the change (later damage uses the new stats).
import { Battle } from '../showdown.mjs';
import { loadTrainerTeam, seedFor } from './common.mjs';

const cynthia = loadTrainerTeam('champion_cynthia');
const lead = { ...cynthia[5], level: 50 }; // Garchomp
const p1Team = [lead, ...cynthia.slice(0, 5).map((m) => ({ ...m, level: 50 }))];

function setLevel(battle, pokemon, newLevel) {
  const oldMax = pokemon.maxhp;
  pokemon.level = newLevel;
  pokemon.set.level = newLevel;
  const stats = battle.spreadModify(pokemon.species.baseStats, pokemon.set);
  pokemon.baseStoredStats = stats;
  for (const s of ['atk', 'def', 'spa', 'spd', 'spe']) pokemon.storedStats[s] = stats[s];
  pokemon.baseMaxhp = stats.hp;
  pokemon.maxhp = stats.hp;
  if (pokemon.hp > 0) pokemon.hp += stats.hp - oldMax;
  return { oldMax, newMax: stats.hp };
}

function run(change) {
  const battle = new Battle({
    formatid: 'gen4customgame', seed: seedFor(42),
    p1: { name: 'P', team: p1Team }, p2: { name: 'C', team: cynthia },
  });
  battle.makeChoices('move 1', 'move 1'); // turn 1
  const mon = battle.p1.active[0];
  const before = { hp: mon.hp, maxhp: mon.maxhp };
  const result = change ? setLevel(battle, mon, 70) : null;
  const after = { hp: mon.hp, maxhp: mon.maxhp, stats: { ...mon.storedStats } };
  battle.makeChoices('move 2', 'move 1'); // turn 2
  const foeHpAfterT2 = battle.p2.active[0].hp;
  return { before, after, result, foeHpAfterT2, log: battle.log.slice(-30).join('\n') };
}

const A = run(false);
const B = run(true);

const fresh = new Battle({
  formatid: 'gen4customgame', seed: seedFor(42),
  p1: { name: 'P', team: [{ ...lead, level: 70 }] }, p2: { name: 'C', team: [cynthia[0]] },
}).p1.pokemon[0];

const statsMatch = ['atk', 'def', 'spa', 'spd', 'spe'].every((s) => B.after.stats[s] === fresh.storedStats[s])
  && B.after.maxhp === fresh.maxhp;
const hpRule = B.after.hp - B.before.hp === B.result.newMax - B.result.oldMax;
const diverged = A.foeHpAfterT2 !== B.foeHpAfterT2;

console.log(JSON.stringify({
  A_lead_after_t1: A.after, B_lead_after_change: B.after, fresh_level70: { maxhp: fresh.maxhp, stats: fresh.storedStats },
  B_hp_before_change: B.before, foeHp_after_t2: { A: A.foeHpAfterT2, B: B.foeHpAfterT2 },
  checks: { statsMatchFreshLevel70: statsMatch, hpRaisedByMaxHpDelta: hpRule, laterDamageDiffers: diverged },
}, null, 1));
process.exit(statsMatch && hpRule && diverged ? 0 : 1);
