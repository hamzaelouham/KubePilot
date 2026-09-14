# Current Feature

**Title:** Preserve and bootstrap KUBEPILOT_ENCRYPTION_KEY in deploy.sh
**Type:** Fix
**Status:** verified
**Branch:** `fix/preserve-and-bootstrap-kubepilot-encryption-key-in-deploy-sh`

## The problem

The root `deploy.sh` applies the Kubernetes Secret manifest containing the committed placeholder `KUBEPILOT_ENCRYPTION_KEY`. That leaves credential operations unavailable on a fresh local Minikube deployment, and blindly reapplying the manifest can overwrite a valid encryption key on later deployments. Replacing the key without warning would also make previously encrypted credentials unreadable.

## The fix

Update `deploy.sh` to initialize the bootstrap encryption key after the namespace and shared configuration exist, while preserving the existing Kubernetes Secret data. Accept a caller-supplied valid Fernet key, otherwise generate a local-compatible key when the key is missing or still the placeholder. Refuse invalid supplied keys and refuse replacing a different valid cluster key. Apply the remaining workload manifests only after the Secret is ready, and document the behavior in `backend/README.md`.

Do not print or persist the key outside Kubernetes, rotate an existing valid key automatically, change application/UI behavior, or alter unrelated deployment flags.

## Build steps

### 1. [x] Make deploy.sh encryption-key bootstrap safe

Implement the key validation/generation/preservation flow and ordered manifest application, then update the deployment documentation.

Done when:

- `deploy.sh` is shell-valid and preserves a valid existing `KUBEPILOT_ENCRYPTION_KEY` across repeat deployments.
- A supplied key is validated as a Fernet key; an absent/placeholder key is initialized without exposing its value; a different valid existing key is never overwritten.
- The Secret is created or patched before backend workloads are applied, while existing Secret fields remain intact.
- `--no-build` and `--teardown` behavior remains unchanged, and documentation explains the local bootstrap behavior.

## Verify

- Run `bash -n deploy.sh`.
- Run `git diff --check`.
- Review the diff to confirm no key value is logged or written to a repository file.
- If Minikube is available, run `./deploy.sh --no-build` and confirm the Secret contains a valid key, then run it again and confirm the key is unchanged. Do not perform teardown as part of verification.

## Notes for the AI

- Keep this fix limited to the root deployment script and its directly related documentation.
- Use the existing `minikube kubectl --` wrapper and manifest paths; do not require host `kubectl`.
- The Kubernetes Secret is the source of truth for the local bootstrap key. Never use a generated key as a database-backed application setting.
