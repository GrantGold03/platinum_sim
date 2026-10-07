// T038 tests: sim/ai/parse.mjs against the decomp's AI script.
// Every expected value below is copied from a pokeplatinum/ file and cited (path:line).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseAiScript, opcodeUsage, LEAGUE_FLAGS, reachableFrom } from '../ai/parse.mjs';

const prog = parseAiScript();
const insAt = (line) => prog.instructions.find((i) => i.line === line);

test('opcode table has 109 commands (include/data/scripts/aicmd.h:8-116, research R6)', () => {
  assert.equal(prog.opcodes.length, 109);
  // aicmd.h:8 is the first ScriptCommand, numbered 0 by cmd_table.h:13-21.
  assert.equal(prog.opcodes[0].constant, 'AICMD_IFRANDOMLESSTHAN');
  // aicmd.h:116, the last one.
  assert.equal(prog.opcodes[108].constant, 'AICMD_LOADABILITY');
  // aicmd.h:37 -> index 29; aicmd.inc:189-191 hard-codes `.long 29` for LoadTurnCount and the
  // parser cross-checks every literal opcode against the enum.
  assert.equal(prog.macros.get('loadturncount').opcode, 29);
  assert.equal(prog.opcodes[29].constant, 'AICMD_LOADTURNCOUNT');
});

test('every command macro maps to exactly one opcode and every opcode has a macro', () => {
  const cmdMacros = [...prog.macros.values()].filter((m) => m.kind === 'command');
  assert.equal(cmdMacros.length, 109);
  assert.deepEqual(new Set(cmdMacros.map((m) => m.opcode)).size, 109);
  // Data macros: TableEntry (aicmd.inc:634-636) and LabelDistance (aicmd.inc:638-640).
  assert.deepEqual([...prog.macros.values()].filter((m) => m.kind === 'data').map((m) => m.name).sort(), ['LabelDistance', 'TableEntry']);
});

test('parses the full script', () => {
  // script.s is 8108 lines (`wc -l`); its last line is `.endif`.
  assert.ok(prog.instructions.length > 3000, `instructions: ${prog.instructions.length}`);
  assert.equal(prog.image.length, prog.totalWords);
  // Each instruction's first image word is its opcode.
  for (const ins of prog.instructions) assert.equal(prog.image[ins.word], ins.op);
  // Terminate is the last label: script.s:8105-8106 `Terminate:` / `PopOrEnd`.
  assert.equal(prog.labels.Terminate.line, 8105);
  assert.equal(prog.instructions.at(-1).line, 8106);
  assert.equal(prog.instructions.at(-1).name, 'PopOrEnd');
});

test('section labels are at their script.s lines', () => {
  // research R6 names the League sections but gives no line numbers; these are read from
  // src/battle/trainer_ai/script.s.
  const expected = {
    Basic_Main: 52, // script.s:52
    Expert_Main: 1623, // script.s:1623
    EvalAttack_Main: 6353, // script.s:6353
    SetupFirstTurn_Main: 6417, // script.s:6417
    PrioritizeExtremes_Main: 6499, // script.s:6499
    Terminate: 8105, // script.s:8105
  };
  for (const [label, line] of Object.entries(expected)) {
    assert.ok(prog.labels[label], `missing label ${label}`);
    assert.equal(prog.labels[label].line, line, label);
  }
  // The four League sections run from script.s:52 to the line before PrioritizeExtremes_Main
  // (6498): 6447 lines, matching R6's "~6,450".
  assert.equal(6498 - 52 + 1, 6447);
});

test('gTrainerAITable flag offsets resolve to the sections, bit i = generated/ai_flags.txt name i+1', () => {
  // script.s:18-50: FlagTable, one LabelDistance per bit; ai_flags.txt:1 is AI_FLAG_NONE.
  assert.equal(prog.flagTable.length, 32);
  const byFlag = Object.fromEntries(prog.flagTable.map((f) => [f.flag, f]));
  assert.equal(byFlag.AI_FLAG_BASIC.bit, 0); // script.s:19, ai_flags.txt:2
  assert.equal(byFlag.AI_FLAG_BASIC.label, 'Basic_Main');
  assert.equal(byFlag.AI_FLAG_EVAL_ATTACK.label, 'EvalAttack_Main'); // script.s:20
  assert.equal(byFlag.AI_FLAG_EXPERT.label, 'Expert_Main'); // script.s:21
  assert.equal(byFlag.AI_FLAG_SETUP_FIRST_TURN.bit, 3); // script.s:22
  assert.equal(byFlag.AI_FLAG_SETUP_FIRST_TURN.label, 'SetupFirstTurn_Main');
  assert.equal(byFlag.AI_FLAG_UNUSED_11.label, 'Terminate'); // script.s:30
  // The stored word is the distance from FlagTable (word 0) to the label: the cursor value that
  // TrainerAI_EvalMoves loads (trainer_ai.c:488).
  for (const f of prog.flagTable) {
    assert.equal(prog.image[f.bit], prog.labels[f.label].word);
    assert.equal(prog.instructions[prog.wordToInstr.get(prog.image[f.bit])].line > f.labelLine - 1, true);
  }
});

