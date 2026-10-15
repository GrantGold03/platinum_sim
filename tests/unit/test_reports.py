"""T055: report writers (result.json, result.xlsx, result.csv, team.txt).

SYNTHETIC FIXTURES ONLY: every species / move / item / ability / trainer / map key below is a
made-up placeholder ("species_0", "move_0_1", "trainer_e4_1", ...). Rates, levels, commits and
divergence entries are invented test numbers. Nothing here claims a value from the decomp or from
Showdown; these tests check the report *format*, not game facts.
"""

import csv
import json

import pytest
from openpyxl import load_workbook

from platsim.legality.models import Build, MoveChoice, TeamCandidate, export_team, import_team
from platsim.report import OUTPUT_FILES, write_all
from platsim.report.csv_report import TEAM_HEADERS, MissingProvenance, team_rows
from platsim.report.json_report import (
    QUICK_WARNING,
    BattleStat,
    DivergenceEntry,
    EvaluationReport,
    LossCause,
    NoQualifying,
    ResourceLine,
)
from platsim.report.team_txt import NO_TEAM_LINE
from platsim.report.xlsx import SHEET_NAMES

SPEC_TEAM_HEADERS = (  # contracts/spreadsheet.md, sheet "Team", in order
    ["Slot", "Species", "Obtained from", "Start level", "Final level (expected)", "Ability"]
    + ["Ability choice", "Held item", "Held item source", "Nature", "IVs", "EVs"]
    + [f"Move {i}" for i in range(1, 5)]
    + [f"Move {i} source" for i in range(1, 5)]
)

_KINDS = ["level_up", "tm", "tutor", "pre_evo_level_up", "egg", "relearner", "hm"]
_DETAILS = {
    "level_up": "Lv 30",
    "tm": "TM99 – synthetic shop (unlimited)",
    "tutor": "synthetic tutor – 1R/2B/0Y/0G",
    "pre_evo_level_up": "synthetic_pre Lv 20",
    "egg": "",  # egg moves have a fixed label even without detail
    "relearner": "synthetic relearner",
    "hm": "HM99 – synthetic gift",
}


def _build(i: int, nmoves: int = 4) -> Build:
    moves = []
    for j in range(nmoves):
        kind = _KINDS[(i + j) % len(_KINDS)]
        moves.append(MoveChoice(f"move_{i}_{j}", kind, _DETAILS[kind], f"avail:synthetic:{i}{j}"))
    return Build(
        species=f"species_{i}",
        source=f"avail:wild_slot:map_{i}",
        start_level=40 + i,
        moves=moves,
        ability=f"ability_{i}",
        ability_reason="single_ability",
        held_item=None if i == 3 else f"item_{i}",
    )


def _common(**over) -> dict:
    d = dict(
        n_runs=2000,
        clear_rate=0.8,
        clear_ci95=(0.782, 0.817),
        per_battle={
            f"trainer_e4_{k}": BattleStat(0.95, (0.94, 0.96), 2000 - 10 * k) for k in range(1, 5)
        }
        | {"trainer_champ": BattleStat(0.85, (0.83, 0.87), 1900)},
        champion_rate=0.86,
        champion_ci95=(0.845, 0.874),
        champion_battles=2500,
        budget_preset="standard",
        expected_final_levels=[45.2, 46.0, 47.5, 48.1, 49.9, 50.3],
        expected_avg_final_level=47.83,
        final_level_gap_max=5.1,
        loss_causes=[LossCause("trainer_champ", "species_opp_1", 120)],
        threshold=0.75,
        qualified=True,
        borderline=False,
        player_policy="synthetic-player-v0",
        opponent_policy="synthetic-ai@0000000",
        seeds={"master": 12345, "scheme": "synthetic derivation"},
        decomp_commit="synthetic-decomp-commit",
        showdown_commit="synthetic-showdown-commit",
        divergence_ledger_version="synthetic-ledger-1",
        divergences=[
            DivergenceEntry(
                "DIV-SYN-1", "data", "synthetic", "decomp:1", "ps:1", "corrected", "none", "t_x"
            )
        ],
    )
    d.update(over)
    return d


