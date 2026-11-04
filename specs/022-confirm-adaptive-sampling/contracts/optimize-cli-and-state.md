# Contract: optimize CLI, request, fingerprint, state and provenance

- `platsim optimize S1..S6 [--sampling {full,adaptive}] [--floor F]`: `--sampling` default from `OptimizeRequest.sampling`
  (`full` until the owner's go); `--floor` default 0.98, usage error (exit 2) outside [0.9, 1.0].
- `job_fingerprint`: `sampling` key only when the request's value differs from the class default; `floor` likewise.
- state.json: `stages.confirm_attempts[*]` gain `sampling, full_runs, cynthia_only_runs, switch_run, banked_states,
  discarded, extension`; `stages.confirm.comparison` gains `pairs, excluded, full_pairs, cynthia_only_pairs`.
- result.json (the winner's report): the 021 fields as evaluate writes them; `provenance.sampling_per_stage`.
- The level search and the setup check: unchanged requests, unchanged results for the same request.
