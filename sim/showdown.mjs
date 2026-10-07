// The only module that imports Pokemon Showdown. Everything else imports from here.
// Showdown is vendored at ../pokemon-showdown (pinned commit, see src/platsim/pins.py)
// and must be built first: `cd pokemon-showdown && npm ci && node build`.
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const sim = require('../pokemon-showdown/dist/sim/index.js');

export const { Battle, Dex, Teams, PRNG } = sim;
