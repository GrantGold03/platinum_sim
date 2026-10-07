// T044 tests: misc-group trainer-AI opcode handlers (sim/ai/cmds/misc.mjs).
// Each test runs a real parsed instruction (found by name + script.s line) against a real
// gen4customgame Battle through the T039 adapter, with a hand-built AI_CONTEXT mem and a counting
// rand stub. C references: pokeplatinum/src/battle/trainer_ai/trainer_ai.c (TAI).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Battle } from '../showdown.mjs';
import { createAdapter } from '../ai/adapter.mjs';
import { parseAiScript } from '../ai/parse.mjs';
import { HANDLERS, makeCtx, runSection } from '../ai/interp.mjs';
import { handlers as misc } from '../ai/cmds/misc.mjs';

const prog = parseAiScript();
const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 };
const evs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
const mon = (species, moves, extra = {}) => ({ species, moves, level: 50, nature: 'Serious', ivs, evs, item: '', ...extra });

// Player (p1, battlers 0/2) and AI (p2, battlers 1/3). Moves are chosen to reach each condition
// with real moves; gen4customgame does not check learnsets.
function makeBattle() {
  return new Battle({
    formatid: 'gen4customgame',
    seed: [1, 2, 3, 4],
    p1: { name: 'Player', team: [
      mon('skarmory', ['stealthrock', 'thunderwave', 'seismictoss', 'safeguard'], { ability: 'Keen Eye' }),
      mon('snorlax', ['explosion', 'seismictoss', 'reflect', 'rest'], { ability: 'Thick Fat' }),
      mon('blissey', ['softboiled', 'seismictoss', 'protect', 'toxic'], { ability: 'Natural Cure' }),
    ] },
    p2: { name: 'AI', team: [
      mon('blissey', ['spikes', 'toxicspikes', 'lightscreen', 'raindance'], { ability: 'Serene Grace' }),
      mon('chansey', ['sunnyday', 'hail', 'sandstorm', 'trickroom'], { ability: 'Serene Grace' }),
      mon('gengar', ['gravity', 'protect', 'shadowball', 'curse'], { ability: 'Levitate' }),
    ] },
  });
}

function ins(name, line) {
  const i = prog.instructions.find((x) => x.name === name && x.line === line);
  assert.ok(i, `no ${name} at script.s:${line}`);
  return i;
}

// Counting stub for BattleSystem_RandNext: returns the given u16 values in order.
function randStub(values) {
  const r = () => {
    if (r.calls >= values.length) throw new Error('rand stub exhausted');
    return values[r.calls++];
  };
  r.calls = 0;
  return r;
}

