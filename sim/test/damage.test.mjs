// T037 cross-check: decomp damage-formula port (sim/damage.mjs) vs Showdown's gen4 damage.
//
// For every case we build a real gen4customgame Battle (Showdown), put both battlers in the same
// state, and compare all 16 rolls:
//   - Showdown: battle.actions.getDamage(attacker, defender, activeMove) with move.willCrit fixed
//     and battle.randomizer forced to each multiplier 85..100 (the same tr(tr(d*m)/100) that
//     pokemon-showdown/sim/battle.ts:2395-2398 uses, with random(16) replaced by 100-m).
//   - Port: calcDamage(fromShowdown(...)) — move data from pokeplatinum/res/moves/*/data.json.
// A case either matches exactly, or names a divergence id from damage_divergences.json; for those
// the test asserts the two engines DO differ (so a fixed divergence is noticed) and checks the
// port against hand arithmetic from the decomp where given.
//
// Trainer Pokemon (species/level/moves) are read from pokeplatinum/res/trainers/data/*.json; IVs
// = ivScale * 31 / 255 (pokeplatinum/src/trainer_data.c:214). Abilities/natures are chosen per
// case (legal gen-4 abilities) because the cross-check is about the formula, not the party data.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { Battle } from '../showdown.mjs';
import { calcDamage, fromShowdown, calcBaseDamage, applyTypeChart, TYPE_CHART, moveData, itemData } from '../damage.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const DECOMP = join(here, '../../pokeplatinum');
const DIVERGENCES = JSON.parse(readFileSync(join(here, 'damage_divergences.json'), 'utf8'));
const DIV_IDS = new Set(DIVERGENCES.map((d) => d.id));

const toId = (c) => c.replace(/^(SPECIES|MOVE|ITEM)_/, '').toLowerCase().replace(/[^a-z0-9]/g, '');
function trainerMon(key, idx, ability, extra = {}) {
  const data = JSON.parse(readFileSync(join(DECOMP, 'res/trainers/data', `${key}.json`), 'utf8'));
  const m = data.party[idx];
  const iv = Math.floor((m.iv_scale * 31) / 255); // trainer_data.c:214
  return {
    species: toId(m.species), level: m.level, ability, nature: 'Serious',
    item: m.item === 'ITEM_NONE' ? '' : toId(m.item),
    moves: m.moves.filter((x) => x !== 'MOVE_NONE').map(toId),
    ivs: { hp: iv, atk: iv, def: iv, spa: iv, spd: iv, spe: iv },
    evs: { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 },
    ...extra,
  };
}
const C = (i, ab, x) => trainerMon('champion_cynthia', i, ab, x);
const AARON = (i, ab, x) => trainerMon('elite_four_aaron', i, ab, x);
const BERTHA = (i, ab, x) => trainerMon('elite_four_bertha', i, ab, x);
const FLINT = (i, ab, x) => trainerMon('elite_four_flint', i, ab, x);
const LUCIAN = (i, ab, x) => trainerMon('elite_four_lucian', i, ab, x);
// Player-side mons: realistic level-60ish sets with EVs.
function P(species, level, ability, extra = {}) {
  return {
    species, level, ability, nature: extra.nature ?? 'Adamant', item: extra.item ?? '',
    moves: extra.moves ?? ['tackle'], gender: extra.gender,
    ivs: { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 },
    evs: extra.evs ?? { hp: 4, atk: 252, def: 0, spa: 0, spd: 0, spe: 252 },
  };
}

const tr = (x) => Math.trunc(x);
function run(c) {
  const battle = new Battle({ formatid: 'gen4customgame', seed: 'sodium,' + '0'.repeat(31) + '1',
    p1: { name: 'A', team: [c.att] }, p2: { name: 'D', team: [c.def] } });
  const a = battle.p1.active[0];
  const d = battle.p2.active[0];
  // Neutralise switch-in effects (Intimidate, weather abilities) so the case controls state.
  for (const p of [a, d]) { for (const k in p.boosts) p.boosts[k] = 0; }
  battle.field.clearWeather();
  c.setup?.({ battle, a, d });
  const sd = [];
  for (let m = 85; m <= 100; m++) {
    battle.randomizer = (dmg) => tr(tr(dmg * m) / 100);
    // Same pre-damage steps as useMoveInner (pokemon-showdown/sim/battle-actions.ts:427-439), so
    // move-modifying abilities (Normalize, Scrappy, Mold Breaker) and Unaware see an active move.
    let mv = battle.dex.getActiveMove(c.move);
    battle.setActiveMove(mv, a, d);
    battle.singleEvent('ModifyType', mv, null, a, d, mv, mv);
    battle.singleEvent('ModifyMove', mv, null, a, d, mv, mv);
    mv = battle.runEvent('ModifyType', a, d, mv, mv);
    mv = battle.runEvent('ModifyMove', a, d, mv, mv);
    mv.willCrit = !!c.crit;
    const r = battle.actions.getDamage(a, d, mv, true);
    battle.clearActiveMove();
    sd.push(typeof r === 'number' ? r : 0);
  }
  const input = fromShowdown(battle, a, d, c.move, { crit: !!c.crit, ...(c.portMove ?? {}) });
  const port = calcDamage(input);
  return { sd, port: port.rolls, result: port, input };
}

