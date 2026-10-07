// T038: parse the decomp's trainer-AI bytecode source into an instruction list.
//
// Inputs (all under pokeplatinum/, never edited):
//   - include/data/scripts/aicmd.h: the opcode table. Each ScriptCommand(AICMD_X, AICmd_X) line is
//     one opcode; data/scripts/cmd_table.h:13-21 numbers them from 0 in file order (`new_enum`
//     starts __enum__ at 0, `inc_enum` assigns then increments). The same list is the C handler
//     table sAICommandTable (src/battle/trainer_ai/trainer_ai.c:207-209).
//   - asm/macros/aicmd.inc: one `.macro` per command. Each `.long` in the body is one 32-bit word:
//       `.long AICMD_X` or `.long <int>`      opcode word
//       `.long \p`                            plain argument (constant expression)
//       `.long (\p-.) / 4 - K`                label relative to this word (K=1 jumps, K=2 tables)
//       `.long (\a-\b) / 4`                   label distance (LabelDistance, aicmd.inc:638-640)
//     GNU as matches macro names case-insensitively, which script.s relies on: it calls
//     `IfLoadedInTable` while aicmd.inc:167 defines `IfLoadedinTable`.
//   - src/battle/trainer_ai/script.s: labels, macro calls, data (TableEntry/LabelDistance).
//
// The cursor model mirrors the game: the script is an array of 32-bit words
// (battleCtx->aiScriptTemp = gTrainerAITable, battle_controller_player.c:4816), read as `int`
// (AIScript_Read, trainer_ai.c:2726-2732). A jump word holds (target - thisWord - 1): handlers read
// it, which leaves the cursor at thisWord + 1, then AIScript_Iter(jump) (trainer_ai.c:2752-2755)
// lands on the target. A table word (IfLoadedInTable, trainer_ai.c:858-874) holds
// (table - thisWord - 2), read via AIScript_ReadOffset(cursor + ofs) with the cursor two words past
// it, i.e. after both argument reads.
//
// Output of parseAiScript():
//   { opcodes, macros, labels, instructions, data, image, wordToInstr, flagTable, symbolsUsed }
//   instructions[i] = { index, op, name, args:[{name, kind, text, value, label?, targetWord?,
//                       targetInstr?}], line, word, size }
//   image: Int32Array of every word of gTrainerAITable, exactly what the game reads.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { DECOMP_ROOT, loadConstants, readList } from './constants.mjs';

export const SCRIPT_PATH = 'src/battle/trainer_ai/script.s';
export const MACRO_PATH = 'asm/macros/aicmd.inc';
export const OPCODE_PATH = 'include/data/scripts/aicmd.h';
export const HANDLER_PATH = 'src/battle/trainer_ai/trainer_ai.c';

const readLines = (root, rel) => readFileSync(join(root, rel), 'utf8').split('\n');

// ---------- opcode table ----------

export function parseOpcodes(root = DECOMP_ROOT) {
  const ops = [];
  readLines(root, OPCODE_PATH).forEach((line, i) => {
    const m = line.match(/^ScriptCommand\(\s*(AICMD_\w+)\s*,\s*(\w+)\s*\)/);
    if (m) ops.push({ index: ops.length, constant: m[1], func: m[2], src: `${OPCODE_PATH}:${i + 1}` });
  });
  if (ops.length === 0) throw new Error(`parse: no ScriptCommand lines in ${OPCODE_PATH}`);
  // Handler definition lines in trainer_ai.c, for citations.
  const handlerLines = new Map();
  readLines(root, HANDLER_PATH).forEach((line, i) => {
    const m = line.match(/^static void (AICmd_\w+)\(BattleSystem \*battleSys, BattleContext \*battleCtx\)$/);
    if (m) handlerLines.set(m[1], i + 1);
  });
  for (const op of ops) {
    const l = handlerLines.get(op.func);
    if (!l) throw new Error(`parse: no handler definition for ${op.func} in ${HANDLER_PATH}`);
    op.handler = `${HANDLER_PATH}:${l}`;
  }
  return ops;
}

