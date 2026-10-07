// Seed derivation (T033). Must match src/platsim/sim/seeds.py exactly.
//   derive(master, run, battle) = "sodium," + first 32 hex chars of sha256(`${master}|${run}|${battle}`)
// The input string is UTF-8 encoded; master/run/battle are stringified as-is (ints in decimal).
// "sodium,<32 hex>" is the PRNG seed format Showdown accepts (contracts/worker-protocol.md).
// CLI (used by the Python cross-check test): reads a JSON array of [master, run, battle]
// triples on stdin, writes a JSON array of seeds on stdout.
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

export function deriveSeed(master, run, battle) {
  const hex = createHash('sha256').update(`${master}|${run}|${battle}`, 'utf8').digest('hex');
  return `sodium,${hex.slice(0, 32)}`;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  let input = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (d) => { input += d; });
  process.stdin.on('end', () => {
    const triples = JSON.parse(input);
    process.stdout.write(JSON.stringify(triples.map(([m, r, b]) => deriveSeed(m, r, b))) + '\n');
  });
}
