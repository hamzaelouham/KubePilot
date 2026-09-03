# Current Feature

**Status:** verified
**Branch:** feature/deploy-onto-minikube

## Goal

Deploy the three containerized services (Next.js frontend, FastAPI backend, PostgreSQL) as Kubernetes workloads on the local Minikube cluster, and expose a functional UI so a browser can operate against the live Kubernetes API. The backend authenticates to the cluster through its in-cluster ServiceAccount (read-only for discovery), automatically runs migrations, and surfaces real cluster data through the UI.

## In scope

- Add Kubernetes manifests under `backend/deploy/kubernetes/` that deploy the frontend, backend, and PostgreSQL into the `kubepilot` namespace as workloads with Services.
- Deploy PostgreSQL as a single-replica workload with a PersistentVolumeClaim for data persistence and a `db` Service on port 5432.
- Reuse the existing read-only RBAC (`service-account.yaml`: ServiceAccount `kubepilot-api`, ClusterRole `kubepilot-api-discovery`, binding) unchanged; bind the backend pod to that ServiceAccount so it talks to the Kubernetes API with `get`/`list`/`watch` only.
- Add a Kubernetes Secret for secrets (`KUBEPILOT_AUTH_SECRET`, database credentials, admin password) and a ConfigMap for non-secret env (cluster name, service name, admin email, backend URL), matching the compose/README env contract.
- Expose the frontend as a NodePort Service and the backend as a ClusterIP Service; document `minikube service kubepilot-ui -n kubepilot` to open the UI.
- Load the host-built images (`kubepilot-backend:latest`, `kubepilot-ui:latest`) into Minikube with `minikube image load`.
- Add a documented, repeatable deploy command using the `minikube kubectl --` wrapper (kubectl is not on the host PATH) and a teardown path.
- Verify end-to-end that the UI operates against the live cluster: pods Ready, backend health responds, the backend's in-cluster discovery returns real Minikube namespaces, and the UI is reachable.

## Out of scope

- Expanding RBAC to allow create/update/delete (scale, restart, or any write). The backend remains read-only for discovery; RBAC/multi-user control is feature 11 (Post-MVP). `backend/tests/test_rbac.py` enforces the read-only `get`/`list`/`watch` contract and must stay green (the rule set was widened across resource kinds, never with write verbs).
- Helm charts or kustomize overlays (repo-native plain YAML is used).
- Publishing images to a registry (images are loaded directly into Minikube).
- Ingress/tls, DNS, or custom domain (NodePort + `minikube service` is used for local access).
- Multi-cluster support (feature 12), RBAC/multi-user controls (feature 11), or real-time refresh/health updates (feature 10).
- Resource detail views for the newly surfaced kinds (cron-jobs, jobs, etc.) beyond the generic `CoreResourceView` list; write operations on any resource.
- Installing `kubectl` on the host; all cluster interaction uses `minikube kubectl --`.

## Folded-in application work (merged into this feature's commit)

This feature's commit also carries the dashboard real-data wiring and the resource-tab
expansion completed in the same session, documented here so the archive matches the commit:

- **Real cluster data in the dashboard** - replaced the hardcoded mock data. New `OverviewView`
  (fetches real deployments + pods, computes donut charts and the deployments table) and
  `NamespacesView` (fetches real namespaces) components; `dashboard/page.tsx` now renders
  those for the overview/workloads/namespaces views; a new `/api/cluster/namespaces` proxy
  and a dynamic namespace dropdown populated from the backend.
- **Restored and expanded resource tabs** - the backend `ClusterClient` now lists and reads
  replica-sets, daemon-sets, stateful-sets, jobs, cron-jobs, replication-controllers
  (namespaced) and persistent-volumes, cluster-roles, storage-classes (cluster-scoped) via
  `AppsV1Api`, `BatchV1Api`, `RbacAuthorizationV1Api`, `StorageV1Api`. `ResourceType` and
  `DetailResourceType` literals, the frontend proxy allow-list, the nav, `CoreResourceView`
  columns, and the RBAC ClusterRole were expanded accordingly.
- **Bug fix - namespaced listing** - fixed `Client.resources()` using a broken method-name
  derivation (`list_<resource>_for_namespace` instead of the correct `list_namespaced_<resource>`),
  which caused "Kubernetes request failed" on every namespaced resource tab.

## Build loop

The configured workflow uses `workflow.stepReview: "feature"` and `workflow.checkpointCommits: "disabled"`. Implementation proceeds in small passing steps and ends with a verified feature archive and work commit. The automated host gate is `cd backend && python3 -m pytest`, `cd backend && python3 -m compileall -q app`, and `cd k8s-ui && yarn build`. Because 9b's value is runtime behavior on the cluster, each step's `Done when` requires observed Minikube evidence (ready Pods, healthy endpoints, real discovery responses) via the `minikube kubectl --` wrapper, not build output alone. All cluster commands use `minikube kubectl -- <args>` and `minikube service` since `kubectl` is not on the host PATH.

