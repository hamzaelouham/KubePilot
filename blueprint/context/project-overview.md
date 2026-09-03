# Project Overview

<!-- blueprint:source-hash 027c4f95fd3cf41807f66192dbaec2b4712d263691d1a0f0b13862d0f8723aec -->

## Product summary

KubePilot is a self-hosted Kubernetes operations platform for DevOps engineers, platform engineers, and SREs. It is designed to centralize visibility into cluster health, workloads, namespaces, events, and resource state without forcing teams to live in raw kubectl output or fragmented dashboards.

The app is intentionally not a visual clone of Kubernetes Dashboard alone. It is a modern operational UI built to support real Kubernetes workflows and later AI-assisted investigation.

## Problem and users

The core problem is operational overload: teams need a clearer, higher-trust path to understand cluster health, identify failing workloads, investigate issues, and make safe operational decisions with less context switching.

Primary users:
- DevOps engineers
- Platform engineers
- SREs

Secondary users:
- Technical operators who need health visibility
- Internal engineering managers reviewing system health

## MVP scope and build order

The build order in the tracked checklist is the source of truth for feature work:

1. Dashboard foundation - polished UI shell, navigation, and layout
2. Cluster overview and mock data - metrics, workload visibility, namespace controls
3. Authentication and protected app access - local admin login and session-protected routes
4. FastAPI backend foundation - API layer and project structure
5. PostgreSQL application data model - users, sessions, metadata, settings, and audit records
6. Kubernetes connection and namespace discovery - live cluster access and inventory
7. Core resource views - pods, deployments, services, and nodes
8. Resource details and troubleshooting surfaces - YAML, status, logs, and events
9. Basic operations - scale and restart flows behind controls

Post-MVP additions:
- real-time refresh and health updates
- RBAC and multi-user controls
- multi-cluster support
- observability enhancements
- AI Copilot for operational investigation

## Data model

The project data model is centered on real Kubernetes operations plus app-level access metadata.

Core entities:
- UserAccount: id, email, passwordHash, role, createdAt
- Session: id, userId, issuedAt, expiresAt
- ClusterConnection: id, name, endpoint, kubeconfigRef, status, createdAt
- Namespace: id, clusterId, name, status, createdAt
- Workload: id, clusterId, namespace, kind, name, status, labels, image
- Pod: id, clusterId, namespace, name, status, ready, restarts, age
- Deployment: id, clusterId, namespace, name, replicas, status, image
- Service: id, clusterId, namespace, name, selector, ports, status
- Node: id, clusterId, name, role, status, version
- Event: id, clusterId, namespace, kind, name, message, createdAt
- AuditAction: id, actorId, action, resourceType, resourceId, createdAt
- UserPreference: id, userId, defaultNamespace, viewSettings

These entities support the operational workflows the app needs: cluster overview, workload investigation, resource detail inspection, and safe admin actions.

## Stack and runtime constraints

- Frontend: Next.js with TypeScript and Tailwind CSS
- Backend: FastAPI for the application API layer
- Database: PostgreSQL for app data and metadata
- Kubernetes integration: FastAPI connects to one initial cluster through a Kubernetes ServiceAccount and Kubernetes RBAC
- Authentication: local app auth with sessions and protected routes
- System of record: Kubernetes remains the live authority for cluster resources; the app stores only what is needed for operational UI and access control

## Deployment shape

The planned deployment shape is self-hosted and operationally focused rather than consumer-app styled.

Expected deployment model:
- Frontend served via a runtime environment
- FastAPI service for app APIs and cluster integration
- PostgreSQL for app persistence
- FastAPI-only Kubernetes API connectivity to one initial cluster through a ServiceAccount and Kubernetes RBAC
- Protected environment variables for DB connection strings, auth secrets, and cluster config
- Health-check endpoints and operational logging

Initial topology: Next.js frontend, FastAPI backend, and PostgreSQL. Multi-cluster support is planned later, not implemented in the first cluster integration.

## Gaps and TODOs

The plans are broadly aligned. The major remaining items are:
- exact ServiceAccount and Kubernetes RBAC policy bindings for the first cluster
- whether the product is self-hosted software, managed service, or both
- exact deployment environment and environment-variable layout

No major contradictions were found between the project plan and build plan. The main gap is the operational model for live cluster connection and access control, which is intentionally left for implementation planning.