def _report(**over) -> EvaluationReport:
    builds = [_build(i, nmoves=1 + i % 4) for i in range(6)]
    team = TeamCandidate(builds=builds, resource_use={"tm99": 1, "item_1": 1})
    kw = _common(
        team=team,
        obtained_from=[f"Wild – synthetic map {i}" for i in range(6)],
        held_item_sources=[None if i == 3 else f"Item ball – synthetic map {i}" for i in range(6)],
        resources=[ResourceLine("tm99", "tm", ["species_0", "species_2"], 2, 2)],
    )
    kw.update(over)
    return EvaluationReport(**kw)


def _no_team_report(**over) -> EvaluationReport:
    kw = _common(
        team=None,
        qualified=False,
        clear_rate=0.41,
        clear_ci95=(0.39, 0.43),
        no_qualifying=NoQualifying(
            best_clear_rate=0.41,
            best_clear_ci95=(0.39, 0.43),
            best_n_runs=2000,
            best_levels=[100, 100, 100, 100, 100, 100],
            species=[f"species_{i}" for i in range(6)],
        ),
    )
    kw.update(over)
    return EvaluationReport(**kw)


def _sheet_rows(ws):
    return [list(r) for r in ws.iter_rows(values_only=True)]


def test_xlsx_sheets_and_team_headers(tmp_path):
    paths = write_all(_report(), tmp_path)
    wb = load_workbook(paths["xlsx"])
    assert tuple(wb.sheetnames) == SHEET_NAMES == (
        "Team",
        "Evaluation",
        "Resources",
        "Candidates",  # 007 (contracts/candidate-report.md)
        "Provenance",
        "Divergences",
    )
    assert TEAM_HEADERS == SPEC_TEAM_HEADERS
    rows = _sheet_rows(wb["Team"])
    assert rows[0] == SPEC_TEAM_HEADERS
    assert len(rows) == 1 + 6


def test_every_move_has_a_nonempty_source(tmp_path):
    report = _report()
    wb = load_workbook(write_all(report, tmp_path)["xlsx"])
    rows = _sheet_rows(wb["Team"])
    hdr = rows[0]
    checked = 0
    for row, build in zip(rows[1:], report.team.builds, strict=True):
        for n in range(1, 5):
            move = row[hdr.index(f"Move {n}")]
            src = row[hdr.index(f"Move {n} source")]
            if n <= len(build.moves):
                assert move == build.moves[n - 1].move
                assert isinstance(src, str) and src.strip(), (move, src)
                checked += 1
            else:  # unused move slot: both cells empty (openpyxl reads "" back as None)
                assert move in (None, "") and src in (None, "")
    # Positive control: the fixture really has moves (1+2+3+4+1+2), so the loop checked something.
    assert checked == sum(len(b.moves) for b in report.team.builds) == 13


def test_missing_move_source_is_refused(tmp_path):
    report = _report()
    report.team.builds[0].moves[0] = MoveChoice("move_x", "tm", "  ", None)
    with pytest.raises(MissingProvenance):
        write_all(report, tmp_path)


def test_csv_matches_team_sheet(tmp_path):
    paths = write_all(_report(), tmp_path)
    with paths["csv"].open(newline="", encoding="utf-8") as f:
        csv_rows = list(csv.reader(f))
    sheet = _sheet_rows(load_workbook(paths["xlsx"])["Team"])
    def norm(v):  # CSV is text; xlsx keeps numbers (46.0 reads back as int 46)
        if v is None or v == "":
            return ""
        try:
            return float(v)
        except (TypeError, ValueError):
            return str(v)

    assert [[norm(v) for v in r] for r in csv_rows] == [[norm(v) for v in r] for r in sheet]
    assert len(csv_rows) == 7


def test_evaluation_sheet_reports_champion_separately(tmp_path):
    r = _report()
    ws = load_workbook(write_all(r, tmp_path)["xlsx"])["Evaluation"]
    kv = {row[0]: row[1] for row in _sheet_rows(ws) if row and row[0]}
    assert kv["Clear rate (full gauntlet)"] == r.clear_rate
    assert kv["Clear rate 95% CI low"] == r.clear_ci95[0]
    assert kv["Champion win rate P(win | reached Cynthia)"] == r.champion_rate
    assert kv["Champion 95% CI low"] == r.champion_ci95[0]
    assert kv["Champion 95% CI high"] == r.champion_ci95[1]
    assert kv["Champion battles (full runs + top-up)"] == r.champion_battles
    assert kv["Threshold (min clear rate)"] == 0.75
    assert kv["Status"] == "qualified"
    assert kv["Runs (full gauntlets)"] == 2000
    rows = _sheet_rows(ws)
    for trainer, st in r.per_battle.items():  # per-trainer rows
        assert [trainer, st.rate, st.ci95[0], st.ci95[1], st.battles] in rows
    assert "Final level gap (max)" in kv and "Expected average final level" in kv


