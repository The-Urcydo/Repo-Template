#!/usr/bin/env bash
# Merge a pull request only when every condition holds; otherwise print why and exit without merging.
#
# usage: merge_guarded.sh <PR number> <reviewed head sha> <reviewed files file>
#
# The files file has one changed path per line, sorted, exactly as the reviewer saw them:
#   gh api --paginate repos/The-Urcydo/Repo-Template/pulls/<PR>/files --jq '.[].filename' | sort > reviewed-files.txt
# A file name containing a newline or carriage return cannot be represented that way, so the guard refuses it.
#
# Conditions, in order (each refusal exits 2):
#   1. the PR is open, not a draft, and its head is a branch of this repository;
#   2. its base is main;
#   3. its head is the reviewed commit;
#   4. its changed-file list equals the reviewed list and has fewer than 3000 entries (GitHub
#      truncates the list there, so a longer one cannot be verified); a file name with a newline
#      or carriage return is refused for the same reason;
#   5. at least one CODEOWNERS login's latest decisive review (approval, change request or
#      dismissal) is an APPROVED review of exactly that head, and no CODEOWNERS login's latest
#      decisive review is a change request (whatever commit it names);
#   6. mergeable_state is clean (polled while it reads unknown or null);
#   7. the latest run of every check is completed with success, neutral or skipped.
# Then it merges with a merge commit pinned to the head, with a message ending
# "Delegated-under: ADR-0011", and verifies two parents, a deleted branch and green main CI.
#
# Exit codes: 0 merged and verified; 2 refused before merging; 1 could not read or call;
#             3 merged but a post-merge verification failed.
#
# Needs gh and jq, and network access for one `git fetch origin main`; the guard reads the base
# CODEOWNERS from it, so a PR cannot add an owner and a stale checkout cannot hide a change on main.
# The owner must have approved in person; this script never approves, never creates a review, and
# never touches a secret.

set -uo pipefail
export LC_ALL=C

R="The-Urcydo/Repo-Template"
N="${1:-}"
EXPECT="${2:-}"
FILES_EXPECT="${3:-}"
ADR="ADR-0011"
MERGEABLE_POLLS="${MERGEABLE_POLLS:-12}"
MERGEABLE_SLEEP="${MERGEABLE_SLEEP:-10}"
MAIN_CI_POLLS="${MAIN_CI_POLLS:-60}"
MAIN_CI_SLEEP="${MAIN_CI_SLEEP:-10}"

die() { echo "REFUSE: $*" >&2; exit 2; }
fail() { echo "ERROR: $*" >&2; exit 1; }

command -v gh >/dev/null || fail "gh is not installed"
command -v jq >/dev/null || fail "jq is not installed"
[ "$#" -eq 3 ] || die "usage: merge_guarded.sh <PR number> <reviewed head sha> <reviewed files file>"
[ -n "$N" ] && [[ "$N" =~ ^[0-9]+$ ]] || die "usage: merge_guarded.sh <PR number> <reviewed head sha> <reviewed files file>"
[[ "$EXPECT" =~ ^[0-9a-f]{40}$ ]] || die "the reviewed head must be a full 40-character lowercase sha"
[ -n "$FILES_EXPECT" ] && [ -f "$FILES_EXPECT" ] || die "the reviewed files file is missing: ${FILES_EXPECT:-<empty>}"
[[ "$MERGEABLE_POLLS" =~ ^[1-9][0-9]*$ ]] || die "MERGEABLE_POLLS must be a positive integer"
[[ "$MAIN_CI_POLLS" =~ ^[1-9][0-9]*$ ]] || die "MAIN_CI_POLLS must be a positive integer"

tmp=$(mktemp -d) || fail "cannot create a temporary directory"
trap 'rm -rf "$tmp"' EXIT
live="$tmp/live"; expected="$tmp/expected"
reviews_json="$tmp/reviews.json"; checks_json="$tmp/checks.json"; files_json="$tmp/files.json"

# 1. Read the PR, refuse a closed or draft PR at once, and poll only mergeable_state:
# GitHub computes it lazily after main moves.
pr=""; ms="null"; i=0
while :; do
  pr=$(gh api "repos/$R/pulls/$N") || fail "cannot read PR #$N"
  state=$(jq -r '.state // ""' <<<"$pr") || fail "cannot parse the PR"
  draft=$(jq -r '.draft // false' <<<"$pr") || fail "cannot parse the PR"
  [ "$state" = open ] || die "the PR is not open"
  [ "$draft" = false ] || die "the PR is a draft"
  ms=$(jq -r '.mergeable_state // "null"' <<<"$pr") || fail "cannot parse the PR"
  case "$ms" in
    unknown|null|"") ;;
    *) break ;;
  esac
  i=$((i + 1))
  [ "$i" -ge "$MERGEABLE_POLLS" ] && break
  sleep "$MERGEABLE_SLEEP"
