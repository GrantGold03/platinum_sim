"""Held-item candidates of B1-B5 (bench_007.json from 007-status-moves-items): every member, variant, Lv 45/55/65."""
import json, subprocess, sys
from platsim.availability.ledger import build_ledger
from platsim.optimizer import candidates as C

bench = json.loads(subprocess.run(["git", "show", "007-status-moves-items:tests/fixtures/bench_007.json"],
                                  check=True, capture_output=True, text=True).stdout)
led = build_ledger()
out = {}
for b, t in sorted(bench["teams"].items()):
    team = tuple(C.resolve_species(t["species"], led))
    for const in team:
        for v in C.variants(const, led):
            for lv in (45, 55, 65):
                mc = C.member_candidates(const, v, lv, led, team=team)
                out[f"{b}|{const}|{v.key}|{lv}"] = {
                    "items": {"/".join(ms): it for ms, it in mc.items.items()},
                    "movesets": [list(m) for m in mc.movesets]}
json.dump(out, open(sys.argv[1], "w"), indent=1, sort_keys=True)
print(len(out), "entries")
