"""003 T050 (spec FR-022): every move-type colour is readable on the card background in both themes
(WCAG contrast ratio >= 4.5:1). Type colours are page styling, not game data; the 17 type names come
from the decomp (generated/pokemon_types.txt via platsim.decomp)."""

from __future__ import annotations

import re

import pytest

from platsim.pins import REPO_ROOT

CSS = REPO_ROOT / "src/platsim/web/static/style.css"
TYPES = ("normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground", "flying", "psychic",
         "bug", "rock", "ghost", "dragon", "dark", "steel")


def _lum(h: str) -> float:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _block(css: str, selector: str) -> dict[str, str]:
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\n\}", css, re.S)
    assert m, selector
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6});", m.group(1)))


def _themes(css: str) -> dict[str, dict[str, str]]:
    return {"light": _block(css, ":root"), "dark": _block(css, ':root[data-theme="dark"]')}


def test_type_names_match_the_decomp():
    from platsim.decomp.moves import load_moves

    types = {m.type.removeprefix("TYPE_").lower() for m in load_moves().values()} - {"mystery", "none"}
    assert types == set(TYPES), types


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_type_colour_is_readable(theme):
    t = _themes(CSS.read_text())[theme]
    bg = t["surface"]
    low = {k: round(ratio(t[f"type-{k}"], bg), 2) for k in TYPES if ratio(t[f"type-{k}"], bg) < 4.5}
    assert not low, (theme, low)


def test_positive_control_a_bad_colour_fails():
    assert ratio("#ffff00", "#ffffff") < 4.5
    stub = ':root {\n  --surface: #ffffff;\n  --type-electric: #ffff00;\n}\n:root[data-theme="dark"] {\n  --surface: #000000;\n}\n'
    t = _themes(stub)["light"]
    assert ratio(t["type-electric"], t["surface"]) < 4.5
