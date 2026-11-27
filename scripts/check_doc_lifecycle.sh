#!/usr/bin/env bash
#
# check_doc_lifecycle.sh -- pre-commit NUDGE (never blocks) for the
# living-document discipline: CHANGELOG.md gets an entry in the same
# commit as notable work, report-shaped docs land in an archive location
# instead of the top-level docs/ dir, GAMEPLAN.md stays under 30,000
# characters, and CLAUDE.md stays a rulebook rather
# than absorbing the incident write-ups that belong in the lessons file.
#
# Language-agnostic: matches by extension/dir pattern, not by any
# particular stack. Fast, pure git/grep -- no interpreter startup.
# Inspects STAGED files only. Every check WARNS and exit 0 -- notability
# and "is it done" are judgment calls a hook cannot make on its own.

set -uo pipefail

staged_any="$(git diff --cached --name-only || true)"
added_files="$(git diff --cached --name-only --diff-filter=A || true)"

[ -z "$staged_any" ] && exit 0

# ---------------------------------------------------------------------------
# Check A -- CHANGELOG / close-out discipline.
# ---------------------------------------------------------------------------
# Common migration/schema-change directory shapes across stacks.
mig="$(printf '%s\n' "$staged_any" | grep -E \
  '(^|/)(migrations?|alembic/versions|db/migrate|prisma/migrations)/' \
  || true)"

# New source files, common extensions, excluding anything that reads as
# a test/spec/fixture/mock/generated file or lives in a vendored/build dir.
newsrc="$(printf '%s\n' "$added_files" \
  | grep -E '\.(py|js|jsx|ts|tsx|go|rs|java|kt|rb|c|cc|cpp|h|hpp|swift|cs|php|scala|ex|exs)$' \
  | grep -viE '(^|/)(test|tests|spec|specs|__tests__|__mocks__|fixtures?|mocks?)(/|_|\.)' \
  | grep -viE '(^|/)(node_modules|vendor|dist|build|out|target|\.venv|venv)/' \
  || true)"

notable="$(printf '%s\n%s\n' "$mig" "$newsrc" | grep -v '^$' || true)"

# NOTE: `grep -x ... >/dev/null`, never `grep -qx`. Under `pipefail`,
# `grep -q` exits at the first match and the still-writing `printf` takes
# SIGPIPE, so the pipeline reports 141 and `!` inverts it into a false
# "CHANGELOG.md is not staged" warning. It only triggers once the staged
# list is long enough that printf has not finished -- silent on two-file
# commits, wrong on thirty-file ones, i.e. exactly inverted from where
# this check earns its keep. (Found 2026-08-09; the deployed copies in
# imessagemcp and imessage_mcp carry the same fix.)
if [ -n "$notable" ] && ! printf '%s\n' "$staged_any" | grep -x 'CHANGELOG.md' >/dev/null; then
  echo "⚠️  Doc-lifecycle WARNING (close-out discipline):"
  printf '%s\n' "$notable" | while IFS= read -r f; do [ -n "$f" ] && echo "   • $f"; done
  echo "   A migration or new source file is staged but CHANGELOG.md is"
  echo "   not. Notable changes get a CHANGELOG entry in the same landing"
  echo "   commit; on close-out also flip GAMEPLAN.md status."
  echo "   (Warning only -- commit proceeds; skip only for the trivial.)"
  echo ""
fi

# ---------------------------------------------------------------------------
# Check B -- report-shaped docs belong in an archive location, not top-level.
# ---------------------------------------------------------------------------
report_docs=""
if [ -n "$added_files" ]; then
  report_docs="$(printf '%s\n' "$added_files" \
    | grep -E '^docs/[^/]+\.md$' \
    | grep -iE '(report|summary|snapshot|handoff|state-of-play|status|post-?mortem)' \
    || true)"
fi

if [ -n "$report_docs" ]; then
  echo "⚠️  Doc-lifecycle WARNING (location signals status):"
  printf '%s\n' "$report_docs" | while IFS= read -r f; do [ -n "$f" ] && echo "   • $f"; done
  echo "   New docs/ file reads as a report/snapshot -- frozen history"
  echo "   belongs in docs/archive/, and current status belongs in"
  echo "   GAMEPLAN.md. (Warning only.)"
  echo ""
fi

# ---------------------------------------------------------------------------
# Check C -- CLAUDE.md size ratchet.
#
# CLAUDE.md loads into EVERY agent request, so its size is a per-turn tax on
# every session. It holds RULES; the incident behind a rule (measured numbers,
# commit hashes, detection tells) belongs in the lessons file. Both repos that
# adopted this split watched it erode: one went 87,097 -> 44,672 bytes and was
# back to 67,953 within sixteen days, because each new gotcha was appended to
# the rulebook instead of the lessons file. Nothing measured it, so nothing
# objected.
#
# A RATCHET, not a ceiling. It fires only when a commit makes the file BIGGER
# than the budget, so it is silent in normal work. Landing a genuinely new rule
# that pushes past it is legitimate: move the matching evidence out first, and
# if it still does not fit, raise CLAUDE_MD_BUDGET below IN THE SAME COMMIT and
# record why in CHANGELOG.md. Re-baselining silently is the failure mode.
#
# Set CLAUDE_MD_BUDGET to roughly the file's current size when you adopt this.
# ---------------------------------------------------------------------------
CLAUDE_MD_BUDGET=${CLAUDE_MD_BUDGET:-8000}
LESSONS_FILE="${LESSONS_FILE:-docs/LESSONS.md}"

claude_staged=0
printf '%s\n' "$staged_any" | grep -x 'CLAUDE.md' >/dev/null && claude_staged=1

