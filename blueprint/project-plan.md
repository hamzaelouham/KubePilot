# Project Plan

## 1. Problem - What problem are we solving?

This project solves the problem of operating Kubernetes clusters without forcing engineers to live in raw terminal workflows and fragmented dashboards. The platform is meant to give DevOps, platform, and SRE teams a centralized, modern interface for understanding cluster health, investigating failures, and managing workloads with less operational friction.

The product is designed to make Kubernetes operations more approachable and more operationally transparent for teams that need visibility across namespaces, workloads, pods, services, nodes, and events. It keeps Kubernetes as the source of truth while presenting it in a cleaner and more decision-oriented interface.

KubePilot is deployed as self-hosted software and can operate registered
Kubernetes environments that are on-premise, private-cloud, or
customer-managed cloud clusters. Whether KubePilot itself will also be offered
as a managed service remains a commercial decision.

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
- AI-Powered SRE/DevOps Assistant (post-MVP, feature 14): native streaming investigations, typed tools wrapping existing APIs, evidence-based diagnosis, and human-approved resource/Helm lifecycle operations using Vercel AI SDK and AI Elements.
- KubePilot Marketplace (post-MVP) for discovering, installing, and tracking Kubernetes Helm packages from Artifact Hub
- Manage resources (post-MVP, feature 19) for Kubernetes create/delete operations and Helm release/repository management in the selected cluster
- Centralized Settings (post-MVP, feature 20) for application preferences, appearance, AI providers and models, encrypted credentials, and audit logs
- Direct AI provider architecture (post-MVP, feature 21) using Settings-managed OpenAI, OpenRouter, and Ollama/local models without Vercel AI Gateway; tool access follows each model's declared capabilities
- Integrations and AI agent automation (post-MVP, feature 22) for Slack, Gmail, and Microsoft Outlook configuration under Settings, plus configurable Kubernetes workflows under the existing AI Assistant area after provider capability enforcement and audit visibility are complete
- In-chat Assistant mode switching (22d7) so operators can choose direct model chat or an enabled configured agent without leaving the shared streaming conversation experience; server-side model/agent boundaries, agent-scoped tools, permissions, and human approvals remain authoritative

AI Agents (22d) lives at `/assistant/agents`, nested under AI Assistant. Deliver it
in five ordered slices: agent management; skills/capabilities/templates; manual
execution; integration notifications; schedules/events. Agents are shared within
the KubePilot installation and managed by admins. Manual execution uses the
caller's current permissions, model capabilities, and assigned supported tools.
Reusable skills contain instructions, not arbitrary executable code. Scheduled
and event-driven runs use a designated owner whose permissions are rechecked on
each run; unattended execution permits investigation and explicitly configured
notifications only. Kubernetes/Helm changes require authenticated human approval.
Instructions, skills, templates, and capability settings never grant permissions.
Exact trigger types, schedule semantics, run retention, and background approval
handoff contracts will be specified in 22d5 before implementation.

Manage resources is delivered in four ordered items:

- **19a - Kubernetes resources:** list, create through validated YAML, and delete pods, deployments, namespaces, services, and other common resource types explicitly identified in the implementation spec.
- **19b - Installed Helm releases:** discover releases directly from the selected cluster, including installations outside KubePilot; show release status and revision history, and support rollback and uninstall.
- **19c - Helm repository configuration:** list, add, update, and remove global KubePilot-managed public URL-only chart repository connections. Helm repositories are client configuration and cannot be automatically discovered from a cluster in the same way as installed releases.
- **19d - Helm release upgrades:** upgrade installed releases using an explicitly selected KubePilot-managed repository, chart, and version. The source and version are selected for each upgrade rather than inferred from the cluster or persisted as a release association.