done
base=$(jq -r '.base.ref // ""' <<<"$pr")
head=$(jq -r '.head.sha // ""' <<<"$pr")
head_ref=$(jq -r '.head.ref // ""' <<<"$pr")
head_repo=$(jq -r '.head.repo.full_name // ""' <<<"$pr")
head_label=$(jq -r '.head.label // ""' <<<"$pr")
title=$(jq -r '.title // ""' <<<"$pr")
echo "#$N state=$state draft=$draft base=$base head=${head:0:7} mergeable_state=$ms"

[ "$state" = open ] || die "the PR is not open"
[ "$draft" = false ] || die "the PR is a draft"
[ "$(echo "$head_repo" | tr 'A-Z' 'a-z')" = "$(echo "$R" | tr 'A-Z' 'a-z')" ] \
  || die "the head is ${head_repo:-<deleted>}, not a branch of $R; a delegated merge only covers our own branches"
[ "$base" = main ] || die "the base is $base, not main"
[ "$head" = "$EXPECT" ] || die "the head is $head, not the reviewed $EXPECT"

# 2. Changed files: the live list must equal the reviewed list. A newline in a file name would
# split one name into two lines and could forge a match, so refuse it before comparing.
gh api --paginate "repos/$R/pulls/$N/files" > "$files_json" || fail "cannot read the PR files"
bad_names=$(jq -s -r '
  [ .[][] | select((.filename | contains("\n")) or (.filename | contains("\r"))) | .filename ] | length
' "$files_json") || fail "cannot parse the PR files"
[ "$bad_names" = 0 ] \
  || die "a changed file name contains a newline or carriage return, so the file list cannot be compared line by line"
jq -s -r '.[][] | .filename' "$files_json" | sort > "$live" || fail "cannot parse the PR files"
sort "$FILES_EXPECT" > "$expected"
if ! diff -u "$expected" "$live" >/dev/null; then
  echo "--- reviewed files (expected)" >&2; cat "$expected" >&2
  echo "--- live files" >&2; cat "$live" >&2
  die "the changed-file list differs from the reviewed list"
fi
# GitHub stops listing a PR's files at 3000; past that, these two lists can be equal and still incomplete.
awk 'END { exit !(NR < 3000) }' "$live" \
  || die "the PR changes 3000 or more files; GitHub truncates the file list there, so it cannot be reviewed this way"
echo "files: $(wc -l < "$live" | tr -d ' ') reviewed"

# 3. Owner approvals from the base CODEOWNERS. Fetching first keeps origin/main from going stale,
# so an owner added or removed on main is seen as main has it now.
git fetch --quiet origin main >/dev/null 2>&1 || fail "cannot fetch origin/main"
owners=$(git show "origin/main:.github/CODEOWNERS" 2>/dev/null \
  | sed 's/#.*//' \
  | awk 'NF { for (i = 2; i <= NF; i++) { sub(/^@/, "", $i); print tolower($i) } }' \
  | sort -u) || fail "cannot read .github/CODEOWNERS from origin/main"
[ -n "$owners" ] || die "CODEOWNERS names no owners"
echo "owners: $(echo "$owners" | tr '\n' ' ')"

gh api --paginate "repos/$R/pulls/$N/reviews" > "$reviews_json" || fail "cannot read the reviews"
verdict=$(jq -s -r --arg head "$head" --arg owners "$owners" '
  ($owners | split("\n") | map(select(length > 0))) as $o
  | [ .[] | .[] | {login: ((.user.login // "") | ascii_downcase), id: (.id // 0), state, sha: (.commit_id // ""), at: (.submitted_at // "")} ]
  | map(select(.state == "APPROVED" or .state == "CHANGES_REQUESTED" or .state == "DISMISSED"))
  | map(select(.login as $l | any($o[]; . == $l)))
  | group_by(.login)
  | map(sort_by(.at, .id) | last)
  | {
      changes: [ .[] | select(.state == "CHANGES_REQUESTED") | .login ],
      approved: [ .[] | select(.state == "APPROVED" and .sha == $head) | .login ]
    }
  | "changes=\(.changes | join(",")) approved=\(.approved | join(","))"
' "$reviews_json") || fail "cannot parse the reviews"
echo "reviews: $verdict"
changes=${verdict#changes=}; changes=${changes%% approved=*}
approved=${verdict##*approved=}
[ -z "$changes" ] || die "a CODEOWNERS login has a current change request: $changes"
[ -n "$approved" ] || die "no CODEOWNERS login has approved the latest commit"

# 4. mergeable_state, from the final PR read.
[ "$ms" = clean ] || die "mergeable_state is $ms, not clean"

# 5. The latest run of every check must be completed and green, neutral or skipped. Grouping by
# name and app ignores an older failed run of a check that was re-run green.
gh api --paginate "repos/$R/commits/$head/check-runs" > "$checks_json" || fail "cannot read the check runs"
bad=$(jq -s -r '
  [ .[] | (.check_runs // [])[] ]
  | group_by([.name, (.app.id // 0)])
  | map(sort_by(.id) | last)
  | map(select(.status != "completed"
               or (.conclusion != "success" and .conclusion != "neutral" and .conclusion != "skipped")))
  | length
' "$checks_json") || fail "cannot parse the check runs"
echo "checks not green: $bad"
[ "$bad" = 0 ] || die "the latest run of a check is not completed green, neutral or skipped"

# 6. Merge, pinned to the head, with the audit trailer.
[ -n "$head_label" ] || head_label="${R%%/*}:$head_ref"
head_label=${head_label/:/\/}
msg=$(printf 'Merge pull request #%s from %s\n\n%s\n\nDelegated-under: %s' "$N" "$head_label" "$title" "$ADR")
merge=$(gh api -X PUT "repos/$R/pulls/$N/merge" \
  -f merge_method=merge -f sha="$head" -f commit_message="$msg") || fail "the merge call failed"
jq -e 'type == "object" and (.merged | type == "boolean")' <<<"$merge" >/dev/null 2>&1 \
  || fail "cannot parse the merge response; read the PR before retrying"
merged=$(jq -r '.merged // false' <<<"$merge")
merge_sha=$(jq -r '.sha // ""' <<<"$merge")
[ "$merged" = true ] || die "GitHub did not merge: $(jq -r '.message // "no message"' <<<"$merge")"
[ -n "$merge_sha" ] || { echo "ERROR: the merge response has no sha" >&2; exit 3; }
echo "merged as $merge_sha"

# 7. Post-merge: two parents, branch deleted, main CI green.
parents=$(gh api "repos/$R/commits/$merge_sha" | jq -r '.parents | length') \
  || fail "cannot read the merge commit"
[ "$parents" = 2 ] || { echo "ERROR: the merge commit has $parents parents, not 2" >&2; exit 3; }
echo "merge commit parents: 2"
# Branch names may contain `%` or `#`; encode them so the ref URL cannot be truncated at a fragment.
head_ref_url=${head_ref//%/%25}
head_ref_url=${head_ref_url//#/%23}
if ref_err=$(gh api "repos/$R/git/ref/heads/$head_ref_url" 2>&1 >/dev/null); then
  echo "ERROR: the branch $head_ref still exists" >&2; exit 3
fi
if [ "$ref_err" = 'gh: Not Found (HTTP 404)' ]; then
  echo "branch deleted: $head_ref"
else
  echo "ERROR: cannot verify the branch was deleted: $ref_err" >&2; exit 3
fi

main_status=""
for i in $(seq 1 "$MAIN_CI_POLLS"); do
  main_status=$(gh api --paginate "repos/$R/commits/$merge_sha/check-runs" \
    | jq -s -r '[ .[] | (.check_runs // [])[] | select(.name == "ci-gate" and (.app.id // 0) == 15368) ]
                | sort_by(.id) | last
                | if . == null then "none" else "\(.status) \(.conclusion)" end') \
    || fail "cannot read main CI"
  echo "main ci-gate: $main_status"
  case "$main_status" in
    "completed success") break ;;
    "completed "*) echo "ERROR: main ci-gate is $main_status" >&2; exit 3 ;;
  esac
  [ "$i" -lt "$MAIN_CI_POLLS" ] && sleep "$MAIN_CI_SLEEP"
done
[ "$main_status" = "completed success" ] || { echo "ERROR: main ci-gate did not finish green" >&2; exit 3; }

echo "DONE: #$N merged as $merge_sha, branch deleted, main ci-gate green"
