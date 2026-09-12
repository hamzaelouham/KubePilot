# Marketplace SSR and Background Jobs

**Type:** Fix

**Completed:** 2026-09-12

## Summary

Moved Marketplace's initial package loading to the authenticated Next.js server
route, refreshed the Marketplace card and dialog presentation to match the
Manage resources design language, and removed installation history from the
Marketplace page.

Added a dedicated `/background-jobs` page and sidebar entry. Existing
installation, rollback, and uninstall jobs can be opened from the table to view
their lifecycle metadata and backend-captured Helm output.

## Delivered

- Added bounded `installation_jobs.log_output` persistence and an Alembic
  migration.
- Captured successful and failed Helm output for install, rollback, and
  uninstall operations.
- Added authenticated `/api/v1/marketplace/installations/{job_id}/logs` and its
  same-origin Next.js proxy.
- Added clickable background-job rows with status, target, timestamps, errors,
  and loading/empty/error log states.
- Added `/background-jobs`, sidebar navigation, route protection, and preserved
  existing job filters, pagination, permissions, and release actions.
- Server-fetched the initial Marketplace package page and passed it into the
  hydrated client browser for interactive search, sorting, pagination, and
  install flows.
- Refined Marketplace cards and package details with shared semantic surfaces,
  spacing, typography, badges, and responsive treatments.

## Verification

- `cd backend && .venv/bin/python3 -m pytest` — 456 passed.
- Focused log/worker tests — 2 passed.
- `cd k8s-ui && yarn lint` — passed with four pre-existing warnings.
- `cd k8s-ui && yarn verify` — passed; Next.js build and TypeScript checks passed.
- `PYTHONPATH=. .venv/bin/alembic upgrade head --sql` with local-safe settings — passed.
- `git diff --check` — passed.

The combined Verify command documented in `AGENTS.md` uses `cd k8s-ui` after
entering `backend/`, so its frontend path is incorrect. The equivalent corrected
root-level sequence was used for the final gate; the frontend verify command
also passed independently.

## Manual review path

Start the backend and frontend using the commands in `AGENTS.md`, then review
`/marketplace` for server-provided package content, package details, search,
sort, pagination, and install behavior. Open `/background-jobs`, click jobs in
each lifecycle state, and verify backend logs, empty logs, errors, filters,
pagination, and permission-aware release actions.
