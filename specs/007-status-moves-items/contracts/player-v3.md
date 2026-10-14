# Contract: battle player expectimax2-v3 (007, FR-016)

## Naming and dispatch

- Name: `expectimax2-v3`. Exported as `expectimax2v3` from `sim/policy/expectimax2.mjs` and registered in `sim/gauntlet.mjs`.
- The worker `hello.policies` lists it.
- `expectimax2-v1` and `expectimax2-v2` stay registered, and their behaviour is **byte-identical**. This is enforced by a golden `log_hash` test that is recorded before any edit to the player.

## Options

- `V3_OPTS` extends `V2_OPTS` with flags for each new mechanic and for the search settings (`kRoot`, `kPly2`, `switchBeam`, `ply2Switches`, `depth`, `rollBuckets`, `leaf`).
- **`expectimax2-v3-ref`**, the reference: every mechanic flag on, with expensive search settings (research R4.4). It is registered for development and benchmarks, and it is not a user default.
- The production `expectimax2-v3` settings are the cheapest variant accepted against `-v3-ref` (FR-019). The accepted settings and the comparison are recorded in `validation-log.md`.

## MODELLED table

- `export const MODELLED = { 'expectimax2-v1': {...}, 'expectimax2-v2': {...}, 'expectimax2-v3': {effects: [...BATTLE_EFFECT names without prefix], items: [...HOLD_EFFECT names]} }`.
- It is plain literal data, so Python can parse it the same way `SELF_BOOSTS` is parsed. Python also checks that the worker `hello` lists the same policy names.
- Python flags an offered move or item as `not_modelled` when its effect or hold effect is missing from the table for the policy in use.

## Behavioural guarantees

- **Determinism:** same seed → same choices.
- The AI sample streams are seeded by the version name, as today.
- **Every newly modelled mechanic** has a unit test that cites its decomp location, plus a positive-control position (SC-008): v3 chooses the move or uses the item when it helps, v2 does not, and v3 does not choose it in a matching position where it doesn't help.
- **Friendship:** `sim/team.mjs` sets `happiness: 255` explicitly for player builds.
