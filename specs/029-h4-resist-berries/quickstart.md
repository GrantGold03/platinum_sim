# Quickstart: validating feature 029

1. `(cd sim && node --test test/resist_berries.test.mjs test/replay.test.mjs)`.
2. Player check (alone): `uv run python specs/028-h4-shell-bell/scripts/paired_policies.py --battle-style shift --a expectimax2-v4 --b 'expectimax2-v4?resistBerries=0' --teams file:runs/029-evidence/teams/b2-berry.json --runs 2000 --workers 16 --out runs/029-evidence/pairs`
   after `--self` and a conditions control on the unmodified team.
3. `specs/029-h4-resist-berries/scripts/acceptance.py --side main|branch` (028's script).
4. Gates: Node suite; full pytest; engine diff empty.
