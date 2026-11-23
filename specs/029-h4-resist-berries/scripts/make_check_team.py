"""029 T007: the player-check teams: the pre-feature B2 winner unchanged (b2-plain.json, the conditions control) and with the
top-ranked resist berry on the member whose top berry blocks the most (b2-berry.json), replacing its item (research R6)."""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
from platsim.availability.ledger import build_ledger
from platsim.evaluate import load_and_validate
from platsim.legality.models import LegalityOptions
from platsim.optimizer import candidates as C

led = build_ledger().with_options(LegalityOptions())
res = json.loads((REPO / "runs/029-evidence/b2-main/result.json").read_text())
team = res["team"]
out_dir = REPO / "runs/029-evidence/teams"; out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "b2-plain.json").write_text(json.dumps(team, indent=1))
best = None
for b in team["builds"]:
    const = C.resolve_species([x["species"] for x in team["builds"]], led)[team["builds"].index(b)]
    rank = C.resist_berry_ranking(const, b["start_level"], led)
    print(b["species"], b.get("held_item"), "->", [(k, round(v, 1)) for k, v in rank[:3]])
    if rank and (best is None or rank[0][1] > best[2]):
        best = (b, rank[0][0], rank[0][1])
b, berry, value = best
print(f"chosen: {b['species']} gets {berry} (blocks {value:.1f}) in place of {b.get('held_item')}")
b["held_item"] = berry
(out_dir / "b2-berry.json").write_text(json.dumps(team, indent=1))
load_and_validate(out_dir / "b2-berry.json"); load_and_validate(out_dir / "b2-plain.json")
print("written and validated")
