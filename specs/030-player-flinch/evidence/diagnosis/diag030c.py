"""030: in the flinch model's Cynthia battles (fresh2 seeds, a sample of 300 gauntlets), how often the player's flinch moves went
first in their turn, and how often they flinched."""
import json, sys, collections, re
from pathlib import Path
REPO = Path("/home/grant/Desktop/platinum_sim")
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "specs/030-player-flinch/scripts"))
import paired_policies as PP
from platsim.sim.seeds import derive_seed
from platsim.sim.pool import WorkerPool
team = "file:runs/030-evidence/teams/b2-main.json"
team_reqs = PP.load_team_requests(team, REPO / "runs/030-evidence/pairs-fresh2")
master = f"018-pairs|{team}|fresh2"
FLINCH = {"Rock Slide", "Waterfall"}
with WorkerPool(16) as pool:
    rs = pool.map([{"op": "gauntlet", "id": f"g{i}", "team": team_reqs, "seed": derive_seed(master, i, 0), "player_policy": "expectimax2-v4",
                    "opponent_policy": PP.OPPONENT, "stop_on_loss": True, "log": "full", "battle_style": "shift"} for i in range(300)])
first = second = flinched = 0; tgt = collections.Counter(); tgt_second = collections.Counter()
for r in rs:
    for b, lg in zip(r["battles"], r["log"]):
        if b["trainer"] != "cynthia": continue
        lines = (lg if isinstance(lg, str) else "\n".join(lg)).split("\n")
        turn = []
        for l in lines + ["|turn|end"]:
            if l.startswith("|turn|"):
                moved = []
                for i, t in enumerate(turn):
                    m = re.match(r"\|move\|(p[12])a: ([^|]+)\|([^|]+)\|(p[12])a: ([^|]+)", t)
                    if m: moved.append((i, m.group(1), m.group(3), m.group(5)))
                for i, side, mv, target in moved:
                    if side == "p1" and mv in FLINCH:
                        foe_before = any(s == "p2" and j < i for j, s, _, _ in moved)
                        if foe_before: second += 1; tgt_second[target] += 1
                        else: first += 1; tgt[target] += 1
                        if any(x.startswith("|cant|p2a") and x.endswith("flinch") for x in turn): flinched += 1
                turn = []
            else:
                turn.append(l)
print(f"player's Rock Slide/Waterfall in Cynthia battles: first {first}, second {second}; turns with a Cynthia flinch {flinched}")
print("targets when first:", dict(tgt.most_common(8))); print("targets when second:", dict(tgt_second.most_common(8)))
