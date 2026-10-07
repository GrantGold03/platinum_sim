// T034: Build / trainer party -> Showdown sets.
// - Stats: Showdown's own stats for the converted mons (captured before team.mjs overwrites
//   them) and the JS port both equal the Python reference platsim.decomp.stats.calc_stats (port
//   of Pokemon_CalcStats, pokeplatinum/src/pokemon.c:564), which is called here through
//   `.venv/bin/python -c` with the base stats read by platsim.decomp.species (not the JSON).
// - PP: Dark Pulse has base PP 15 (pokeplatinum/res/moves/dark_pulse/data.json:14); Cynthia's
//   Spiritomb knows it (pokeplatinum/res/trainers/data/champion_cynthia.json:18,23). Showdown
//   would give 24 (3 PP Ups, pokemon-showdown/sim/pokemon.ts:361).
// - Id mapping covers every League mon and every generated species/move; unmapped items are
//   reported (printed) and must have no in-battle hold effect Showdown models.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { REPO_ROOT, loadGameData } from '../gamedata.mjs';
import { calcStats } from '../exp.mjs';
import { mappingReport, newBattle, opponentMembers, playerMember } from '../team.mjs';

const gd = loadGameData();
const PY = join(REPO_ROOT, '.venv', 'bin', 'python');
const PY_CODE = `
import json, sys
from platsim.decomp.species import load_species
from platsim.decomp.stats import calc_stats
sp = load_species()
out = []
for q in json.load(sys.stdin):
    s = sp[q["key"]]
    out.append(calc_stats(s.base_stats, q["ivs"], q["evs"], q["level"], q["nature"],
                          species="SPECIES_" + s.key.upper() if s.form is None else None))
print(json.dumps(out))
`;
function pythonStats(queries) {
  const r = spawnSync(PY, ['-c', PY_CODE], { input: JSON.stringify(queries), encoding: 'utf8', cwd: REPO_ROOT });
  assert.equal(r.status, 0, r.stderr);
  return JSON.parse(r.stdout);
}

const SEED = 'sodium,' + '0'.repeat(31) + '3';
const stat6 = (v) => ({ hp: v, atk: v, def: v, spa: v, spd: v, spe: v });
const builds = [
  { species: 'garchomp', start_level: 50, moves: ['earthquake', 'dragon_claw'], ability: 'ABILITY_SAND_VEIL', nature: 'Hardy' },
  { species: 'garchomp', start_level: 73, moves: ['earthquake'], ability: 'ABILITY_SAND_VEIL', nature: 'NATURE_ADAMANT' },
  { species: 'spiritomb', start_level: 58, moves: ['dark_pulse', 'shadow_ball'], ability: 'ABILITY_PRESSURE', nature: 'Hardy' },
  { species: 'shedinja', start_level: 40, moves: ['shadow_sneak'], ability: 'ABILITY_WONDER_GUARD', nature: 'NATURE_TIMID' },
  { species: 'rotom_wash', start_level: 45, moves: ['hydro_pump'], ability: 'ABILITY_LEVITATE', nature: 'NATURE_MODEST',
    ivs: { hp: 31, atk: 0, def: 7, spa: 20, spd: 3, spe: 12 }, evs: { hp: 4, atk: 0, def: 252, spa: 252, spd: 0, spe: 0 } },
  { species: 'lucario', start_level: 1, moves: ['quick_attack'], ability: 'ABILITY_STEADFAST', nature: 'NATURE_BRAVE' },
];

test('player builds: Showdown stats == JS port == Python calc_stats', () => {
  const party = builds.map((b, i) => playerMember(gd, b, i));
  const battle = newBattle(gd, { seed: SEED, player: party, opponent: opponentMembers(gd, gd.trainers[4]) });
  const py = pythonStats(party.map((m) => ({ key: m.rec.key, ivs: m.ivs, evs: m.evs, level: m.level, nature: m.nature })));
  battle.p1.pokemon.forEach((p) => {
    const m = party[p.platsimSlot];
    const want = py[p.platsimSlot];
    assert.deepEqual(calcStats(gd, m.rec, m.ivs, m.evs, m.level, m.nature), want, `JS port ${m.rec.key}`);
    assert.deepEqual(p.platsimShowdownStats, want, `Showdown native ${m.rec.key} L${m.level}`);
    assert.equal(p.maxhp, want.hp);
  });
});

