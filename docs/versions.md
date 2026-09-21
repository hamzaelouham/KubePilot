# KubePilot Version and Image Tags

Use semantic versioning for releases and immutable branch/commit tags for
preview builds.

## Release versions

| Change | Git tag | Docker image tags |
| --- | --- | --- |
| Bug fix | `v1.0.1` | `v1.0.1`, `latest` |
| Backward-compatible feature | `v1.1.0` | `v1.1.0`, `latest` |
| Breaking change | `v2.0.0` | `v2.0.0`, `latest` |
| Release candidate | `v1.1.0-rc.1` | `v1.1.0-rc.1` |

- Patch versions contain fixes only.
- Minor versions add backward-compatible features.
- Major versions contain breaking changes.

Create an annotated release tag on the completed commit:

```bash
git tag -a v1.1.0 -m "KubePilot v1.1.0"
git push origin master v1.1.0
```

Then run the **Build and push Docker images** GitHub Actions workflow from
`master`, providing `v1.1.0` as the image tag. The workflow publishes:

```text
hamzaelouham/kubepilot-backend:v1.1.0
hamzaelouham/kubepilot-backend:latest
hamzaelouham/kubepilot-ui:v1.1.0
hamzaelouham/kubepilot-ui:latest
```

The workflow requires the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository
secrets.

## Preview builds

Preview images should identify both the branch type and commit, for example:

```text
feature-resource-filters-a1b2c3d
fix-sidebar-context-e4f5g6h
```

Use these tags for feature and fix branches. Do not overwrite `latest` from a
pull-request build; reserve `latest` for an approved release build.

This gives every change a traceable Git commit, release tag, and Docker image.