def test_provenance_resources_divergences(tmp_path):
    r = _report()
    wb = load_workbook(write_all(r, tmp_path)["xlsx"])
    prov = {row[0]: row[1] for row in _sheet_rows(wb["Provenance"]) if row[0]}
    for key, val in [
        ("Decomp commit", r.decomp_commit),
        ("Showdown commit", r.showdown_commit),
        ("Divergence ledger version", r.divergence_ledger_version),
        ("Player policy", r.player_policy),
        ("Opponent policy", r.opponent_policy),
        ("Master seed", 12345),
        ("Budget preset", "standard"),
    ]:
        assert prov[key] == val
    res = _sheet_rows(wb["Resources"])
    assert res[0] == ["Resource", "Kind", "Used by", "Copies used", "Copies available"]
    assert res[1] == ["tm99", "tm", "species_0, species_2", 2, 2]
    div = _sheet_rows(wb["Divergences"])
    assert div[0][0] == "ID" and "Resolution" in div[0] and "Impact" in div[0]
    assert div[1][0] == "DIV-SYN-1" and div[1][div[0].index("Resolution")] == "corrected"


def test_json_round_trip(tmp_path):
    r = _report()
    paths = write_all(r, tmp_path)
    back = EvaluationReport.from_json(paths["json"].read_text(encoding="utf-8"))
    assert back == r
    assert back.to_dict() == json.loads(paths["json"].read_text(encoding="utf-8"))
    nq = _no_team_report()
    assert EvaluationReport.from_json(nq.to_json()) == nq


def test_team_txt_is_showdown_export(tmp_path):
    r = _report()
    text = write_all(r, tmp_path)["team"].read_text(encoding="utf-8")
    assert text == export_team(r.team)
    assert import_team(text) == [b.showdown_set() for b in r.team.builds]


def test_quick_budget_warning_everywhere(tmp_path):
    with pytest.raises(ValueError, match="never be qualified"):
        _report(budget_preset="quick", qualified=True)
    r = _report(budget_preset="quick", qualified=False)
    assert r.warnings[0] == QUICK_WARNING
    paths = write_all(r, tmp_path)
    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert data["budget_preset"] == "quick" and QUICK_WARNING in data["warnings"]
    wb = load_workbook(paths["xlsx"])
    for sheet in ("Evaluation", "Provenance"):
        rows = _sheet_rows(wb[sheet])
        assert ["WARNING", QUICK_WARNING] in [r[:2] for r in rows], sheet
    # Positive control: a standard report carries no such warning.
    assert QUICK_WARNING not in _report().warnings
    # Round trip does not duplicate the warning.
    assert EvaluationReport.from_json(r.to_json()).warnings.count(QUICK_WARNING) == 1


def test_no_qualifying_team_writes_all_four_files(tmp_path):
    r = _no_team_report()
    paths = write_all(r, tmp_path)
    assert {p.name for p in paths.values()} == set(OUTPUT_FILES.values())
    for p in paths.values():
        assert p.is_file() and p.stat().st_size > 0, p
    data = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert data["team"] is None and data["qualified"] is False
    assert data["no_qualifying"]["best_clear_rate"] == 0.41
    assert data["no_qualifying"]["best_levels"] == [100] * 6
    text = paths["team"].read_text(encoding="utf-8")
    assert text.startswith(NO_TEAM_LINE) and "41.0%" in text
    with pytest.raises(ValueError):  # never importable as a team
        import_team(text)
    wb = load_workbook(paths["xlsx"])
    assert tuple(wb.sheetnames) == SHEET_NAMES
    team = _sheet_rows(wb["Team"])
    assert team[0] == SPEC_TEAM_HEADERS and "No qualifying team found" in team[1][1]
    ev = {row[0]: row[1] for row in _sheet_rows(wb["Evaluation"]) if row and row[0]}
    assert ev["Status"] == "no qualifying team"
    assert "levels 100/100/100/100/100/100" in ev["Result"]
    assert team_rows(r)[0][1] == team[1][1]


