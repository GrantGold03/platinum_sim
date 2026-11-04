"""Feature 023: the battle style carried on every worker request.

``set`` is Showdown's behaviour (only the side whose Pokemon fainted replaces it); ``shift`` is Platinum's
default (after the trainer's active faints and the player's does not, the trainer's replacement is named and
the player may switch for free before it enters; sim/gauntlet.mjs implements it through the engine's own
switch flag and instant-switch path). The default is ``shift`` since the owner's decision of 2026-11-04 on the
feature's acceptance table (Shift better on all four teams, p down to 1e-111); ``set`` stays available as the
reference. The worker echoes ``battle_style`` only under Shift, so a response without the
key reads as ``set`` (``style_of``) and Set results are byte-identical to before the feature.
"""

from __future__ import annotations

BATTLE_STYLES = ("set", "shift")
DEFAULT_BATTLE_STYLE = "shift"


def check_style(style: str, flag: str = "battle_style") -> str:
    if style not in BATTLE_STYLES:
        raise ValueError(f"{flag} must be one of {', '.join(BATTLE_STYLES)}, got {style!r}")
    return style


WORKER_ABSENT_STYLE = "set"  # the worker echoes the field only under Shift; this never follows DEFAULT_BATTLE_STYLE


def style_of(response: dict) -> str:
    """The style a worker response was played under (absent means ``set``, whatever the Python default)."""
    return response.get("battle_style", WORKER_ABSENT_STYLE)


def request_fields(style: str) -> dict:
    """The request-dict entry: always sent, so every builder is explicit."""
    return {"battle_style": style}
