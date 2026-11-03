// Feature 019 timing harness (research R4): a module `load` hook that rewrites sim/gauntlet.mjs IN MEMORY so each
// battle appends one JSON line {pid, seed, battle_index, trainer, turns, decisions, ns} to
// $PLATSIM_TIMING_DIR/<pid>.jsonl. The worker's stdout response is untouched; nothing on disk changes. Every patch
// must apply exactly once or the hook throws, so a drifted source is caught at worker start.
const PATCHES = [
  ["let end = null;\n    while (!battle.ended) {",
   "const __t0 = process.hrtime.bigint(); let __dec = 0;\n    let end = null;\n    while (!battle.ended) {"],
  ["playerPolicy.choose(ctxFor(p1))", "(__dec++, playerPolicy.choose(ctxFor(p1)))"],
  ["if (!end) end = battle.winner === P1_NAME",
   "if (process.env.PLATSIM_TIMING_DIR) __afs(`${process.env.PLATSIM_TIMING_DIR}/${process.pid}.jsonl`, JSON.stringify({ pid: process.pid, seed, battle_index: i, trainer: trainer.name.toLowerCase(), turns: battle.turn, decisions: __dec, ns: Number(process.hrtime.bigint() - __t0) }) + '\\n');\n    if (!end) end = battle.winner === P1_NAME"],
];

function patch(src) {
  let out = src;
  for (const [from, to] of PATCHES) {
    const n = out.split(from).length - 1;
    if (n !== 1) throw new Error(`019 timing hook: pattern found ${n} times (expected 1): ${JSON.stringify(from.slice(0, 50))}`);
    out = out.replace(from, to);
  }
  return `import { appendFileSync as __afs } from 'node:fs';\n${out}`;
}

export async function load(url, context, nextLoad) {
  const r = await nextLoad(url, context);
  if (!url.endsWith('/sim/gauntlet.mjs')) return r;
  const src = typeof r.source === 'string' ? r.source : new TextDecoder().decode(r.source);
  return { ...r, source: patch(src) };
}