// ---------- macro definitions ----------

export function parseMacros(root = DECOMP_ROOT, opcodes = parseOpcodes(root)) {
  const byConst = new Map(opcodes.map((o) => [o.constant, o]));
  const macros = new Map(); // lower-case name -> def
  const lines = readLines(root, MACRO_PATH);
  let cur = null;
  lines.forEach((raw, i) => {
    const line = raw.trim();
    const src = `${MACRO_PATH}:${i + 1}`;
    let m;
    if ((m = line.match(/^\.macro\s+(\w+)\s*(.*)$/))) {
      const params = m[2].trim() === '' ? [] : m[2].split(',').map((p) => {
        const pm = p.trim().match(/^(\w+)(?::req|=(.*))?$/);
        if (!pm) throw new Error(`parse: bad macro parameter ${JSON.stringify(p)} at ${src}`);
        return pm[1];
      });
      cur = { name: m[1], params, words: [], src };
      return;
    }
    if (line === '.endm') {
      if (!cur) throw new Error(`parse: .endm without .macro at ${src}`);
      finishMacro(cur, byConst);
      const key = cur.name.toLowerCase();
      if (macros.has(key)) throw new Error(`parse: duplicate macro ${cur.name} at ${src}`);
      macros.set(key, cur);
      cur = null;
      return;
    }
    if (!cur) return; // .equ / #include lines outside macros are handled by constants.mjs
    if ((m = line.match(/^\.long\s+(.+)$/))) {
      const body = m[1].trim();
      let w;
      if (/^AICMD_\w+$/.test(body)) w = { kind: 'opcode', constant: body };
      else if (/^\d+$/.test(body)) w = { kind: 'opcode', literal: Number(body) };
      else if ((w = body.match(/^\\(\w+)$/))) w = { kind: 'arg', param: w[1] };
      else if ((w = body.match(/^\(\\(\w+)-\.\)\s*\/\s*4\s*-\s*(\d+)$/))) w = { kind: Number(w[2]) === 1 ? 'jump' : 'table', param: w[1], bias: Number(w[2]) };
      else if ((w = body.match(/^\(\\(\w+)-\\(\w+)\)\s*\/\s*4$/))) w = { kind: 'distance', param: w[1], from: w[2] };
      else throw new Error(`parse: unknown .long form ${JSON.stringify(body)} at ${src}`);
      w.src = src;
      cur.words.push(w);
      return;
    }
    if (line !== '') throw new Error(`parse: unknown line inside macro ${cur.name}: ${JSON.stringify(line)} at ${src}`);
  });
  if (cur) throw new Error(`parse: unterminated macro ${cur.name}`);
  return macros;
}

function finishMacro(mac, byConst) {
  const first = mac.words[0];
  if (first && first.kind === 'opcode') {
    // The opcode is the AICMD_ constant whose name is the macro name upper-cased.
    const expect = `AICMD_${mac.name.toUpperCase()}`;
    const op = byConst.get(expect);
    if (!op) throw new Error(`parse: macro ${mac.name} (${mac.src}) has no ${expect} in ${OPCODE_PATH}`);
    if (first.constant && first.constant !== expect) throw new Error(`parse: macro ${mac.name} emits ${first.constant}, expected ${expect} (${mac.src})`);
    // Some macros hard-code the number (e.g. `LoadTurnCount` -> `.long 29`); it must equal the enum.
    if (first.literal !== undefined && first.literal !== op.index) {
      throw new Error(`parse: macro ${mac.name} emits ${first.literal} but ${expect} = ${op.index} (${mac.src})`);
    }
    mac.opcode = op.index;
    mac.kind = 'command';
  } else {
    mac.kind = 'data';
  }
  for (const w of mac.words.slice(mac.kind === 'command' ? 1 : 0)) {
    if (w.kind === 'opcode') throw new Error(`parse: opcode word in the middle of ${mac.name} (${w.src})`);
    if (!mac.params.includes(w.param)) throw new Error(`parse: ${mac.name} uses unknown parameter \\${w.param} (${w.src})`);
  }
  mac.size = mac.words.length;
}

