// Decomp constant resolution for the AI interpreter (T038/T039).
//
// Game facts come only from pokeplatinum/ (Constitution I). This module reads:
//   - C headers under pokeplatinum/include/ (object-like `#define NAME expr`), following
//     `#include "..."` recursively;
//   - metang constant lists pokeplatinum/generated/<name>.txt, which the build turns into
//     generated/<name>.h (pokeplatinum/generated/meson.build:13-17 and the foreach at the end of
//     the generator table). Enum lists use C-enum numbering: first name = 0, each next name = +1,
//     `NAME = X` sets the value (same reading as src/platsim/decomp/constants.py, T011).
//     Mask lists (meson.build `'type': 'mask'`, e.g. ai_flags at generated/meson.build:17) are NOT
//     given numeric values here: only their names in file order are exposed (maskNames()).
//   - the `.equ` lines of pokeplatinum/asm/macros/aicmd.inc (FALSE/TRUE at :3-4, TABLE_END at :632).
//
// Every resolved symbol carries a `src` "path:line" reference.
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
export const DECOMP_ROOT = join(here, '../../pokeplatinum');

const IDENT = /^[A-Za-z_][A-Za-z0-9_]*$/;

// ---------- expression evaluation (C integer expressions, int32 results) ----------

function tokenize(text, where) {
  const toks = [];
  const re = /\s*(0[xX][0-9a-fA-F]+|\d+)[uUlL]*|\s*([A-Za-z_][A-Za-z0-9_]*)|\s*(<<|>>|<=|>=|==|!=|&&|\|\||[-+*/%()~!&|^<>])|\s+/y;
  let i = 0;
  while (i < text.length) {
    re.lastIndex = i;
    const m = re.exec(text);
    if (!m || m[0].length === 0) throw new Error(`constants: cannot tokenize ${JSON.stringify(text)} at ${where}`);
    i = re.lastIndex;
    if (m[1] !== undefined) toks.push({ t: 'num', v: Number(BigInt(m[1])) });
    else if (m[2] !== undefined) toks.push({ t: 'id', v: m[2] });
    else if (m[3] !== undefined) toks.push({ t: 'op', v: m[3] });
  }
  return toks;
}

const BINARY = [
  ['||'], ['&&'], ['|'], ['^'], ['&'], ['==', '!='], ['<', '<=', '>', '>='], ['<<', '>>'], ['+', '-'], ['*', '/', '%'],
];

// Evaluates `text` with identifiers resolved by `lookup(name) -> number`. Results are int32
// (the AI script words are read as `int`, trainer_ai.c:2728).
export function evalExpr(text, lookup, where = '?') {
  const toks = tokenize(text, where);
  let p = 0;
  const peek = () => toks[p];
  const fail = (msg) => { throw new Error(`constants: ${msg} in ${JSON.stringify(text)} at ${where}`); };
  function primary() {
    const t = toks[p++];
    if (!t) fail('unexpected end');
    if (t.t === 'num') return t.v | 0;
    if (t.t === 'id') return lookup(t.v) | 0;
    if (t.v === '(') { const v = binary(0); if (!toks[p] || toks[p].v !== ')') fail('missing )'); p++; return v; }
    if (t.v === '-') return (-primary()) | 0;
    if (t.v === '+') return primary();
    if (t.v === '~') return ~primary();
    if (t.v === '!') return primary() ? 0 : 1;
    fail(`unexpected ${t.v}`);
  }
  function binary(level) {
    if (level === BINARY.length) return primary();
    let left = binary(level + 1);
    while (peek() && peek().t === 'op' && BINARY[level].includes(peek().v)) {
      const op = toks[p++].v;
      const right = binary(level + 1);
      switch (op) {
        case '||': left = left || right ? 1 : 0; break;
        case '&&': left = left && right ? 1 : 0; break;
        case '|': left |= right; break;
        case '^': left ^= right; break;
        case '&': left &= right; break;
        case '==': left = left === right ? 1 : 0; break;
        case '!=': left = left !== right ? 1 : 0; break;
        case '<': left = left < right ? 1 : 0; break;
        case '<=': left = left <= right ? 1 : 0; break;
        case '>': left = left > right ? 1 : 0; break;
        case '>=': left = left >= right ? 1 : 0; break;
        case '<<': left <<= right; break;
        case '>>': left >>= right; break;
        case '+': left = (left + right) | 0; break;
        case '-': left = (left - right) | 0; break;
        case '*': left = Math.imul(left, right); break;
        case '/': if (right === 0) fail('division by zero'); left = Math.trunc(left / right) | 0; break;
        case '%': if (right === 0) fail('modulo by zero'); left = (left % right) | 0; break;
        default: fail(`bad op ${op}`);
      }
    }
    return left;
  }
  const v = binary(0);
  if (p !== toks.length) fail(`trailing tokens from ${toks[p].v}`);
  return v;
}

// ---------- metang lists ----------

