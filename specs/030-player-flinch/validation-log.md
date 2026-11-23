# Validation log: feature 030, the battle player models flinch

Branch `030-player-flinch` from `main` 9877958, main checkout. Times US Eastern.

## T001 Setup (3:52 PM EST, 2026-11-23)

`git diff --stat main -- src sim tests pyproject.toml`: 0 lines. Before-values:

```
sim_code_hash platsim_code_hash: sha256:913f9f0c381b70c19212477c76b55c78b72aa48ebd282463315485c29985b048 sha256:f3271a011f8a55146cccdac95b0b5baeecb638885f83dd0d4b4f493c16f2b974
divergence_ledger_version: sha256:821f33356f6a61bb
```

Scripts copied from 029 under `scripts/`: `acceptance.py` (`runs/030-evidence`, identity seed `030-ident`; identity differences
reported, not failures; the pass rule requires every snapshot member identical, `snapshot_members_changed == 0`), `attribution.py`,
`equal_levels.py` (master `030-equal|B2`), `paired_policies.py` (029's, with `--battle-style`).

## T002 Pre-feature side (3:52:29 to 4:07:06 PM EST, alone, all exit 0; code identical to `main` 9877958)

B2 quick: levels [52, 50, 50, 50, 51, 53], clear 0.9440 [0.9203, 0.961], wall 641.3 s: the same winner as 027 to 029. Identity
evaluations (seed 030-ident). Snapshot `evidence/candidates-main.json` (36 records). Generation 1.6 s for six members, 7.0 s with the
allocation. **v4 bench digest on `main`** (`node sim/bench.mjs --policy expectimax2-v4`, 40 gauntlets): digest_full `05fa8cb1…`,
digest_logs `624cbb4c…` (`evidence/pre/v4-main-bench.json`). Today's B2 winner written to `runs/030-evidence/teams/b2-main.json` and
validated by the evaluate loader (analyze U1).
