<!--
Sync Impact Report
- Version change: (unversioned template) → 1.0.0
- Modified principles: n/a (initial ratification; all placeholders replaced)
  - [PRINCIPLE_1_NAME] → I. Decomp Is Ground Truth (NON-NEGOTIABLE)
  - [PRINCIPLE_2_NAME] → II. Showdown Is the Battle Engine
  - [PRINCIPLE_3_NAME] → III. In-Game Legality of Every Output
  - [PRINCIPLE_4_NAME] → IV. Reproducible, Statistically Honest Evaluation
  - [PRINCIPLE_5_NAME] → V. Verified Claims With Positive Controls
- Added sections: Technical Constraints; Development Workflow & Quality Gates; Governance
- Removed sections: none
- Templates reviewed (read at runtime, not modified by this command):
  - .specify/templates/plan-template.md (Constitution Check gate) — compatible
  - .specify/templates/spec-template.md — compatible
  - .specify/templates/tasks-template.md — compatible
- Deferred TODOs: none
-->

# Pokemon Platinum Team Simulator Constitution

The Pokemon Platinum Team Simulator takes six Pokemon species as input and produces an
optimized team (moves, ability, nature, held item, IVs/EVs, level as applicable). Game data is
checked against the `pokeplatinum` decompilation; battles are run with Pokemon Showdown's
simulator.

## Core Principles

### I. Decomp Is Ground Truth (NON-NEGOTIABLE)

- All game data — base stats, types, abilities, learnsets (level-up, TM/HM, tutor, egg),
  evolution rules, item data and availability, move data, and trainer parties — MUST be
  extracted programmatically from the `pokeplatinum` decomp sources (`res/`, `src/`, `include/`).
- Hand-typed game data is forbidden. Wikis, Bulbapedia, Serebii, Smogon, and Showdown's own
  data files MUST NOT be used as a source of truth; they MAY be used only as a cross-check.
- Every extracted datum MUST be traceable to a decomp source path and the pinned decomp commit.
- The target game is Platinum (USA) Rev 1 (`sha1 0862ec35b24de5c7e2dcb88c9eea0873110d755c`),
  which is the decomp's default build target. Any other revision requires a constitution amendment.

Rationale: the whole value of the tool is that its answers hold in the real cartridge. Any
second-hand data source reintroduces the errors the decomp exists to eliminate.

### II. Showdown Is the Battle Engine

- Battle simulation MUST use Pokemon Showdown's simulator with its Gen 4 Platinum ruleset
  (`data/mods/gen4pt`) at a pinned commit. The project MUST NOT reimplement battle mechanics.
- Where Showdown's data (learnsets, stats, items, move data) disagrees with the decomp, the
  decomp wins. The disagreement MUST be recorded in a divergence ledger and either corrected by
  injecting decomp data into the simulator or explicitly accepted with a stated impact.
- Known mechanical gaps between Showdown and the cartridge (e.g., in-game trainer AI, which
  Showdown does not model) MUST be documented. The opponent decision policy used in battle
  tests MUST be named in every result.
- Modifications to the vendored `pokemon-showdown` tree MUST be avoided; integrate through its
  public APIs (e.g., `BattleStream`, `Dex`, `Teams`) or a project-owned mod/patch layer.

Rationale: Showdown is a mature, tested engine; reimplementing it is a large source of bugs.
Its data is not the cartridge's data, so the seams must be explicit.

### III. In-Game Legality of Every Output

- Every team the tool outputs MUST be obtainable in Platinum per decomp data: each move learnable
  by that species (or a pre-evolution) by a decomp-listed method, abilities valid for the species,
  held items obtainable in Platinum, IVs 0–31, EVs ≤255 per stat and ≤510 total.
- Legality MUST be enforced by a validator that is independent of the optimizer and runs on
  every output. The optimizer MUST NOT be trusted to stay legal on its own.
- Optional constraints (level cap, item availability by story progress, banned methods) MUST be
  explicit inputs, never silent assumptions.
