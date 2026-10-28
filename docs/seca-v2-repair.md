# SECALight V2 frontend repair

Reference: `badd43151ad2c221c991caa73305bd01c108aa1d`. The web trees at
`e2a553c` and `6d882fb0` are identical. This repair preserves native V2 output,
source identities, HKT topology, persisted state and all legacy controls.

## UI audit and restoration

PR #9 replaced the experimental toolbar with a V2 header, retained-source
statistics and a reconstruction table; removed original controls in V2 mode;
changed wrapper spacing/overflow and colour treatment; reset the treemap on
batch changes; and introduced a replacement empty-model message.

The repair reuses the original component shell, Experimental badge, classes,
single hierarchy colour, layout buttons, breadcrumb, Reset and source-link
interactions. The root breadcrumb uses the original `SECA Tree` label. There
are no replacement headers, panels, tables, labels or controls. Legacy and
fallback presentation and controls retain their original behaviour.

Remaining visible differences from the reference, exclusively in V2 mode:

- Window/history, final-HKT error metric and direction controls, diagnostic
  availability text and batch slider/date/count are omitted. Native publication
  supplies one current hierarchy, and reconstruction errors describe evaluated
  scopes before reconstruction; these controls have no scientifically equivalent
  V2 binding. The existing layout, breadcrumb and Reset controls remain.
- Native descriptor labels, refuge nodes, nesting, memberships and source links
  determine the data shown. An empty native model leaves the treemap empty rather
  than substituting legacy data or introducing a new status message.
- Tile areas divide each source's mass among overlapping siblings and carry
  those fractions into descendants. Uncovered child mass leaves parent area
  without child tiles. Retained-but-unmapped evidence leaves root area without
  tiles; no synthetic remainder/refuge/source nodes are added.

## Data and layout

Each distinct mapped root source starts with mass one. Within every HKT, each
source's inherited mass is divided by its sibling membership multiplicity.
Node counts and source references remain native integer counts and identities;
only layout mass is fractional. Sources without child memberships retain their
mass locally. Root local mass is retained count minus distinct mapped count;
a mapped count exceeding retained count still fails validation.

`secaV2Mass` is frontend layout metadata only. D3 sums local mass with descendants.
For V2-marked nodes only, the tiler receives a child rectangle reduced to the
covered fraction, and a proxy budget equal to child mass. This handles binary's
fill behaviour and avoids reserving mass twice in slice/dice. Main Newsmap and
legacy trees use the original layout path. Empty native nodes and child topology
are retained even when their layout area is zero.

The existing dashboard poll now refreshes the server result in every mode.
Changing mode alone does not trigger another refresh. The original component
hierarchy is retained, with no batch key or mode-specific component remount.

## Validation

Focused tests cover unmapped evidence through the loader, invalid counts,
incomplete children, overlapping memberships at two levels, empty memberships,
all six D3 tilers, actual default padding, a 50,000-source report, unchanged
unmarked layout behaviour, refresh transitions and treemap mount preservation.
Run from `web`: `pnpm typecheck`, `pnpm test --maxWorkers=2`, `pnpm build`.

A local Chromium harness used the real components, compiled application CSS,
and synthetic data at 1440x900. Legacy timeline and fallback screenshots were
byte-identical against the `6d882fb0` component. The V2 screenshot showed actual
uncovered root and parent area; browser SVG child width was 350.25 versus parent
width 707.5 with default padding. Double-click exposed the expected source link;
there were no browser errors. Artifacts and the temporary harness are in
`/tmp/seca-v2-ui-review/`. This is component-level evidence, not full-application,
all-theme, responsive or production visual certification.

Rust, Python, SQLite, scheduler, publication paths and main Newsmap components
are unchanged. No bootstrap, replay, deployment, push or merge was performed.

## File-by-file summary

| File | Change |
| --- | --- |
| `web/components/newsmap/treemap-experimental-client.tsx` | Restore original shell and colour/interaction props; bind V2 data without new presentation or batch remounts. |
| `web/components/dashboard/newsmap-experimental-live-page.tsx` | Refresh on completed dashboard polling in every mode, without a mode-change refresh loop. |
| `web/lib/seca-v2.ts` | Accept unmapped evidence; distribute per-source fractional mass; preserve zero-mass topology and original root label. |
| `web/lib/dashboard-schema.ts` | Declare V2-only layout mass metadata. |
| `web/lib/treemap/layout.ts` | Reserve actual uncovered area exclusively for marked V2 nodes. |
| `web/tests/unit/treemap-experimental-client.test.tsx` | Check original styling/colour props, absent replacement panels, empty model and mount preservation. |
| `web/tests/unit/seca-v2-refresh.test.tsx` | Check polling across all modes and no duplicate refresh on transitions. |
| `web/tests/unit/seca-v2.test.ts` | Check restored root label, invalid mapped counts and loader acceptance of unmapped evidence. |
| `web/tests/unit/seca-v2-geometry.test.ts` | Verify real D3 geometry, overlaps, zero/large reports and unchanged main/legacy paths. |
| `docs/seca-v2-repair.md` | Record audit, visible exceptions, implementation and verification boundaries. |

Final checks passed: local type checking, all 126 frontend tests (24 files), and
production Next.js build. The repository's `docker/Dockerfile.web` also built
successfully as `risklive-web:seca-v2-repair-local`. Its `build` stage was tagged
`risklive-web:seca-v2-repair-tests`; a disposable container with `--network none`
and no host mounts passed `pnpm exec tsc --noEmit --incremental false` and all
126 frontend tests. Logs are `/tmp/seca-v2-repair-{build,tests,docker-build,docker-tests}.log`.
These checks do not establish production readiness.
