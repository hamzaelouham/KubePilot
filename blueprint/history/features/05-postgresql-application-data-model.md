# PostgreSQL application data model

**Branch:** feature/postgresql-application-data-model

**Status:** verified

## Goal

Add the PostgreSQL persistence layer for KubePilot application-owned data. Define typed SQLAlchemy models, constraints, indexes, and an initial Alembic migration for users, sessions, cluster metadata, preferences, and audit records, while preserving Kubernetes as the source of truth for live resources and keeping the current frontend authentication contract unchanged.

## In scope

- Add PostgreSQL-compatible SQLAlchemy model metadata for `UserAccount`, `Session`, `ClusterConnection`, `Namespace`, `Workload`, `Pod`, `Deployment`, `Service`, `Node`, `Event`, `AuditAction`, and `UserPreference`.
- Add explicit primary keys, foreign keys, timestamps, lifecycle/status fields, uniqueness constraints, and indexes needed by the overview and namespace-scoped operational queries.
- Store password hashes and session token hashes only; never persist plaintext passwords, raw session tokens, kubeconfigs, or secret values.
- Add Alembic configuration and a reviewable initial migration that creates the application schema without connecting to or mutating a production database during implementation.
- Connect the existing FastAPI database dependency seam to a request-scoped SQLAlchemy session factory with rollback/close behavior.
- Add repository-level configuration documentation and focused persistence checks that can run without a live PostgreSQL or Kubernetes cluster.

## Out of scope

- User registration, password reset, login/session issuance, or changing the Next.js cookie/session contract; these require an explicit auth bridge decision.
- Kubernetes client calls, cluster discovery, namespace synchronization, resource snapshots, or log retrieval; those belong to feature 6 and later.
- API CRUD endpoints for every stored entity, frontend data wiring, background reconciliation, or audit event generation.
- Production database provisioning, credential rotation, backup policy, deployment topology, or running migrations against an external database.
- Destructive schema changes, data backfills, or multi-tenant/RBAC policy beyond database ownership relationships.

## Build loop

Continuous Mode is running with `workflow.stepReview: "feature"` and `workflow.checkpointCommits: "disabled"`; implementation proceeds through small passing steps, then archives and locally squash-merges the feature without pushing. The final gate must include the backend checks, persistence checks, and the existing frontend `yarn build` regression check.

## Build steps

- [x] 1. **Add PostgreSQL persistence dependencies and configuration** - add SQLAlchemy, Alembic, and the PostgreSQL driver, then extend backend settings and documentation with a single database URL source and migration commands.
  - Done when: the backend imports with the configured dependencies, the database URL is parsed through one settings path, migration commands are documented, and `python -m compileall -q app` plus the frontend `yarn build` pass.

- [x] 2. **Define the application data model** - implement the overview entities with typed columns, relationships, lifecycle fields, ownership boundaries, and query indexes.
  - Done when: model metadata imports successfully, every overview entity has a primary key, required foreign-key relationships and uniqueness rules are explicit, timestamps are timezone-aware, and secret-bearing values are represented only by hashes or references; focused metadata checks pass without a live database.

- [x] 3. **Create and validate the initial migration** - configure Alembic against the model metadata and add one deterministic initial revision for the application-owned schema.
  - Done when: Alembic can render the initial upgrade/downgrade SQL in offline mode, the migration has no destructive operations or external side effects, and the generated schema includes the declared constraints and indexes.

- [x] 4. **Connect request-scoped database sessions** - replace the foundation placeholder session object with a SQLAlchemy session dependency that commits only at an explicit service boundary and rolls back/closes failed or completed requests.
  - Done when: a dependency consumer receives a real session factory product, session cleanup occurs on both success and exception paths, configuration errors remain non-sensitive, and focused checks run without requiring PostgreSQL by using an isolated test engine or dependency seam.

- [x] 5. **Add persistence verification and operating notes** - add the stack-native Python test command if needed, document local migration/inspection steps, and verify the model and migration contract together.
  - Done when: the documented focused persistence test command passes, the backend compile check and `yarn build` pass, and the README clearly distinguishes application-owned metadata from live Kubernetes state.

## Files / areas

- `backend/requirements.txt` for SQLAlchemy, Alembic, and the PostgreSQL driver
- `backend/app/core/config.py` for the existing database URL settings path
- `backend/app/db/` for engine, session factory, base metadata, and dependency lifecycle
- `backend/app/models/` for the application entities and relationships
- `backend/alembic.ini`, `backend/alembic/env.py`, and `backend/alembic/versions/` for migration configuration and the initial revision
- `backend/tests/` for focused metadata, migration, and session-lifecycle checks
- `backend/README.md` and `AGENTS.md` for setup, migration, and verification commands

