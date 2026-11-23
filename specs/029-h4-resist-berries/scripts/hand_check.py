"""029 hand check (quickstart step 3): the six B2 species' extras with dead moves under their own valuation."""
import json, sys, time
sys.path.insert(0, __import__("os").path.dirname(__file__))
import attribution as A
from platsim.availability.ledger import build_ledger
from platsim.legality.models import LegalityOptions
from platsim.optimizer import candidates as C
from platsim.optimizer import run as RUN

led = build_ledger().with_options(LegalityOptions())
consts = C.resolve_species(["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"], led)
short = lambda ms: " / ".join(m.removeprefix("MOVE_") for m in ms)
t0 = time.perf_counter()
mcs = {c: C.member_candidates(c, C.variants(c, led)[0], 48, led, team=tuple(consts)) for c in consts}
print(f"member_candidates, six B2 species at Lv 48: {time.perf_counter() - t0:.1f} s")
t0 = time.perf_counter(); RUN._build_cands(consts, led, 48)
print(f"full team build with the allocation at Lv 48: {time.perf_counter() - t0:.1f} s (SC-006, at most 10 s)")
total = 0
for c in consts:
    mc = mcs[c]
    n = len(mc.movesets) - mc.extras
    print(f"{c} base {[short(ms) for ms in mc.movesets[:n]]}")
    for ms in mc.movesets[:n]:
        print(f"  items_extra[{short(ms)}]: {mc.items_extra.get(ms)}")
    for e in A.extras_of(mc):
        total += len(e["dead"])
        print(f"  extra[{e['kind']}{'/' + e['item'] if e['item'] else ''}]: {short(e['set'])}  dead {[m.removeprefix('MOVE_') for m in e['dead']]}"
              + (f"  filler: {e['filler_reason']}" if e['filler_reason'] else ""))
    if getattr(mc, "dropped_extras", None):
        print(f"  dropped_extras: {mc.dropped_extras}")
print(f"dead moves in B2 extras: {total}")

# 029: the berry ranking per B2 member (resist_berry_ranking, when the code has it)
if hasattr(C, "resist_berry_ranking"):
    for c in consts:
        mc = mcs[c]
        print(f"{c} berry ranking: {[(k, round(v, 1)) for k, v in C.resist_berry_ranking(c, mc.ref_level, led)[:4]]}")
