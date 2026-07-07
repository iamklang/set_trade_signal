#!/usr/bin/env bash
# Scaffold a new Spec-Driven Development feature folder (the github/spec-kit
# workflow). PROJECT-AGNOSTIC: drop this skill dir into any repo's
# .claude/skills/ and it works — templates are bundled inside the skill and
# generated specs land in the host project's specs/.
#
# Usage:
#   bash new-feature.sh <feature-slug> ["Human Readable Name"]
#   bash new-feature.sh user-auth "User Authentication"
#
# Resolution:
#   * Repo root  = $SPEC_ROOT if set, else the nearest ancestor containing .git,
#                  else three levels up from this skill dir (the standard
#                  .claude/skills/<name>/ location).
#   * Templates  = $ROOT/templates/ if the project ships its own (lets a project
#                  customize), else the copy bundled in this skill dir.
#
# Creates  specs/NNN-<slug>/  with spec/plan/research/data-model/quickstart/
# tasks .md (auto-numbered, mechanical placeholders substituted) + contracts/.
# Seeds memory/constitution.md once (never overwrites). Never clobbers a spec.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATE="$(date +%Y-%m-%d)"

# --- resolve repo root ---------------------------------------------------
find_root() {
  [ -n "${SPEC_ROOT:-}" ] && { echo "$SPEC_ROOT"; return; }
  local d="$PWD"
  while [ "$d" != / ]; do
    [ -d "$d/.git" ] && { echo "$d"; return; }
    d="$(dirname "$d")"
  done
  ( cd "$SKILL_DIR/../../.." && pwd )   # fallback: standard skill location
}
ROOT="$(find_root)"

# --- resolve templates dir (project override > bundled) ------------------
if [ -d "$ROOT/templates" ] && ls "$ROOT"/templates/*.template.md >/dev/null 2>&1; then
  TPL="$ROOT/templates"
else
  TPL="$SKILL_DIR/templates"
fi

# --- args ----------------------------------------------------------------
slug="${1:-}"
name="${2:-$slug}"
if [ -z "$slug" ]; then
  echo "usage: bash new-feature.sh <feature-slug> [\"Human Readable Name\"]" >&2
  exit 2
fi
slug="$(printf '%s' "$slug" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-')"
[ -d "$TPL" ] || { echo "no templates found (looked in \$ROOT/templates and $SKILL_DIR/templates)" >&2; exit 1; }

# --- next zero-padded feature number -------------------------------------
max=0
for d in "$ROOT"/specs/[0-9][0-9][0-9]-*/; do
  [ -d "$d" ] || continue
  n=$((10#$(basename "$d" | cut -d- -f1)))
  [ "$n" -gt "$max" ] && max=$n
done
nnn=$(printf '%03d' $((max + 1)))
id="${nnn}-${slug}"
dest="$ROOT/specs/$id"
[ -e "$dest" ] && { echo "refusing to overwrite existing $dest" >&2; exit 1; }
mkdir -p "$dest/contracts"

# --- fill the mechanical placeholders; leave content ones for the author -
fill() { sed -e "s/{{DATE}}/$DATE/g" \
             -e "s/{{FEATURE_NAME}}/$name/g" \
             -e "s/{{NNN-feature-name}}/$id/g" \
             -e "s/{{PROJECT_NAME}}/$(basename "$ROOT")/g" "$1"; }

for t in spec plan research data-model quickstart tasks; do
  [ -f "$TPL/$t.template.md" ] && fill "$TPL/$t.template.md" > "$dest/$t.md"
done
cat > "$dest/contracts/.gitkeep" <<'EOF'
# Put API/interface contracts here (e.g. openapi.yaml) before /plan -> /implement.
EOF

# --- seed constitution once (project-level) ------------------------------
if [ ! -f "$ROOT/memory/constitution.md" ] && [ -f "$TPL/constitution.template.md" ]; then
  mkdir -p "$ROOT/memory"
  fill "$TPL/constitution.template.md" > "$ROOT/memory/constitution.md"
  echo "seeded memory/constitution.md (edit it — it governs every feature)"
fi

echo "root:      $ROOT"
echo "templates: $TPL"
echo "created:   specs/$id/"
ls -1 "$dest"
cat <<EOF

Next (spec-kit workflow):
  1. /constitution -> review memory/constitution.md
  2. /specify      -> fill specs/$id/spec.md  (WHAT/WHY only; mark [NEEDS CLARIFICATION])
  3. /clarify      -> resolve every [NEEDS CLARIFICATION] before planning
  4. /plan         -> specs/$id/plan.md + research/data-model/quickstart + contracts/
  5. /tasks        -> specs/$id/tasks.md (test-first, mark [P] parallel)
  6. /analyze      -> cross-check artifacts for consistency
  7. /implement    -> build it, tests before code
EOF
