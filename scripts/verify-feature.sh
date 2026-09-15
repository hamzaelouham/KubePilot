#!/usr/bin/env bash

set -euo pipefail

project_root="$(git rev-parse --show-toplevel)"
cd "$project_root"

base_ref="${VERIFY_BASE_REF:-origin/master}"
if ! git rev-parse --verify --quiet "$base_ref^{commit}" >/dev/null; then
  base_ref="master"
fi
merge_base="$(git merge-base HEAD "$base_ref")"

changed_backend_output="$(
  {
    git diff --name-only --diff-filter=ACMR "$merge_base" -- backend/app backend/tests
    git ls-files --others --exclude-standard -- backend/app backend/tests
  }
)"

declare -A selected_tests=()
backend_changed=false

while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  backend_changed=true
  if [[ "$path" == backend/tests/test_*.py ]]; then
    selected_tests["${path#backend/}"]=1
  fi
done <<< "$changed_backend_output"

if [[ "$backend_changed" == true && ${#selected_tests[@]} -eq 0 ]]; then
  echo "Backend code changed, but no focused backend test file was found." >&2
  echo "Add or update a matching backend/tests/test_*.py file before verification." >&2
  exit 1
fi

if [[ ${#selected_tests[@]} -gt 0 ]]; then
  backend_tests=("${!selected_tests[@]}")
  echo "Running focused backend tests: ${backend_tests[*]}"
  (
    cd backend
    .venv/bin/python3 -m pytest "${backend_tests[@]}"
  )
else
  echo "No backend application or test changes detected; skipping backend pytest."
fi

(
  cd k8s-ui
  yarn test:assistant
  yarn verify
)
