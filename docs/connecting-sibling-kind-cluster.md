# Connecting a sibling kind cluster from a Minikube-deployed KubePilot

How to make a local `kind` cluster reachable from the KubePilot backend when the
backend runs as a pod **on Minikube** (both on the same host, Docker driver).

Applies to: GitHub Actions–built images (`hamzaelouham/kubepilot-backend`,
`hamzaelouham/kubepilot-ui`) deployed via `backend/deploy/kubernetes/`.

## Why the pasted kubeconfig fails

The real kind kubeconfig points at `https://127.0.0.1:40393` (kind publishes its
API server on the **host** loopback). From the backend pod that address is the
pod's own loopback — nothing is listening there. Verified evidence:

| Target | From host | From Minikube container / pod | Why |
|---|---|---|---|
| `127.0.0.1:40393` (kind, host loopback) | OK | unreachable | pod loopback != host loopback |
| `172.18.0.2:6443` (kind node on the `kind` bridge) | OK | unreachable | `kind` and `minikube` are separate Docker bridges; Docker's `FORWARD` policy is `DROP` |
| `192.168.49.3:6443` (kind node after attaching to the `minikube` bridge) | OK | **OK** | same layer-2 bridge |

The current fix makes this failure explicit at registration time (probe + clear
`kubeconfig_unreachable` error naming the server, `${cause}`, and the localhost
hint). The recipe below turns the mismatch into a working connection.

## Recipe

1.  Attach the kind node to Minikube's Docker bridge so the pod's network path
    can reach it:

    ```bash
    docker network connect minikube kind-control-plane
    ```

    The node gains a second IP on `192.168.49.0/24` (for example
    `192.168.49.3`). Confirm:

    ```bash
    docker inspect kind-control-plane \
      --format '{{range $n, $c := .NetworkSettings.Networks}}{{$n}}={{$c.IPAddress}} {{end}}'
    ```

2.  Build a rewritten kubeconfig whose `server` is that reachable address. The
    kind API server's serving certificate only contains the pre-attach
    addresses (`kind-control-plane`, `127.0.0.1`, `172.18.0.2`, ...), so a
    strict CA verification of the reachable IP fails; set
    `insecure-skip-tls-verify: true`. Client certificates still authenticate,
    so Kubernetes authn and RBAC are unchanged.

    ```bash
    kubectl config view --context kind-kind --raw > kind-rewritten.yaml
    # edit 'server' -> https://<node-ip-on-minikube-network>:6443
    # set 'insecure-skip-tls-verify: true'
    ```

    The backend's kubernetes client honors `insecure-skip-tls-verify` from the
    kubeconfig, so the registration probe accepts it.

3.  Register the rewritten kubeconfig in **Settings → Clusters → Register
    cluster**, or via the API:

    ```bash
    curl -X POST $BASE/api/v1/clusters \
      -H "Cookie: kubepilot_session=$TOKEN" -H "content-type: application/json" \
      -d "{\"name\": \"kind\", \"kubeconfig_content\": \"$(cat kind-rewritten.yaml | tr '\n' ' ')\"}"
    ```

    Expect `status: "active"` with `endpoint: https://192.168.49.x:6443`;
    namespaces/workloads then load through the UI and API.

Seen live (validated session): `/cluster/namespaces` lists the kind cluster's
namespaces, `/cluster/resources/pods?namespace=kube-system` lists 8 pods,
`/cluster/resources/nodes` lists `kind-control-plane`.

## Verification from the backend pod itself

```bash
minikube kubectl -- exec -i -n kubepilot backend-<pod> -- sh -c 'cat > /tmp/kc.yaml' < kind-rewritten.yaml
minikube kubectl -- exec -n kubepilot backend-<pod> -- python3 -c "
from kubernetes import config, client
config.load_kube_config('/tmp/kc.yaml')
print([n.metadata.name for n in client.CoreV1Api().list_namespace().items])"
```

## Persistence

`docker network connect` is not durable:

- recreate the kind cluster — attach again
- restart Docker / delete the `minikube` container — attach again after
  `minikube start`

For a persistent setup, recreate kind on the Minikube bridge so the serving
certificate is generated with the `192.168.49.x` SAN (drops the
`insecure-skip-tls-verify` flag, but destroys the current kind cluster):

```yaml
# kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  dockerNetwork: minikube
```

```bash
kind delete cluster
kind create cluster --config kind-config.yaml
```

## Security note

Using `insecure-skip-tls-verify` is acceptable for a local dev rig where
the API server is a container you created; it disables server-identity pinning
only (client-cert / RBAC auth is untouched). Do not use the skip flag against
external or shared clusters — prefer Recipe B (SAN'd certificate) or a
reachable public endpoint.