// ---------- script ----------

function splitArgs(text) {
  const out = [];
  let depth = 0;
  let cur = '';
  for (const ch of text) {
    if (ch === '(') depth++;
    if (ch === ')') depth--;
    if (ch === ',' && depth === 0) { out.push(cur.trim()); cur = ''; continue; }
    cur += ch;
  }
  if (cur.trim() !== '') out.push(cur.trim());
  return out;
}

const IGNORED_DIRECTIVES = /^\.(ifndef|set|text|global|endif)\b/;

// `scriptText` replaces script.s (used by tests for negative controls).
export function parseAiScript({ root = DECOMP_ROOT, scriptText } = {}) {
  const constants = loadConstants(root);
  const opcodes = parseOpcodes(root);
  const macros = parseMacros(root, opcodes);
  const lines = scriptText !== undefined ? scriptText.split('\n') : readLines(root, SCRIPT_PATH);

  // Pass 1: labels and word addresses.
  const labels = {};
  const items = []; // {mac, args, line, word}
  let word = 0;
  lines.forEach((raw, i) => {
    const lineNo = i + 1;
    let text = raw.replace(/\/\/.*$/, '').trim();
    if (text === '') return;
    if (text.startsWith('#include') || IGNORED_DIRECTIVES.test(text)) return;
    let m = text.match(/^([A-Za-z_]\w*):\s*(.*)$/);
    if (m) {
      if (labels[m[1]]) throw new Error(`parse: duplicate label ${m[1]} at ${SCRIPT_PATH}:${lineNo}`);
      labels[m[1]] = { name: m[1], line: lineNo, word };
      text = m[2].trim();
      if (text === '') return;
    }
    m = text.match(/^([A-Za-z_]\w*)\s*(.*)$/);
    if (!m) throw new Error(`parse: cannot parse ${JSON.stringify(raw)} at ${SCRIPT_PATH}:${lineNo}`);
    const mac = macros.get(m[1].toLowerCase());
    if (!mac) throw new Error(`parse: unknown macro ${m[1]} at ${SCRIPT_PATH}:${lineNo}`);
    const args = splitArgs(m[2]);
    if (args.length !== mac.params.length) {
      throw new Error(`parse: ${mac.name} takes ${mac.params.length} args, got ${args.length} at ${SCRIPT_PATH}:${lineNo}`);
    }
    items.push({ mac, args, line: lineNo, word, callName: m[1] });
    word += mac.size;
  });
  const totalWords = word;

  // Pass 2: resolve every word.
  const image = new Int32Array(totalWords);
  const instructions = [];
  const data = [];
  const wordToInstr = new Map();
  const symbolsUsed = new Map(); // symbol -> {value, src, count}
  const labelWord = (name, where) => {
    const l = labels[name];
    if (!l) throw new Error(`parse: unknown label ${name} at ${where}`);
    return l.word;
  };
  const evalArg = (text, where) => constants.eval(text, where);
  for (const it of items) {
    const where = `${SCRIPT_PATH}:${it.line}`;
    const named = Object.fromEntries(it.mac.params.map((p, k) => [p, it.args[k]]));
    const outArgs = [];
    it.mac.words.forEach((w, k) => {
      const at = it.word + k;
      let value;
      if (w.kind === 'opcode') {
        value = it.mac.opcode;
      } else if (w.kind === 'arg') {
        const text = named[w.param];
        value = evalArg(text, where);
        for (const id of text.match(/[A-Za-z_]\w*/g) || []) {
          const s = symbolsUsed.get(id) || { value: constants.get(id), src: constants.src(id), count: 0 };
          s.count++;
          symbolsUsed.set(id, s);
        }
        outArgs.push({ name: w.param, kind: 'value', text, value });
      } else if (w.kind === 'jump' || w.kind === 'table') {
        const text = named[w.param];
        const target = labelWord(text, where);
        value = target - at - w.bias;
        outArgs.push({ name: w.param, kind: w.kind, text, label: text, value, targetWord: target });
      } else if (w.kind === 'distance') {
        const a = labelWord(named[w.param], where);
        const b = labelWord(named[w.from], where);
        value = a - b;
        outArgs.push({ name: w.param, kind: 'distance', text: named[w.param], label: named[w.param], from: named[w.from], value, targetWord: a });
      }
      image[at] = value | 0;
    });
    if (it.mac.kind === 'command') {
      const ins = { index: instructions.length, op: it.mac.opcode, name: it.mac.name, args: outArgs, line: it.line, word: it.word, size: it.mac.size };
      wordToInstr.set(it.word, ins.index);
      instructions.push(ins);
    } else {
      data.push({ name: it.mac.name, args: outArgs, line: it.line, word: it.word, size: it.mac.size });
    }
  }
  for (const ins of instructions) {
    for (const a of ins.args) if (a.kind === 'jump') {
      a.targetInstr = wordToInstr.get(a.targetWord);
      if (a.targetInstr === undefined) throw new Error(`parse: jump to ${a.label} (word ${a.targetWord}) is not an instruction, ${SCRIPT_PATH}:${ins.line}`);
    }
  }
  for (const l of Object.values(labels)) l.instr = wordToInstr.get(l.word);

  const flagTable = resolveFlagTable({ root, labels, data, lines });
  return { opcodes, macros, labels, instructions, data, image, wordToInstr, flagTable, symbolsUsed, totalWords, constants };
}