function maskGenerators(root) {
  const text = readFileSync(join(root, 'generated/meson.build'), 'utf8');
  return new Set([...text.matchAll(/'(\w+)':\s*\{\s*'type':\s*'mask'/g)].map((m) => m[1]));
}

// Returns [{name, line}] for a generated/<name>.txt list, in file order.
export function readList(name, root = DECOMP_ROOT) {
  const path = join(root, 'generated', `${name}.txt`);
  return readFileSync(path, 'utf8').split('\n').map((raw, i) => ({ raw: raw.trim(), line: i + 1 }))
    .filter((e) => e.raw && !e.raw.startsWith('#'));
}

// ---------- the symbol table ----------

export class Constants {
  constructor(root = DECOMP_ROOT) {
    this.root = root;
    this.defs = new Map(); // name -> {expr, src} | {value, src}
    this.values = new Map(); // name -> number (memo)
    this.masks = maskGenerators(root);
    this.loadedFiles = new Set();
    this.lists = new Map(); // generated list name -> [{name, value, src}]
  }

  rel(path) { return relative(this.root, path); }

  define(name, entry) {
    if (!this.defs.has(name)) this.defs.set(name, entry);
  }

  // Load a metang list. Enums get values; masks only get their names recorded.
  loadGenerated(name) {
    if (this.lists.has(name)) return this.lists.get(name);
    const path = join(this.root, 'generated', `${name}.txt`);
    if (!existsSync(path)) return null;
    const out = [];
    const isMask = this.masks.has(name);
    let next = 0;
    for (const { raw, line } of readList(name, this.root)) {
      const m = raw.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*(\S+))?\s*$/);
      if (!m) throw new Error(`constants: bad line ${JSON.stringify(raw)} at ${this.rel(path)}:${line}`);
      const src = `${this.rel(path)}:${line}`;
      if (isMask) { out.push({ name: m[1], src }); continue; }
      if (m[2] !== undefined) next = evalExpr(m[2], (id) => this.get(id), src);
      out.push({ name: m[1], value: next, src });
      this.define(m[1], { value: next, src });
      next += 1;
    }
    this.lists.set(name, out);
    return out;
  }

  // Load a header (relative to include/) and its #includes, recursively.
  loadHeader(incPath) {
    const gen = incPath.match(/^generated\/(\w+)\.h$/);
    if (gen) { this.loadGenerated(gen[1]); return; }
    const path = join(this.root, 'include', incPath);
    if (this.loadedFiles.has(path) || !existsSync(path)) return;
    this.loadedFiles.add(path);
    const lines = readFileSync(path, 'utf8').split('\n');
    for (let i = 0; i < lines.length; i++) {
      const startLine = i + 1;
      let text = lines[i];
      while (text.endsWith('\\') && i + 1 < lines.length) text = text.slice(0, -1) + ' ' + lines[++i];
      text = text.replace(/\/\*.*?\*\//g, '').replace(/\/\/.*$/, '');
      const inc = text.match(/^\s*#\s*include\s+"([^"]+)"/);
      if (inc) { this.loadHeader(inc[1]); continue; }
      const def = text.match(/^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)(\(?)\s*(.*?)\s*$/);
      if (def && def[2] !== '(' && def[3] !== '') {
        this.define(def[1], { expr: def[3], src: `${this.rel(path)}:${startLine}` });
      }
    }
  }

  // aicmd.inc `.equ NAME, value` lines.
  loadEqu(asmPath) {
    const path = join(this.root, asmPath);
    readFileSync(path, 'utf8').split('\n').forEach((line, i) => {
      const m = line.match(/^\s*\.equ\s+([A-Za-z_]\w*)\s*,\s*(.+?)\s*$/);
      if (m) this.define(m[1], { expr: m[2], src: `${asmPath}:${i + 1}` });
    });
  }

  has(name) { return this.defs.has(name); }

  get(name, stack = []) {
    if (this.values.has(name)) return this.values.get(name);
    const d = this.defs.get(name);
    if (!d) throw new Error(`constants: unknown symbol ${name}`);
    if (stack.includes(name)) throw new Error(`constants: recursive definition ${[...stack, name].join(' -> ')}`);
    const v = d.value !== undefined ? d.value : evalExpr(d.expr, (id) => this.get(id, [...stack, name]), d.src);
    this.values.set(name, v);
    return v;
  }

  src(name) { return this.defs.get(name)?.src; }

  eval(text, where) { return evalExpr(text, (id) => this.get(id), where); }

  // Reverse lookup within a generated list, e.g. nameOf('moves', 89) -> 'MOVE_EARTHQUAKE'.
  nameOf(list, value) {
    const l = this.loadGenerated(list);
    const e = l && l.find((x) => x.value === value);
    return e ? e.name : undefined;
  }

  maskNames(list) { return this.loadGenerated(list).map((e) => e.name); }
}

let cached = null;

// The constant set visible to pokeplatinum/src/battle/trainer_ai/script.s: its #includes
// (script.s:4-11) plus aicmd.inc's .equ lines, plus the headers the adapter needs.
export function loadConstants(root = DECOMP_ROOT) {
  if (cached && cached.root === root) return cached;
  const c = new Constants(root);
  c.loadEqu('asm/macros/aicmd.inc');
  const script = readFileSync(join(root, 'src/battle/trainer_ai/script.s'), 'utf8');
  for (const m of script.matchAll(/^#include\s+"([^"]+\.h)"/gm)) c.loadHeader(m[1]);
  // Lists the adapter maps Showdown state into (not all are reached by script.s includes).
  for (const l of ['moves', 'abilities', 'items', 'pokemon_types', 'item_hold_effects', 'move_classes',
    'move_battle_effects', 'battle_stats', 'genders', 'ai_weather_types', 'ai_load_type_targets', 'species']) {
    c.loadGenerated(l);
  }
  c.loadHeader('constants/battle/condition.h');
  c.loadHeader('constants/battle/moves.h');
  c.loadHeader('constants/battle/battle_script.h'); // DEFAULT_STAT_STAGE (:5)
  cached = c;
  return c;
}

export { IDENT };