## Build steps

- [x] 1. **Confirm cluster prerequisites and reuse RBAC** - confirm Minikube is running, the images `kubepilot-backend:latest` and `kubepilot-ui:latest` exist locally, and load them into Minikube.
	- Done when: `minikube status` reports a Running control plane; `docker images` lists both `kubepilot-backend:latest` and `kubepilot-ui:latest`; `minikube image load kubepilot-backend:latest kubepilot-ui:latest` succeeds with no error; `minikube kubectl -- get pods -A` returns the cluster's system pods.

- [x] 2. **Create the kubepilot namespace and RBAC** - apply the namespace and the existing read-only `service-account.yaml` so the backend can use its ServiceAccount.
	- Done when: `minikube kubectl -- get ns kubepilot` exists; `minikube kubectl -- get sa -n kubepilot kubepilot-api` returns `kubepilot-api`; the ClusterRole/ClusterRoleBinding are applied; `backend/tests/test_rbac.py` still passes.

- [x] 3. **Add ConfigMap and Secret** - add manifests that provide the environment contract (non-secrets in a ConfigMap; `KUBEPILOT_AUTH_SECRET`, DB credentials, and admin password in a Secret) matching the compose/README variables.
	- Done when: `minikube kubectl -- get configmap -n kubepilot` and `minikube kubectl -- get secret -n kubepilot` show the created resources; `minikube kubectl -- get secret -n kubepilot <name> -o jsonpath='{.data}'` decodes to the expected keys; the Secret's `KUBEPILOT_AUTH_SECRET` is at least 32 characters.

- [x] 4. **Deploy PostgreSQL** - add PostgreSQL Deployment (single replica, `postgres:16-alpine`) with a PersistentVolumeClaim and a `db` ClusterIP Service; run migrations implicitly when the backend starts.
	- Done when: `minikube kubectl -- rollout status deployment/postgres -n kubepilot` reports success; `minikube kubectl -- get pods -n kubepilot -l app=postgres` shows Ready; `minikube kubectl -- get pvc -n kubepilot` is Bound; `minikube kubectl -- get svc -n kubepilot db` is a ClusterIP on 5432.

- [x] 5. **Deploy the backend** - add a backend Deployment bound to `serviceAccountName: kubepilot-api`, with env from the ConfigMap and Secret, and a `backend` Service; it runs `alembic upgrade head` then uvicorn on start.
	- Done when: `minikube kubectl -- rollout status deployment/backend -n kubepilot` reports success; the backend pod is Ready; `minikube kubectl -- logs deploy/backend -n kubepilot` shows migrations applied then `Application startup complete` with no psycopg/module error; backend health returns `200` (check via `minikube kubectl -- port-forward` or service).

- [x] 6. **Verify backend-to-Kubernetes discovery** - confirm the backend's in-cluster ServiceAccount can talk to the live cluster and surface real data.
	- Done when: a call to the backend's discovery endpoint (`/api/v1/cluster/namespaces`) returns the real Minikube namespaces (e.g. `kube-system`, `default`, `kubepilot`) with HTTP 200, proving read-only Kubernetes API access through the ServiceAccount; the response contains no RBAC-denied error.

- [x] 7. **Deploy the frontend** - add a frontend Deployment with env from the ConfigMap and Secret, and a NodePort Service; the frontend proxies `/api` to the backend via `http://backend:8000`.
	- Done when: `minikube kubectl -- rollout status deployment/frontend -n kubepilot` reports success; the frontend pod is Ready; `minikube kubectl -- get svc -n kubepilot kubepilot-ui` is NodePort; `minikube service kubepilot-ui -n kubepilot` opens a reachable URL returning HTTP 200.

- [x] 8. **Add the deploy/teardown command and verify the stack** - write the repeatable apply/teardown commands into `backend/README.md` and the `AGENTS.md` Commands section using the `minikube kubectl --` wrapper, then run the full automated host gate.
	- Done when: `backend/README.md` and the `AGENTS.md` Commands section document `minikube image load`, the apply command `minikube kubectl -- apply -f backend/deploy/kubernetes/`, the `minikube service kubepilot-ui -n kubepilot` open command, and a teardown command; `cd backend && python3 -m pytest` (21), `compileall`, and `cd k8s-ui && yarn build` all pass.

## Files / areas

