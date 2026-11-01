// Benchmark tool and replay harness for the battle player (feature 015, contracts/bench-tool.md).
//
// Runs a fixed set of gauntlets in THIS process (so the policy counters in `STATS` are visible) and
// reports throughput, ms per decision and two digests of the results:
//   digest_full  sha256 over JSON.stringify(result) of each gauntlet in request order (the digest the
//                015 profiling harness recorded on `main`: db6d20cf... for expectimax2-v2);
//   digest_logs  sha256 over one line per gauntlet, `seed|cleared|final_levels,|battles;` with each battle
//                `trainer:end:turns:log_hash` (strings and integers only, so `platsim bench` can compute
//                the same digest from the worker pool's results and prove it ran the same battles).
// `runRecorded` wraps the two policies to record every player choice and the trainer-AI draw count
// inside every decision (the policy's predictions via STATS.aiDraws, the live AI via its RNG). The
// wrappers call through and keep the registered names, so the result is byte-identical to a plain run.
// `--record FILE` writes/merges the replay fixture that sim/test/replay.test.mjs checks.
//
// usage: node sim/bench.mjs [--policy expectimax2-v2] [--n 20] [--block a] [--teams bench,ref]
//                           [--trainers aaron,bertha,flint,lucian,cynthia] [--json] [--record FILE]
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { DIVERGENCES_PATH, GENERATED_DIR, loadGameData } from './gamedata.mjs';
import { OPPONENT_POLICIES, PLAYER_POLICIES, RequestError, runGauntlet } from './gauntlet.mjs';
import { STATS } from './policy/expectimax2.mjs';
import { DECOMP_AI, stateFor } from './ai/opponent.mjs';
import { CHECK_STATS } from './ai/adapter.mjs';
import { simCodeHash } from './version.mjs';

export const TEAM_FILES = {
  bench: ['../tests/fixtures/policy_benchmark_team.json', 'team'],
  ref: ['../tests/fixtures/reference_team.json', 'builds'],
};
export const LEAGUE = ['aaron', 'bertha', 'flint', 'lucian', 'cynthia'];
export const DEFAULT_SET = { block: 'a', n: 20, teams: ['bench', 'ref'], trainers: LEAGUE, stop_on_loss: false, opponent_policy: DECOMP_AI };

export function loadTeam(name) {
  const f = TEAM_FILES[name];
  if (!f) throw new RequestError('invalid_team', `unknown bench team ${name} (known: ${Object.keys(TEAM_FILES)})`);
  return JSON.parse(readFileSync(new URL(f[0], import.meta.url), 'utf8'))[f[1]];
}

/** The request set: for each team in order, seeds `prof-<block>-<team>-<i>`, i < n. */
export function benchRequests({ block = 'a', n = 20, teams = ['bench', 'ref'], trainers, policy = 'expectimax2-v2' } = {}) {
  const out = [];
  for (const tn of teams) {
    const team = loadTeam(tn);
    for (let i = 0; i < n; i++) {
      const req = { team, seed: `prof-${block}-${tn}-${i}`, player_policy: policy, opponent_policy: DECOMP_AI, stop_on_loss: false };
      if (trainers && trainers.length) req.trainers = trainers;
      out.push(req);
    }
  }
  return out;
}

export const digestFull = (jsons) => {
  const h = createHash('sha256');
  for (const j of jsons) h.update(j);
  return h.digest('hex');
};

export const logLine = (r, seed) => `${seed}|${r.cleared ? 1 : 0}|${r.final_levels.join(',')}|${r.battles.map((b) => `${b.trainer}:${b.end}:${b.turns}:${b.log_hash}`).join(';')}\n`;

export const digestLogs = (results, seeds) => {
  const h = createHash('sha256');
  results.forEach((r, i) => h.update(logLine(r, seeds[i]), 'utf8'));
  return h.digest('hex');
};

let recSeq = 0;

/**
 * Runs one request with recording wrappers around both policies. Returns
 * { result, json, choices, policy_ai_draws, live_ai_draws }: choices[i] is the player's i-th choice,
 * policy_ai_draws[i] the STATS.aiDraws delta across it, live_ai_draws[j] the live AI's RNG draws across
 * the opponent's j-th choice of the gauntlet (battles concatenated; 0 baseline before its state exists).
 */
