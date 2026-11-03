// Feature 019 timing harness: loaded into each worker through NODE_OPTIONS=--import=<abs path>/register.mjs.
import { register } from 'node:module';
register('./hooks.mjs', import.meta.url);
