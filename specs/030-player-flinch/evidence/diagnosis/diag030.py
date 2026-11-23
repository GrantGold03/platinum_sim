"""030 diagnosis: replay the discordant B2 gauntlets with both players; tabulate where each lost (trainer) and turn counts."""
import json, sys, collections
from pathlib import Path
REPO = Path("/home/grant/Desktop/platinum_sim")
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "specs/030-player-flinch/scripts"))
import paired_policies as PP
from platsim.sim.seeds import derive_seed
from platsim.sim.pool import WorkerPool
d = REPO / "runs/030-evidence/pairs-b2-main"
A = json.loads((d / "file_runs_030-evidence_teams_b2-main.json__expectimax2-v4__2000.json").read_text())
B = json.loads((d / "file_runs_030-evidence_teams_b2-main.json__expectimax2-v4_Q_flinch-0__2000.json").read_text())
only_ref = [i for i in range(2000) if B["cleared"][i] and not A["cleared"][i]]
only_mod = [i for i in range(2000) if A["cleared"][i] and not B["cleared"][i]]
team = "file:runs/030-evidence/teams/b2-main.json"
team_reqs = PP.load_team_requests(team, d)
master = f"018-pairs|{team}"
def reqs(policy, idx):
    return [{"op": "gauntlet", "id": f"{policy}-{i}", "team": team_reqs, "seed": derive_seed(master, i, 0), "player_policy": policy,
             "opponent_policy": PP.OPPONENT, "stop_on_loss": True, "log": "none", "battle_style": "shift"} for i in idx]
res = {}
with WorkerPool(16) as pool:
    for pol in ("expectimax2-v4", "expectimax2-v4?flinch=0"):
        rs = pool.map(reqs(pol, only_ref + only_mod))
        res[pol] = dict(zip(only_ref + only_mod, rs))
def lost_at(r):
    for b in r["battles"]:
        if b.get("end") != "win": return b["trainer"]
    return None
for name, idx in (("model lost, reference cleared", only_ref), ("model cleared, reference lost", only_mod)):
    ca = collections.Counter(lost_at(res["expectimax2-v4"][i]) if name.startswith("model lost") else lost_at(res["expectimax2-v4?flinch=0"][i]) for i in idx)
    print(name, len(idx), "losing battle:", dict(ca))
    chk = sum(1 for i in idx if bool(res["expectimax2-v4"][i]["cleared"]) == bool(A["cleared"][i]) and bool(res["expectimax2-v4?flinch=0"][i]["cleared"]) == bool(B["cleared"][i]))
    print("  reproduced", chk, "of", len(idx))
json.dump({"only_ref": only_ref, "only_mod": only_mod, "battles": {p: {str(i): r["battles"] for i, r in v.items()} for p, v in res.items()}},
          open(REPO / "runs/030-evidence/diag-discordant.json", "w"))
print("first battle keys:", list(res["expectimax2-v4"][only_ref[0]]["battles"][0].keys()))
