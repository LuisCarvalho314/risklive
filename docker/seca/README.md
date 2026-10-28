# Reproducible SECA build inputs

Source gitlink: `experimental`, commit `4630d280e323ed2067b9ac7a0efb4f59447d335d`.
`SOURCE.sha256` covers the tracked workspace manifest and all tracked crate
files, including V1, V2 scientific sources, and `seca-v2-cli`. Docker verifies
these before compiling. Regenerate listed hashes, the revision file, and the
image label with `scripts/update-seca-pin.sh` after updating the gitlink; add
new copied source paths to the manifest before running the script.

Builder: `rust:1.92.0-bookworm@sha256:e90e846de4124376164ddfbaab4b0774c7bdeef5e738866295e5a90a34a307a2`.
The parent-owned `Cargo.lock` pins the build dependency graph, including the
V2 workspace package and dependencies required by the pinned V1 CLI. Docker
uses this reviewed lock in place of the upstream workspace lock.

The existing builder tests all three packages with `--release --locked --jobs 2`
and builds both binaries. Only `realtime-seca-cli` and `seca-v2-cli` are copied
into the application runtime. The Python service continues to use V1.

From the repository root, build and run V2 in the development environment:

```sh
docker build --target seca-builder -f docker/Dockerfile.app -t risklive-seca-builder:local .
mkdir -p /tmp/risklive-v2
cat > /tmp/risklive-v2/batch.json <<'JSON'
{"batch":0,"sources":[{"id":"article-001","words":["nuclear","reactor"]}]}
JSON
cat > /tmp/risklive-v2/config.json <<'JSON'
{"alpha":0.7,"beta":0.5,"error_limits":{"alpha":0.1,"beta":0.2,"importance":0.3},"minimum_branch_sources":2,"window":3}
JSON
docker run --rm --user "$(id -u):$(id -g)" -v /tmp/risklive-v2:/data risklive-seca-builder:local seca-v2-cli update --batch /data/batch.json --config /data/config.json --state /data/state.json
docker run --rm --user "$(id -u):$(id -g)" -v /tmp/risklive-v2:/data risklive-seca-builder:local seca-v2-cli show-last --state /data/state.json
```

Use consecutive batch numbers when resuming the state. The configuration above
is a local example, not a production setting. See the
[upstream V2 CLI contract](../../experimental/crates/realtime-seca-v2/README.md)
for state and report semantics.