// gTrainerAITable starts with FlagTable (script.s:15-18): one LabelDistance per thinking-mask bit.
// TrainerAI_EvalMoves sets the cursor to aiScriptTemp[thinkingBitShift] (trainer_ai.c:488), and
// TrainerAI_MainSingles tests bit 0 with AI_FLAG_BASIC while shifting the mask right and
// incrementing thinkingBitShift (trainer_ai.c:297-309). So FlagTable entry i belongs to bit i.
// Bit-to-name: generated/ai_flags.txt lists AI_FLAG_NONE first (the zero mask) and AI_FLAG_ALL
// last; the remaining names in order are bits 0..31. Each script.s FlagTable line carries the flag
// name as a comment, and this function fails if the two orders disagree.
function resolveFlagTable({ root, labels, data, lines }) {
  const flagNames = readList('ai_flags', root).map((e) => e.raw).filter((n) => n !== 'AI_FLAG_NONE' && n !== 'AI_FLAG_ALL');
  const start = labels.FlagTable;
  if (!start || start.word !== 0) throw new Error('parse: FlagTable must be at word 0 of gTrainerAITable');
  const entries = data.filter((d) => d.name === 'LabelDistance' && d.args[0].from === 'FlagTable')
    .sort((a, b) => a.word - b.word);
  return entries.map((d, i) => {
    if (d.word !== i) throw new Error(`parse: FlagTable entry ${i} not at word ${i}`);
    const comment = (lines[d.line - 1].match(/\/\/\s*(AI_FLAG_\w+)/) || [])[1];
    if (comment !== flagNames[i]) {
      throw new Error(`parse: FlagTable entry ${i} comment ${comment} != generated/ai_flags.txt bit ${i} ${flagNames[i]} (${SCRIPT_PATH}:${d.line})`);
    }
    return { bit: i, flag: flagNames[i], label: d.args[0].label, word: d.args[0].value, line: d.line, labelLine: labels[d.args[0].label].line };
  });
}

// ---------- reachability ----------