All four items live under the "Manage resources" sidebar entry. Admins and operators have management controls; viewers remain read-only. Every resource operation and release action targets the selected registered cluster and applicable namespace, with FastAPI enforcing permissions. Destructive actions require confirmation of the target and produce audit records. Helm mutations use the existing background job/progress pattern, and repository credentials are out of scope for 19c.

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
- Assistant action proposals: UUID, actor/session identifiers, immutable validated action arguments and target cluster, expiration, one-use execution/denial state and sanitized result. Conversations remain in the active browser view for V1; prompts and raw tool data are not persisted in audit records.
- Application-level session and RBAC metadata for local access control
- Marketplace installation and release-action jobs (package and chart metadata, target cluster, namespace, release name, action, revision where applicable, status, error message, timestamps) and resolved Artifact Hub package metadata; feature 19 extends release management to externally installed releases and upgrades
- KubePilot-managed global public Helm chart repository configuration (name and URL); 19c does not support credentials, and 19d requires explicit repository/chart/version selection for each upgrade without a persisted release-to-chart-source association
- Centralized runtime application settings, encrypted provider credentials, allowlisted AI provider configuration, and an administrator-managed model registry with enabled/default, availability, and capability metadata
- Shared AI agent definitions with identity, instructions, Settings-managed model reference, enabled state, and actor/timestamp metadata; later slices add reusable instruction skills, supported capability assignments, templates, notification bindings, trigger configuration, designated run owner, and bounded run history. Agent configuration is distinct from conversation history; no instructions, prompts, credentials, or raw tool data belong in audit payloads.

Kubernetes remains the source of truth for live resources and Helm releases. Manage resources reads current cluster state; Marketplace installation history is not an inventory of every installed release. Persist only the application configuration, action/job metadata, and audit records needed to support management and progress reporting.

## 5. Tech - What stack are we using?

- Frontend: Next.js with TypeScript, Tailwind CSS, and shadcn/ui component library
- Backend: FastAPI for the application API layer
- Database: PostgreSQL for application data and operational metadata
- Kubernetes integration: Kubernetes Python client and Kubernetes API access through FastAPI only
- Authentication: local admin account with a shared, signed, HTTP-only session cookie validated by Next.js and FastAPI against PostgreSQL
- Architecture: a modern UI backed by structured API endpoints, with Kubernetes as the operational system of record; Kubernetes and Helm credentials remain exclusively in FastAPI, while encrypted AI provider credentials stay in server-side application storage and never reach the browser
- AI integration: installed Vercel AI SDK ToolLoopAgent and AI Elements with Settings-managed direct OpenAI, OpenRouter, and Ollama/local adapters; the server-side Next.js model resolver accepts only internal administrator-enabled model IDs, attaches tools only for models declaring tool support, and preserves backend-only safe observations and durable human approval. No Vercel AI Gateway or additional agent framework.
- Marketplace integration: Artifact Hub package search API (read-only, public search, no API key for basic search) and Helm execution inside the FastAPI backend (repo add/update/install) with a simple background job mechanism for V1; do not introduce Celery/RQ unless the existing architecture already needs it
- Resource management: Kubernetes resource creation/deletion through the Kubernetes Python client in FastAPI; live Helm release discovery, history, rollback, uninstall, repository configuration, and upgrades through backend Helm integration, using validated command arguments and the existing job mechanism for release mutations

Confirmed architecture: the browser reaches the Next.js UI, Next.js server
routes resolve configured AI models and call direct providers, and the UI uses
FastAPI over HTTPS or WebSocket for authenticated application and tool APIs.
FastAPI is the only application component that reaches Kubernetes or executes
Helm. AI providers never receive Kubernetes credentials, provider credentials
never reach the browser, and every operational action retains FastAPI
authorization, approval, and audit enforcement.

## 6. Monetize - How will this make money?

This product is positioned as a self-hosted operations platform rather than an ad-supported SaaS product. The likely business model is a commercial open-core or enterprise product that bundles the self-hosted platform with support, deployment tooling, and premium operational features.

Potential monetization paths:

- Self-hosted licensing for teams operating production clusters
- Paid enterprise support and onboarding
- Premium operational modules such as multi-cluster management or audit workflows
- Managed hosting or turnkey deployment for customers who want the platform without operating it themselves

