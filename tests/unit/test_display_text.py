"""T004 (003): `web.display_text.clean` removes requirement ids and the word "species" from text the
page shows (spec FR-001, FR-002; research R6). The report files are never changed; this only cleans
what the page displays."""

import re

import pytest

from platsim.report.json_report import QUICK_WARNING
from platsim.web.display_text import clean

ID_RE = re.compile(r"\b(FR|SC)-\d+[a-z]?\b|research\.md R\d+")


def test_paired_runs_warning_loses_its_requirement_id():
    text = ("Winner and runner-up are statistically indistinguishable on paired runs (FR-019); "
            "the winner is the screening winner.")
    assert clean(text) == ("Winner and runner-up are statistically indistinguishable on paired runs; "
                           "the winner is the screening winner.")


# As recorded in reports written before 003 (e.g. runs/job-20261008T115114Z-feb186/result.json).
RECORDED_QUICK = ("QUICK BUDGET: this result used the 'quick' simulation preset (research.md R8). Its run counts "
                  "have no confidence-interval target, it does not meet SC-003, and it can never be 'qualified'. "
                  "For testing only.")


def test_quick_warning_loses_internal_references_and_keeps_its_meaning():
    out = clean(RECORDED_QUICK)
    assert ID_RE.search(RECORDED_QUICK), "positive control: the recorded warning does contain ids"
    assert not ID_RE.search(QUICK_WARNING) and clean(QUICK_WARNING) == QUICK_WARNING  # new reports: nothing to clean
    assert not ID_RE.search(out)
    assert "QUICK BUDGET" in out and "never be 'qualified'" in out
    assert "  " not in out and "()" not in out and " ," not in out and " ." not in out


@pytest.mark.parametrize("raw, want", [
    ("exactly 6 species are required, got 5", "exactly 6 Pokémon are required, got 5"),
    ("Species data is loading", "Pokémon data is loading"),
    ("SPECIES LIST", "POKÉMON LIST"),
    ("unknown species", "unknown Pokémon"),
    ("the same pokemon and seed", "the same Pokémon and seed"),
    ("Pokemon Showdown", "Pokémon Showdown"),
    ("excluded by project rule (too costly to obtain, spec FR-006a)", "excluded by project rule (too costly to obtain)"),
    ("needs the National Dex (not allowed, FR-003a)", "needs the National Dex (not allowed)"),
    ("trade evolution from Graveler (needs a second cartridge, FR-005; allowed only with the trade-evolutions option)",
     "trade evolution from Graveler (needs a second cartridge; allowed only with the trade-evolutions option)"),
])
def test_patterns(raw, want):
    assert clean(raw) == want


def test_text_with_nothing_to_clean_is_unchanged():
    for s in ("Wild - Route 209 (Staravia, grass)", "Pokémon", "subspecies-like words: specieslike",
              "allow_post_game_pokemon", "pokemon-showdown/sim/battle.ts", "res/pokemon/gible", ""):
        assert clean(s) == s


def test_none_stays_none():
    assert clean(None) is None


def test_positive_control_every_pattern_changes():
    raw = "species FR-001 (SC-002) (research.md R8)"
    out = clean(raw)
    assert out != raw and out == "Pokémon"
