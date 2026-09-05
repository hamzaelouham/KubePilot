# Project Overview

<!-- blueprint:source-hash e104a530e5b4606f9b6b7e4cb5c31a9a059d8ae2fb83d7d64657ba9bd0988270 -->

## Problem

Kubernetes operations teams face operational overload: they need a clearer, higher-trust path to understand cluster health, identify failing workloads, investigate issues, and make safe operational decisions with less context switching. Raw kubectl and fragmented dashboards force engineers to context-switch between tools when they need unified visibility.

## Users

Primary:
- DevOps engineers
- Platform engineers
- SREs

Secondary:
- Technical operators needing health visibility
- Engineering managers reviewing system health

## Features

MVP (build-plan order):

1. **Dashboard foundation** - polished UI shell, navigation, and resource layout for cluster operations.
2. **Cluster overview and mock data** - overview metrics, workload statuses, namespace controls, and resource tables using placeholder data.
3. **Authentication and protected app access** - local admin login, sessions, and protected routes.
4. **FastAPI backend foundation** - API layer, project structure, and database-backed service foundation.
5. **PostgreSQL application data model** - persistent storage for users, sessions, cluster metadata, settings, and audit records.
6. **Kubernetes connection and namespace discovery** - live cluster access, namespaces, endpoints, and resource inventory through the backend.
7. **Core resource views** - pods, deployments, services, and nodes with status-driven data and real cluster context.
8. **Resource details and troubleshooting surfaces** - detail pages for status, YAML, logs, and recent events for a selected resource.
9. **Run app on top of real k8s cluster (local minikube)** - deploy the platform into a real Kubernetes cluster running locally with Minikube as a set of Kubernetes workloads, validating it is a real Kubernetes-native application.

Post-MVP:
- Real-time refresh and health updates
- Live resource metrics and observability
- shadcn/ui integration and table migration
- Header components and theme support - remove non-functional header search, migrate header controls (notification, logout) to shadcn/ui, and add light/dark theme support with a theme switcher.
- RBAC and multi-user controls
- Multi-cluster support
- AI Copilot for Kubernetes operations

## Data model

Core entities (from features 3–8 that ship the data layer):

- **UserAccount**: id, email, passwordHash, role, createdAt
- **Session**: id, userId, tokenHash, issuedAt, expiresAt
- **ClusterConnection**: id, name, endpoint, kubeconfigRef, status, createdAt
- **Namespace**: id, clusterId, name, status, createdAt
- **Workload**: id, clusterId, namespace, kind, name, status, labels, image
- **Pod**: id, clusterId, namespace, name, status, ready, restarts, age
- **Deployment**: id, clusterId, namespace, name, replicas, status, image
- **Service**: id, clusterId, namespace, name, selector, ports, status
- **Node**: id, clusterId, name, role, status, version
- **Event**: id, clusterId, namespace, kind, name, message, createdAt
- **AuditAction**: id, actorId, action, resourceType, resourceId, createdAt
- **UserPreference**: id, userId, defaultNamespace, viewSettings

These entities support cluster overview, workload investigation, resource detail inspection, and future admin actions.

## Tech stack

- **Next.js (TypeScript, Tailwind CSS, shadcn/ui)** - frontend UI and same-origin API proxy layer
- **FastAPI (Python)** - backend API, session validation, and Kubernetes integration
- **PostgreSQL** - application data: users, sessions, cluster metadata, settings
- **Kubernetes Python client** - cluster API access through FastAPI only; frontend never connects to Kubernetes directly
- **Shared signed HTTP-only session cookie** - authentication boundary between Next.js and FastAPI, validated against PostgreSQL

## Monetization

Self-hosted operations platform, likely commercial open-core or enterprise model. First version focuses on product value and reliability before aggressive monetization.

## UI/UX

Desktop-first operations dashboard with strong status emphasis:

- `/login` - local admin login
- `/dashboard?resource=<type>&namespace=<ns>` - overview, workloads, pods, deployments, services, nodes, namespaces
- `/dashboard/detail?resourceType=<type>&name=<name>&namespace=<ns>` - resource detail with Status, YAML, Logs, Events tabs

Design direction: calm operational surfaces, readable hierarchy, clear status indicators, low-noise layouts. Tailwind CSS with a polished control-plane aesthetic, theme-aware via semantic tokens with light/dark mode support and a header theme switcher.

## Deployment shape

Self-hosted, operationally focused:

- Frontend: Next.js app served via runtime environment
- Backend: FastAPI service for app APIs and cluster integration
- Database: PostgreSQL for app persistence
- Kubernetes: FastAPI connects to one initial cluster through a ServiceAccount and Kubernetes RBAC
- Environment variables: KUBEPILOT_AUTH_SECRET (≥32 chars), KUBEPILOT_DATABASE_URL, KUBEPILOT_CLUSTER_NAME (default: "primary"), KUBEPILOT_ADMIN_EMAIL, KUBEPILOT_ADMIN_PASSWORD
- Health endpoint: `GET /api/v1/health`
- Initial topology: one cluster only; multi-cluster is planned later

## Authentication boundary

- Next.js and FastAPI share the signing secret, cookie name (`kubepilot_session`), and session format.
- Session cookie is signed and HTTP-only; browser JavaScript cannot mint or override identity.
- FastAPI validates signature and expiry, retrieves the user from PostgreSQL, and serves protected API data.
- Kubernetes credentials remain exclusively in the FastAPI ServiceAccount runtime; the frontend and AI paths never receive them.

## Open questions

- **Project plan §3 lists "Basic resource actions such as scale and restart" as MVP, but the build plan has no such feature.** Feature 9 in the build plan is "Run app on top of real k8s cluster (local minikube)." If scale/restart operations are desired for MVP, a build-plan item must be added. The current `current-feature.md` contains a spec for "Basic operations" that does not match the current build plan and should be reset or replaced.
- Exact ServiceAccount and Kubernetes RBAC policy bindings for the first cluster are not yet defined.
- Whether the product will be released as self-hosted software, managed service, or both remains open.
- The Minikube deployment target (feature 9) needs clarification on whether it includes Kubernetes manifests, Helm charts, or kustomize overlays for deploying the app itself.
