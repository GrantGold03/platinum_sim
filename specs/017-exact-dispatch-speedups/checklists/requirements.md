# Specification Quality Checklist: Exact Dispatch, Damage-Input and Speed Speedups for expectimax2 (round three)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-02
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
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
- [x] No implementation details leak into specification

## Notes

- The Input quotes the user's description verbatim, including file and function names; the spec body refers to
  them only in the Context table as profile evidence and in the edge case about the sim code hash. They are
  evidence and constraints, not design (same convention as features 015 and 016).
- Policy names (`expectimax2-v1`, `expectimax2-v2`, `decomp-ai`), the fixed seed set and the two digests are kept
  because the acceptance test is defined by them (Principle IV: same seeds, same opponents) and the fixture is
  feature 015's, used unchanged.
- SC-002's 1.15x bar is set below the profile estimate (about 1.2x); a smaller gain is reported, not a reason to
  widen scope (FR-013).
- "Control mode" (FR-006) and "freeze guard" (FR-007) name the feature-015/016 test facilities, not designs; the
  plan decides how the shared conversions join them. User Story 1 scenario 4 (a jump landing inside a list)
  names a behaviour the preparation must have, not how the script is split.
- Two interpreter loops exist today (plain and tracing); the edge case records that both must agree. Which one
  the live AI and the player use is a plan question.
