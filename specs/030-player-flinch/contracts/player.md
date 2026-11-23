# Contract: the battle player's flinch model

- `expectimax2-v4` (default): flinch modelled per R1 to R3.
- `expectimax2-v4?flinch=0`: no flinch, Fake Out as today; byte-identical play to `main`'s v4 (the replay test with this knob).
- A flinch outcome is considered only when the flinch move's user moves before its target in the turn (owner's rule, FR-012).
- No change to report fields; the policy keeps the name `expectimax2-v4`.
