"""028 T007: the player-check team: the B2 quick winner (028 pre-feature side) with Garchomp holding Shell Bell in place of
its Sitrus Berry (research R5), validated by the evaluate loader (legality and the one copy)."""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
from platsim.evaluate import load_and_validate

res = json.loads((REPO / "runs/028-evidence/b2-main/result.json").read_text())
team = res["team"]
hits = [b for b in team["builds"] if b["species"] == "garchomp"]
assert len(hits) == 1, [b["species"] for b in team["builds"]]
print("Garchomp's item before:", hits[0].get("held_item"))
hits[0]["held_item"] = "shell_bell"
out = REPO / "runs/028-evidence/teams/b2-shellbell.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(team, indent=1))
load_and_validate(out)
print("written and validated:", out)