// Control-flow successors of one instruction, per the handlers in trainer_ai.c:
//   GoTo (:2561): only the target.  PushAndGoTo (:2554): the target; the return lands on the next
//   instruction (PopOrEnd pops it, :2568), so the fall-through is also reachable.
//   PopOrEnd (:2568) and Escape (:1875): no static successor.
//   Dummy3E (:1881) / Dummy3F (:1886): return without moving the cursor, so the game re-executes
//   them forever; no successor (and the caller should treat reaching them as an error).
//   Every other command: fall-through, plus its jump target if it has one.
export function successors(prog, ins) {
  const next = prog.wordToInstr.get(ins.word + ins.size);
  const jumps = ins.args.filter((a) => a.kind === 'jump').map((a) => a.targetInstr);
  switch (ins.name) {
    case 'GoTo': return jumps;
    case 'PushAndGoTo': return [...jumps, next].filter((x) => x !== undefined);
    case 'PopOrEnd': case 'Escape': case 'Dummy3E': case 'Dummy3F': return [];
    default: return [...jumps, next].filter((x) => x !== undefined);
  }
}

export function reachableFrom(prog, labelNames) {
  const seen = new Set();
  const stack = labelNames.map((n) => {
    const l = prog.labels[n];
    if (!l || l.instr === undefined) throw new Error(`parse: label ${n} is not an instruction`);
    return l.instr;
  });
  while (stack.length) {
    const i = stack.pop();
    if (seen.has(i)) continue;
    seen.add(i);
    for (const s of successors(prog, prog.instructions[i])) stack.push(s);
  }
  return seen;
}

// The four flags the League trainers use. Source: res/trainers/data/elite_four_{aaron,bertha,
// flint}.json:8-12 and champion_cynthia.json:10-14 list BASIC, EVAL_ATTACK, EXPERT;
// elite_four_lucian.json:8-13 adds SETUP_FIRST_TURN.
export const LEAGUE_FLAGS = ['AI_FLAG_BASIC', 'AI_FLAG_EVAL_ATTACK', 'AI_FLAG_EXPERT', 'AI_FLAG_SETUP_FIRST_TURN'];

// Per-opcode usage: static instruction counts over the instructions reachable from `flags`.
export function opcodeUsage(prog, flags = LEAGUE_FLAGS) {
  const entry = flags.map((f) => {
    const e = prog.flagTable.find((x) => x.flag === f);
    if (!e) throw new Error(`parse: no FlagTable entry for ${f}`);
    return e.label;
  });
  const reach = reachableFrom(prog, entry);
  const counts = new Map();
  for (const i of reach) {
    const ins = prog.instructions[i];
    const c = counts.get(ins.op) || { op: ins.op, name: ins.name, count: 0, firstLine: ins.line };
    c.count++;
    c.firstLine = Math.min(c.firstLine, ins.line);
    counts.set(ins.op, c);
  }
  return { entry, reachable: reach, counts: [...counts.values()].sort((a, b) => a.op - b.op) };
}

// CLI: `node sim/ai/parse.mjs` prints a summary (used to build sim/ai/OPCODES.md).
if (import.meta.url === `file://${process.argv[1]}`) {
  const prog = parseAiScript();
  const u = opcodeUsage(prog);
  console.log(JSON.stringify({
    opcodes: prog.opcodes.length,
    instructions: prog.instructions.length,
    dataItems: prog.data.length,
    words: prog.totalWords,
    labels: Object.keys(prog.labels).length,
    flagTable: prog.flagTable.map((f) => `${f.bit} ${f.flag} -> ${f.label} (line ${f.labelLine})`),
    leagueReachableInstructions: u.reachable.size,
    leagueOpcodes: u.counts.length,
    usage: u.counts.map((c) => `${c.op} ${c.name} x${c.count} (first ${SCRIPT_PATH}:${c.firstLine}) ${prog.opcodes[c.op].handler}`),
  }, null, 1));
}
