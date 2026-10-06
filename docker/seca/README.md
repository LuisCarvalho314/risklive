# Reproducible SECA build inputs

Source gitlink: `experimental`, commit `a03e2ba3385d328a10eacbf584c57cddc6f40a62`.
`SOURCE.sha256` covers the copied workspace and crate files. Docker verifies
these before compiling. The former timeline-many patch is now part of the
Rust repository; it must not be applied twice.

Builder: `rust:1.92.0-bookworm@sha256:e90e846de4124376164ddfbaab4b0774c7bdeef5e738866295e5a90a34a307a2`.
The parent-owned Cargo.lock pins the existing dependency graph. No dependency
changes are required by the persistent update command. The Rust workspace
ignores locally generated root lockfiles; Docker uses this reviewed lock.

The builder runs core and CLI tests with `--release --locked --jobs 2`, then
builds the CLI with the same flags. Only the binary is copied into runtime.
The update command restores full schema-3 state and selectively evolves HKTs;
RiskLive's Python service owns the transactional stream database and snapshots.
See [the state lifecycle and verification guide](../../docs/seca-light-stream.md).

To update inputs, update the submodule gitlink, regenerate hashes from tracked
Cargo.toml/crates files, update the image's source-revision label, and review
locked dependency changes if needed. Run core, CLI and isolated stream checks.
A successful offline core/example build does not establish a passing complete
CLI/container build.

The current Rust commit is local: publication was attempted but blocked by
shell DNS resolution and GitHub connector HTTP 403. Publish that commit to the
Rust repository before sharing a parent commit that depends on its gitlink.
