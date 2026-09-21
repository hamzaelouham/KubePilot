# Reference the versioning guide in agent instructions

**Type:** Fix

**Status:** verified

**Branch:** `fix/reference-versioning-guide-in-agent-instructions`

## The problem

`docs/versions.md` defines KubePilot's semantic release versions, preview image tags, `latest` policy, and release-tag workflow, but `AGENTS.md` does not tell AI agents to read it. An agent preparing a release could therefore invent or inconsistently choose a version or Docker image tag.

## The fix

Add a concise release-versioning section to `AGENTS.md` that makes `docs/versions.md` the authoritative version and image-tag policy for every release. Require agents to read it before proposing, creating, tagging, or publishing a release and to derive semantic version bumps and Docker tags from it. Preserve the existing rule that tagging, pushing, publishing, deployment, and remote workflow actions still require explicit user authorization; the documentation reference must not grant those permissions.

## Build steps

- [x] **1. Link the release versioning policy from `AGENTS.md`.** Add the durable instruction near the existing deployment/release guidance, using a repository-relative link or path that works for all supported coding agents. Keep the change limited to documentation and do not duplicate the full versioning policy in `AGENTS.md`.
  **Done when:** `AGENTS.md` explicitly directs every release-preparing agent to read and follow `docs/versions.md` for semantic versions and Docker image tags, while retaining all existing approval boundaries for tags, pushes, publishing, and deployment.

## Verify

- Confirm the reference resolves to the tracked `docs/versions.md` file.
- Confirm the instruction covers release version selection and image tagging.
- Confirm `git diff --check` passes and no release, tag, push, deployment, or remote workflow action occurred.