// ------------------------------------------------------------------------------------------------
const brn = ({ a }) => { a.setStatus('brn', a); };
const weather = (w) => ({ battle }) => battle.field.setWeather(w, 'debug');
const side = (cond) => ({ battle, d }) => d.side.addSideCondition(cond, d);
const boost = (who, stat, n) => (ctx) => { ctx[who].boosts[stat] = n; };
const all = (...fs) => (ctx) => fs.forEach((f) => f(ctx));

const CASES = [
  // --- basic physical / special, STAB, effectiveness ---
  { name: 'Garchomp EQ vs Infernape (STAB, x2)', att: P('garchomp', 62, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake' },
  { name: 'Cynthia Garchomp Dragon Rush vs player Garchomp (x2)', att: C(5, 'Sand Veil'), def: P('garchomp', 60, 'Sand Veil'), move: 'dragonrush' },
  { name: 'Cynthia Garchomp EQ vs Magnezone (x4)', att: C(5, 'Sand Veil'), def: P('magnezone', 58, 'Sturdy'), move: 'earthquake' },
  { name: 'Cynthia Lucario Aura Sphere vs Tyranitar (x4 special)', att: C(3, 'Inner Focus'), def: P('tyranitar', 60, 'Sand Stream'), move: 'aurasphere' },
  { name: 'Cynthia Milotic Ice Beam vs Garchomp (x4)', att: C(4, 'Marvel Scale'), def: P('garchomp', 60, 'Sand Veil'), move: 'icebeam' },
  { name: 'Cynthia Roserade Energy Ball vs Rhyperior Lightningrod (x4)', att: C(1, 'Natural Cure'), def: BERTHA(4, 'Lightningrod'), move: 'energyball' },
  { name: 'Cynthia Garchomp Flamethrower vs Kingdra (x0.25)', att: C(5, 'Sand Veil'), def: P('kingdra', 58, 'Swift Swim'), move: 'flamethrower' },
  { name: 'Aaron Scizor X-Scissor vs Infernape (x0.25)', att: AARON(1, 'Technician'), def: FLINT(3, 'Blaze'), move: 'xscissor' },
  { name: 'Lucario Aura Sphere vs Togekiss (x0.5)', att: C(3, 'Inner Focus'), def: C(2, 'Serene Grace'), move: 'aurasphere' },
  { name: 'Lucario Stone Edge vs Gyarados (x2 non-STAB)', att: C(3, 'Inner Focus'), def: P('gyarados', 60, 'Intimidate'), move: 'stoneedge' },
  { name: 'Milotic Surf vs Snorlax (neutral STAB special)', att: C(4, 'Marvel Scale'), def: P('snorlax', 60, 'Immunity'), move: 'surf' },
  { name: 'Spiritomb Shadow Ball vs Alakazam (x2 STAB)', att: C(0, 'Pressure'), def: LUCIAN(3, 'Synchronize'), move: 'shadowball' },
  { name: 'Garchomp Giga Impact vs Lucario (x0.5 STAB)', att: C(5, 'Sand Veil'), def: C(3, 'Inner Focus'), move: 'gigaimpact' },
  { name: 'Togekiss Air Slash vs Lucario (x2 then x0.5 in table order)', att: C(2, 'Serene Grace'), def: C(3, 'Inner Focus'), move: 'airslash' },
  { name: 'Garchomp Flamethrower vs Ludicolo (x0.5 then x2 in table order)', att: C(5, 'Sand Veil'), def: P('ludicolo', 55, 'Swift Swim'), move: 'flamethrower', divergence: 'type-chart-sequential-truncation' },
  { name: 'Milotic Ice Beam vs Gyarados (x0.5 then x2 in table order)', att: C(4, 'Marvel Scale'), def: P('gyarados', 60, 'Intimidate'), move: 'icebeam', divergence: 'type-chart-sequential-truncation' },
  // --- immunities ---
  { name: 'Garchomp EQ vs Togekiss (x0 Flying)', att: C(5, 'Sand Veil'), def: C(2, 'Serene Grace'), move: 'earthquake' },
  { name: 'Lucario Extreme Speed vs Spiritomb (x0 Ghost)', att: C(3, 'Inner Focus'), def: C(0, 'Pressure'), move: 'extremespeed' },
  { name: 'Alakazam Psychic vs Spiritomb (x0 Dark)', att: LUCIAN(3, 'Synchronize'), def: C(0, 'Pressure'), move: 'psychic' },
  { name: 'Togekiss Shock Wave vs Garchomp (x0 Ground)', att: C(2, 'Serene Grace'), def: C(5, 'Sand Veil'), move: 'shockwave' },
  { name: 'Garchomp EQ vs Bronzong Levitate', att: C(5, 'Sand Veil'), def: LUCIAN(2, 'Levitate'), move: 'earthquake' },
  { name: 'Rampardos (Mold Breaker) EQ vs Bronzong Levitate', att: P('rampardos', 60, 'Mold Breaker', { moves: ['earthquake'] }), def: LUCIAN(2, 'Levitate'), move: 'earthquake' },
  { name: 'Garchomp EQ vs Togekiss under Gravity', att: C(5, 'Sand Veil'), def: C(2, 'Serene Grace'), move: 'earthquake', setup: ({ battle }) => battle.field.addPseudoWeather('gravity', 'debug') },
  { name: 'Garchomp EQ vs Togekiss holding Iron Ball', att: C(5, 'Sand Veil'), def: C(2, 'Serene Grace', { item: 'ironball' }), move: 'earthquake' },
  { name: 'Garchomp EQ vs Magnezone with Magnet Rise', att: C(5, 'Sand Veil'), def: P('magnezone', 58, 'Sturdy'), move: 'earthquake', setup: ({ d }) => d.addVolatile('magnetrise') },
  { name: 'Lucario Extreme Speed vs Spiritomb under Foresight', att: C(3, 'Inner Focus'), def: C(0, 'Pressure'), move: 'extremespeed', setup: ({ d }) => d.addVolatile('foresight') },
  { name: 'Kangaskhan (Scrappy) Return vs Gengar', att: P('kangaskhan', 60, 'Scrappy'), def: P('gengar', 60, 'Levitate'), move: 'bodyslam' },
  // --- crits / stages ---
  { name: 'Crit: Garchomp EQ vs Infernape', att: C(5, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake', crit: true },
  { name: 'Crit: Milotic Surf vs Rhyperior special', att: C(4, 'Marvel Scale'), def: BERTHA(4, 'Lightningrod'), move: 'surf', crit: true },
  { name: 'Crit ignores -2 Atk', att: C(5, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake', crit: true, setup: boost('a', 'atk', -2) },
  { name: 'Crit keeps +2 Atk', att: C(5, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake', crit: true, setup: boost('a', 'atk', 2) },
  { name: 'Crit ignores +2 Def', att: C(5, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake', crit: true, setup: boost('d', 'def', 2) },
  { name: 'Crit keeps -1 SpD', att: C(4, 'Marvel Scale'), def: FLINT(3, 'Blaze'), move: 'surf', crit: true, setup: boost('d', 'spd', -1) },
  { name: 'Crit ignores Reflect', att: C(5, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake', crit: true, setup: side('reflect') },
  { name: 'Crit vs Battle Armor Drapion (no crit)', att: C(5, 'Sand Veil'), def: AARON(4, 'Battle Armor'), move: 'earthquake', crit: true },
  { name: 'Sniper Drapion crit (x3)', att: AARON(4, 'Sniper'), def: LUCIAN(3, 'Synchronize'), move: 'xscissor', crit: true, divergence: 'sniper-after-variance' },
  { name: '+6 Atk Garchomp EQ', att: C(5, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake', setup: boost('a', 'atk', 6) },
  { name: '-6 Atk Garchomp EQ', att: C(5, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake', setup: boost('a', 'atk', -6) },
  { name: '+1 SpA vs -1 SpD Milotic Surf', att: C(4, 'Marvel Scale'), def: FLINT(3, 'Blaze'), move: 'surf', setup: all(boost('a', 'spa', 1), boost('d', 'spd', -1)) },
  { name: '+3 Def defender', att: C(5, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake', setup: boost('d', 'def', 3) },
  // --- burn / Guts / Marvel Scale ---
  { name: 'Burned Garchomp EQ', att: C(5, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake', setup: brn },
  { name: 'Burned Garchomp Flamethrower (special unaffected)', att: C(5, 'Sand Veil'), def: P('scizor', 60, 'Technician'), move: 'flamethrower', setup: brn },
  { name: 'Guts Heracross burned Megahorn', att: AARON(3, 'Guts'), def: LUCIAN(3, 'Synchronize'), move: 'megahorn', setup: brn },
  { name: 'Marvel Scale Milotic (paralyzed) vs EQ', att: C(5, 'Sand Veil'), def: C(4, 'Marvel Scale'), move: 'earthquake', setup: ({ d }) => d.setStatus('par', d) },
  // --- items ---
  { name: 'Choice Band Garchomp EQ', att: P('garchomp', 60, 'Sand Veil', { item: 'choiceband' }), def: FLINT(3, 'Blaze'), move: 'earthquake' },
  { name: 'Choice Specs Alakazam Psychic', att: LUCIAN(3, 'Synchronize', { item: 'choicespecs' }), def: FLINT(3, 'Blaze'), move: 'psychic' },
  { name: 'Life Orb Garchomp EQ', att: P('garchomp', 60, 'Sand Veil', { item: 'lifeorb' }), def: FLINT(3, 'Blaze'), move: 'earthquake' },
  { name: 'Life Orb Alakazam Psychic', att: LUCIAN(3, 'Synchronize', { item: 'lifeorb' }), def: FLINT(3, 'Blaze'), move: 'psychic' },
  { name: 'Expert Belt Lucario Aura Sphere vs Tyranitar', att: C(3, 'Inner Focus', { item: 'expertbelt' }), def: P('tyranitar', 60, 'Sand Stream'), move: 'aurasphere', divergence: 'expert-belt-rounding' },
  { name: 'Muscle Band Garchomp Dragon Rush', att: C(5, 'Sand Veil', { item: 'muscleband' }), def: C(4, 'Marvel Scale'), move: 'dragonrush' },
  { name: 'Wise Glasses Milotic Surf', att: C(4, 'Marvel Scale', { item: 'wiseglasses' }), def: FLINT(3, 'Blaze'), move: 'surf' },
  { name: 'Mystic Water Milotic Surf', att: C(4, 'Marvel Scale', { item: 'mysticwater' }), def: FLINT(3, 'Blaze'), move: 'surf' },
  { name: 'Charcoal Magmortar Flamethrower', att: FLINT(4, 'Flame Body', { item: 'charcoal' }), def: AARON(1, 'Technician'), move: 'flamethrower' },
  { name: 'Splash Plate (Mystic-equivalent) Milotic Surf', att: C(4, 'Marvel Scale', { item: 'splashplate' }), def: FLINT(3, 'Blaze'), move: 'surf' },
  { name: 'Klutz Lopunny Choice Band (ignored)', att: P('lopunny', 60, 'Klutz', { item: 'choiceband' }), def: LUCIAN(3, 'Synchronize'), move: 'megakick' },
  { name: 'Thick Club Marowak', att: P('marowak', 55, 'Rock Head', { item: 'thickclub' }), def: FLINT(3, 'Blaze'), move: 'earthquake' },
  { name: 'Light Ball Pikachu Thunderbolt', att: P('pikachu', 50, 'Static', { item: 'lightball', nature: 'Modest', evs: { hp: 4, atk: 0, def: 0, spa: 252, spd: 0, spe: 252 } }), def: P('gyarados', 60, 'Intimidate'), move: 'thunderbolt' },
  { name: 'Adamant Orb Dialga Dragon Pulse', att: P('dialga', 50, 'Pressure', { item: 'adamantorb', nature: 'Modest' }), def: C(5, 'Sand Veil'), move: 'dragonpulse' },
  // --- weather ---
  { name: 'Sun Magmortar Flamethrower', att: FLINT(4, 'Flame Body'), def: AARON(1, 'Technician'), move: 'flamethrower', setup: weather('sunnyday') },
  { name: 'Sun Milotic Surf (halved)', att: C(4, 'Marvel Scale'), def: FLINT(3, 'Blaze'), move: 'surf', setup: weather('sunnyday') },
  { name: 'Rain Milotic Surf', att: C(4, 'Marvel Scale'), def: FLINT(3, 'Blaze'), move: 'surf', setup: weather('raindance') },
  { name: 'Rain Magmortar Flamethrower (halved)', att: FLINT(4, 'Flame Body'), def: AARON(1, 'Technician'), move: 'flamethrower', setup: weather('raindance') },
  { name: 'Sandstorm Rock SpD boost: Milotic Surf vs Rhyperior', att: C(4, 'Marvel Scale'), def: BERTHA(4, 'Lightningrod'), move: 'surf', setup: weather('sandstorm') },
  { name: 'Solar Beam in rain (halved)', att: FLINT(2, 'Flash Fire'), def: BERTHA(0, 'Oblivious'), move: 'solarbeam', setup: weather('raindance') },
  { name: 'Cloud Nine Golduck in sun: Flamethrower unboosted', att: FLINT(4, 'Flame Body'), def: P('golduck', 55, 'Cloud Nine'), move: 'flamethrower', setup: weather('sunnyday') },
  // --- screens ---
  { name: 'Reflect vs Garchomp EQ', att: C(5, 'Sand Veil'), def: FLINT(3, 'Blaze'), move: 'earthquake', setup: side('reflect') },
  { name: 'Light Screen vs Milotic Surf', att: C(4, 'Marvel Scale'), def: FLINT(3, 'Blaze'), move: 'surf', setup: side('lightscreen') },
  // --- damage-modifying abilities ---
  { name: 'Thick Fat Snorlax vs Flamethrower', att: FLINT(4, 'Flame Body'), def: P('snorlax', 60, 'Thick Fat'), move: 'flamethrower' },
  { name: 'Thick Fat Snorlax vs Ice Beam', att: C(4, 'Marvel Scale'), def: P('snorlax', 60, 'Thick Fat'), move: 'icebeam' },
  { name: 'Huge Power Azumarill Waterfall', att: P('azumarill', 55, 'Huge Power'), def: FLINT(3, 'Blaze'), move: 'waterfall' },
  { name: 'Technician Scizor Bullet Punch', att: AARON(1, 'Technician'), def: LUCIAN(3, 'Synchronize'), move: 'bulletpunch' },
  { name: 'Technician Scizor Aerial Ace (60 BP boundary)', att: AARON(1, 'Technician'), def: AARON(3, 'Guts'), move: 'aerialace' },
  { name: 'Technician Scizor X-Scissor (80 BP, no boost)', att: AARON(1, 'Technician'), def: LUCIAN(3, 'Synchronize'), move: 'xscissor' },
  { name: 'Adaptability Porygon-Z Tri Attack', att: P('porygonz', 60, 'Adaptability', { nature: 'Modest', evs: { hp: 4, atk: 0, def: 0, spa: 252, spd: 0, spe: 252 } }), def: FLINT(3, 'Blaze'), move: 'triattack' },
  { name: 'Solid Rock Rhyperior vs Energy Ball (x4)', att: C(1, 'Natural Cure'), def: BERTHA(4, 'Solid Rock'), move: 'energyball' },
  { name: 'Solid Rock Rhyperior vs Surf (x4)', att: C(4, 'Marvel Scale'), def: BERTHA(4, 'Solid Rock'), move: 'surf' },
  { name: 'Filter Mr. Mime vs Shadow Ball (x2)', att: C(0, 'Pressure'), def: LUCIAN(0, 'Filter'), move: 'shadowball' },
  { name: 'Mold Breaker Rampardos vs Filter Mr. Mime', att: P('rampardos', 60, 'Mold Breaker'), def: LUCIAN(0, 'Filter'), move: 'crunch' },
  { name: 'Tinted Lens Yanmega Bug Buzz vs Infernape (x0.25)', att: AARON(0, 'Tinted Lens'), def: FLINT(3, 'Blaze'), move: 'bugbuzz' },
  { name: 'Heatproof Bronzong vs Flamethrower', att: FLINT(4, 'Flame Body'), def: LUCIAN(2, 'Heatproof'), move: 'flamethrower' },
  { name: 'Dry Skin Toxicroak vs Flamethrower', att: FLINT(4, 'Flame Body'), def: P('toxicroak', 55, 'Dry Skin'), move: 'flamethrower', divergence: 'bp-modifier-rounding' },
  { name: 'Flash Fire active Houndoom Flamethrower', att: FLINT(0, 'Flash Fire'), def: AARON(1, 'Technician'), move: 'flamethrower', setup: ({ a }) => a.addVolatile('flashfire') },
  { name: 'Blaze Infernape at 1/3 HP Flare Blitz', att: FLINT(3, 'Blaze'), def: AARON(1, 'Technician'), move: 'flareblitz', setup: ({ a }) => a.sethp(Math.floor(a.maxhp / 3)) },
  { name: 'Blaze Infernape just above 1/3 HP', att: FLINT(3, 'Blaze'), def: AARON(1, 'Technician'), move: 'flareblitz', setup: ({ a }) => a.sethp(Math.floor(a.maxhp / 3) + 1) },
  { name: 'Swarm Heracross low HP Megahorn', att: AARON(3, 'Swarm'), def: LUCIAN(3, 'Synchronize'), move: 'megahorn', setup: ({ a }) => a.sethp(1) },
  { name: 'Torrent Empoleon low HP Surf', att: P('empoleon', 60, 'Torrent', { nature: 'Modest' }), def: FLINT(3, 'Blaze'), move: 'surf', setup: ({ a }) => a.sethp(10) },
  { name: 'Overgrow Torterra low HP Wood Hammer', att: P('torterra', 60, 'Overgrow'), def: BERTHA(2, 'Sand Stream'), move: 'woodhammer', setup: ({ a }) => a.sethp(10) },
  { name: 'Hustle Togekiss physical (Giga Impact)', att: C(2, 'Hustle'), def: LUCIAN(3, 'Synchronize'), move: 'gigaimpact' },
  { name: 'Iron Fist Hitmonchan Thunder Punch', att: P('hitmonchan', 55, 'Iron Fist'), def: P('gyarados', 60, 'Intimidate'), move: 'thunderpunch' },
  { name: 'Rivalry same gender Luxray', att: P('luxray', 55, 'Rivalry', { gender: 'M' }), def: P('gyarados', 60, 'Intimidate', { gender: 'M' }), move: 'crunch' },
  { name: 'Rivalry opposite gender Luxray', att: P('luxray', 55, 'Rivalry', { gender: 'M' }), def: P('gyarados', 60, 'Intimidate', { gender: 'F' }), move: 'crunch' },
  { name: 'Simple Bibarel +1 Atk', att: P('bibarel', 50, 'Simple'), def: FLINT(3, 'Blaze'), move: 'waterfall', setup: boost('a', 'atk', 1) },
  { name: 'Unaware defender vs +2 Atk', att: C(5, 'Sand Veil'), def: P('bibarel', 50, 'Unaware'), move: 'dragonrush', setup: boost('a', 'atk', 2) },
  { name: 'Normalize Delcatty Thunderbolt->Normal', att: P('delcatty', 55, 'Normalize', { nature: 'Modest' }), def: FLINT(3, 'Blaze'), move: 'thunderbolt' },
  { name: 'Charge Magnezone Thunderbolt', att: P('magnezone', 60, 'Magnet Pull', { nature: 'Modest' }), def: P('gyarados', 60, 'Intimidate'), move: 'thunderbolt', setup: ({ a }) => a.addVolatile('charge') },
  { name: 'Explosion Golem (defense halved)', att: BERTHA(3, 'Sturdy'), def: AARON(3, 'Guts'), move: 'explosion' },
  { name: 'Level 100 Garchomp vs level 5 Bidoof', att: P('garchomp', 100, 'Sand Veil'), def: P('bidoof', 5, 'Simple'), move: 'dragonclaw' },
  // --- stacked modifiers (where integer-floor vs 4096-rounding orders could differ) ---
  { name: 'Technician + Muscle Band Scizor Bullet Punch', att: AARON(1, 'Technician', { item: 'muscleband' }), def: LUCIAN(3, 'Synchronize'), move: 'bulletpunch' },
  { name: 'Huge Power + Choice Band Azumarill Waterfall', att: P('azumarill', 55, 'Huge Power', { item: 'choiceband' }), def: FLINT(3, 'Blaze'), move: 'waterfall' },
  { name: 'Choice Band +1 Atk Garchomp EQ', att: P('garchomp', 60, 'Sand Veil', { item: 'choiceband' }), def: FLINT(3, 'Blaze'), move: 'earthquake', setup: boost('a', 'atk', 1) },
  { name: 'Choice Band -1 Atk Garchomp EQ', att: P('garchomp', 60, 'Sand Veil', { item: 'choiceband' }), def: FLINT(3, 'Blaze'), move: 'earthquake', setup: boost('a', 'atk', -1), divergence: 'stat-modifier-before-stages' },
  { name: 'Life Orb crit Garchomp EQ', att: P('garchomp', 60, 'Sand Veil', { item: 'lifeorb' }), def: FLINT(3, 'Blaze'), move: 'earthquake', crit: true },
  { name: 'Life Orb + Expert Belt-free SE: Alakazam Focus Blast vs Tyranitar', att: LUCIAN(3, 'Synchronize', { item: 'lifeorb' }), def: P('tyranitar', 60, 'Sand Stream'), move: 'focusblast' },
  { name: 'Expert Belt vs Filter Mr. Mime', att: C(0, 'Pressure', { item: 'expertbelt' }), def: LUCIAN(0, 'Filter'), move: 'shadowball', divergence: 'final-modifier-chaining' },
  { name: 'Metronome item (2 consecutive) Garchomp Dragon Rush', att: C(5, 'Sand Veil', { item: 'metronome' }), def: C(4, 'Marvel Scale'), move: 'dragonrush',
    setup: ({ a }) => { a.addVolatile('metronome'); a.volatiles.metronome.numConsecutive = 2; } },
  { name: 'Mystic Water in rain Milotic Surf', att: C(4, 'Marvel Scale', { item: 'mysticwater' }), def: FLINT(3, 'Blaze'), move: 'surf', setup: weather('raindance') },
  { name: 'Burn + Reflect + crit-free Lucario Stone Edge', att: C(3, 'Inner Focus'), def: P('gyarados', 60, 'Intimidate'), move: 'stoneedge', setup: all(brn, side('reflect')) },
  { name: 'Flash Fire + sun Houndoom Flamethrower', att: FLINT(0, 'Flash Fire'), def: AARON(1, 'Technician'), move: 'flamethrower', setup: all(weather('sunnyday'), ({ a }) => a.addVolatile('flashfire')) },
  { name: 'Low-level 1-damage floor', att: P('bidoof', 5, 'Simple'), def: P('steelix', 70, 'Sturdy'), move: 'tackle' },
];

test('type chart parsed from battle_lib.c:2399 has 112 rows incl. sentinels', () => {
  // Positive control: count of "{ " rows in pokeplatinum/src/battle/battle_lib.c:2400-2516 is 112.
  assert.equal(TYPE_CHART.entries.length, 112);
  assert.equal(TYPE_CHART.line, 2399);
  // pokeplatinum/src/battle/battle_lib.c:2419 { TYPE_ELECTRIC, TYPE_GROUND, TYPE_MULTI_IMMUNE }
  assert.ok(TYPE_CHART.entries.some((e) => e.atk === 'TYPE_ELECTRIC' && e.def === 'TYPE_GROUND' && e.mul === 0 && e.line === 2419));
});

test('decomp move/item data loaded from res/', () => {
  // pokeplatinum/res/moves/earthquake/data.json: power 100, TYPE_GROUND, CLASS_PHYSICAL
  assert.deepEqual([moveData('MOVE_EARTHQUAKE').power, moveData('MOVE_EARTHQUAKE').type, moveData('MOVE_EARTHQUAKE').class],
    [100, 'TYPE_GROUND', 'CLASS_PHYSICAL']);
  // pokeplatinum/res/items/data/life_orb.json: effectParam 30, HOLD_EFFECT_HP_DRAIN_ON_ATK
  assert.deepEqual(itemData('ITEM_LIFE_ORB'), { holdEffect: 'HOLD_EFFECT_HP_DRAIN_ON_ATK', effectParam: 30, src: 'pokeplatinum/res/items/data/life_orb.json' });
});

test('hand-computed base damage (no Showdown): sequential type truncation', () => {
  // Pure-port arithmetic check, every step from battle_lib.c: L50 attacker, SpA 100, SpD 100,
  // Flamethrower (power 95, CLASS_SPECIAL, TYPE_FIRE: pokeplatinum/res/moves/flamethrower/data.json).
  const atk = { species: 'SPECIES_MAGMORTAR', level: 50, types: ['TYPE_FIRE', 'TYPE_FIRE'], stats: { atk: 100, def: 100, spa: 100, spd: 100 },
    stages: {}, hp: 100, maxhp: 100, ability: 'ABILITY_NONE', item: 'ITEM_NONE', status: '', gender: 'N' };
  const def = { ...atk, species: 'SPECIES_LUDICOLO', types: ['TYPE_WATER', 'TYPE_GRASS'] };
  const move = { id: 'MOVE_FLAMETHROWER' };
  // :6995 100*1 ; :7006 *95 = 9500 ; :7007 *(50*2/5+2=22) = 209000 ; :7021 /100 = 2090 ; :7022 /50 = 41 ; :7078 +2 = 43
  assert.equal(calcBaseDamage({ attacker: atk, defender: def, move }), 43);
  // ApplyTypeChart(43): STAB 43*15/10=64 (:2595); FIRE/WATER x5/10 -> 32 (:2627, table row :2403);
  // FIRE/GRASS x20/10 -> 64 (:2637, row :2404).
  assert.equal(applyTypeChart({ attacker: atk, defender: def, move }, 43).damage, 64);
  // 41 -> STAB 61 -> 30 -> 60 (Showdown would give 61): the divergence.
  assert.equal(applyTypeChart({ attacker: atk, defender: def, move }, 41).damage, 60);
});

test('hand-computed divergence arithmetic (port side = decomp integer math)', () => {
  const base = { species: 'SPECIES_GARCHOMP', level: 60, types: ['TYPE_DRAGON', 'TYPE_GROUND'],
    stats: { atk: 238, def: 100, spa: 100, spd: 100 }, stages: {}, hp: 100, maxhp: 100,
    ability: 'ABILITY_SAND_VEIL', item: 'ITEM_NONE', status: '', gender: 'M' };
  const def = { ...base, species: 'SPECIES_INFERNAPE', types: ['TYPE_FIRE', 'TYPE_FIGHTING'], ability: 'ABILITY_BLAZE' };
  const eq = { id: 'MOVE_EARTHQUAKE' };
  // stat-modifier-before-stages: Choice Band (battle_lib.c:6724-6725) on raw 238 -> 357, then -1 stage
  // 10/15 (:6550 table, :6955-6956) -> 238, so damage equals the unboosted, unstaged 238 case.
  const cb = { ...base, item: 'ITEM_CHOICE_BAND', stages: { atk: -1 } };
  assert.equal(calcBaseDamage({ attacker: cb, defender: def, move: eq }), calcBaseDamage({ attacker: base, defender: def, move: eq }));
  // 238*100*(60*2/5+2=26)/100/50 + 2 = 123 + 2 = 125 (:6955-6976, :7078)
  assert.equal(calcBaseDamage({ attacker: base, defender: def, move: eq }), 125);
  // expert-belt-rounding: SE STAB hit, Ground vs Fire. 89 -> STAB 89*15/10 = 133 (:2595) -> x20/10 = 266
  // (:2627) -> Expert Belt 266*120/100 = 319 (:2663-2665). Showdown: (266*4915+2047)>>12 = 319 here too;
  // the battle case shows rolls where they differ.
  const belt = { ...base, item: 'ITEM_EXPERT_BELT' };
  assert.equal(applyTypeChart({ attacker: belt, defender: def, move: eq }, 89).damage, Math.trunc(Math.trunc(Math.trunc(89 * 15 / 10) * 20 / 10) * 120 / 100));
  assert.equal(applyTypeChart({ attacker: belt, defender: def, move: eq }, 89).damage, 319);
  // bp-modifier-rounding: Dry Skin power 95 -> 95*125/100 = 118 (battle_lib.c:6845-6847).
  const mag = { ...base, species: 'SPECIES_MAGMORTAR', types: ['TYPE_FIRE', 'TYPE_FIRE'], stats: { atk: 100, def: 100, spa: 100, spd: 100 }, level: 50 };
  const tox = { ...mag, species: 'SPECIES_TOXICROAK', types: ['TYPE_POISON', 'TYPE_FIGHTING'], ability: 'ABILITY_DRY_SKIN' };
  // 100*118*22/100/50 + 2 = 51 + 2 = 53 (with power 119 it would be 52 + 2 = 54)
  assert.equal(calcBaseDamage({ attacker: mag, defender: tox, move: { id: 'MOVE_FLAMETHROWER' } }), 53);
});

const results = [];
for (const c of CASES) {
  test(`damage: ${c.name}`, () => {
    const r = run(c);
    const match = r.sd.every((v, i) => v === r.port[i]);
    results.push({ name: c.name, match, divergence: c.divergence, zero: r.sd[15] === 0 && r.port[15] === 0 });
    if (c.divergence) {
      assert.ok(DIV_IDS.has(c.divergence), `unknown divergence id ${c.divergence}`);
      assert.ok(!match, `expected divergence ${c.divergence} but engines agree: ${JSON.stringify(r.sd)}`);
    } else {
      assert.deepEqual(r.port, r.sd, `port ${JSON.stringify(r.port)}\n   sd ${JSON.stringify(r.sd)}`);
    }
  });
}

test('summary', () => {
  const n = results.length;
  const exact = results.filter((x) => x.match).length;
  const div = results.filter((x) => x.divergence).length;
  const zero = results.filter((x) => x.zero).map((x) => x.name);
  console.log(`# damage cross-check: ${n} combinations, ${exact} exact 16-roll matches, ${div} known divergences, ${zero.length} zero-damage (immunity) cases`);
  // Positive control against a silent harness: only the immunity cases may be all-zero.
  assert.ok(zero.every((name) => /x0|Levitate|Magnet Rise/.test(name)), `unexpected zero-damage cases: ${zero}`);
  assert.ok(n >= 50);
});
