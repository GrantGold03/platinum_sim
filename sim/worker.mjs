// Long-lived sim worker (T032, contracts/worker-protocol.md): NDJSON requests on stdin, one
// response line per request on stdout (echoing `id`); stderr is for logs only.
//
// Startup (before any Dex.*.get(), research R4): load data/generated/*.json, apply every
// `corrected` data patch from data/divergences.json (absent until T053 -> no patches,
// divergence_ledger_version "none"), register the trainerfullrestore pseudo-move (T010).
// All of that is sim/gamedata.mjs loadGameData().
//
// Ops: hello, gauntlet. Unknown ops and failures answer
//   {"id", "ok": false, "error": {"kind": "invalid_team" | "ai_unimplemented" | "internal", "detail"}}
// Env: PLATSIM_GENERATED_DIR / PLATSIM_DIVERGENCES override the data paths (tests).
import { createInterface } from 'node:readline';
import { DIVERGENCES_PATH, GENERATED_DIR, loadGameData, showdownCommit } from './gamedata.mjs';
import { OPPONENT_POLICIES, PLAYER_POLICIES, runGauntlet } from './gauntlet.mjs';

const gd = loadGameData({
  dir: process.env.PLATSIM_GENERATED_DIR || GENERATED_DIR,
  divergencesPath: process.env.PLATSIM_DIVERGENCES || DIVERGENCES_PATH,
});
const SHOWDOWN_COMMIT = showdownCommit();

function hello() {
  return {
    showdown_commit: SHOWDOWN_COMMIT,
    decomp_commit: gd.manifest.decomp_commit,
    decomp_data_hash: gd.decompDataHash,
    divergence_ledger_version: gd.dexPatch.version,
    divergence_patches_applied: gd.dexPatch.applied.length,
    policies: [...PLAYER_POLICIES.keys()],
    opponent_policies: [...OPPONENT_POLICIES.keys()],
    pp_restore_between_battles: gd.availability?.pp_restore_between_battles === true,
  };
}

const OPS = {
  hello,
  gauntlet: (req) => runGauntlet(gd, req),
};

function handle(line) {
  let req;
  try {
    req = JSON.parse(line);
  } catch (e) {
    return { id: null, ok: false, error: { kind: 'internal', detail: `bad JSON: ${e.message}` } };
  }
  const op = OPS[req.op];
  if (!op) return { id: req.id ?? null, ok: false, error: { kind: 'internal', detail: `unknown op ${req.op}` } };
  try {
    return { id: req.id, ok: true, ...op(req) };
  } catch (e) {
    const kind = ['invalid_team', 'ai_unimplemented'].includes(e.kind) ? e.kind : 'internal';
    if (kind === 'internal') process.stderr.write(`worker: request ${req.id}: ${e.stack}\n`);
    return { id: req.id, ok: false, error: { kind, detail: String(e.message) } };
  }
}

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on('line', (line) => {
  if (!line.trim()) return;
  process.stdout.write(`${JSON.stringify(handle(line))}\n`);
});
