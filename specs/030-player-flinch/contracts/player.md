# Contract: the battle player's flinch model

- `expectimax2-v4` (default): flinch modelled per R1 to R3.
- `expectimax2-v4?flinch=0`: no flinch, Fake Out as today; byte-identical play to `main`'s v4 (its bench digest equals the one
  recorded on `main` before the change).
- `expectimax2-v1`, `expectimax2-v2`: unchanged (flinch off; their replay entries stay byte-identical; v4's entry is re-recorded).
- A flinch outcome is considered only when the flinch move's user moves before its target in the turn (owner's rule, FR-012).
- No change to report fields; the policy keeps the name `expectimax2-v4`.
