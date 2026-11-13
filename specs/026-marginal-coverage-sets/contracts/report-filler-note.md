# Contract: the filler-move note in the player-facing report (FR-009a)

- `EvaluationReport.member_notes: list[str]`, default `[]`; `from_dict` tolerates absence; round trip tested.
- Text per member: `"<Name>: <moves> are filler: no better option, its two strongest moves cover every League opponent"`.
- `team_txt.team_text`: after the Showdown export, a blank line then a block starting with `Notes:` and one line per note;
  `legality.models.import_team` skips a block whose first line starts with `Notes:`; `import_team(team_text(r)) ==
  [b.showdown_set() for b in r.team.builds]` still holds (test).
- `evaluate.summary_text`: the notes after the per-battle lines; the xlsx Evaluation sheet: one "Member note" row per
  note (the Team sheet's headers are a published contract, contracts/spreadsheet.md of feature 001, and stay unchanged).
- The optimizer fills the notes from the winner's `MemberCandidates.no_live_reason` for the chosen set; `evaluate` of a
  user-supplied team writes none.
