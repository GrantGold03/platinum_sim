# Quickstart: validating feature 028

1. `(cd sim && node --test test/shell_bell.test.mjs test/replay.test.mjs)`: the heal cases, the knob, the engine checks; replay green.
2. Player check, alone (about 15 min): `uv run python specs/018-expectimax2-v4/scripts/paired_policies.py --a expectimax2-v4 --b 'expectimax2-v4?shellBell=0' --teams file:runs/028-evidence/teams/b2-shellbell.json --runs 2000 --workers 16 --out runs/028-evidence/pairs`
   after a `--self` pairing control on the same team (0 discordant pairs) → clear rates, discordant pairs, McNemar p; not worse required.
3. Pre-feature side before the optimizer change, then the branch side: `specs/028-h4-shell-bell/scripts/acceptance.py --side main|branch`
   (027's script with Shell Bell reporting).
4. Gates: Node suite; full pytest; engine diff empty; sim hash changed (the player), ledger version changed only with an entry.
