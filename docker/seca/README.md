# Reproducible SECA build inputs

Source gitlink: `experimental`, commit `42c07c098c1fadb931a4e7b5b6920ee9561dabc5`.
The submodule remains unchanged. `SOURCE.sha256` covers the copied pinned workspace
and crate files. The Docker builder checks those hashes before applying the patch.

Builder: `rust:1.92.0-bookworm@sha256:e90e846de4124376164ddfbaab4b0774c7bdeef5e738866295e5a90a34a307a2`.
The pinned workspace has no root Cargo.lock. This parent-owned Cargo.lock locks its
61 packages, including checksums, without updating an existing Rust workspace lock.
Python uv.lock and frontend pnpm-lock.yaml are unchanged.

Build: `cargo build --release --locked -p realtime-seca-cli --jobs 2`.
The builder first runs `cargo test --release --locked -p realtime-seca-cli --jobs 2`.
Cargo's [locked mode](https://doc.rust-lang.org/cargo/commands/cargo-build.html)
rejects dependency resolution changes. Only the binary is copied to the runtime.

`timeline-many.patch` is an explicitly approved compatibility extension for the
missing CLI command; it does not change the core, existing timeline, or from-csv.
It preserves each input batch as a daily step instead of re-chunking all articles.
It validates sequential indices, scopes only the pinned CSV converter's synthetic
row_N identities by batch (avoiding unrelated-row collisions across dates), and
exports the same tree/manifest structure. Custom IDs retain their identity.
Its tests cover unequal day sizes and reject out-of-order batches before output.
No model, provider, HTTP server, or scheduler is used by this command.

To update inputs in future, deliberately update the gitlink, regenerate checksums
from clean pinned files, review the compatibility patch, resolve the workspace lock
in a temporary copy, and repeat offline fixture validation. Do not generate or
modify Cargo.lock inside the submodule for this build.