test('known instructions decode with the right opcode and arguments', () => {
  // script.s:62 `FlagMoveDamageScore USE_MAX_DAMAGE`: AICMD_FLAGMOVEDAMAGESCORE is aicmd.h:40
  // (index 32); USE_MAX_DAMAGE = 0 (constants/battle/trainer_ai.h:45).
  const a = insAt(62);
  assert.equal(a.name, 'FlagMoveDamageScore');
  assert.equal(a.op, 32);
  assert.deepEqual(a.args.map((x) => [x.text, x.value]), [['USE_MAX_DAMAGE', 0]]);

  // script.s:63 `IfLoadedEqualTo AI_NO_COMPARISON_MADE, Basic_CheckSoundproof`: aicmd.h:27 (19);
  // AI_NO_COMPARISON_MADE = 0 (trainer_ai.h:35); label at script.s:115.
  const b = insAt(63);
  assert.equal(b.op, 19);
  assert.equal(b.args[0].value, 0);
  assert.equal(b.args[1].label, 'Basic_CheckSoundproof');
  assert.equal(prog.instructions[b.args[1].targetInstr].line > 115, true);
  // Jump word = target - thisWord - 1 (aicmd.inc:134 `(\jump-.) / 4 - 1`); the handler reads it
  // with the cursor at thisWord + 1 and adds it (trainer_ai.c:786-796, 2752-2755).
  const jw = b.word + 2;
  assert.equal(jw + 1 + prog.image[jw], prog.labels.Basic_CheckSoundproof.word);

  // script.s:1213 `IfLoadedInTable Basic_FlingItems_Poison, Basic_FlingPoison`: the macro is
  // spelled `IfLoadedinTable` in aicmd.inc:167 (case-insensitive match). Table word holds
  // table - thisWord - 2 (aicmd.inc:169); AICmd_IfLoadedInTable reads it after both reads, i.e.
  // with the cursor at opcodeWord + 3 (trainer_ai.c:858-874).
  const c = insAt(1213);
  assert.equal(c.op, 25); // aicmd.h:33
  const ofs = prog.image[c.word + 1];
  const tableWord = c.word + 3 + ofs;
  assert.equal(tableWord, prog.labels.Basic_FlingItems_Poison.word);
  // script.s:1289-1291: HOLD_EFFECT_PSN_USER (generated/item_hold_effects.txt:101 -> 100),
  // HOLD_EFFECT_STRENGTHEN_POISON, TABLE_END (aicmd.inc:632, 0xFFFFFFFF read as int = -1).
  assert.equal(prog.image[tableWord], 100);
  assert.equal(prog.image[tableWord + 2], -1);
});

test('unknown macros and unknown symbols fail loudly (negative controls)', () => {
  assert.throws(() => parseAiScript({ scriptText: 'Start:\n    BogusCommand 1\n' }), /unknown macro BogusCommand/);
  assert.throws(() => parseAiScript({ scriptText: 'Start:\n    AddToMoveScore NOT_A_CONSTANT\n' }), /unknown symbol NOT_A_CONSTANT/);
  assert.throws(() => parseAiScript({ scriptText: 'Start:\n    GoTo Nowhere\n' }), /unknown label Nowhere/);
  assert.throws(() => parseAiScript({ scriptText: 'Start:\n    AddToMoveScore 1, 2\n' }), /takes 1 args, got 2/);
  // Positive control for the same path: a valid one-liner parses.
  const ok = parseAiScript({ scriptText: 'FlagTable:\nStart:\n    AddToMoveScore -5\n    PopOrEnd\n' });
  assert.equal(ok.instructions[0].args[0].value, -5);
});

test('League sections: reachable opcodes and usage counts', () => {
  // League trainer flags: res/trainers/data/elite_four_aaron.json:8-12 (and bertha, flint,
  // champion_cynthia.json:10-14) BASIC/EVAL_ATTACK/EXPERT; elite_four_lucian.json:8-13 adds
  // SETUP_FIRST_TURN.
  assert.deepEqual(LEAGUE_FLAGS, ['AI_FLAG_BASIC', 'AI_FLAG_EVAL_ATTACK', 'AI_FLAG_EXPERT', 'AI_FLAG_SETUP_FIRST_TURN']);
  const u = opcodeUsage(prog);
  assert.equal(u.counts.length, 77);
  const names = new Set(u.counts.map((c) => c.name));
  // Positive: EvalAttack_Main's IfCurrentMoveKills (script.s:6358) is reachable.
  assert.ok(names.has('IfCurrentMoveKills'));
  // Negative, with the positive control above: the doubles-only partner check
  // CheckIfHighestDamageWithPartner (TagStrategy section) is not reachable from League flags,
  // but is reachable from AI_FLAG_TAG_STRATEGY.
  assert.ok(!names.has('CheckIfHighestDamageWithPartner'));
  const tag = opcodeUsage(prog, ['AI_FLAG_TAG_STRATEGY']);
  assert.ok(tag.counts.some((c) => c.name === 'CheckIfHighestDamageWithPartner'));
  // Dummy3E/Dummy3F never advance the cursor (trainer_ai.c:1881-1889); they must be unreachable.
  assert.ok(!names.has('Dummy3E') && !names.has('Dummy3F'));
  // Counts add up to the reachable instruction count.
  assert.equal(u.counts.reduce((s, c) => s + c.count, 0), u.reachable.size);
  // No reachable League instruction names a partner battler (singles have none).
  for (const i of u.reachable) {
    for (const a of prog.instructions[i].args) assert.ok(!/PARTNER/.test(a.text), `line ${prog.instructions[i].line}`);
  }
  assert.ok(reachableFrom(prog, ['SetupFirstTurn_Main']).size > 0);
});
