"""Read-only: dead moves in the 024/025 extra sets on main, judged without the item and with each set's own item."""
import json
from collections import Counter
from platsim.availability.ledger import build_ledger
from platsim.legality.models import LegalityOptions
from platsim.optimizer import candidates as C

led = build_ledger().with_options(LegalityOptions())
snap = json.load(open("specs/026-marginal-coverage-sets/evidence/candidates-main.json"))
EFFECT = {"wide_lens": C.ACCURACY_UP_EFFECT, "razor_claw": C.CRITRATE_UP_EFFECT}
tot = Counter(); members_with = 0; examples = []
for key, s in snap.items():
    call = s["call"]
    v = next(x for x in C.variants(call["species"], led) if x.key == call["variant"])
    mc = C.member_candidates(call["species"], v, call["ref_level"], led, k=call["k"], team=tuple(call["team"]))
    n_base = len(mc.movesets) - mc.extras
    any_dead = False
    for ms in mc.movesets[n_base:]:
        kind = mc.extra_kind.get(ms, "variable_power")
        plain = {m: C.move_value(mc.species, m, mc.ref_level) for m in ms}
        d_plain = C.dead_moves(ms, plain)
        eff = EFFECT.get(mc.item_extras.get(ms))
        own = {m: C.move_value(mc.species, m, mc.ref_level, item_effect=eff) for m in ms} if eff else plain
        d_own = C.dead_moves(ms, own)
        tot[(kind, "sets")] += 1; tot[(kind, "dead_plain")] += len(d_plain); tot[(kind, "dead_own")] += len(d_own)
        tot[(kind, "sets_with_dead_own")] += bool(d_own)
        if d_own:
            any_dead = True
            if len(examples) < 4 and key.startswith("B2quick"):
                examples.append((key.split("|")[1], kind, [m.removeprefix("MOVE_") for m in ms], [m.removeprefix("MOVE_") for m in d_own]))
    members_with += any_dead
for kind in ("variable_power", "accuracy_item", "crit_item"):
    print(f"{kind:15s} sets {tot[(kind,'sets')]:4d}  dead (no item) {tot[(kind,'dead_plain')]:4d}  dead (own valuation) {tot[(kind,'dead_own')]:4d}  sets with a dead move {tot[(kind,'sets_with_dead_own')]:4d}")
print("members (of 36) with a dead move in an extra set:", members_with)
for e in examples: print("  e.g.", e)
