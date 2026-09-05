# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now.

**Fix: Frontend Docker build is slow.**

**Type:** Fix

**Status:** verified

**Branch:** fix/frontend-docker-build-is-slow

## The problem

`k8s-ui/Dockerfile` builds a slow, fat frontend image locally and in the cloud
(GitHub Actions):

- The **final image ships the full `node_modules` (~720 MB)** because the runner
  starts with `yarn start` (`next start` needs the `next` binary from
  `node_modules`). This inflates every COPY, the recursive `chown -R /app` over
  ~800 MB, cache download/unpack on cloud runners, and the push/pull/extract of
  the published image.
- **No install/build cache inside the build.** On any cache miss (changed
  `yarn.lock`, evicted GHA cache, fresh runner) `yarn install --frozen-lockfile`
  re-downloads all dependencies. The GHA layer cache in
  `.github/workflows/docker-build-push.yml` exists, but a fresh runner still
  pulls the large archive and re-runs the full `yarn build` on every source
  change, then pushes the bloated image.
- The `chown -R nextjs:nodejs /app` step churns the entire 800 MB tree every
  time it runs (observed stalling local builds).

The existing `k8s-ui/.dockerignore` already excludes `node_modules`, `.next`,
`.env`, docs, and `.git`, so build context upload is fine and stays as is.

## The fix

Use Next.js **standalone output** (stable since Next 13.4, present in Next 16)
so the build emits a self-contained runtime server with only traced
dependencies, and trim the runner to that output:

- `k8s-ui/next.config.ts`: add `output: "standalone"`. The build then produces
  `.next/standalone` with `server.js` and the runtime `node_modules`.
- Rewrite `k8s-ui/Dockerfile`:
  - `deps` stage: `RUN --mount=type=cache,target=/usr/local/share/.cache/yarn
    yarn install --frozen-lockfile` so repeat installs reuse a yarn cache layer.
  - `builder` stage: `RUN --mount=type=cache,target=/root/.next/cache yarn
    build` so repeated local builds reuse the Next build cache. Add a
    `.dockerignore` entry for the local `.next` cache only if needed; the
    existing file already excludes the heavy paths.
  - `runner` stage: copy only `.next/standalone`, `.next/static`, and `public`
    with `--chown=nextjs:nodejs` on each COPY (no recursive `chown -R`), keep
    `USER nextjs`, `EXPOSE 3000`, `ENV PORT=3000 HOSTNAME=0.0.0.0 NODE_ENV=
    production`, and `CMD ["node", "server.js"]`. No `node_modules` copy, no
    `yarn start`.
- No change to the GitHub Actions workflow (GHA cache already wired), image
  tags, manifests, env vars, or probe paths.

Must not break:

- The middleware `/api` proxy (middleware.ts) must still work in standalone
  mode; `KUBEPILOT_BACKEND_URL` / `KUBEPILOT_AUTH_SECRET` env handling is
  unchanged (the standalone `server.js` reads `process.env` like `next start`).
- The dev workflow (`yarn dev`, `yarn build`, `yarn lint`) is untouched.
- Port 3000 readiness/liveness probes and the `kubepilot-ui` Service are
  unaffected.

## Build steps

- [x] 1. **Standalone runner image** - enable `output: "standalone"` in
  `next.config.ts`, rewrite `k8s-ui/Dockerfile` to a standalone runner with
  yarn/Next cache mounts. Local `docker build`/`docker run` was **waived by the
  user** (skipped to keep the session focused); image behavior is instead
  verified by the cloud `Build and push Docker images` workflow on the next
  push and the post-merge Minikube deploy.
  `Done when`: `yarn build` emits `.next/standalone/server.js` and
  `.next/static`; `yarn lint` reports 0 errors; the runner stage copies only
  `.next/standalone`, `.next/static`, and `public` with no `node_modules` copy
  and no recursive `chown -R`.

## Verify

- `yarn build` produces `.next/standalone/server.js` and `.next/static` —
  **confirmed locally** (build passes; standalone server + static assets
  emitted).
- `yarn lint` — **0 errors** (one pre-existing `dashboard-shell.tsx` warning).
- Local `docker build`/`docker run` was **waived by the user**; the container
  image is built by the `Build and push Docker images` GitHub Actions workflow
  on the next push, and after the fix merges it is deployed to Minikube
  (`./deploy.sh` or the manual commands in AGENTS.md) to confirm `/login`
  renders and the middleware `/api` proxy still works.
- Note: compared to the old image, the standalone runner ships no `node_modules`
  at the image root and drops the recursive `chown -R /app` step entirely.

## How to try it

The image is not built locally. Push the branch, run the **Build and push
Docker images** GitHub Actions workflow for it, then on Minikube:

1. Pull the new UI image (`hamzaelouham/kubepilot-ui:latest`) once the workflow
   finishes: `docker pull hamzaelouham/kubepilot-ui:latest`.
2. `minikube image load hamzaelouham/kubepilot-ui:latest` and
   `minikube kubectl -- apply -f backend/deploy/kubernetes/`.
3. Open the UI (`minikube service kubepilot-ui -n kubepilot`), confirm `/login`
   renders and log in with a test account — the middleware `/api` proxy must
   still work and the auth cookie flow must be unchanged.
4. Sanity-check the image size with `docker images` — it should be far smaller
   than the old `node_modules`-sized image.

## Testing evidence

- `yarn build` — **passes**, emits `.next/standalone/server.js` + `.next/static`
  (standalone confirmed; middleware "Proxy" listed in the build output).
- `yarn lint` — **0 errors** (pre-existing `dashboard-shell.tsx:10`
  `@next/next/no-location-assign-relative-destination` warning remains, out of
  scope).
- Backend untouched by the fix; regression gate rerun anyway:
  `cd backend && .venv/bin/python3 -m pytest` — **79 passed** (post-12a).
- Final safety pass rerun at completion on the merged tree
  (`master` @ `7fa352e` + fix changes): build 8.25s, lint clean, 79 pytest
  passed.

## Notes for the AI

- The runner `CMD ["node", "server.js"]` and `ENV HOSTNAME=0.0.0.0` are
  required for standalone output; the middleware must run with
  `standaloneOutput` (Next handles it), and `KUBEPILOT_BACKEND_URL` /
  `KUBEPILOT_AUTH_SECRET` are read from `process.env` exactly as before.
- `feature/multi-user-authentication` (12a) merged to `master` as the prereq
  for the green lint gate; the fix branch is rebased on top.
- `/complete` ran the final safety pass; `/fix` is the path for any regression
  found when the cloud build / Minikube deploy is exercised.