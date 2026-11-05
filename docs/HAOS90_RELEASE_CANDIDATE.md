# 2.3.79-haos90 local release preparation

**Status:** local, uncommitted, unpublished and uninstalled. Approved scope is preparation, focused checks and independent review only. No commit, push, tag, image build/publication, release, HA access or live settings change is authorized in this stage.

## Verified baseline and scope

Repository: [Belot77/sigenergy-optimizer](https://github.com/Belot77/sigenergy-optimizer).
Workspace: `C:\Projects\sigenergy_optimizer-release-haos90`.
Branch: `release/2.3.79-haos90`.
Base: verified main `52705dba6d90590a9cc292903dda76c6b810f769`.

PR [#76](https://github.com/Belot77/sigenergy-optimizer/pull/76) merged normally at that base on 5 November 2026 at 12:26:13 AEDT (01:26:13Z). Its reviewed source is `b06cf9edaa0279ef5ad36f404f2267628a6f1a60`; merge tree `845357ff62c9cbf56217e790dc1a47bb8465a4b5` equals the tested source tree. Original worktrees and unfinished work remain preserved.

Preparation changes exactly five version literals from `2.3.78-haos89` to `2.3.79-haos90`: API version, optimizer runtime signature, add-on config version, build-label version and buildstamp. The other seven paths are README, CHANGELOG, AI_HANDOVER, CURRENT_STATE, CONTROL_CONTRACT, ROADMAP and this release record. No other production, test, build-script, configuration or permanent instruction changes.

Latest published and confirmed installed remains `2.3.78-haos89`, source `352b61303e7b18da4a46b40ba57546e0c8baa1e7`, confirmed by the operator's 5 November 08:02:25 AEDT startup. Auto update was last explicitly confirmed off on 4 November. The proposed `v2.3.79-haos90` tag is not created and there is no .90 image/source receipt.

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

- Release: finish local checks/review, then obtain separate approval for the metadata commit, branch push/PR, exact tag/build, source/digest verification, normal merge, GitHub release and receipt.
- Live: separate installation authorization and exact startup runtime/source proof; then observe an applied Dump reaching its floor, closure request/readback/flows and any rebound through the rest of the same morning. Do not restart or force a discharge for acceptance. Restart semantics remain a software limitation requiring applicable future evidence.
- Existing .89 deliberate-export target correction still needs changing positive-target evidence on an eligible Dump/Boost cycle. Service-call success alone is not settlement.
- O4 Boost qualification retention/stability, O5 reserve/load/price policy, O6 broader handoff/depletion behavior and O9 ownership/status audit remain open. Published Solar/provider/fill and MSC corrections retain applicable physical-proof requirements.
- Legacy O11 causes remain unresolved and parked. O20 non-positive-price Dump redesign and provisional-tariff switching are parked; no tariff timer is included. Historical O8 loss is irrecoverable; short Demand Window spikes remain deferred rather than confirmed defects.
- After stability/live gates: ownership audit, architecture consolidation, cleanup, GUI/UX, Climate Manager, integration validation/polish, then later replay/modelling and experimental scheduling.

Safest rollback now is withholding this uncommitted candidate. Any later rollback is a separately reviewed scoped software revert preserving unrelated work. Publication, installation identity and physical acceptance must be reported separately.
