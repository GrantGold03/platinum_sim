// Feature 017 (specs/017-exact-dispatch-speedups/contracts/interp-api.md; FR-004, FR-005, SC-004): the parse-time
// dispatch tables on runs of consecutive IfCurrentMoveEffectEqualTo instructions (TAI:1441-1451), the by-name
// argument index, and the interpreter step counters.
//
// Reference for the tables (Constitution VI): stepping through the run's instructions as the handler would, computed
// here from the instruction list for every defined effect value plus undefined ones; the structure facts (13 runs,
// lengths below) are those of the pinned decomp script measured on 2026-11-02; a decomp bump changes them.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { aiProgram } from '../ai/choose.mjs';
import { effectRuns, parseAiScript } from '../ai/parse.mjs';
import { INTERP_STATS, makeCtx } from '../ai/interp.mjs';
import { decide } from '../ai/opponent.mjs';
import { B, leagueBattle, stubRng } from './ai_fixtures.mjs';

const prog = aiProgram();
const OP = 'IfCurrentMoveEffectEqualTo';
const EFFECT_LIST = prog.constants.loadGenerated('move_battle_effects');
const EFFECTS = EFFECT_LIST.map((e) => e.value);
const UNDEFINED_VALUES = [-1, 100000];
const EXPECTED_LENGTHS = [178, 152, 5, 5, 5, 5, 4, 3, 2, 2, 1, 1, 1]; // sums to 364

// The reference: evaluate instructions start..end in order for effect e (first match jumps, else fall through).
function walk(p, start, end, e) {
  for (let k = start; k <= end; k++) {
    const ins = p.instructions[k];
    if ((ins.a.battle_effect | 0) === e) return ins.jt.jump;
  }
  return end + 1;
}
const answer = (head, e) => head.dispatch.table.get(e) ?? head.dispatch.after;
const values = () => [...EFFECTS, ...UNDEFINED_VALUES];

test('017 structure: 13 runs on the real script, no splits, tables on runs >= 2, one repeated value (first wins), every instruction indexed', () => {
  const runs = effectRuns(prog);
  const lengths = runs.map((r) => r.end - r.start + 1).sort((a, b) => b - a);
  assert.deepEqual(lengths, EXPECTED_LENGTHS, 'run lengths of the pinned decomp script (2026-11-02)');
  assert.equal(lengths.reduce((a, b) => a + b, 0), prog.instructions.filter((i) => i.name === OP).length);
  assert.ok(runs.every((r) => r.split === false), 'no entry point lands inside a run of the real script');
  const heads = prog.instructions.filter((i) => i.dispatch);
  assert.equal(heads.length, runs.filter((r) => r.end > r.start).length, 'one table per run of length >= 2');
  for (const r of runs) {
    const head = prog.instructions[r.start];
    for (let k = r.start; k <= r.end; k++) assert.equal(prog.instructions[k].name, OP);
    if (r.end > r.start) {
      assert.ok(head.dispatch, `head at ${r.start} has a table`);
      assert.equal(head.dispatch.length, r.end - r.start + 1);
      assert.equal(head.dispatch.after, r.end + 1);
      for (let k = r.start + 1; k <= r.end; k++) assert.equal(prog.instructions[k].dispatch, undefined);
    } else {
      assert.equal(head.dispatch, undefined, 'a run of one check has no table');
    }
  }
  let repeats = 0;
  for (const r of runs) {
    const seen = new Map();
    for (let k = r.start; k <= r.end; k++) {
      const ins = prog.instructions[k];
      const v = ins.a.battle_effect | 0;
      if (seen.has(v)) { repeats++; assert.equal(prog.instructions[r.start].dispatch.table.get(v), seen.get(v), 'first entry wins'); } else seen.set(v, ins.jt.jump);
    }
  }
  assert.equal(repeats, 1, 'exactly one repeated effect value inside a run');
  for (const ins of prog.instructions) {
    assert.deepEqual(Object.keys(ins.a).sort(), ins.args.map((a) => a.name).sort(), `ins.a keys at script.s:${ins.line}`);
    assert.deepEqual(Object.keys(ins.jt).sort(), ins.args.filter((a) => a.kind === 'jump').map((a) => a.name).sort());
    for (const a of ins.args) {
      assert.equal(ins.a[a.name], a.value);
      if (a.kind === 'jump') assert.equal(ins.jt[a.name], a.targetInstr);
    }
  }
});

test('017 exhaustive equivalence: every table x every defined effect value (+2 undefined) equals the step-by-step walk', (t) => {
  const runs = effectRuns(prog).filter((r) => r.end > r.start);
  let compared = 0;
  for (const r of runs) {
    const head = prog.instructions[r.start];
    for (const e of values()) {
      assert.equal(answer(head, e), walk(prog, r.start, r.end, e), `run at ${r.start} (script.s:${head.line}), effect ${e}`);
      compared++;
    }
  }
  assert.ok(compared >= 10 * (EFFECTS.length + 2), `${compared} comparisons`);
  t.diagnostic(`dispatch equivalence: ${runs.length} tables x ${EFFECTS.length + 2} effect values = ${compared} comparisons, 0 mismatches`);
});