const SENTINEL = 0x5A5A;
function freshMem() {
  return {
    move: 0, moveSlot: 0, moveScore: [100, 100, 100, 100], moveDamageRolls: [100, 100, 100, 100],
    calcTemp: SENTINEL, battlerMoves: [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
    battlerAbilities: [0, 0, 0, 0], battlerHeldItems: [0, 0, 0, 0], stack: [],
  };
}

// Run one instruction the way runSection does (ctx.next defaults to index + 1).
function run(ai, i, { rand = randStub([]), mem = freshMem() } = {}) {
  const ctx = makeCtx({ prog, ai, mem, rand });
  ctx.next = i.index + 1;
  HANDLERS[i.name](ctx, i);
  return { ctx, mem, rand, jumped: ctx.next !== i.index + 1, fell: ctx.next === i.index + 1 };
}
const jumpTarget = (i) => i.args.find((a) => a.kind === 'jump').targetInstr;

test('all 14 misc opcodes from OPCODES.md are implemented in misc.mjs and reachable via HANDLERS', () => {
  const names = ['IfRandomLessThan', 'IfSideCondition', 'LoadTurnCount', 'CountAlivePartyBattlers',
    'IfPartyMemberStatus', 'LoadCurrentWeather', 'LoadIsFirstTurnInBattle', 'LoadBattleType',
    'IfTargetIsPartner', 'IfFieldConditionsMask', 'LoadSpikesLayers', 'IfAnyPartyMemberIsWounded',
    'IfAnyPartyMemberUsedPP', 'LoadBattlerTurnCount'];
  for (const n of names) {
    assert.equal(typeof misc[n], 'function', n);
    assert.equal(HANDLERS[n], misc[n], n);
  }
});

test('IfRandomLessThan (TAI:528): one u16 draw per run, jump iff draw % 256 < i', () => {
  const ai = createAdapter(makeBattle());
  const i = ins('IfRandomLessThan', 1821); // IfRandomLessThan 128, Expert_StatusSleep_End
  assert.equal(i.args[0].value, 128);
  // 127 -> jump; 128 -> no jump; 0xFF7F % 256 = 127 -> jump (high byte ignored); 0x0180 % 256 = 128 -> no.
  for (const [r, jump] of [[127, true], [128, false], [0xFF7F, true], [0x0180, false], [0, true], [255, false]]) {
    const res = run(ai, i, { rand: randStub([r]) });
    assert.equal(res.rand.calls, 1, `exactly one draw for ${r}`);
    assert.equal(res.ctx.next, jump ? jumpTarget(i) : i.index + 1, `draw ${r}`);
    assert.equal(res.mem.calcTemp, SENTINEL, 'calcTemp untouched');
  }
  // Positive control on the jump target: it is the label the source names.
  assert.equal(jumpTarget(i), prog.labels.Expert_StatusSleep_End.instr);
});

test('IfSideCondition (TAI:732): side of AIScript_Battler, real Light Screen / Stealth Rock', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const ls = ins('IfSideCondition', 551); // ATTACKER, SIDE_CONDITION_LIGHT_SCREEN
  const sr = ins('IfSideCondition', 1494); // DEFENDER, SIDE_CONDITION_STEALTH_ROCK
  const sp = ins('IfSideCondition', 1493); // DEFENDER, SIDE_CONDITION_SPIKES
  assert.ok(run(ai, ls).fell);
  assert.ok(run(ai, sr).fell);
  assert.ok(run(ai, sp).fell);
  // Player sets Stealth Rock on the AI's side; AI sets Light Screen on its own side.
  battle.makeChoices('move stealthrock', 'move lightscreen');
  assert.ok(battle.p2.sideConditions.lightscreen, 'positive control: Light Screen up on AI side');
  assert.ok(battle.p2.sideConditions.stealthrock, 'positive control: Stealth Rock on AI side');
  assert.equal(run(ai, ls).ctx.next, jumpTarget(ls)); // ATTACKER -> side 1
  // DEFENDER -> battler 0 -> side 0: the AI-side Stealth Rock does not count.
  assert.ok(run(ai, sr).fell);
  // AI sets Spikes on the player's side: DEFENDER -> side 0 -> jump.
  battle.makeChoices('move thunderwave', 'move spikes');
  assert.ok(battle.p1.sideConditions.spikes, 'positive control: Spikes on player side');
  const r = run(ai, sp);
  assert.equal(r.ctx.next, jumpTarget(sp));
  assert.equal(r.rand.calls, 0);
  assert.equal(r.mem.calcTemp, SENTINEL);
  // Same Stealth Rock mask with battler ATTACKER (hand-edited argument): side 1 -> jump.
  const srAtk = { ...sr, args: sr.args.map((x) => (x.name === 'battler' ? { ...x, value: 1 } : x)) };
  assert.equal(run(ai, srAtk).ctx.next, jumpTarget(sr));
});

test('LoadTurnCount (TAI:931): calcTemp = totalTurns (0 on the first decision)', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const i = ins('LoadTurnCount', 1385);
  let r = run(ai, i);
  assert.equal(r.mem.calcTemp, 0);
  assert.equal(r.ctx.next, i.index + 1);
  battle.makeChoices('move thunderwave', 'move lightscreen');
  battle.makeChoices('move seismictoss', 'move raindance');
  r = run(ai, i);
  assert.equal(r.mem.calcTemp, 2);
  assert.equal(r.rand.calls, 0);
});

