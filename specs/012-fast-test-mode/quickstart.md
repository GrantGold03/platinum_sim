# Quickstart: fast test mode

Prerequisites: `uv sync` done; `data/generated/` built (`uv run platsim extract`); system Chrome for browser tests.

## 1. Fast mode

```sh
uv run pytest -q -m "not battle_sim"
```

Expected: about 480 tests pass (4 expected failures), no failure from the split checks, finishes in at most 30 min
(SC-001). Record the count and time in `validation-log.md`.

## 2. Guard test alone

```sh
uv run pytest -q tests/unit/test_battle_split.py
```

Expected: passes. It proves the detection works: a deliberately unmarked worker start is caught, a known battle
test carries the mark, `WorkerPool`'s default command uses the bare `node`, and a marked test that does not reach the
worker is reported (contracts/test-modes.md).

## 3. Full suite (merge gate, about 2.5 h, local only)

```sh
uv run pytest -q --durations=0 -rA > runs/012-evidence/full-pytest.log 2>&1
node --test sim/test/*.test.mjs > runs/012-evidence/full-node.log 2>&1
```

Expected: same outcomes as 2026-10-26 (517 passed + the one test that failed only from the mid-run commit, 4
expected failures) plus the new tests; Node 314/314; no split failure in either direction. Do not commit while it
runs. Paste the summary lines and the battle-set list with each test's route to the worker into
`validation-log.md` (FR-005, FR-009).

## 4. Hands-on (user)

Run step 1 and time it. Optionally add `import subprocess; subprocess.run(["node", "sim/worker.mjs"], input="")` to a
throwaway unmarked test and see it fail with the message in the contract.