test('017 positive controls: a retargeted or deleted table entry is detected by the walk', () => {
  const run = effectRuns(prog).reduce((best, r) => (r.end - r.start > best.end - best.start ? r : best));
  const head = prog.instructions[run.start];
  const [someKey] = head.dispatch.table.keys();
  const retargeted = { ...head, dispatch: { ...head.dispatch, table: new Map(head.dispatch.table) } };
  retargeted.dispatch.table.set(someKey, head.dispatch.after);
  const deleted = { ...head, dispatch: { ...head.dispatch, table: new Map(head.dispatch.table) } };
  deleted.dispatch.table.delete(someKey);
  const mism = (h) => values().filter((e) => answer(h, e) !== walk(prog, run.start, run.end, e)).length;
  assert.ok(mism(retargeted) >= 1, 'retargeted entry reported');
  assert.ok(mism(deleted) >= 1, 'deleted entry reported');
  assert.equal(mism(head), 0, 'control: the real table has no mismatch');
});

test('017 split: a label inside a run splits it into two runs whose tables agree with the walk from each entry', () => {
  const [e0, e1, e2, e3] = EFFECT_LIST.map((e) => e.name);
  const scriptText = [
    'FlagTable:',
    'Start:',
    `    ${OP} ${e0}, T0`,
    `    ${OP} ${e1}, T1`,
    'Mid:',
    `    ${OP} ${e2}, T2`,
    `    ${OP} ${e3}, T3`,
    '    PopOrEnd',
    'T0:', '    AddToMoveScore 1', '    PopOrEnd',
    'T1:', '    AddToMoveScore 2', '    PopOrEnd',
    'T2:', '    AddToMoveScore 3', '    PopOrEnd',
    'T3:', '    AddToMoveScore 4', '    PopOrEnd',
    'Again:', '    GoTo Mid',
    '',
  ].join('\n');
  const p = parseAiScript({ scriptText });
  const runs = effectRuns(p);
  assert.deepEqual(runs.map((r) => [r.start, r.end, r.split]), [[0, 1, false], [2, 3, true]]);
  for (const r of runs) {
    const head = p.instructions[r.start];
    assert.ok(head.dispatch);
    assert.equal(head.dispatch.after, r.end + 1);
    for (const e of [...p.constants.loadGenerated('move_battle_effects').map((x) => x.value), -1]) {
      assert.equal(answer(head, e), walk(p, r.start, r.end, e), `split run at ${r.start}, effect ${e}`);
    }
  }
  // Entering at Mid must skip the first two checks: the first run's effects are not answered by the second table.
  const mid = p.instructions[2];
  assert.equal(answer(mid, mid.a.battle_effect | 0), mid.jt.jump);
  assert.equal(answer(mid, p.instructions[0].a.battle_effect | 0), 4);
});

test('017 arguments by name: same values, same errors for a missing argument or jump target (FR-005)', () => {
  const ctx = makeCtx({ prog, ai: {}, mem: {}, rand: () => 0 });
  const add = prog.instructions.find((i) => i.name === 'AddToMoveScore');
  const goTo = prog.instructions.find((i) => i.name === 'GoTo');
  assert.equal(ctx.arg(add, 'i'), add.args[0].value);
  assert.throws(() => ctx.arg(add, 'nope'), /AddToMoveScore \(script\.s:\d+\) has no argument nope/);
  assert.equal(ctx.target(goTo), goTo.args.find((a) => a.kind === 'jump').targetInstr);
  assert.throws(() => ctx.target(add), /AddToMoveScore \(script\.s:\d+\) has no jump target jump/);
});

test('017 runtime: one golden decision dispatches runs and stays far below a stepped evaluation', (t) => {
  const x = leagueBattle('elite_four_aaron', [B('alakazam', 56, ['psychic', 'shadow_ball', 'energy_ball', 'calm_mind'], 'ABILITY_SYNCHRONIZE')], { rng: stubRng([], 255) });
  const s0 = { ...INTERP_STATS };
  const r = decide(x.st, x.p2);
  assert.equal(r.kind, 'move');
  const steps = INTERP_STATS.steps - s0.steps, dispatches = INTERP_STATS.dispatches - s0.dispatches;
  assert.ok(dispatches >= 4, `${dispatches} dispatches (at least one per move slot)`);
  assert.ok(steps < 2000, `${steps} steps for one decision (the two long runs alone would be 330 per visit when stepped)`);
  t.diagnostic(`one Aaron decision: ${steps} interpreter steps, ${dispatches} dispatched runs`);
});