- `backend/deploy/kubernetes/namespace.yaml` (new)
- `backend/deploy/kubernetes/configmap.yaml` (new)
- `backend/deploy/kubernetes/secret.yaml` (new; local Minikube dev placeholder values matching compose defaults, documented as overridable)
- `backend/deploy/kubernetes/postgres.yaml` (new; Deployment + PVC + Service)
- `backend/deploy/kubernetes/backend.yaml` (new; Deployment bound to `kubepilot-api` SA + ClusterIP Service)
- `backend/deploy/kubernetes/frontend.yaml` (new; Deployment + NodePort Service)
- `backend/deploy/kubernetes/service-account.yaml` (existing; RBAC widened to read-only discovery across the added resource kinds, verified by `backend/tests/test_rbac.py`)
- `backend/README.md` and `AGENTS.md` Commands section (deploy/teardown usage with the `minikube kubectl --` wrapper)
- `backend/app/kubernetes/client.py` (cluster client expanded for added resource kinds; namespaced-listing method-name fix)
- `backend/app/api/v1/discovery_schemas.py` and `detail_schemas.py` (expanded `ResourceType` / `DetailResourceType`)
- `backend/app/api/v1/routes.py` (cluster-scoped namespace validation for pv/cluster-roles/storage-classes)
- `backend/tests/test_kubernetes.py`, `backend/tests/test_rbac.py` (updated + new coverage)
- `k8s-ui/app/dashboard/page.tsx` (overview/workloads/namespaces via live components; all resource kinds mapped to `CoreResourceView`)
- `k8s-ui/components/dashboard-shell.tsx` (restored + expanded nav; dynamic namespace dropdown)
- `k8s-ui/components/core-resource-view.tsx` (columns for added resource kinds; cluster-scoped row handling)
- `k8s-ui/components/overview-view.tsx`, `k8s-ui/components/namespaces-view.tsx`, `k8s-ui/app/api/cluster/namespaces/route.ts` (new - real-data views + namespace proxy)
- `k8s-ui/app/api/cluster/resources/route.ts` (allow-list + cluster-scoped namespace handling)

## Data / contracts

- All workloads and the ServiceAccount live in the `kubepilot` namespace.
- Backend connects to PostgreSQL at `db:5432`; `KUBEPILOT_DATABASE_URL=postgresql+psycopg://<user>:<password>@db:5432/<db>` uses the psycopg 3 driver (matching the 9a fix).
- Backend authenticates to Kubernetes with `load_incluster_config` only, reading the mounted ServiceAccount token from `/var/run/secrets/kubernetes.io/serviceaccount`; no kubeconfig volume or `KUBECONFIG` env is added. RBAC remains read-only (`get`/`list`/`watch`) for namespaces, pods, services, nodes, endpoints, replicationcontrollers, persistentvolumes (core); deployments, replicasets, daemonsets, statefulsets (apps); jobs, cronjobs (batch); clusterroles (rbac.authorization.k8s.io); storageclasses (storage.k8s.io); `backend/tests/test_rbac.py` continues to enforce verbs and the exact resource set.
- The frontend reaches the backend at `http://backend:8000` (`KUBEPILOT_BACKEND_URL`) and proxies same-origin `/api` calls, forwarding only the signed session cookie — never Kubernetes credentials.
- Env split: Secret holds `KUBEPILOT_AUTH_SECRET` (≥32 chars, shared by backend and frontend), `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`, `KUBEPILOT_ADMIN_PASSWORD`; ConfigMap holds `KUBEPILOT_CLUSTER_NAME` (`primary`), `KUBEPILOT_SERVICE_NAME` (`kubepilot-api`), `KUBEPILOT_ADMIN_EMAIL`, `KUBEPILOT_BACKEND_URL` (`http://backend:8000`).
- Images referenced by the workloads are `kubepilot-backend:latest` and `kubepilot-ui:latest` with `imagePullPolicy: IfNotPresent` (present locally after `minikube image load`).
- PostgreSQL uses a PersistentVolumeClaim for data durability; storage is local to the single-node Minikube cluster.
- No forward of kubectl into pods; all admin operations run from the host via `minikube kubectl --`.

## Testing

Backend has a configured pytest runner (23 tests). `backend/tests/test_rbac.py` verifies the RBAC manifest stays read-only (`get`/`list`/`watch` only) across the widened resource set. `test_kubernetes.py` covers namespaced and cluster-scoped listing for the added resource kinds. The full host gate (`pytest`, `compileall`, `yarn build`) runs at the end.

## Notes for the AI

- Use `minikube kubectl -- <args>` for every cluster command; `kubectl` is not on the host PATH (confirmed).
- Keep the RBAC manifest byte-for-byte unchanged unless `backend/tests/test_rbac.py` still passes with any change; do not add write verbs (scale/restart is out of scope for 9b).
- Load images into Minikube before applying manifests so `IfNotPresent` resolves locally; do not pull from a registry.
- Confirm the backend pod mounts the `kubepilot-api` ServiceAccount (`serviceAccountName`), or discovery returns RBAC-denied; a denied discovery response counts as failure.
- Verify real cluster data (Minikube's actual namespaces) rather than mock/placeholder data to prove Kubernetes-native behavior.
- Do not commit real secret values; the committed Secret uses local Minikube dev placeholders (matching compose defaults) and is documented as overridable before a non-local deployment.
- Placeholder values to a Secret are the project's repo-native approach for local Minikube; real deployments override them.

## Open questions

- None that block implementation. PersistentVolumeCapacity and the StorageClass for the PostgreSQL PVC may be adjusted to the Minikube default storage class during implementation based on observed cluster output.