test('CountAlivePartyBattlers (TAI:1126): non-active, HP != 0 party members', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const atk = ins('CountAlivePartyBattlers', 310); // ATTACKER
  const def = ins('CountAlivePartyBattlers', 312); // DEFENDER
  assert.equal(run(ai, atk).mem.calcTemp, 2);
  assert.equal(run(ai, def).mem.calcTemp, 2);
  // Player switches to Snorlax, which explodes into Gengar's Protect and faints.
  battle.makeChoices('switch 2', 'switch 3');
  battle.makeChoices('move explosion', 'move protect');
  assert.equal(battle.p1.pokemon.find((p) => p.species.id === 'snorlax').hp, 0, 'positive control: Snorlax fainted');
  battle.makeChoices('switch 3', ''); // forced replacement: Blissey (game slot 2)
  assert.equal(ai.selectedPartySlot(0), 2);
  // Defender = Blissey (slot 2) active; Skarmory alive, Snorlax 0 HP -> 1.
  assert.equal(run(ai, def).mem.calcTemp, 1);
  assert.equal(run(ai, atk).mem.calcTemp, 2);
  // Doubles branch (TAI:1137-1139) with the partner from BattleSystem_GetPartner: in this singles
  // battle the partner battler 3 has no party slot (u8 255), so the count is unchanged.
  const aiD = createAdapter(battle, { battleType: ai.constants.get('BATTLE_TYPE_DOUBLES') | ai.constants.get('BATTLE_TYPE_TRAINER') });
  assert.equal(run(aiD, def).mem.calcTemp, 1);
});

test('IfPartyMemberStatus (TAI:1348): statused, alive, non-active party member', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const i = ins('IfPartyMemberStatus', 1046); // ATTACKER, MON_CONDITION_ANY
  assert.equal(i.args[1].value, 255);
  assert.ok(run(ai, i).fell);
  battle.makeChoices('move thunderwave', 'move lightscreen');
  assert.equal(battle.p2.active[0].status, 'par', 'positive control: AI Blissey paralysed');
  // Paralysed Blissey is the active slot -> excluded.
  assert.ok(run(ai, i).fell);
  battle.makeChoices('move seismictoss', 'switch 2');
  assert.equal(ai.selectedPartySlot(1), 1);
  const r = run(ai, i);
  assert.equal(r.ctx.next, jumpTarget(i));
  assert.equal(r.rand.calls, 0);
});

test('LoadCurrentWeather (TAI:1414): real rain / sun / hail / sand, then precedence', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const K = (n) => ai.constants.get(n);
  const i = ins('LoadCurrentWeather', 535);
  assert.equal(run(ai, i).mem.calcTemp, K('AI_WEATHER_CLEAR'));
  battle.makeChoices('move thunderwave', 'move raindance');
  assert.equal(battle.field.weather, 'raindance');
  assert.equal(run(ai, i).mem.calcTemp, K('AI_WEATHER_RAINING'));
  battle.makeChoices('move seismictoss', 'switch 2');
  const seq = [['sunnyday', 'AI_WEATHER_SUNNY'], ['hail', 'AI_WEATHER_HAILING'], ['sandstorm', 'AI_WEATHER_SANDSTORM']];
  for (const [move, want] of seq) {
    battle.makeChoices('move safeguard', `move ${move}`);
    assert.equal(battle.field.weather, move, `positive control: ${move} active`);
    assert.equal(run(ai, i).mem.calcTemp, K(want), move);
  }
  // Precedence of the overwriting ifs (rain < sand < sun < hail < fog) with masks the adapter
  // cannot produce from Showdown (two weathers at once; DEEP_FOG).
  const withMask = (m) => ({ ...ai, fieldConditionsMask: () => m });
  assert.equal(run(withMask(K('FIELD_CONDITION_RAINING_TEMP') | K('FIELD_CONDITION_SUNNY_PERM')), i).mem.calcTemp, K('AI_WEATHER_SUNNY'));
  assert.equal(run(withMask(K('FIELD_CONDITION_HAILING_PERM') | K('FIELD_CONDITION_SANDSTORM_TEMP')), i).mem.calcTemp, K('AI_WEATHER_HAILING'));
  assert.equal(run(withMask(K('FIELD_CONDITION_DEEP_FOG') | K('FIELD_CONDITION_HAILING_TEMP')), i).mem.calcTemp, K('AI_WEATHER_DEEP_FOG'));
  assert.equal(run(withMask(K('FIELD_CONDITION_TRICK_ROOM')), i).mem.calcTemp, K('AI_WEATHER_CLEAR'));
});

