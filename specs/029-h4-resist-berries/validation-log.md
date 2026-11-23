# Validation log: feature 029 H4, resist berries

Branch `029-h4-resist-berries` from `main` 58f1570, main checkout. Times US Eastern.

## T001 Setup (11:18 AM EST, 2026-11-23)

`git diff --stat main -- src sim tests pyproject.toml`: 0 lines. Before-values:

```
sim_code_hash platsim_code_hash: sha256:6c038ef7601b38e3b400c96159a24968a7c0998d915f0586a50dcd1f0fa472d1 sha256:4e8673d95a2ff503a0b7325977601ac4cc128f962f868d6426f236e799de842b
divergence_ledger_version: sha256:821f33356f6a61bb
```

Scripts adapted from 028 under `scripts/`: `acceptance.py` (`runs/029-evidence`, identity seed `029-ident`, holders of any of the 17
resist berries reported per winner), `attribution.py` (an appended-items list may gain at most two resist berries at its end;
anything else a defect), `equal_levels.py` (master `029-equal|B2`), `hand_check.py` (plus the berry ranking per B2 member),
`make_check_team.py` (the unmodified B2 winner for the conditions control and the same team with the top-ranked berry on the member
whose top berry blocks the most). Ordering note: the check-team script needs the ranking function, which T008 defines; the function is
written before the player check (T007) and wired into the item lists only after it (T008), so the optimizer change still follows the
player check.

## T002 Pre-feature side (11:18:33 to 11:29:50 AM EST, alone, exit 0; code identical to `main` 58f1570)

B2 quick: levels [52, 50, 50, 50, 51, 53], clear 0.9440 [0.9203, 0.961], wall 507.3 s, no resist-berry holder: the same winner as
027 and 028. Generation at the job's reference level 47: 1.6 s for six members, 7.0 s with the allocation. Identity evaluations
(seed 029-ident). Snapshot `evidence/candidates-main.json`: 36 records.
