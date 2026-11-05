# 2.3.79-haos90 publication receipt

**Status:** published and install-ready for a separately authorized operator action. Publication and image/source verification are complete; .90 installation and physical acceptance are unverified. Latest confirmed installed is .89. Auto update was confirmed off on 5 November 2026. No agent-performed HA action occurred.

## Current published release: 2.3.79-haos90 - 5 November 2026

Published at 2026-11-05T01:52:52Z (12:52:52 AEDT): [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.79-haos90). Tag source `00b837b34e5c26639dd8d2f0d4d448dbf4e452b7`, tree `6970c5ed6468ee272e4880bae685247af73ab967`, annotated tag object `801de298f8c834188aada2e0d7d2b4ed2dcab197`. Metadata PR #77 merged normally at `545a4bd6f80d8fb602a53e85a75b3eea68a4e0d1` (01:49:47Z); merge tree equals the tagged tree.

Build [41950610118](https://github.com/Belot77/sigenergy-optimizer/actions/runs/41950610118) succeeded at 01:47:10Z. Version/latest OCI index `sha256:f15fe33002420affaece797353fa53a191b1fa5a9ab2a7d7f7de48db78b2823e`; amd64 `sha256:11e5dc3a6e6c7812a8ec79dff67dc5570d110ab49353ac84f9bdf796d08776eb`; arm64 `sha256:e438157e4db05cf1bdecbd93397dbdeb81b9ff028f70f42490f49a23cabaae09`. Source fingerprint `sha256:da7274c7f7ae841163dee06028364d3ca0b07837b680c3a7bfc4c44092738ee5` uses SHA-256(sorted absolute image path + NUL + file bytes + NUL). All 11 compressed layers/diff IDs and 15 selected source files/modes per platform were verified using default TLS, without extraction or container execution. Independent helper/source-expectation, registry metadata/config and completed-proof consistency reviews are GO; independent reviewers did not redownload layer bodies. The offline verifier passed 73 cases. Prior immutable .89 index `sha256:1d9e0ed00453cb57698d04d3ca0ef972cf1e672a4bd87a369029334b647961b5` is unchanged. Post-publication tag/source/normal-merge/release/index checks passed.

This release carries PR #76's floor-stop admission retirement: after an already-applied automatic Morning Dump reaches its configured floor under trusted automatic application, further same-window Dump admission stops. No timer or floor change. Later same-window refill cannot restore Dump admission; restart forgets the process-local latch and current checks must pass again. Closure still needs its own proof, and the Dump floor is not a whole-system SoC minimum.

Pre-bump source validation passed 1,737 tests / 1,758 subtests; release checks passed 123 tests / 156 subtests. Independent reviews are GO. Published and install-ready for a separately authorized operator action; .90 installation and physical acceptance are unverified. Latest confirmed installed remains `2.3.78-haos89` / `352b61303e7b18da4a46b40ba57546e0c8baa1e7` from 5 November 08:02:25 AEDT. Auto update was confirmed off on 5 November. No agent-performed HA action occurred.

O4 Boost qualification/stability, O5 reserve/load/price policy, O6 broader handoff/depletion and O9 ownership/status work remain open. Relevant live proof, including .90 floor retirement and .89 changing deliberate-export targets, remains outstanding. Legacy O11 and O20 remain parked; provisional-tariff switching has no timer change. Next action is separate installation authorization, exact startup identity and applicable supervised live evidence. The detailed historical preparation and remaining gates follow.



## Historical preparation baseline and scope

Repository: [Belot77/sigenergy-optimizer](https://github.com/Belot77/sigenergy-optimizer).
Workspace: `C:\Projects\sigenergy_optimizer-release-haos90`.
Branch: `release/2.3.79-haos90`.
Base: verified main `52705dba6d90590a9cc292903dda76c6b810f769`.

PR [#76](https://github.com/Belot77/sigenergy-optimizer/pull/76) merged normally at that base on 5 November 2026 at 12:26:13 AEDT (01:26:13Z). Its reviewed source is `b06cf9edaa0279ef5ad36f404f2267628a6f1a60`; merge tree `845357ff62c9cbf56217e790dc1a47bb8465a4b5` equals the tested source tree. Original worktrees and unfinished work remain preserved.

Preparation changes exactly five version literals from `2.3.78-haos89` to `2.3.79-haos90`: API version, optimizer runtime signature, add-on config version, build-label version and buildstamp. The other seven paths are README, CHANGELOG, AI_HANDOVER, CURRENT_STATE, CONTROL_CONTRACT, ROADMAP and this release record. No other production, test, build-script, configuration or permanent instruction changes.

At preparation, latest published and confirmed installed was `2.3.78-haos89`, source `352b61303e7b18da4a46b40ba57546e0c8baa1e7`, confirmed by the operator's 5 November 08:02:25 AEDT startup. Auto update had last been confirmed off on 4 November. Publication and image/source verification were completed later as recorded above; installed identity remains .89 and Auto update was reconfirmed off on 5 November.

## Correction and tradeoff

Before PR #76, an already-applied Morning Dump could reach its configured floor, close, and re-enter after a small SoC rebound during the same identified morning. The supplied 5 November pre-update .88 archive showed two brief 15.1% re-entries. These were not .89 regression evidence and did not establish a sustained floor breach.

After PR #76, a trusted finite SoC at or below the configured floor during a real automatic application retires further Dump admission for that window, provided a genuinely completed automatic Dump has recorded that window and the supplied state/decision still indicate automatic ownership and Remote EMS enabled. Retirement occurs before awaiting closure, survives pending/failed/exceptional/cancelled closure and clamps stale permissive Dump decisions.

Decision previews cannot arm or retire Dump. Independent owners, Manual/Force targets, current actuator restrictions and refill-feasibility retirement stay separate. Floor retirement has its own diagnostic reason: `morning_dump_floor_window_retired` / `floor_reached_retired_this_window`. No timer, hysteresis, floor change or durable storage is added.

The tradeoff is no later same-window Dump even after significant battery refill. The next identified morning may qualify; a process restart forgets this latch and requires all current admission checks again. This is an admission repair, not physical close proof. The configured 15% remains a Dump stop, not a whole-system battery minimum.

## Validation

The exact pre-bump source passed the guarded full suite: **1,737 tests / 1,758 subtests**, zero failures, 206 warnings, 284.64 seconds. Guards recorded 75 memory and 2,237 isolated temporary SQLite connections, zero rejected paths, 2,419 internal socket pairs and zero rejected external connections. Protected database size/mtime metadata stayed unchanged; contents were not read. Dotenv and external DNS/socket access were disabled. Independent source/safety, test and documentation/scope reviews are GO.

Static version/source-pinning checks passed **16 tests** in 9.91 seconds. Ten focused runtime modules covering Dump floor retirement/refill re-entry/export intent, existing floor characterization, special-mode safety, deliberate-target dispatch and MSC settlement/recovery passed **107 tests / 156 subtests**, zero failures (202 warnings, 7.75 seconds). These disjoint release checks total **123 tests / 156 subtests**. Runtime guards recorded 221 isolated temporary SQLite connections and 169 internal socket pairs, zero rejected paths/connections. Protected database metadata stayed unchanged; dotenv and external DNS/socket access were disabled. Independent version/source and final release documentation/scope reviews are GO.

A full suite is not repeated for five version literals and documentation when source identity and focused release checks pass. Software checks do not establish physical acceptance.

## Remaining work and live evidence

- Publication is complete under the operator's separate approval. The receipt documentation records the verified source, image proof and remaining limits. Installation and live settings remain separately authorized actions.
- Live: separate installation authorization and exact startup runtime `2.3.79-haos90` / source `00b837b34e5c26639dd8d2f0d4d448dbf4e452b7` proof; then observe an applied Dump reaching its floor, closure request/readback/flows and any rebound through the rest of the same morning. Do not restart or force a discharge for acceptance. Restart semantics remain a software limitation requiring applicable future evidence.
- Existing .89 deliberate-export target correction still needs changing positive-target evidence on an eligible Dump/Boost cycle. Service-call success alone is not settlement.
- O4 Boost qualification retention/stability, O5 reserve/load/price policy, O6 broader handoff/depletion behavior and O9 ownership/status audit remain open. Published Solar/provider/fill and MSC corrections retain applicable physical-proof requirements.
- Legacy O11 causes remain unresolved and parked. O20 non-positive-price Dump redesign and provisional-tariff switching are parked; no tariff timer is included. Historical O8 loss is irrecoverable; short Demand Window spikes remain deferred rather than confirmed defects.
- After stability/live gates: ownership audit, architecture consolidation, cleanup, GUI/UX, Climate Manager, integration validation/polish, then later replay/modelling and experimental scheduling.

The historical preparation rollback was withholding the uncommitted candidate. Before installation, the operator can withhold .90; any source rollback requires a separately reviewed scoped software revert preserving unrelated work. Publication, installation identity and physical acceptance must be reported separately.