The first version should focus on product value and reliability before monetization is aggressively expanded.

## 7. UI/UX - How should this look and feel?

The product should feel like a modern, high-trust operations platform: clean,
focused, credible, and low-friction for real-world workflows. The shipped
dashboard direction uses a calm light operational palette with strong status
indicators and careful hierarchy, plus System, Light, and Dark theme choices so
operators can match their environment without losing readability.

The interface should prioritize:

- Clear identification of unhealthy states
- Structured navigation by resource type and namespace
- Low-noise layouts that reduce cognitive overload
- Actionable data without hiding technical detail beneath visual clutter
- Consistency across overview, workload, and detail views
- A responsive, desktop-first experience for operations work
- A "Manage resources" sidebar entry at `/manage-resources`, using the existing application shell and selected cluster/namespace controls, with Kubernetes resources and Helm releases tabs plus repository configuration under the same section
- Clear creation/deletion feedback, release action progress, confirmation of destructive targets, and loading, empty, denied, and error states; switching clusters refreshes the displayed scope and prevents actions from using a stale target
- AI Assistant contains an AI Agents child page. Use `blueprint/reference/settings-ai-agents.png`, `settings-ai-agents-create.png`, and `settings-ai-agents-capabilities-templates.png` as visual references, adapting their navigation to Assistant. Reuse the existing shadcn/ui theme and AI Elements; provide searchable agent lists, responsive list/detail views, guided creation, capability tables, and template cards as their slices ship. Statistics must reflect actual data, with no fabricated usage or success rates.
- The Assistant conversation keeps one shared streaming surface while making its mode explicit: direct chat exposes an eligible model selector, and agent chat exposes an enabled-agent selector with agent identity/status metadata; switching mode warns before clearing incompatible conversation context.

The long-term UI should evolve from an elegant dashboard foundation into a dense but readable operational workflow surface that supports investigation, change review, and escalation.

## 8. Deployment - Where and how will this ship?

The initial product direction is a self-hosted Kubernetes operations platform, not a single-host consumer app. It should be deployable in a real operational environment, whether on-premise, in a private cloud, or in a managed Kubernetes environment operated by the customer.

Expected deployment shape:

- Frontend: Next.js app deployed behind a web server or runtime environment
- Backend: FastAPI service providing app APIs and connection logic
- Database: PostgreSQL for application metadata, auth, and audit data
- Kubernetes integration: FastAPI routes requests across registered clusters using scoped kubeconfig or in-cluster ServiceAccount access and Kubernetes RBAC
- Environment variables: bootstrap cluster/admin configuration, DB connection string, shared session signing secret, session settings, backend URL, and the Kubernetes-managed encryption key; mutable provider/model settings and provider credentials live in PostgreSQL-backed Settings
- Operational needs: health-check endpoints, logs, background workers or polling jobs as needed, and secure secret management
- Domain and hosting: a private or enterprise-ready deployment model, likely behind internal access controls or a corporate network boundary

Deployment topology: Next.js frontend, FastAPI backend, and PostgreSQL.
Multi-cluster registration, routing, selection, and administration are shipped;
each Kubernetes and Helm request remains explicitly scoped to a registered
cluster.

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
- Live Kubernetes integration, multi-cluster support, Settings, and the AI Assistant are shipped foundations.
- Direct providers and initial Slack/Gmail/Outlook connection and delivery foundations are shipped; the current milestone is AI Agents under Assistant, delivered through 22d1-22d5.

Open assumptions or TODOs:

- Exact ServiceAccount and Kubernetes RBAC policy bindings for the first cluster
- Whether the product will be released as self-hosted software, managed service, or both

Explicit exclusions for the first build phase:

- Large-scale AI orchestration is not part of the early implementation
- A broad Kubernetes admin platform with every possible feature is not the MVP
- A visual clone of Kubernetes Dashboard without real operating logic is not the product direction
