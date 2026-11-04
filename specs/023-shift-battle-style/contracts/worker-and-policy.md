# Contract: worker request, the offer, the policy hook

## Request (`gauntlet` op)

- `battle_style`: `"set"` (default when absent) or `"shift"`. Any other value: the worker answers `ok: false` with a
  request error naming the field. All other fields unchanged.
- Hello gains `battle_styles: ["set", "shift"]`.

## Behaviour under `shift` (per battle, in the turn loop)

1. When p1 has no request and p2's request is a replacement: `c2 = oppPolicy.choose(ctxFor(p2))` once; parse `switch N`;
   `incoming = p2.pokemon[N-1]`.
2. Gate: p1's active has HP, and p1 has a member with HP that is not active (eggs never enter a party here). If the gate
   fails: `makeChoices('', c2)` exactly as under Set.
3. Offer: `{choice, reason} = playerPolicy.shiftChoice?.(ctxFor(p1), incoming) ?? {choice: null, reason: 'no hook'}`.
   Validate: `choice` is `null` (stay) or `switch N` with N a p1 member with HP, not active; anything else is a policy
   error (thrown, like an illegal choice today). `reason` is a short string the gauntlet writes into the log line and
   the event record.
4. Log line `|-message|shift: ...` (data-model) appended before the choices are made.
5. On a switch: `p1.active[0].switchFlag = true; battle.makeRequest('switch'); battle.makeChoices('switch N', c2)`.
   On stay: `battle.makeChoices('', c2)`.
6. Battle record gains `shift: {offers, switches, events}`; the run response gains `battle_style: "shift"`.

Under `set`: no step above runs; no field, no line, no extra draw. Fixture digests and determinism are the guard.

## Policy hook

`shiftChoice(ctx, incoming) -> {choice: null | "switch N", reason: string}` (optional). `ctx = {gd, battle, side,
request, trainer, bag, members}` as for `choose`. The policy must not write to the battle log (the gauntlet does) and must be deterministic for the same
battle state and seed. Wrappers (`runRecorded`, test instruments) forward it when present.

- expectimax2 (v1, v2, v4): `scoreShift(ctx, opts, name, foeIdx) -> {stay: v, candidates: [{idx, v}]}`;
  `shiftChoice` returns `{choice: 'switch N', reason}` for the best candidate when its value is strictly above the stay
  value, else `{choice: null, reason}`; `reason` names the stay value and the best candidate's value.
- greedy-v1: `memberScore(gd, battle, side, pokemon, foe)`; `{choice: 'switch N', reason}` for the best bench member
  when strictly above the active's score against `incoming`, else `{choice: null, reason}`; `reason` names both scores.
