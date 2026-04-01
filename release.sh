#!/bin/bash
set -euo pipefail

DRY_RUN=0
ARGS=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    *) ARGS+=("$arg") ;;
  esac
done

BUMP=${ARGS[0]:-patch}
if [ "${#ARGS[@]}" -gt 0 ]; then
  ARGS=("${ARGS[@]:1}")
fi
COMMIT_MESSAGE="${ARGS[*]:-}"
ADDON_CONFIG="sigenergy_optimizer_addon/config.yaml"
WORKFLOW_FILE=".github/workflows/build.yml"
POLL_INTERVAL=5
MAX_WAIT_SECONDS=3600

github_repo() {
  git remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##'
}

current_branch() {
  git rev-parse --abbrev-ref HEAD
}

github_api() {
  local url=$1
  if [ -n "${GITHUB_TOKEN:-}" ]; then
    curl -fsSL \
      -H "Accept: application/vnd.github+json" \
      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      "$url"
  else
    curl -fsSL \
      -H "Accept: application/vnd.github+json" \
      "$url"
  fi
}

wait_for_release_run() {
  local repo=$1
  local tag=$2
  local tag_sha=$3
  local workflow_file=$4
  local start_ts
  local run_json=""
  local run_id=""
  local status=""
  local conclusion=""
  local html_url=""
  local elapsed=0

  start_ts=$(date +%s)

  while :; do
    if ! run_json=$(
      github_api "https://api.github.com/repos/${repo}/actions/workflows/$(basename "$workflow_file")/runs?event=push&per_page=20" |
        jq -c --arg sha "$tag_sha" --arg tag "$tag" '
          .workflow_runs
          | map(select(.head_sha == $sha and ((.head_branch // "") == $tag or ((.display_title // "") | contains($tag)))))
          | sort_by(.created_at)
          | last // empty
        '
    ); then
      echo "Warning: could not query GitHub Actions API to wait for ${tag}."
      return 0
    fi

    if [ -n "$run_json" ]; then
      run_id=$(printf '%s' "$run_json" | jq -r '.id')
      break
    fi

    elapsed=$(( $(date +%s) - start_ts ))
    if [ "$elapsed" -ge "$MAX_WAIT_SECONDS" ]; then
      echo "Timed out waiting for workflow run for ${tag}." >&2
      return 1
    fi

    sleep "$POLL_INTERVAL"
  done

  while :; do
    if ! run_json=$(github_api "https://api.github.com/repos/${repo}/actions/runs/${run_id}"); then
      echo "Warning: lost access while polling GitHub Actions for ${tag}."
      return 0
    fi
    status=$(printf '%s' "$run_json" | jq -r '.status')
    conclusion=$(printf '%s' "$run_json" | jq -r '.conclusion // ""')
    html_url=$(printf '%s' "$run_json" | jq -r '.html_url')

    if [ "$status" = "completed" ]; then
      if [ "$conclusion" = "success" ]; then
        echo "GitHub Actions completed successfully for ${tag}."
        echo "Workflow: ${html_url}"
        return 0
      fi

      echo "GitHub Actions failed for ${tag}."
      echo "Conclusion: ${conclusion:-unknown}"
      echo "Workflow: ${html_url}"
      return 1
    fi

    elapsed=$(( $(date +%s) - start_ts ))
    if [ "$elapsed" -ge "$MAX_WAIT_SECONDS" ]; then
      echo "Timed out waiting for workflow completion for ${tag}." >&2
      [ -n "$html_url" ] && echo "Workflow: ${html_url}"
      return 1
    fi

    sleep "$POLL_INTERVAL"
  done
}

case "$BUMP" in
  major|minor|patch) ;;
  *) echo "Usage: $0 [--dry-run] [major|minor|patch] [commit message...]" >&2; exit 1 ;;
esac

CURRENT=$(grep '^version:' "$ADDON_CONFIG" | sed 's/version: *"\?//;s/"\?$//')
if [ -z "$CURRENT" ]; then
  echo "Error: could not read version from $ADDON_CONFIG" >&2
  exit 1
fi

if [[ "$CURRENT" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)(-.+)?$ ]]; then
  MAJOR="${BASH_REMATCH[1]}"
  MINOR="${BASH_REMATCH[2]}"
  PATCH="${BASH_REMATCH[3]}"
  SUFFIX="${BASH_REMATCH[4]:-}"
else
  echo "Error: unsupported version format '${CURRENT}' in ${ADDON_CONFIG}" >&2
  echo "Expected format like 1.2.3 or 1.2.3-haos21" >&2
  exit 1
fi

case "$BUMP" in
  major) MAJOR=$((MAJOR+1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR+1)); PATCH=0 ;;
  patch) PATCH=$((PATCH+1)) ;;
esac

NEW="${MAJOR}.${MINOR}.${PATCH}${SUFFIX}"
TAG="v${NEW}"
REPO=$(github_repo)
BRANCH=$(current_branch)

if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null 2>&1; then
  echo "Error: tag ${TAG} already exists." >&2
  exit 1
fi

echo "Bumping $CURRENT -> $NEW ($BUMP)"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] Would update ${ADDON_CONFIG} to version ${NEW}."
  [ -n "$COMMIT_MESSAGE" ] || COMMIT_MESSAGE="Release ${TAG}"
  echo "[dry-run] Would run: git add -A"
  echo "[dry-run] Would run: git commit -m \"${COMMIT_MESSAGE}\""
  echo "[dry-run] Would run: git tag ${TAG}"
  echo "[dry-run] Would run: git push origin ${BRANCH}"
  echo "[dry-run] Would run: git push origin ${TAG}"
  echo "[dry-run] Would wait for workflow: ${WORKFLOW_FILE}"
  exit 0
fi

sed -i "s/^version: .*/version: \"${NEW}\"/" "$ADDON_CONFIG"

git add -A
if git diff --cached --quiet; then
  echo "Error: nothing staged for commit." >&2
  exit 1
fi

if [ -z "$COMMIT_MESSAGE" ]; then
  COMMIT_MESSAGE="Release ${TAG}"
fi
git commit -m "$COMMIT_MESSAGE"

git tag "$TAG"
git push origin "$BRANCH"
git push origin "$TAG"
TAG_SHA=$(git rev-list -n 1 "$TAG")

echo "Released ${TAG}; waiting for CI image publish..."
wait_for_release_run "$REPO" "$TAG" "$TAG_SHA" "$WORKFLOW_FILE"