# Validation log: feature 028 H4, Shell Bell

Branch `028-h4-shell-bell` from `main` 634e270, main checkout. Times US Eastern.

## T001 Setup (10:15 AM EST, 2026-11-20)

`git diff --stat main -- src sim tests pyproject.toml`: 0 lines. Before-values:

```
sim_code_hash platsim_code_hash: sha256:e968ff0f403539460e6c0260db6253ad971d1a3eb7c02feaa8c9fbe393e74b7d sha256:85fa0353274dcefe4ec170f28ff6f17e3eb555853d9c7dad3fe7b2e3902c53b9
divergence_ledger_version: sha256:feb2a48ef2e1dd08 (027's results; unchanged since)
```

Scripts adapted from 027 under `scripts/`: `attribution.py` (027's plus: extras must be unchanged; an appended-items list may
only gain `shell_bell` at its end, cause `appended`; anything else a defect), `acceptance.py` (evidence `runs/028-evidence`,
identity seed `028-ident`, Shell Bell holders reported per winner), `equal_levels.py` (master `028-equal|B2`), `hand_check.py`
(appended items per set), `make_check_team.py` (the B2 winner with Garchomp's Sitrus Berry replaced by Shell Bell, validated).

## T002 Pre-feature side (10:15:49 to 10:27:00 AM EST, alone, exit 0; code identical to `main` 634e270)

B2 quick: levels [52, 50, 50, 50, 51, 53], clear 0.9440 [0.9203, 0.961] (n 500, 2 attempts), wall 492.9 s, no Shell Bell holder
(not offered on main): the same winner as 027. Generation at the job's reference level 47: 1.7 s for six members, 7.2 s for the
team build with the allocation. Identity evaluations `ident-main/{ref,b2main}` (seed 028-ident). Snapshot
`evidence/candidates-main.json`: 36 records with the appended-item lists.
