# Project Plan

## 1. Problem - What problem are we solving?

This project solves the problem of operating Kubernetes clusters without forcing engineers to live in raw terminal workflows and fragmented dashboards. The platform is meant to give DevOps, platform, and SRE teams a centralized, modern interface for understanding cluster health, investigating failures, and managing workloads with less operational friction.

The product is designed to make Kubernetes operations more approachable and more operationally transparent for teams that need visibility across namespaces, workloads, pods, services, nodes, and events. It keeps Kubernetes as the source of truth while presenting it in a cleaner and more decision-oriented interface.

> TODO (confirm): Confirm whether the product is targeted only at self-hosted/on-premise clusters or also for cloud-hosted Kubernetes environments.

## 2. Users - Who is this for?

Primary users are DevOps engineers, platform engineers, and SREs who need to operate clusters and troubleshoot issues without relying exclusively on kubectl. These users typically spend time validating workload health, tracing failures, checking system resources, and understanding operational impact before taking action.

Secondary users may include engineering managers and technical operators who need higher-level health visibility, but the main product focus remains on operational practitioners who are comfortable with infrastructure tooling and need speed and clarity.

## 3. Features - What does the MVP need?

- Cluster overview with health signals and system status
- Namespace and workload visibility
- Pods, deployments, services, and nodes listings
- Resource detail views with status, metadata, and history
- Event and log inspection for troubleshooting
- Local authentication and protected operating views
- Basic resource actions such as scale and restart
- Event-driven or refreshable data updates for operational clarity
- AI-assisted investigation as a later expansion, not the initial delivery

## 4. Data - What are we storing?

- User accounts and local authentication records
- Cluster connection metadata and environment configuration
- Namespace and workload resources discovered from Kubernetes
- Node and service inventory
- Pod, deployment, and replicaset status snapshots
- Kubernetes events and recent activity
- Log references or cached log excerpts for troubleshooting
- User-defined settings such as default namespace and view preferences
- Audit records for admin actions and resource operations
- Application-level session and RBAC metadata for local access control

## 5. Tech - What stack are we using?

- Frontend: Next.js with TypeScript and Tailwind CSS
- Backend: FastAPI for the application API layer
- Database: PostgreSQL for application data and operational metadata
- Kubernetes integration: Kubernetes Python client and Kubernetes API access through FastAPI only
- Authentication: local admin account with a shared, signed, HTTP-only session cookie validated by Next.js and FastAPI against PostgreSQL
- Architecture: a modern UI backed by structured API endpoints, with Kubernetes as the operational system of record and credentials kept exclusively in FastAPI
- Future direction: AI Copilot integration for investigation and guided action support

Confirmed architecture: the browser reaches the Next.js UI, the UI reaches FastAPI over HTTPS or WebSocket, and FastAPI is the only application component that reaches the Kubernetes API. AI features will use the same backend API and never connect directly to Kubernetes.

## 6. Monetize - How will this make money?

This product is positioned as a self-hosted operations platform rather than an ad-supported SaaS product. The likely business model is a commercial open-core or enterprise product that bundles the self-hosted platform with support, deployment tooling, and premium operational features.

Potential monetization paths:

- Self-hosted licensing for teams operating production clusters
- Paid enterprise support and onboarding
- Premium operational modules such as multi-cluster management or audit workflows
- Managed hosting or turnkey deployment for customers who want the platform without operating it themselves

The first version should focus on product value and reliability before monetization is aggressively expanded.

## 7. UI/UX - How should this look and feel?

The product should feel like a modern, high-trust operations platform: clean, focused, credible, and low-friction for real-world workflows. The current dashboard direction uses a dark, polished control-plane aesthetic with strong contrast, clear status indicators, and careful hierarchy so operators can quickly scan the system.

The interface should prioritize:

- Clear identification of unhealthy states
- Structured navigation by resource type and namespace
- Low-noise layouts that reduce cognitive overload
- Actionable data without hiding technical detail beneath visual clutter
- Consistency across overview, workload, and detail views
- A responsive, desktop-first experience for operations work

The long-term UI should evolve from an elegant dashboard foundation into a dense but readable operational workflow surface that supports investigation, change review, and escalation.

## 8. Deployment - Where and how will this ship?

The initial product direction is a self-hosted Kubernetes operations platform, not a single-host consumer app. It should be deployable in a real operational environment, whether on-premise, in a private cloud, or in a managed Kubernetes environment operated by the customer.

Expected deployment shape:

- Frontend: Next.js app deployed behind a web server or runtime environment
- Backend: FastAPI service providing app APIs and connection logic
- Database: PostgreSQL for application metadata, auth, and audit data
- Kubernetes integration: FastAPI connects to one initial cluster through a Kubernetes ServiceAccount and Kubernetes RBAC
- Environment variables: cluster endpoint config, DB connection string, shared session signing secret, and session settings
- Operational needs: health-check endpoints, logs, background workers or polling jobs as needed, and secure secret management
- Domain and hosting: a private or enterprise-ready deployment model, likely behind internal access controls or a corporate network boundary

Initial deployment topology: Next.js frontend, FastAPI backend, and PostgreSQL. The first release supports one cluster; multi-cluster support is designed for later, not implemented now.

Authentication contract:

- Next.js and FastAPI share the same signing secret, cookie name, and session format.
- The session cookie is signed and HTTP-only; browser JavaScript and request payloads cannot mint or override identity.
- FastAPI validates the signature and expiry, then retrieves the authenticated user from PostgreSQL before serving protected API data.
- Kubernetes credentials remain only in the backend runtime ServiceAccount and are never sent to the frontend, browser, or AI integration.

## Key assumptions and exclusions

Confirmed decisions:

- This is a self-hosted Kubernetes operations platform.
- The primary users are DevOps, platform, and SRE operators.
- The current dashboard is a polished front-end foundation for a real product.
- The next milestone is backend integration with live Kubernetes data.
- AI Copilot is a later-stage capability, not the first shipped feature set.

Open assumptions or TODOs:

- Exact ServiceAccount and Kubernetes RBAC policy bindings for the first cluster
- Whether the product will be released as self-hosted software, managed service, or both

Explicit exclusions for the first build phase:

- Large-scale AI orchestration is not part of the early implementation
- Full multi-cluster management is not the first milestone
- A broad Kubernetes admin platform with every possible feature is not the MVP
- A visual clone of Kubernetes Dashboard without real operating logic is not the product direction
