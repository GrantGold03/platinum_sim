"""030 diagnosis 2: full logs of the discordant B2 gauntlets; in the Cynthia battle count the player's moves per Pokemon,
its switches, and flinch events, model against reference."""
import json, sys, collections, re
from pathlib import Path
REPO = Path("/home/grant/Desktop/platinum_sim")
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "specs/030-player-flinch/scripts"))
import paired_policies as PP
from platsim.sim.seeds import derive_seed
from platsim.sim.pool import WorkerPool
D = json.loads((REPO / "runs/030-evidence/diag-discordant.json").read_text())
idx = D["only_ref"] + D["only_mod"]
team = "file:runs/030-evidence/teams/b2-main.json"
d = REPO / "runs/030-evidence/pairs-b2-main"
team_reqs = PP.load_team_requests(team, d)
master = f"018-pairs|{team}"
def reqs(policy):
    return [{"op": "gauntlet", "id": f"{policy}-{i}", "team": team_reqs, "seed": derive_seed(master, i, 0), "player_policy": policy,
             "opponent_policy": PP.OPPONENT, "stop_on_loss": True, "log": "full", "battle_style": "shift"} for i in idx]
logs = {}
with WorkerPool(16) as pool:
    for pol in ("expectimax2-v4", "expectimax2-v4?flinch=0"):
        logs[pol] = dict(zip(idx, pool.map(reqs(pol))))
def stats(pol, which):
    moves, sw, cant_p1, cant_p2, turns = collections.Counter(), 0, 0, 0, 0
    for i in which:
        r = logs[pol][i]
        for b, lg in zip(r["battles"], r["log"]):
            if b["trainer"] != "cynthia": continue
            text = lg if isinstance(lg, str) else "\n".join(lg)
            for l in text.split("\n"):
                m = re.match(r"\|move\|p1a: ([^|]+)\|([^|]+)\|", l)
                if m: moves[(m.group(1), m.group(2))] += 1
                if l.startswith("|switch|p1a"): sw += 1
                if l.startswith("|cant|p1a") and l.endswith("flinch"): cant_p1 += 1
                if l.startswith("|cant|p2a") and l.endswith("flinch"): cant_p2 += 1
                if l.startswith("|turn|"): turns += 1
    return moves, sw, cant_p1, cant_p2, turns
for which_name, which in (("model lost / ref cleared (87)", D["only_ref"]), ("model cleared / ref lost (59)", D["only_mod"]), ("all 146", idx)):
    print("==", which_name)
    sm, sr = stats("expectimax2-v4", which), stats("expectimax2-v4?flinch=0", which)
    print(f"  switches model {sm[1]} ref {sr[1]}; player flinched model {sm[2]} ref {sr[2]}; Cynthia flinched model {sm[3]} ref {sr[3]}; turns model {sm[4]} ref {sr[4]}")
    keys = sorted(set(sm[0]) | set(sr[0]), key=lambda k: -(sm[0][k] + sr[0][k]))
    for k in keys[:16]:
        print(f"  {k[0]:10} {k[1]:14} model {sm[0][k]:4} ref {sr[0][k]:4}")