if [ "$claude_staged" -eq 1 ]; then
  size="$(git show :CLAUDE.md 2>/dev/null | wc -c | tr -d ' ' || echo 0)"
  if [ "$size" -gt "$CLAUDE_MD_BUDGET" ]; then
    echo "!!  CLAUDE.md is ${size} bytes -- $((size - CLAUDE_MD_BUDGET)) over the ${CLAUDE_MD_BUDGET} budget."
    echo "    It loads into EVERY agent request. Rules belong here; the story"
    echo "    behind a rule belongs in ${LESSONS_FILE}. Move the evidence, keep"
    echo "    the rule + a link. If it really is a new RULE, raise"
    echo "    CLAUDE_MD_BUDGET in this script and say why in CHANGELOG.md."
    echo "    (Warning only -- commit proceeds.)"
    echo ""
  fi
fi

# ---------------------------------------------------------------------------
# Check D -- a rule added without its story. Check C measures size only, which
# a net-zero swap defeats trivially (add 300 bytes of evidence, trim 300 bytes
# of rule). This checks the actual contract.
# ---------------------------------------------------------------------------
if [ "$claude_staged" -eq 1 ] && [ -f "$LESSONS_FILE" ]; then
  ns="$(git diff --cached --numstat -- CLAUDE.md || true)"
  add="$(printf '%s' "$ns" | awk '{print $1}')"
  del="$(printf '%s' "$ns" | awk '{print $2}')"
  case "$add$del" in
    *-*) : ;;
    *)
      if [ -n "$add" ] && [ "$add" -gt "${del:-0}" ]; then
        if ! printf '%s\n' "$staged_any" | grep -x "$LESSONS_FILE" >/dev/null; then
          echo "!!  CLAUDE.md grew (+${add}/-${del}) but ${LESSONS_FILE} is not staged."
          echo "    Add a rule, add its story in the same commit -- the rule without"
          echo "    its evidence gets argued away by the next session; the evidence"
          echo "    without the rule never gets read. Ignore if this was a reword."
          echo ""
        fi
      fi
      ;;
  esac
fi

# ---------------------------------------------------------------------------
# Check E -- stranded evidence. The only CORRECTNESS check here: a link with
# no target leaves a rule whose justification is unreachable, which is exactly
# how a rule gets argued away.
# ---------------------------------------------------------------------------
if [ "$claude_staged" -eq 1 ] && [ -f "$LESSONS_FILE" ]; then
  cm="$(git show :CLAUDE.md 2>/dev/null || git show HEAD:CLAUDE.md 2>/dev/null || true)"
  pm="$(git show ":$LESSONS_FILE" 2>/dev/null || git show "HEAD:$LESSONS_FILE" 2>/dev/null || true)"
  base="$(basename "$LESSONS_FILE")"
  if [ -n "$cm" ] && [ -n "$pm" ]; then
    defined="$( { printf '%s\n' "$pm" | grep -oE '\{#[a-z0-9-]+\}' | tr -d '{}#' || true
                  printf '%s\n' "$pm" | grep -oE '<a id="[a-z0-9-]+"' \
                    | sed -E 's/.*"([a-z0-9-]+)".*/\1/' || true
                  printf '%s\n' "$pm" | grep -oE '^#{1,6} .*' \
                    | sed -E 's/^#+ //; s/[^a-zA-Z0-9 -]//g; s/ /-/g' \
                    | tr '[:upper:]' '[:lower:]' || true ; } | sort -u)"
    linked="$(printf '%s\n' "$cm" | grep -oE "${base}#[a-z0-9-]+" | sed 's/.*#//' | sort -u || true)"
    broken="$(comm -23 <(printf '%s\n' "$linked" | grep -v '^$' || true) \
                       <(printf '%s\n' "$defined" | grep -v '^$' || true) || true)"
    if [ -n "$broken" ]; then
      echo "!!  A link in CLAUDE.md resolves to nothing in ${LESSONS_FILE}:"
      printf '%s\n' "$broken" | while IFS= read -r a; do
        [ -n "$a" ] && echo "      #$a"
      done
      echo "    Add the anchor ({#name}) or fix the link. (Warning only.)"
      echo ""
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Check F -- GAMEPLAN.md stays under its size limit.
# GAMEPLAN.md is the first file every session reads, so its size is paid at
# every cold start. It counts characters, not lines: a 200-line limit once let
# a GAMEPLAN reach 64,152 characters because each line was a long paragraph.
# Over the limit: archive finished work and evidence (CLAUDE.md, "Keep or
# archive test"); full decisions belong in docs/decisions.md.
# ---------------------------------------------------------------------------
GAMEPLAN_MAX_CHARS=${GAMEPLAN_MAX_CHARS:-30000}
if printf '%s\n' "$staged_any" | grep -x 'GAMEPLAN.md' >/dev/null; then
  gp_chars="$(git show :GAMEPLAN.md 2>/dev/null | LC_ALL=en_US.UTF-8 wc -m | tr -d ' ')"
  if [ -n "$gp_chars" ] && [ "$gp_chars" -gt "$GAMEPLAN_MAX_CHARS" ]; then
    echo "!!  GAMEPLAN.md is ${gp_chars} characters; the limit is ${GAMEPLAN_MAX_CHARS}."
    echo "    Archive finished work and evidence to CHANGELOG.md or docs/archive/"
    echo "    (CLAUDE.md, \"Keep or archive test\"); full decisions belong in"
    echo "    docs/decisions.md. (Warning only -- commit proceeds.)"
    echo ""
  fi
fi

exit 0
