"""031 T012: the multi-hit measurement teams from the B5 quick winner on the branch: Torterra on its flinch_item set (Earthquake,
Stone Edge, Crunch, Bullet Seed) holding King's Rock, and the same set holding its usual item (the winner's Sitrus Berry); every
other member as in the winner. Realized through the optimizer's own legality path and validated by the evaluate loader."""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
from platsim.availability.ledger import build_ledger
from platsim.evaluate import load_and_validate
from platsim.legality.models import LegalityOptions
from platsim.optimizer import candidates as C, resources as R

led = build_ledger().with_options(LegalityOptions())
res = json.loads((REPO / "runs/031-evidence/b5-branch/result.json").read_text())
builds = res["team"]["builds"]
consts = C.resolve_species([b["species"] for b in builds], led)
levels = [b["start_level"] for b in builds]
mc = C.member_candidates(consts[0], C.variants(consts[0], led)[0], levels[0], led, team=tuple(consts))
flinch = [ms for ms, k in mc.extra_kind.items() if k == "flinch_item"]
assert consts[0] == "SPECIES_TORTERRA" and len(flinch) == 1, (consts[0], flinch)
usual = builds[0]["held_item"]
out = REPO / "runs/031-evidence/teams"; out.mkdir(parents=True, exist_ok=True)
for name, item in (("b5-torterra-kings-rock", "kings_rock"), ("b5-torterra-usual", usual)):
    specs = []
    for i, (c, b) in enumerate(zip(consts, builds)):
        moves = flinch[0] if i == 0 else tuple(f"MOVE_{m['move'].upper()}" for m in b["moves"])
        specs.append(R.MemberSpec(c, "own", moves, item if i == 0 else b["held_item"], b.get("ability")))
    r = R.realize(tuple(specs), levels, led)
    assert not isinstance(r, R.Refusal), r
    team = {"builds": [b.to_dict() if hasattr(b, "to_dict") else b.__dict__ for b in r.team.builds], "resource_use": r.team.resource_use}
    p = out / f"{name}.json"; p.write_text(json.dumps(team, indent=1, default=lambda o: o.__dict__))
    load_and_validate(p)
    print(name, [(b["species"], b["start_level"], b["held_item"], [m["move"] if isinstance(m, dict) else m for m in b["moves"]]) for b in team["builds"]][:1])
