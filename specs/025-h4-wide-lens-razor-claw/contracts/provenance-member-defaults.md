# Contract: `provenance.member_defaults`

- `src/platsim/report/provenance.py`: `member_defaults_block(team: TeamCandidate | None) -> dict` returning nature, ivs, evs,
  friendship, reason, `fixed_by_game` (species of builds whose nature, IVs or EVs differ from `DEFAULT_NATURE`, `DEFAULT_IV`,
  `DEFAULT_EV`); `[]` when `team` is None.
- `evaluate_team` sets `provenance["member_defaults"]`; `run._optimizer_provenance` carries it (the winner's team).
- `EvaluationReport.from_dict` leaves it absent for files without it; `summary_text` unchanged; the xlsx provenance sheet shows
  it through its generic loop; the web view is unchanged.
- The 025 acceptance identity comparison removes `provenance.member_defaults` with the other volatile fields.
