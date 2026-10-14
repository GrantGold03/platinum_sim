# Specification Quality Checklist: Required HMs on the Team

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-13
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — see note 1
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — see note 2
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification — see note 1

## Notes

1. **Command names.** The spec names the command-line commands (`optimize`, `evaluate`,
   `validate`) and the web refusal pattern, because they are the user-facing surfaces the
   requirement must reach. This follows specs 003–005. It does not specify how the optimizer fits
   the HMs in; that is for the plan.
2. **One question asked before writing.** What does "required on the team" mean? The user chose
   "Must be in a moveset" (2026-10-13), which is recorded in Assumptions and FR-002. No markers
   remain.
3. **HM learner counts** come from the engine (`main` at `dccb3a4`). As a check, Garchomp learns
   Surf but not Fly, and the Fly count of 10 final forms matches the earlier analysis.
4. Validation passed on the first iteration (2026-10-13).
