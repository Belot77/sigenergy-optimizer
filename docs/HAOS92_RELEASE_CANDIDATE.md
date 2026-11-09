# 2.3.81-haos92 release candidate

**Status.** Local, uncommitted and unpublished in `C:\Projects\sigenergy_optimizer-release-haos92` on `release/2.3.81-haos92`. The branch was fast-forwarded to merged main `4acb81cb6f941556b683da49a6ccdaf6154780f3` with all 12 prepared files verified byte-for-byte before reconciliation. `.91` remains the latest published release, at source `6144d027496b2a1822219324eb37512d44b002c1`. The latest confirmed installation is `.90` at source `00b837b34e5c26639dd8d2f0d4d448dbf4e452b7`. The operator last confirmed Auto update off on 9 November. [The .91 publication receipt](HAOS91_RELEASE_CANDIDATE.md)

## Included changes

- PR #82 merged as `403f31b`. Apply ESS Controls preserves an explicit 0 kW PV Max in its request and rejects blank, nonnumeric, nonfinite and negative entries before submission. [PR #82](https://github.com/Belot77/sigenergy-optimizer/pull/82)
- PR #83 merged as `b99fa4d`. Successful Mode and ESS API requests show “Request accepted” and refresh the dashboard. Confirm the hardware outcome from request-correlated readbacks. [PR #83](https://github.com/Belot77/sigenergy-optimizer/pull/83)
- PR #84 merged as `362fbbc`. The dashboard distinguishes last optimizer or preset targets, HA-reported limits and measured power for grid export, grid import and ESS charge. It shows snapshot age and replaces stale, unavailable or unverified readings with evidence labels. Positive measured battery power indicates charging and negative indicates discharging. [PR #84](https://github.com/Belot77/sigenergy-optimizer/pull/84)
- PR #85 merged as `4acb81c`. The WebSocket sends unavailable power evidence before the first optimizer snapshot and reads freshness settings when a valid report is present. [PR #85](https://github.com/Belot77/sigenergy-optimizer/pull/85)

## Offline validation and publication gates

The first expanded release run caught an ingress WebSocket failure in the empty-snapshot fixture. PR #85 deferred the freshness-settings reads until a valid report is present and extended the ingress regression. Independent review passed.

The refreshed .92 worktree passed 229 guarded Python tests and 106 subtests, plus 14 Node dashboard and form tests. The Python suite covered release version consistency, local source pinning, ingress and dashboard status, manual ESS, telemetry and adjacent control safety. The guards allowed 154 temporary SQLite stores and 246 internal socket pairs and rejected zero database paths. The candidate is ready for publication approval. Live HA and browser layout remain unverified.

The approved scope is local preparation of version metadata and release documentation. Commit, push, release metadata PR and merge, tagging, image build and publication, GitHub Release and the publication receipt require separate approval. Pushing the release tag triggers publication of the version image and `latest`. After approval, verify the exact tagged source and merge tree, both architecture images and their embedded source, and the version and `latest` index references before recording publication evidence.

## Installation, evidence and rollback

- Withhold the local candidate if review finds a problem. For a later source rollback, use a separately reviewed scoped revert. Before an authorized installation, verify the rollback path and the exact image for the prior confirmed `.90` runtime. A live rollback requires separate authorization.
- After a separately authorized installation, verify the `.92` runtime and exact published container source from startup. Begin with read-only dashboard and HA checks for target, reported limit, measured power, snapshot age and unavailable evidence. Confirm the applicable authority and settings before any supervised actuation.
- During separately authorized live checks, correlate accepted Mode and ESS requests with the requested targets, fresh post-request HA and inverter observations, and measured grid and battery flows. Verify zero PV Max only under an approved scenario with a safe restoration plan. Stop on conflicting or missing evidence or unexpected actuation. Live acceptance remains open.
- O4 sunset continuation and stability, O5 reserve/load/price policy, O6 broader Morning Dump handoff and depletion, and O9 ownership and settings remain open. Capture the passive O4 sunset trace during a natural eligible sunset and correlate the outcome with observed controls and measured export. Relevant .90 floor-retirement and .89 deliberate-export target proof also remain open. [Roadmap](ROADMAP.md)
