"""Seed derivation (T033). Must match sim/seeds.mjs exactly.

    derive_seed(master, run, battle) = "sodium," + sha256(f"{master}|{run}|{battle}")[:32 hex]

The string is UTF-8 encoded; ints format in decimal (same as JS template literals for safe ints).
"sodium,<32 hex>" is the PRNG seed format Showdown accepts (contracts/worker-protocol.md).
Battle index 99 is reserved for Cynthia top-up battles (T057) so they never collide with full runs.
"""

import hashlib

SCHEME = "sodium,sha256(f'{master}|{run}|{battle}')[:32]"


def derive_seed(master: str | int, run: int, battle: int) -> str:
    # bool/float would stringify differently in JS ("true", "1" vs Python "True", "1.0");
    # ints above 2**53 lose precision in JS. Reject them so the two sides cannot disagree.
    for name, v in (("master", master), ("run", run), ("battle", battle)):
        if isinstance(v, bool) or not isinstance(v, (int, str)) or (name != "master" and not isinstance(v, int)):
            raise TypeError(f"{name} must be {'str or ' if name == 'master' else ''}int, got {v!r}")
        if isinstance(v, int) and abs(v) > 2**53:
            raise ValueError(f"{name}={v} exceeds 2**53 (not exact in JS)")
    digest = hashlib.sha256(f"{master}|{run}|{battle}".encode("utf-8")).hexdigest()
    return "sodium," + digest[:32]
