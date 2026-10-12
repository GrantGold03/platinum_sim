"""Cleaning of text the page shows but does not own (003 spec FR-001, FR-002; research R6).

Report warnings, recorded job errors and optimizer/validator messages are written for the report
files and the command line, which keep their wording (Constitution IV: the report files are the
record). Before such text reaches the page it passes through `clean`, which
- removes requirement references (`FR-005`, `FR-006a`, `SC-003`, `research.md R8`) together with the
  parentheses or separators they leave behind, and
- says "Pokémon" instead of the whole word "species" or an unaccented "pokemon" (all capitals stay
  capitals). Identifiers such as `allow_post_game_pokemon` or `pokemon-showdown/` are left alone.

Text the web layer writes itself is worded correctly at its source; this is the safety net for
everything passed through.
"""

from __future__ import annotations

import re

_REF = r"(?:(?:spec\s+)?(?:FR|SC)-\d+[a-z]?|research\.md R\d+)"
# Known recorded phrasings whose reference is part of the sentence: reworded, not just cut.
_PHRASES = (
    (re.compile(r"it does not meet SC-\d+[a-z]?"), "it does not meet the confidence target"),
)
_PAREN_ONLY = re.compile(r"\s*\(\s*" + _REF + r"\s*\)")  # " (FR-019)"
_IN_PAREN = re.compile(r"(?:,\s*|;\s*)" + _REF + r"(?=\s*[);])|" + _REF + r"\s*[,;]\s*(?=[^)]*\))")
_BARE = re.compile(r"\s*\b" + _REF + r"\b")
_SPECIES = re.compile(r"(?<![\w/-])(?:species|pokemon)(?![\w/-])", re.IGNORECASE)


def _species(m: re.Match) -> str:
    return "POKÉMON" if m.group(0).isupper() else "Pokémon"


def clean(text: str | None) -> str | None:
    if text is None:
        return None
    out = text
    for pat, repl in _PHRASES:
        out = pat.sub(repl, out)
    out = _PAREN_ONLY.sub("", out)
    out = _IN_PAREN.sub("", out)
    out = _BARE.sub("", out)
    out = _SPECIES.sub(_species, out)
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"\s+([,.;)])", r"\1", out)
    out = re.sub(r"\(\s+", "(", out)
    out = re.sub(r" {2,}", " ", out)
    return out.strip() if out != text else text
