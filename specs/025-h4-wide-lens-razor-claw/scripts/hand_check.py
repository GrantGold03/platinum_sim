"""025 hand check (quickstart step 3): the six B2 species' candidate lists on the branch."""
import json, sys
from platsim.availability.ledger import build_ledger
from platsim.legality.models import LegalityOptions
from platsim.optimizer import candidates as C

led = build_ledger().with_options(LegalityOptions())
consts = C.resolve_species(["garchomp", "infernape", "staraptor", "rotom", "floatzel", "weavile"], led)
main = json.load(open("specs/025-h4-wide-lens-razor-claw/evidence/candidates-main.json"))
short = lambda ms: " / ".join(m.removeprefix("MOVE_") for m in ms)
for c in consts:
    v = C.variants(c, led)[0]
    mc = C.member_candidates(c, v, 48, led, team=tuple(consts))
    n_today = len(mc.movesets) - mc.extras
    print(f"{c}|{v.key} (Lv 48) variable offered: {mc.variable_offered}; today's {n_today} sets, extras {mc.extras} {mc.extras_by_kind}")
    for ms in mc.movesets[:n_today]:
        print(f"  today: {short(ms)}  items {mc.items[ms]}  items_extra {mc.items_extra.get(ms)}")
    for ms in mc.movesets[n_today:]:
        kind = mc.extra_kind.get(ms, "?")
        print(f"  extra[{kind}]: {short(ms)}  items {mc.items[ms]}" + (f"  items_extra {mc.items_extra[ms]}" if ms in mc.items_extra else ""))
    print(f"  pool: {[m.removeprefix('MOVE_') for m in mc.pool]}")
    dom = {m: r for m, r in mc.pruned.items() if "dominated by" in r}
    for m, r in dom.items():
        print(f"  pruned {m.removeprefix('MOVE_')}: {r}")
    rec = main.get(f"B2quick|{c}|{v.key}")
    if rec:
        old_today = [tuple(x) for x in rec["movesets"][:len(rec["movesets"]) - rec.get("extras", 0)]]
        new_today = list(mc.movesets[:n_today])
        if old_today != new_today:
            print(f"  TODAY'S SETS CHANGED vs main: main {[short(x) for x in old_today]}")
        old_pool = rec["pool"]
        if old_pool != list(mc.pool):
            print(f"  POOL CHANGED vs main: main {[m.removeprefix('MOVE_') for m in old_pool]}")