def test_report_invariants():
    with pytest.raises(ValueError):
        _no_team_report(qualified=True)
    with pytest.raises(ValueError):
        _report(borderline=True)  # qualified and borderline together
    with pytest.raises(ValueError):
        _report(clear_ci95=(0.9, 0.8))
    with pytest.raises(ValueError):
        _report(budget_preset="fast")
    with pytest.raises(ValueError):
        _report(no_qualifying=_no_team_report().no_qualifying)  # both team and no_qualifying


# --- 005: "Obtained from" labels members that need a second Platinum game -------------------------

def _obtained(ledger, members, options):
    """team_sources' "Obtained from" for legal_team.json with its last slots replaced."""
    from test_validator import _with

    from platsim.legality.validator import _team_from_dict
    from platsim.report.sources import team_sources

    team, _, read = _team_from_dict(_with(ledger, *members))
    assert not read
    return team_sources(team, ledger.with_options(options))[0]


def test_second_game_member_is_labelled(ledger):
    from test_validator import DAY_CARE, SECOND_GAME, _member

    from platsim.legality import movesources as MS
    from platsim.legality.models import LegalityOptions

    torterra = _member("SPECIES_TORTERRA", DAY_CARE.format("TURTWIG"), ledger)
    got = _obtained(ledger, [torterra], SECOND_GAME)  # slot 0 Infernape (gift), slot 5 Torterra
    labelled = [i for i, t in enumerate(got) if t.endswith(MS.SECOND_GAME_NOTE)]
    assert labelled == [5], got
    # one starter line: nobody needs a second game
    monferno = _member("SPECIES_MONFERNO", DAY_CARE.format("CHIMCHAR"), ledger)
    assert not any(MS.SECOND_GAME_NOTE in t for t in _obtained(ledger, [monferno], SECOND_GAME))
    assert not any(MS.SECOND_GAME_NOTE in t for t in _obtained(ledger, [monferno], LegalityOptions()))


def test_second_game_label_follows_team_order(ledger):
    """Swap the members: Torterra first, Infernape later - the label moves to Infernape."""
    from test_validator import DAY_CARE, SECOND_GAME, _legal, _member

    from platsim.legality import movesources as MS
    from platsim.legality.validator import _team_from_dict
    from platsim.report.sources import team_sources

    d = _legal()
    infernape = d["builds"][0]
    d["builds"][0] = _member("SPECIES_TORTERRA", DAY_CARE.format("TURTWIG"), ledger)
    d["builds"][5] = infernape
    team, _, _ = _team_from_dict(d)
    got = team_sources(team, ledger.with_options(SECOND_GAME))[0]
    assert [i for i, t in enumerate(got) if t.endswith(MS.SECOND_GAME_NOTE)] == [5], got



def test_candidates_sheet_rows_equal_candidate_tests(tmp_path):
    """007 T050: one Candidates row per provenance.optimizer.candidate_tests entry, in order."""
    from platsim.report.xlsx import CANDIDATE_HEADERS, candidate_rows

    r = _report()
    tests = [{"slot": 4, "species": "SPECIES_MILOTIC", "kind": "status+item", "moves": ["MOVE_SURF", "MOVE_RECOVER"],
              "item": "leftovers", "mode": "reference", "levels": [54] * 6, "round_reached": "final", "round_runs": 375,
              "round_cleared": 300, "n_paired": 200, "rate_alt": 0.79, "rate_current": 0.71, "alt_only": 22,
              "current_only": 6, "p_value": 0.003, "p_holm": 0.012, "verdict": "alternative better", "confirmed": True,
              "adopted": True, "not_modelled": []},
             {"slot": 4, "species": "SPECIES_MILOTIC", "kind": "status", "moves": ["MOVE_SURF", "MOVE_HAZE"], "item": None,
              "mode": "reference", "levels": [54] * 6, "verdict": "dropped in screening", "adopted": False,
              "not_modelled": ["MOVE_HAZE"]}]
    r.provenance = {**(r.provenance or {}), "optimizer": {"candidate_tests": tests}}
    paths = write_all(r, tmp_path)
    wb = load_workbook(paths["xlsx"])
    rows = _sheet_rows(wb["Candidates"])
    assert tuple(rows[0]) == CANDIDATE_HEADERS
    assert len(rows) == 1 + len(tests)
    assert [list(x) for x in rows[1:]] == [[None if v == "" else v for v in row] for row in candidate_rows(r)]
    assert rows[2][-1] == "MOVE_HAZE"