export function runRecorded(gd, req) {
  const player = PLAYER_POLICIES.get(req.player_policy ?? 'placeholder-default');
  if (!player) throw new RequestError('internal', `unknown player_policy ${req.player_policy}`);
  const opp = OPPONENT_POLICIES.get(req.opponent_policy ?? DECOMP_AI);
  if (!opp) throw new RequestError('internal', `unknown opponent_policy ${req.opponent_policy}`);
  const choices = [], policy_ai_draws = [], live_ai_draws = [];
  const liveDraws = (battle) => stateFor(battle)?.rng.draws ?? 0;
  const pw = {
    name: player.name, // keeps `player_policy` in the result unchanged
    choose(ctx) {
      const d0 = STATS.aiDraws;
      const c = player.choose(ctx);
      choices.push(c);
      policy_ai_draws.push(STATS.aiDraws - d0);
      return c;
    },
    afterTurn: player.afterTurn ? (ctx) => player.afterTurn(ctx) : undefined,
  };
  const ow = {
    name: opp.name,
    choose(ctx) {
      const d0 = liveDraws(ctx.battle);
      const c = opp.choose(ctx);
      live_ai_draws.push(liveDraws(ctx.battle) - d0);
      return c;
    },
    afterTurn: opp.afterTurn ? (ctx) => opp.afterTurn(ctx) : undefined,
  };
  const pk = `${player.name}+rec${++recSeq}`, ok = `${opp.name}+rec${recSeq}`;
  PLAYER_POLICIES.set(pk, pw);
  OPPONENT_POLICIES.set(ok, ow);
  try {
    const result = runGauntlet(gd, { ...req, player_policy: pk, opponent_policy: ok });
    return { result, json: JSON.stringify(result), choices, policy_ai_draws, live_ai_draws };
  } finally {
    PLAYER_POLICIES.delete(pk);
    OPPONENT_POLICIES.delete(ok);
  }
}

/** The per-gauntlet fixture record (data-model.md). */
export function fixtureRecord(req, team, rr) {
  const r = rr.result;
  return {
    seed: req.seed, team, cleared: r.cleared, final_levels: r.final_levels,
    battles: r.battles.map((b) => [b.trainer, b.end, b.turns, b.log_hash]),
    choices: rr.choices, policy_ai_draws: rr.policy_ai_draws, live_ai_draws: rr.live_ai_draws,
  };
}

/**
 * Differences between a fixture's policy entry and freshly recorded gauntlets (same order).
 * `actual` = { digest_full, digest_logs, gauntlets: [fixtureRecord...] }. Returns [] when identical.
 */
export function diffRecorded(expected, actual) {
  const out = [];
  if (expected.digest_full !== actual.digest_full) out.push(`digest_full ${expected.digest_full} != ${actual.digest_full}`);
  if (expected.digest_logs !== actual.digest_logs) out.push(`digest_logs ${expected.digest_logs} != ${actual.digest_logs}`);
  if (expected.gauntlets.length !== actual.gauntlets.length) out.push(`gauntlets ${expected.gauntlets.length} != ${actual.gauntlets.length}`);
  const n = Math.min(expected.gauntlets.length, actual.gauntlets.length);
  for (let i = 0; i < n; i++) {
    const e = expected.gauntlets[i], a = actual.gauntlets[i];
    if (e.seed !== a.seed) { out.push(`#${i} seed ${e.seed} != ${a.seed}`); continue; }
    for (const k of ['choices', 'policy_ai_draws', 'live_ai_draws', 'battles', 'final_levels']) {
      const ej = JSON.stringify(e[k]), aj = JSON.stringify(a[k]);
      if (ej !== aj) {
        let j = 0;
        while (j < Math.min(e[k].length, a[k].length) && JSON.stringify(e[k][j]) === JSON.stringify(a[k][j])) j++;
        out.push(`${e.seed} ${k} differs at index ${j}: ${JSON.stringify(e[k][j])} != ${JSON.stringify(a[k][j])} (lengths ${e[k].length}/${a[k].length})`);
      }
    }
    if (e.cleared !== a.cleared) out.push(`${e.seed} cleared ${e.cleared} != ${a.cleared}`);
  }
  return out;
}

const statsSnapshot = () => ({ ...STATS });
const statsDelta = (a, b) => Object.fromEntries(Object.keys(b).map((k) => [k, b[k] - (a[k] ?? 0)]));

