"""018: one default strong player (platsim.evaluate.DEFAULT_PLAYER_POLICY) and `optimize --player-policy`
(specs/018-expectimax2-v4/contracts/python-and-cli.md). No battle is simulated."""

from __future__ import annotations

from platsim import bench, cli
from platsim.evaluate import DEFAULT_PLAYER_POLICY
from platsim.optimizer import levels
from platsim.optimizer.api import OptimizeRequest

SIX = ["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"]


def _sub_help(parser, name: str) -> str:
    for action in parser._subparsers._group_actions:
        if name in getattr(action, "choices", {}):
            return action.choices[name].format_help()
    raise AssertionError(f"no subcommand {name}")


def test_every_default_is_the_one_constant():
    assert bench.DEFAULT_POLICY == DEFAULT_PLAYER_POLICY
    assert levels.POLICY == DEFAULT_PLAYER_POLICY
    assert OptimizeRequest(species=tuple(SIX)).player_policy == DEFAULT_PLAYER_POLICY


def test_cli_defaults_and_help_name_the_constant():
    p = cli.build_parser()
    assert p.parse_args(["evaluate", "x.json"]).player_policy == DEFAULT_PLAYER_POLICY
    assert p.parse_args(["bench"]).policy == DEFAULT_PLAYER_POLICY
    assert p.parse_args(["optimize", *SIX]).player_policy == DEFAULT_PLAYER_POLICY
    for sub in ("evaluate", "bench", "optimize"):
        assert DEFAULT_PLAYER_POLICY in _sub_help(p, sub), sub


def test_optimize_player_policy_reaches_the_request():
    p = cli.build_parser()
    req = cli.optimize_request(p.parse_args(["optimize", *SIX, "--player-policy", "expectimax2-v4"]))
    assert req.player_policy == "expectimax2-v4"
    assert req.species == tuple(SIX)
    assert cli.optimize_request(p.parse_args(["optimize", *SIX])).player_policy == DEFAULT_PLAYER_POLICY
