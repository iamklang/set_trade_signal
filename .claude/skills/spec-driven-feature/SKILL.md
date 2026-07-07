---
name: spec-driven-feature
description: Start a new feature using Spec-Driven Development (the github/spec-kit workflow). Use when asked to spec out, plan, or scaffold a new feature, write a constitution/spec/plan/tasks, or apply spec-kit / SDD. Project-agnostic — copy this skill into any repo.
---

# Spec-Driven Development for a new feature

**Spec-Driven Development (SDD)** — the
[github/spec-kit](https://github.com/github/spec-kit) workflow — makes the spec
the source of truth and generates code *from* it, gated by a project
**constitution**.

This skill is **self-contained and portable**: the artifact templates are
bundled inside it (`templates/`), so it works in any repo with no setup. Drop
the skill dir into another project's `.claude/skills/` and it runs as-is. If the
host project ships its own `templates/*.template.md` at its root, those take
precedence (lets a project customize the skeletons).

Scaffold a feature with **`new-feature.sh`**, then fill the generated files
phase by phase.

## Scaffold a new feature (start here)

```bash
bash .claude/skills/spec-driven-feature/new-feature.sh <feature-slug> "Human Readable Name"
# e.g.
bash .claude/skills/spec-driven-feature/new-feature.sh user-auth "User Authentication"
```

What it does (all verified):
- **Resolves the repo root** = `$SPEC_ROOT` if set, else nearest ancestor with
  `.git`, else the standard `.claude/skills/<name>/` → three levels up.
- **Resolves templates** = host project's `./templates/` if it has
  `*.template.md`, else the copy bundled in this skill.
- **Auto-numbers** the next `specs/NNN-<slug>/` by scanning existing specs.
- Copies `spec / plan / research / data-model / quickstart / tasks`, substitutes
  the mechanical placeholders `{{DATE}}` `{{FEATURE_NAME}}`
  `{{NNN-feature-name}}` `{{PROJECT_NAME}}`, creates `contracts/`.
- **Seeds `memory/constitution.md` once** (only if absent; never overwrites).
- Refuses to clobber an existing feature folder.

Three content placeholders are intentionally left for you to author:
`{{action}}`, `{{EntityName}}`, `{{field}}`.

## The workflow (fill the files in this order)

| # | spec-kit cmd | File(s) to write | Rule |
|---|--------------|------------------|------|
| 1 | `/constitution` | `memory/constitution.md` | Project-level, once. Governs all features. |
| 2 | `/specify` | `spec.md` | **WHAT/WHY only — no HOW.** Mark unknowns `[NEEDS CLARIFICATION]`. |
| 3 | `/clarify` | `spec.md` | Resolve **every** `[NEEDS CLARIFICATION]` before planning. |
| 4 | `/plan` | `plan.md` + `research.md` + `data-model.md` + `quickstart.md` + `contracts/` | The HOW: stack, architecture, decisions + rationale. |
| 5 | `/tasks` | `tasks.md` | Derive ordered tasks; **test-first**; mark `[P]` for parallel. |
| 6 | `/analyze` | — | Cross-check artifacts (spec ↔ plan ↔ tasks ↔ contracts). |
| 7 | `/implement` | code | Build it. Tests before code. Honour the contracts. |

## Non-negotiable principles (the constitution's gates)

- **spec.md is WHAT/WHY, plan.md is HOW.** If a "how" detail leaks into the
  spec, move it to the plan.
- **Resolve clarifications before planning.** A leftover `[NEEDS CLARIFICATION]`
  is a bug; the `/clarify` step exists to catch conflicting answers early.
- **Contract is the single source of truth.** Put API/interface contracts in
  `contracts/` *before* implementing; keep every consumer (models, types, tests)
  in sync with it.
- **Test-first.** `tasks.md` orders tests (🔴) before implementation (🟢); no
  significant logic ships without a test mapped to an acceptance criterion.
- **Simplicity gate.** ≤ 3 main components to start; no speculative
  future-proofing. Record gate decisions (and accepted trade-offs) explicitly in
  `plan.md`.

## Reuse in another project

```bash
# from the other project's root:
cp -r /path/to/spec-driven-feature .claude/skills/
bash .claude/skills/spec-driven-feature/new-feature.sh my-feature "My Feature"
```

The bundled `templates/` make it standalone. To customize skeletons for that
project, either edit the skill's `templates/`, or create a `templates/` dir at
the project root (it overrides the bundled copy). To add a new artifact type,
drop a `<name>.template.md` in whichever templates dir wins and add a line to
the `for t in …` loop in `new-feature.sh`.

## Gotchas

- **Constitution is per-project, not per-feature.** Seeded only when
  `memory/constitution.md` is absent; edit by hand to evolve project rules.
- **Slugs are normalized** (lowercased, spaces→dashes, non-`[a-z0-9-]` stripped)
  — `"User Auth"` and `user-auth` map to the same folder.
- **Numbering scans `specs/NNN-*`** for the max + 1; delete a throwaway folder
  before re-running to reuse its number.
- **No `.git`?** The `.git`-walk fails silently and the script falls back to the
  standard skill location (or set `SPEC_ROOT=/path` to be explicit).
- Only the 4 mechanical placeholders are filled; `{{action}}`, `{{EntityName}}`,
  `{{field}}` are left for you.