test('LoadIsFirstTurnInBattle (TAI:2480): !(fakeOutTurnNumber < totalTurns)', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const i = ins('LoadIsFirstTurnInBattle', 831); // ATTACKER
  assert.equal(run(ai, i).mem.calcTemp, 1); // 0 < 0 false -> TRUE
  battle.makeChoices('move thunderwave', 'move lightscreen');
  assert.equal(run(ai, i).mem.calcTemp, 0); // 0 < 1 -> FALSE
  battle.makeChoices('move seismictoss', 'switch 2'); // switch during totalTurns 1 -> fakeOut 2
  assert.equal(ai.totalTurns(), 2);
  assert.equal(ai.moveEffectsData(1).fakeOutTurnNumber, 2);
  assert.equal(run(ai, i).mem.calcTemp, 1); // 2 < 2 false -> TRUE
  battle.makeChoices('move seismictoss', 'move sunnyday');
  assert.equal(run(ai, i).mem.calcTemp, 0);
});

test('LoadBattleType (TAI:2504): calcTemp = battleType', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const i = ins('LoadBattleType', 894);
  const r = run(ai, i);
  assert.equal(r.mem.calcTemp, ai.constants.get('BATTLE_TYPE_TRAINER'));
  assert.equal(r.ctx.next, i.index + 1);
});

test('IfTargetIsPartner (TAI:2630): attacker & 1 == defender & 1', () => {
  const ai = createAdapter(makeBattle());
  const i = ins('IfTargetIsPartner', 54); // first instruction of Basic_Main
  assert.ok(run(ai, i).fell, 'singles: attacker 1, defender 0');
  assert.equal(run({ ...ai, defender: 3 }, i).ctx.next, jumpTarget(i), 'hand-built: defender 3 is the partner');
});

test('IfFieldConditionsMask (TAI:1936): real Trick Room and Gravity', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const tr = ins('IfFieldConditionsMask', 364); // FIELD_CONDITION_TRICK_ROOM
  const gr = ins('IfFieldConditionsMask', 1028); // FIELD_CONDITION_GRAVITY
  assert.ok(run(ai, tr).fell);
  battle.makeChoices('move thunderwave', 'switch 2');
  battle.makeChoices('move seismictoss', 'move trickroom');
  assert.ok(battle.field.pseudoWeather.trickroom, 'positive control: Trick Room up');
  assert.equal(run(ai, tr).ctx.next, jumpTarget(tr));
  assert.ok(run(ai, gr).fell);
  battle.makeChoices('move seismictoss', 'switch 3');
  battle.makeChoices('move seismictoss', 'move gravity');
  assert.ok(battle.field.pseudoWeather.gravity, 'positive control: Gravity up');
  assert.equal(run(ai, gr).ctx.next, jumpTarget(gr));
});

test('LoadSpikesLayers (TAI:1948): spikes / toxic spikes layers; other args leave calcTemp', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const sp = ins('LoadSpikesLayers', 709); // DEFENDER, SIDE_CONDITION_SPIKES
  const ts = ins('LoadSpikesLayers', 1447); // DEFENDER, SIDE_CONDITION_TOXIC_SPIKES
  assert.equal(run(ai, sp).mem.calcTemp, 0);
  battle.makeChoices('move safeguard', 'move spikes');
  battle.makeChoices('move seismictoss', 'move spikes');
  battle.makeChoices('move seismictoss', 'move toxicspikes');
  assert.equal(battle.p1.sideConditions.spikes.layers, 2, 'positive control: two Spikes layers');
  assert.equal(run(ai, sp).mem.calcTemp, 2);
  assert.equal(run(ai, ts).mem.calcTemp, 1);
  // ATTACKER side has none.
  const spAtk = { ...sp, args: sp.args.map((a) => (a.name === 'battler' ? { ...a, value: 1 } : a)) };
  assert.equal(run(ai, spAtk).mem.calcTemp, 0);
  // Hand-built argument SIDE_CONDITION_STEALTH_ROCK: no switch case -> calcTemp unchanged.
  const other = { ...sp, args: sp.args.map((a) => (a.name === 'side_conditions' ? { ...a, value: ai.constants.get('SIDE_CONDITION_STEALTH_ROCK') } : a)) };
  assert.equal(run(ai, other).mem.calcTemp, SENTINEL);
});

