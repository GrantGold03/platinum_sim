// Code fingerprint of the sim worker (provenance, Constitution IV; contracts/worker-protocol.md `hello`).
//
// sim_code_hash = "sha256:" + sha256 over every behaviour-affecting file of sim/, i.e. every *.mjs and
// package.json under sim/ EXCEPT sim/test/**, sim/spikes/** and node_modules/**. Files are taken in
// ascending order of their repo-relative POSIX path ("sim/ai/adapter.mjs", ...) and each contributes
//   <path utf-8> 0x00 <byte length, decimal ascii> 0x00 <file bytes>
// The same scheme is implemented in src/platsim/version.py (`sim_code_hash`); tests check they agree.
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const SIM_DIR = dirname(fileURLToPath(import.meta.url));
const EXCLUDED_DIRS = new Set(['test', 'spikes']); // only directly under sim/
const isBehaviourFile = (name) => name.endsWith('.mjs') || name === 'package.json';

export function simCodeFiles(simDir = SIM_DIR) {
  const out = [];
  const walk = (abs, rel) => {
    for (const e of readdirSync(abs, { withFileTypes: true })) {
      const r = `${rel}/${e.name}`;
      if (e.isDirectory()) {
        if (e.name === 'node_modules' || (rel === 'sim' && EXCLUDED_DIRS.has(e.name))) continue;
        walk(join(abs, e.name), r);
      } else if (e.isFile() && isBehaviourFile(e.name)) {
        out.push([r, join(abs, e.name)]);
      }
    }
  };
  walk(simDir, 'sim');
  // Byte-wise order of the UTF-8 path (matches Python's sorted() on ASCII paths).
  out.sort((a, b) => Buffer.compare(Buffer.from(a[0]), Buffer.from(b[0])));
  return out;
}

export function simCodeHash(simDir = SIM_DIR) {
  const h = createHash('sha256');
  for (const [rel, abs] of simCodeFiles(simDir)) {
    const bytes = readFileSync(abs);
    h.update(Buffer.from(rel, 'utf8'));
    h.update(Buffer.from([0]));
    h.update(Buffer.from(String(bytes.length), 'ascii'));
    h.update(Buffer.from([0]));
    h.update(bytes);
  }
  return `sha256:${h.digest('hex')}`;
}
