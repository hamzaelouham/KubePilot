#!/usr/bin/env bash
set -euo pipefail

# Build and deploy KubePilot to a local Minikube cluster.
# Usage: ./deploy.sh [--no-build] [--teardown]

NAMESPACE="kubepilot"
BACKEND_IMAGE="kubepilot-backend"
UI_IMAGE="kubepilot-ui"

# Deployment names differ from image/service names in the manifests.
BACKEND_DEPLOYMENT="backend"
FRONTEND_DEPLOYMENT="frontend"
UI_SERVICE="${UI_IMAGE}"

info()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
error() { printf '\033[1;31m==> %s\033[0m\n' "$*" >&2; }

if ! command -v minikube >/dev/null 2>&1; then
  error "minikube is not installed or not on PATH."
  exit 1
fi

k () { minikube kubectl -- "$@"; }

case "${1:-}" in
  --teardown)
    info "Tearing down $NAMESPACE workloads"
    k delete -f backend/deploy/kubernetes/
    exit 0
    ;;
esac

if [ "${1:-}" != "--no-build" ]; then
  info "Building backend image"
  docker build -t "$BACKEND_IMAGE" ./backend
  info "Building UI image"
  docker build -t "$UI_IMAGE" ./k8s-ui
  info "Loading images into Minikube"
  minikube image load "$BACKEND_IMAGE:latest" "$UI_IMAGE:latest"
fi

info "Applying all workloads"
k apply -f backend/deploy/kubernetes/

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

printf '\nDone. Sign in with ops@kubepilot.io / kubepilot and open Workloads.\n'