test('every League opponent: Showdown stats == Python calc_stats; IV 30, EV 0', () => {
  for (const t of gd.trainers) {
    const opp = opponentMembers(gd, t);
    const battle = newBattle(gd, { seed: SEED, player: [playerMember(gd, builds[0], 0)], opponent: opp });
    // trainer_data.c IV = iv_scale*31/255; all League files use iv_scale 250 -> 30 (trainers.json)
    for (const m of opp) assert.deepEqual(m.ivs, stat6(30));
    for (const m of opp) assert.deepEqual(m.evs, stat6(0));
    const py = pythonStats(opp.map((m) => ({ key: m.rec.key, ivs: m.ivs, evs: m.evs, level: m.level, nature: m.nature })));
    battle.p2.pokemon.forEach((p) => {
      assert.deepEqual(p.platsimShowdownStats, py[p.platsimSlot], `${t.key} ${p.platsimRec.key}`);
      assert.equal(p.maxhp, py[p.platsimSlot].hp);
    });
  }
});

test('opponent nature/ability/gender come from trainers.json personality', () => {
  const cyn = gd.trainers.find((t) => t.key === 'champion_cynthia');
  const battle = newBattle(gd, { seed: SEED, player: [playerMember(gd, builds[0], 0)], opponent: opponentMembers(gd, cyn) });
  battle.p2.pokemon.forEach((p, i) => {
    const mon = cyn.party[i];
    assert.equal('NATURE_' + p.set.nature.toUpperCase(), mon.nature);
    assert.equal(p.baseAbility, gd.sdAbility.get(mon.ability));
  });
  // Spiritomb: GENDER_RATIO_FEMALE_50 (127) > (personality & 0xff)? -> F, else M
  const spi = cyn.party[0];
  const want = gd.constants.gender_ratios[gd.species.spiritomb.gender_ratio] > (spi.personality & 0xff) ? 'F' : 'M';
  assert.equal(battle.p2.pokemon[0].gender, want);
});

test('Dark Pulse has base PP 15 on Cynthia\'s Spiritomb and on a player build (no PP Ups)', () => {
  assert.equal(gd.moves.dark_pulse.pp, 15);
  const cyn = gd.trainers.find((t) => t.key === 'champion_cynthia');
  const party = [playerMember(gd, builds[2], 0)];
  const battle = newBattle(gd, { seed: SEED, player: party, opponent: opponentMembers(gd, cyn) });
  const spiritomb = battle.p2.pokemon.find((p) => p.platsimRec.key === 'spiritomb');
  const slot = spiritomb.moveSlots.find((s) => s.id === 'darkpulse');
  assert.equal(slot.maxpp, 15);
  assert.equal(slot.pp, 15);
  const mine = battle.p1.pokemon[0].moveSlots.find((s) => s.id === 'darkpulse');
  assert.deepEqual([mine.pp, mine.maxpp], [15, 15]);
  // positive control: without the reset Showdown builds 24 (15 * 8/5)
  assert.equal(battle.dex.moves.get('darkpulse').pp * 8 / 5, 24);
  // PP is spent from the reset value
  battle.makeChoices('move 1', 'default');
  assert.equal(battle.p1.pokemon.find((p) => p.platsimSlot === 0).baseMoveSlots[0].pp <= 14, true);
});

test('carried PP from start_state is applied', () => {
  const m = playerMember(gd, builds[2], 0, { pp: [3, 9] });
  const battle = newBattle(gd, { seed: SEED, player: [m], opponent: opponentMembers(gd, gd.trainers[0]) });
  assert.deepEqual(battle.p1.pokemon[0].moveSlots.map((s) => [s.pp, s.maxpp]), [[3, 15], [9, 15]]);
});

test('id mapping: every League mon and every species/move/ability maps; unmapped items listed', () => {
  const r = mappingReport(gd);
  console.log(JSON.stringify({
    league_unmapped: r.league_unmapped, unmapped_species: r.unmapped.species, unmapped_moves: r.unmapped.moves,
    unmapped_abilities: r.unmapped.abilities, unmapped_items_total: r.unmapped.items.length,
    unmapped_items_with_hold_effect: r.unmapped_items_with_hold_effect, renamed_moves: r.renamed_moves,
    num_mismatch: r.num_mismatch,
  }));
  assert.deepEqual(r.league_unmapped, []);
  assert.deepEqual(r.unmapped.species, []);
  assert.deepEqual(r.unmapped.moves, []);
  assert.deepEqual(r.unmapped.abilities, []);
  assert.equal(gd.sdSpecies.size, Object.keys(gd.species).length);
  // Held items Showdown does not have: only effects outside battle or handled by sim/exp.mjs.
  const allowed = new Set(['HOLD_EFFECT_MONEY_UP', 'HOLD_EFFECT_ENCOUNTERS_DOWN', 'HOLD_EFFECT_NO_EVOLVE',
    'HOLD_EFFECT_EXP_SHARE', 'HOLD_EFFECT_EXP_UP', 'HOLD_EFFECT_FLEE', 'HOLD_EFFECT_FRIENDSHIP_UP']);
  for (const e of r.unmapped_items_with_hold_effect) assert.ok(allowed.has(e.split(':')[1]), e);
  // positive control: a known item does map
  assert.equal(gd.sdItem.get('sitrus_berry'), 'sitrusberry');
});