/** Runs a set and returns the report object (contracts/bench-tool.md "JSON output") plus the records. */
export function runBench(gd, { policy = 'expectimax2-v2', block = 'a', n = 20, teams = ['bench', 'ref'], trainers = LEAGUE } = {}, onGauntlet) {
  if (!PLAYER_POLICIES.has(policy)) throw new RequestError('internal', `unknown player_policy ${policy} (known: ${[...PLAYER_POLICIES.keys()].filter((k) => !k.includes('+rec'))})`);
  const reqs = benchRequests({ block, n, teams, trainers, policy });
  const teamOf = reqs.map((r) => r.seed.split('-')[2]);
  const s0 = statsSnapshot();
  const c0 = { ...CHECK_STATS }; // 016 control mode counters (PLATSIM_AI_CHECK=1), reported as deltas
  const jsons = [], results = [], records = [];
  let cleared = 0, battles = 0, turns = 0;
  const t0 = process.hrtime.bigint();
  reqs.forEach((req, i) => {
    const rr = runRecorded(gd, req);
    jsons.push(rr.json); results.push(rr.result); records.push(fixtureRecord(req, teamOf[i], rr));
    if (rr.result.cleared) cleared++;
    battles += rr.result.battles.length;
    for (const b of rr.result.battles) turns += b.turns;
    onGauntlet?.(i, reqs.length, rr.result);
  });
  const wall = Number(process.hrtime.bigint() - t0) / 1e9;
  const stats = statsDelta(s0, statsSnapshot());
  const dec = stats.decisions || 0;
  return {
    policy, block, n, teams, trainers,
    gauntlets: reqs.length, cleared, battles, turns,
    wall_s: +wall.toFixed(3), gauntlets_per_s: +(reqs.length / wall).toFixed(4),
    decisions: dec || null,
    ms_per_decision: dec ? +(stats.ms / dec).toFixed(3) : null,
    ai_calls_per_decision: dec ? +(stats.aiCalls / dec).toFixed(2) : null,
    ai_draws: dec ? stats.aiDraws : null,
    check_stats: process.env.PLATSIM_AI_CHECK === '1'
      ? { checks: CHECK_STATS.checks - c0.checks, mismatches: CHECK_STATS.mismatches - c0.mismatches } : null,
    digest_full: digestFull(jsons),
    digest_logs: digestLogs(results, reqs.map((r) => r.seed)),
    stats,
    sim_code_hash: simCodeHash(),
    node: process.version,
    date: new Date().toISOString(),
    records,
  };
}

function gitCommit() {
  try { return execFileSync('git', ['rev-parse', '--short', 'HEAD'], { cwd: new URL('.', import.meta.url), encoding: 'utf8' }).trim(); } catch { return null; }
}

/** Writes or merges the replay fixture for `report.policy`. */
export function recordFixture(file, report) {
  let fx;
  try { fx = JSON.parse(readFileSync(file, 'utf8')); } catch { fx = { policies: {} }; }
  fx.recorded = { commit: gitCommit(), date: report.date.slice(0, 10), node: report.node, sim_code_hash: report.sim_code_hash };
  fx.set = { block: report.block, n: report.n, teams: report.teams, trainers: report.trainers, stop_on_loss: false, opponent_policy: DECOMP_AI };
  fx.policies[report.policy] = { digest_full: report.digest_full, digest_logs: report.digest_logs, gauntlets: report.records };
  writeFileSync(file, JSON.stringify(fx) + '\n');
  return fx;
}

function arg(argv, k, d) { const i = argv.indexOf(`--${k}`); return i >= 0 ? argv[i + 1] : d; }

export function main(argv = process.argv.slice(2)) {
  const opts = {
    policy: arg(argv, 'policy', 'expectimax2-v2'),
    n: Number(arg(argv, 'n', 20)),
    block: arg(argv, 'block', 'a'),
    teams: arg(argv, 'teams', 'bench,ref').split(',').filter(Boolean),
    trainers: arg(argv, 'trainers', LEAGUE.join(',')).split(',').filter(Boolean),
  };
  const json = argv.includes('--json');
  const record = arg(argv, 'record', null);
  const gd = loadGameData({ dir: process.env.PLATSIM_GENERATED_DIR || GENERATED_DIR, divergencesPath: process.env.PLATSIM_DIVERGENCES || DIVERGENCES_PATH });
  let report;
  try {
    report = runBench(gd, opts, (i, total, r) => { if (!json) process.stderr.write(`${i + 1}/${total} ${r.cleared ? 'cleared' : 'lost  '} ${r.battles.length} battles\n`); });
  } catch (e) {
    if (e instanceof RequestError) { process.stderr.write(`bench: ${e.message}\n`); return 1; }
    throw e;
  }
  if (record) { recordFixture(record, report); process.stderr.write(`bench: recorded ${report.policy} into ${record}\n`); }
  const { records, ...out } = report;
  if (json) {
    process.stdout.write(JSON.stringify(out, null, 1) + '\n');
  } else {
    const rows = [
      ['policy', out.policy], ['set', `block ${out.block}, n ${out.n}, teams ${out.teams.join(',')}, trainers ${out.trainers.join(',')}`],
      ['gauntlets / cleared', `${out.gauntlets} / ${out.cleared}`], ['battles / turns', `${out.battles} / ${out.turns}`],
      ['wall', `${out.wall_s} s`], ['gauntlets/s', out.gauntlets_per_s],
      ['decisions', out.decisions ?? 'n/a'], ['ms/decision', out.ms_per_decision ?? 'n/a'],
      ['AI calls/decision', out.ai_calls_per_decision ?? 'n/a'], ['AI draws', out.ai_draws ?? 'n/a'],
      ['CHECK mode', out.check_stats ? `${out.check_stats.checks} checks, ${out.check_stats.mismatches} mismatches` : 'off'],
      ['digest_full', out.digest_full], ['digest_logs', out.digest_logs], ['sim_code_hash', out.sim_code_hash],
    ];
    for (const [k, v] of rows) process.stdout.write(`${k.padEnd(20)} ${v}\n`);
  }
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = main();
}