The existing `k8s-ui/` routes and frontend auth remain unchanged. No Kubernetes package or cluster credential path should be added in this feature.

## Data / contracts

- All application primary keys use UUID values generated by the application/database boundary. All stored timestamps are timezone-aware UTC values, and `created_at` is immutable after insert; mutable records may also have `updated_at`.
- `user_accounts`: `id`, unique normalized `email`, `password_hash`, `role`, `created_at`. Email normalization is lowercase and trim before persistence; plaintext credentials are never stored.
- `sessions`: `id`, `user_id` foreign key to `user_accounts`, unique `token_hash`, `issued_at`, `expires_at`. Raw session tokens are never persisted; expired rows remain queryable for cleanup and are not treated as valid sessions.
- `cluster_connections`: `id`, unique human-readable `name`, `endpoint`, `kubeconfig_ref`, `status`, `created_at`. `kubeconfig_ref` identifies protected external configuration and contains no kubeconfig payload; endpoint and reference values are not returned by generic health responses.
- `namespaces`: `id`, `cluster_id` foreign key, `name`, `status`, `created_at`, with unique `(cluster_id, name)`.
- `workloads`: `id`, `cluster_id`, `namespace`, `kind`, `name`, `status`, `labels`, `image`; identity is unique for `(cluster_id, namespace, kind, name)` and labels are stored as structured JSON.
- `pods`: `id`, `cluster_id`, `namespace`, `name`, `status`, `ready`, `restarts`, `age`; identity is unique for `(cluster_id, namespace, name)`.
- `deployments`: `id`, `cluster_id`, `namespace`, `name`, `replicas`, `status`, `image`; identity is unique for `(cluster_id, namespace, name)`.
- `services`: `id`, `cluster_id`, `namespace`, `name`, `selector`, `ports`, `status`; identity is unique for `(cluster_id, namespace, name)`, with selector and ports represented as structured JSON.
- `nodes`: `id`, `cluster_id`, `name`, `role`, `status`, `version`; identity is unique for `(cluster_id, name)`.
- `events`: `id`, `cluster_id`, `namespace`, `kind`, `name`, `message`, `created_at`; indexes support cluster/namespace/time queries without treating events as authoritative cluster state.
- `audit_actions`: `id`, `actor_id` foreign key to `user_accounts`, `action`, `resource_type`, `resource_id`, `created_at`; actor and action are required, while resource identifiers remain application metadata only.
- `user_preferences`: `id`, unique `user_id` foreign key, `default_namespace`, `view_settings` structured JSON; preferences are application-owned and optional at creation.
- Database ownership is repository-first: cluster-scoped records always carry `cluster_id`, namespace-scoped records carry both `cluster_id` and `namespace`, and user-owned records carry `user_id` or `actor_id`. No request payload may override the actor or tenant scope selected by a trusted service boundary.
- SQLAlchemy models are the metadata source of truth for the initial Alembic revision. Migration upgrades and downgrades are explicit local commands; this feature does not run them against a remote or production database.
- The FastAPI session dependency yields a request-scoped session, rolls back on an exception, and closes it in all cases. Service code owns explicit commit timing; dependency cleanup must not silently commit arbitrary mutations.

## Testing

The current repository has no test runner, so this feature explicitly adds a minimal Python `pytest` setup because persistence constraints and migration metadata need repeatable assertions. Tests use an isolated local engine or metadata inspection and do not require PostgreSQL, Kubernetes, external credentials, or a production connection. Required coverage includes model constraints/indexes, secret-field representation, migration upgrade/downgrade SQL generation, settings validation, and session rollback/close behavior. The final project checks are `cd backend && python -m pytest` and `cd k8s-ui && yarn build`.

## Notes for the AI

- Keep this schema aligned with the project overview; do not add speculative billing, tenancy, analytics, or Kubernetes resource tables beyond the named entities.
- Use SQLAlchemy/Pydantic types and explicit relationships rather than untyped dictionaries except for labels, selectors, ports, and view settings, which are intentionally structured JSON fields.
- Treat `password_hash`, `token_hash`, `kubeconfig_ref`, endpoints, and database URLs as sensitive. Never print values in tests, errors, health responses, or migration output.
- PostgreSQL is the target persistence engine. An isolated SQLite test engine is acceptable only for tests that do not weaken PostgreSQL-specific migration or type validation.
- Preserve the backend auth bridge as a later decision; this feature stores the fields and boundaries needed by future auth without trusting browser-provided identity.

## Open questions

- The exact production deployment topology and secret manager remain unresolved in the project overview; this feature documents local environment variables only and does not add deployment manifests.
- The backend-to-Next.js session bridge remains unresolved. The schema stores token hashes and user ownership, but feature 5 must not decide how the existing frontend cookie is verified by FastAPI.
