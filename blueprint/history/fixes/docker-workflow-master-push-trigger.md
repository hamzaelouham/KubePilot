# Current Fix

## Title

Trigger Docker workflow on every push to master

## Type

Fix

## Status

Verified

## Branch

`fix/docker-workflow-master-push-trigger`

## The problem

`.github/workflows/docker-build-push.yml` can be started manually and runs for
selected pull requests, but it does not run when changes are pushed directly to
`master`. Direct pushes therefore do not automatically build and publish the
backend and UI images.

## The fix

Add a `push` trigger scoped to the `master` branch while preserving the existing
manual `workflow_dispatch` input and pull-request path filters. The workflow's
build, tag, Docker Hub authentication, and image publishing behavior must remain
unchanged.

## Build steps

1. [x] Update `.github/workflows/docker-build-push.yml` with a `push` trigger for
   `master`. Done when the workflow YAML parses successfully and the diff shows
   only the required trigger change.

## Verify

- Run `git diff --check`.
- Parse the workflow YAML successfully.
- Run `./scripts/verify-feature.sh`.
