#!/usr/bin/env bash
set -euo pipefail

# Pull prebuilt KubePilot images from Docker Hub and deploy to a local Minikube cluster.
# Images are built and pushed by the GitHub Actions workflow .github/workflows/docker-build-push.yml.
# Usage: ./deploy.sh [--no-build] [--teardown]
# Provision the Secret externally first. Existing encryption keys are never rotated.

NAMESPACE="kubepilot"
BACKEND_IMAGE="kubepilot-backend"
UI_IMAGE="kubepilot-ui"
BACKEND_IMAGE_HUB="hamzaelouham/kubepilot-backend"
UI_IMAGE_HUB="hamzaelouham/kubepilot-ui"

# Deployment names differ from image/service names in the manifests.
BACKEND_DEPLOYMENT="backend"
FRONTEND_DEPLOYMENT="frontend"
UI_SERVICE="${UI_IMAGE}"
SECRET_NAME="kubepilot-secret"
MANIFEST_DIR="backend/deploy/kubernetes"

info()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
error() { printf '\033[1;31m==> %s\033[0m\n' "$*" >&2; }

if ! command -v minikube >/dev/null 2>&1; then
  error "minikube is not installed or not on PATH."
  exit 1
fi

k () { minikube kubectl -- "$@"; }

is_valid_fernet_key() {
  python3 - "$1" <<'PY'
import base64
import sys

try:
    value = sys.argv[1]
    decoded = base64.urlsafe_b64decode(value.encode("ascii"))
    valid = len(decoded) == 32 and base64.urlsafe_b64encode(decoded).decode("ascii") == value
except (UnicodeDecodeError, ValueError, TypeError):
    valid = False
sys.exit(0 if valid else 1)
PY
}

ensure_encryption_key() {
  local encoded_key existing_key requested_key

  if ! k get secret "$SECRET_NAME" -n "$NAMESPACE" >/dev/null 2>&1; then
    error "Provision $SECRET_NAME with unique credentials and an encryption key before deployment."
    exit 1
  fi
  encoded_key="$(k get secret "$SECRET_NAME" -n "$NAMESPACE" -o 'jsonpath={.data.KUBEPILOT_ENCRYPTION_KEY}' 2>/dev/null || true)"
  existing_key=""
  if [ -n "$encoded_key" ]; then
    if ! existing_key="$(printf '%s' "$encoded_key" | base64 --decode 2>/dev/null)"; then
      error "The cluster Secret contains an unreadable encryption key; refusing to replace it automatically."
      exit 1
    fi
  fi
  requested_key="${KUBEPILOT_ENCRYPTION_KEY:-}"

  if [ -n "$requested_key" ] && ! is_valid_fernet_key "$requested_key"; then
    error "KUBEPILOT_ENCRYPTION_KEY is not a valid Fernet key. Generate one with:"
    error "python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'"
    exit 1
  fi

  if [ -n "$existing_key" ] && is_valid_fernet_key "$existing_key"; then
    if [ -n "$requested_key" ] && [ "$requested_key" != "$existing_key" ]; then
      error "The cluster already has a different encryption key; refusing an unsafe key rotation."
      exit 1
    fi
    info "Preserving existing encryption key in $SECRET_NAME"
    return 0
  fi

  error "Provision a valid encryption key in $SECRET_NAME; refusing to replace it automatically."
  exit 1
}

case "${1:-}" in
  --teardown)
    info "Tearing down $NAMESPACE workloads"
    k delete -f backend/deploy/kubernetes/
    exit 0
    ;;
esac

if [ "${1:-}" != "--no-build" ]; then
  info "Pulling backend image from Docker Hub"
  docker pull "$BACKEND_IMAGE_HUB:latest"
  info "Pulling UI image from Docker Hub"
  docker pull "$UI_IMAGE_HUB:latest"
  # Local builds are commented out: GitHub Actions-built images avoid slow local
  # egress hanging `yarn install`. Kept here for offline or image-customizing setups.
  # docker build -t "$BACKEND_IMAGE" ./backend
  # docker build -t "$UI_IMAGE" ./k8s-ui
  info "Loading images into Minikube"
  minikube image load "$BACKEND_IMAGE_HUB:latest" "$UI_IMAGE_HUB:latest"
fi

info "Applying namespace and shared configuration"
for manifest in namespace.yaml service-account.yaml configmap.yaml; do
  k apply -f "$MANIFEST_DIR/$manifest"
done

if ! k get secret "$SECRET_NAME" -n "$NAMESPACE" -o json | python3 scripts/validate-deployment-secret.py; then
  error "Deployment stopped before applying database or application workloads."
  exit 1
fi
ensure_encryption_key

info "Applying database and application workloads"
for manifest in postgres.yaml backend.yaml frontend.yaml; do
  k apply -f "$MANIFEST_DIR/$manifest"
done

info "Restarting deployments to pick up new images"
k rollout restart "deployment/$BACKEND_DEPLOYMENT" -n "$NAMESPACE" || true
k rollout restart "deployment/$FRONTEND_DEPLOYMENT" -n "$NAMESPACE" || true

info "Waiting for rolls to complete"
k rollout status "deployment/$BACKEND_DEPLOYMENT" -n "$NAMESPACE" --timeout=180s || true
k rollout status "deployment/$FRONTEND_DEPLOYMENT" -n "$NAMESPACE" --timeout=180s || true

info "Pods in $NAMESPACE"
k get pods -n "$NAMESPACE"

info "Opening UI"
minikube service "$UI_SERVICE" -n "$NAMESPACE"

printf '\nDone. Sign in with your configured administrator credentials.\n'
