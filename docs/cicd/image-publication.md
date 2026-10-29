# Candidate images

`CI` (`.github/workflows/ci.yml`) tests every push and pull request. Backend,
frontend and real Rust SECA integration/crash-recovery tests must pass for the
same event SHA before container builds. Containers are scanned for HIGH/CRITICAL
vulnerabilities, including unfixed issues. Publication pushes the scanned local
images without rebuilding, captures registry digests, and uploads
`risklive-candidate` containing `candidate.json` (90-day artifact retention).
Deployment tooling downloads it by the successful CI run ID. Retain deployed
candidate manifests on the host beyond Actions artifact expiry; retain GHCR
versions needed for rollback. Never use retention cleanup on deployed digests.

Publication is disabled until repository variable `GHCR_PUBLICATION_ENABLED` is
`true`. The publish job runs only on trusted pushes to `main` or
`DEVELOPMENT_BRANCH` (default `develop`), after all test jobs. Configure protected
branches and the `registry-publishing` GitHub environment before activation.
Only this job receives `packages: write`; PR container jobs have read permissions
and receive no publication token. No PAT is needed for CI publication.

## Private registry activation (operator action, not performed by this task)

Privacy of either package has **not been confirmed** in this coding session.
Before publishing any RiskLive layer, an operator must provision the
`luiscarvalho314/risklive-app` and `luiscarvalho314/risklive-web` GHCR namespaces
with harmless seed images containing no RiskLive source or secrets. Verify both
packages are private, disable repository permission inheritance, and grant the
RiskLive repository Actions write access and infra Actions read access explicitly.
The public repository visibility does not establish package privacy.

`python scripts/ci/package_privacy.py` uses `GH_TOKEN` (the workflow's
`GITHUB_TOKEN`) to verify existing package visibility, then independently attempts
anonymous GHCR token acquisition and tag access. Missing packages, unreadable
metadata, public visibility, anonymously readable tags, or inconclusive requests
block publication. A plain unauthenticated manifest HTTP 401 is insufficient
because public GHCR packages also require an anonymous bearer-token exchange.
The guard runs before build and again immediately before push. An operator must
keep package visibility private; no workflow can prevent a package administrator
from changing visibility later.

GitHub documentation:
- https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages

## Version contract

Tags are `sha-<40-character-sha>-run<run-id>-<attempt>`. Deployment consumes only
`ghcr.io/luiscarvalho314/risklive-{app,web}@sha256:<64-hex-digest>` from the
manifest. Both images have OCI source/revision labels and
`org.risklive.seca.revision` / `org.risklive.seca-v2.revision` labels.
Candidate state compatibility is deliberately `unverified`: publication cannot
assert database migration or rollback compatibility.

The existing `experimental` Light source remains pinned at
`1631655ad64e43e00c54cba05c6a6fc859e1bcee`. `experimental-v2` separately pins
`4630d280e323ed2067b9ac7a0efb4f59447d335d`. V2's source also changes the legacy
CLI's state format from schema 3 to schema 4, which rejects existing Light state.
The separate gitlinks preserve the production Light state contract while adding
and testing the V2 executable. No source code is copied into infra. Candidate
`source.seca_revision` and `source.seca_v2_revision` record both pins.

## Offline validation

Run `python -m unittest discover -s scripts/ci/tests -v` and
`bash -n scripts/ci/publish.sh`. CI runs real V2 tests separately with
`--confcutdir=tests/integration`; running them only in the broad backend suite
silently skips them because that suite forbids subprocesses. Existing Liwan
Compose/listener tests likewise run in a separate process outside the backend
audit guard. Docker Compose validation does not start containers.