test('IfAnyPartyMemberIsWounded (TAI:1968): non-active slot with hp != maxHP (fainted counts)', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const i = ins('IfAnyPartyMemberIsWounded', 1047); // ATTACKER
  assert.ok(run(ai, i).fell);
  battle.makeChoices('move seismictoss', 'move lightscreen');
  assert.ok(battle.p2.active[0].hp < battle.p2.active[0].maxhp, 'positive control: AI Blissey damaged');
  assert.ok(run(ai, i).fell, 'the wounded mon is the active slot');
  battle.makeChoices('move safeguard', 'switch 2');
  assert.equal(run(ai, i).ctx.next, jumpTarget(i));
  // Fainted member counts: player side, Snorlax explodes and faints, Blissey replaces it.
  const def = { ...i, args: i.args.map((a) => (a.name === 'battler' ? { ...a, value: 0 } : a)) };
  battle.makeChoices('switch 2', 'switch 3');
  battle.makeChoices('move explosion', 'move protect');
  battle.makeChoices('switch 3', '');
  // Skarmory: full HP (took Light Screen turn only). Snorlax: 0 HP -> wounded.
  assert.equal(battle.p1.pokemon.find((p) => p.species.id === 'skarmory').hp, battle.p1.pokemon.find((p) => p.species.id === 'skarmory').maxhp);
  assert.equal(run(ai, def).ctx.next, jumpTarget(i));
});

test('IfAnyPartyMemberUsedPP (TAI:1987): non-active slot with pp != maxPP', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const i = ins('IfAnyPartyMemberUsedPP', 1561); // ATTACKER
  assert.ok(run(ai, i).fell);
  battle.makeChoices('move thunderwave', 'move lightscreen');
  assert.ok(run(ai, i).fell, 'only the active Blissey used PP');
  battle.makeChoices('move seismictoss', 'switch 2');
  const r = run(ai, i);
  assert.equal(r.ctx.next, jumpTarget(i));
  assert.equal(r.rand.calls, 0);
});

test('LoadBattlerTurnCount (TAI:2096): totalTurns - fakeOutTurnNumber', () => {
  const battle = makeBattle();
  const ai = createAdapter(battle);
  const i = ins('LoadBattlerTurnCount', 2589); // DEFENDER
  assert.equal(run(ai, i).mem.calcTemp, 0);
  battle.makeChoices('move thunderwave', 'move lightscreen');
  battle.makeChoices('switch 3', 'move raindance'); // player switches during totalTurns 1
  assert.equal(run(ai, i).mem.calcTemp, 0); // 2 - 2
  battle.makeChoices('move seismictoss', 'move spikes');
  assert.equal(run(ai, i).mem.calcTemp, 1); // 3 - 2
});

test('Dummy3E / Dummy3F (TAI:1881-1889) throw instead of hanging; unreachable ops are ai_unimplemented', () => {
  const ai = createAdapter(makeBattle());
  for (const name of ['Dummy3E', 'Dummy3F']) {
    const i = prog.instructions.find((x) => x.name === name);
    assert.ok(i, `${name} present in script.s`);
    const ctx = makeCtx({ prog, ai, mem: freshMem(), rand: randStub([]) });
    assert.throws(() => runSection(ctx, i.index), (e) => e.kind === 'ai_unimplemented' && e.opcode === name);
  }
  // An unreachable opcode with no handler at all (Escape, op 61) also throws ai_unimplemented.
  const esc = prog.instructions.find((x) => x.name === 'Escape');
  if (esc && !HANDLERS.Escape) {
    const ctx = makeCtx({ prog, ai, mem: freshMem(), rand: randStub([]) });
    assert.throws(() => runSection(ctx, esc.index), (e) => e.kind === 'ai_unimplemented');
  }
});