- An illegal input species or an input that cannot form a legal set MUST fail with a clear error
  naming the reason, not a degraded result.

Rationale: an optimal team that cannot be built in the game is worthless to the user.

### IV. Reproducible, Statistically Honest Evaluation

- Every battle run MUST be seeded; identical inputs, seeds, and pinned commits MUST produce
  identical results.
- Every reported result MUST include: number of battles, win rate with a confidence interval,
  opponent set, opponent policy, seeds, decomp commit, and Showdown commit.
- Comparisons between candidate teams MUST use the same opponents and seeds (paired evaluation).
  A candidate MUST NOT be reported as "better" unless the difference is statistically supported;
  otherwise it is reported as indistinguishable.
- The optimizer's objective function MUST be stated in output and in the feature spec.

Rationale: battle outcomes are stochastic. Without fixed seeds and intervals, the optimizer
chases noise and its rankings cannot be trusted or reproduced.

### V. Verified Claims With Positive Controls

- Data extraction MUST be tested against known values taken directly from the decomp (e.g., a
  specific species' base stats and learnset) so a broken extractor fails loudly.
- Any negative result ("no legal set", "no divergence found", "move unused") MUST be accompanied
  by a positive control showing the check can produce a hit.
- "Done", "passing", and "matches the game" MUST NOT be claimed without running the check and
  showing its output. Unobserved behaviour is labelled unverified.
- Prefer the simplest design that satisfies these principles; added complexity MUST be justified
  in the plan's Complexity Tracking.

Rationale: a silent extractor or simulator failure looks identical to a clean result. Positive
controls are what distinguish them.

## Technical Constraints

- Sources: `pokeplatinum/` (decomp) and `pokemon-showdown/` (simulator) are vendored at the
  repository root. Each MUST be pinned to a recorded commit; bumping either is a tracked change
  that re-runs extraction tests and the divergence ledger.
- ROM: the local `.nds` file MAY be used only to verify revision hashes or decomp build output.
  It MUST NOT be committed, redistributed, or embedded in any artifact.
- Runtime: the tool MUST run locally and offline; no network or paid services are required to
  optimize or battle-test a team.
- Interface: input is six species identifiers plus optional constraints; output is the team in
  Showdown export format plus a machine-readable JSON report containing the provenance from
  Principle IV. Errors go to stderr with a non-zero exit code.
- Generated data (extracted tables, caches) MUST be reproducible from the pinned sources by a
  single documented command and MUST NOT be hand-edited.

## Development Workflow & Quality Gates

- Every feature follows Spec Kit: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement`. The plan's Constitution Check MUST pass, or violations MUST be justified
  in Complexity Tracking.
- Required test layers:
  - Extraction tests: known decomp values per data table (Principle I, V).
  - Legality tests: known-legal and known-illegal sets for the validator (Principle III).
  - Divergence tests: assert each ledger entry is either corrected or explicitly accepted
    (Principle II).
  - Determinism tests: same seed → same battle log (Principle IV).
- A change is not complete until the local test suite runs green and its output is recorded.
- Long-running optimization or research work keeps `RUN-STATE.md` (goal, method, done, next,
  traps) updated as work lands.

## Governance

- This constitution supersedes other project practices. Where a spec, plan, or task conflicts
  with it, the constitution wins until amended.
- Amendments require: the proposed text, the reason, the semantic-version bump, and an updated
  Sync Impact Report at the top of this file. Dependent templates are checked for consistency.
- Versioning: MAJOR for removing or redefining a principle; MINOR for adding a principle or
  section or materially expanding guidance; PATCH for clarifications and wording.
- Compliance: every `/speckit-plan` Constitution Check and every code review MUST verify
  Principles I–V. Runtime development guidance for agents lives in the user's `CLAUDE.md` files.

**Version**: 1.0.0 | **Ratified**: 2026-10-07 | **Last Amended**: 2026-10-07
