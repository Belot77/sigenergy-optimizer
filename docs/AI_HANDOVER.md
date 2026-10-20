# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-20

Read `C:\Projects\AGENTS.md`, worktree `AGENTS.md`, this handover, `CURRENT_STATE.md` and relevant `CONTROL_CONTRACT.md` sections. Inspect only minimum relevant files. Git records repository identity; HA and operator evidence establish live state.

## Current published release and supplied HA evidence - 20 October 2026

**Latest published release: .73 / 2.3.62-haos73.** GitHub Release v2.3.62-haos73 was published on 19 October at 07:02 UTC (18:02 Sydney), source tag/commit 46d36358d38137231dff081176a372c3aa1f4cee. PR #24 merged to main at d8d78320c43096bbae30210bf8bcaa60ec3313d0, tree cbae95c86bc121c92d1aa3d319f6bb44b309594c, exactly matching the reviewed candidate tree. Build run 39211551717 succeeded on attempt 1 for amd64/arm64; the verified .73 and latest OCI index is sha256:a2313bed130c77d7fa4139b03adf67c4282f7a59c1ed116d8d64083e9cfc6f59.

PR #23 source-pinning fix 1042ee95c94c56eb64ff0a5ae123ca863c49cd25 is included in .73. It selects a full SOURCE_REF matching HEAD or resolves BUILD_VERSION to the corresponding version tag, fetches and detached-checks out the selected source, and records its full identity. The original .72 tag/image remains at 3afefcd113d2c6f3eadd5aadd52fbda1a8b35f28 and does not contain that Dockerfile fix. The .73 release-preparation commit changed version markers and documentation; it did not add optimizer control behavior beyond .72. See [HAOS73_STATUS_AND_LIVE_PROOF.md](HAOS73_STATUS_AND_LIVE_PROOF.md) for the dated fixes and scoped live-proof checklist.

The operator supplied startup evidence for 20 October: runtime .73, exact source 46d36358d38137231dff081176a372c3aa1f4cee, Supervisor local build 71 to 73 with BUILD_VERSION=2.3.62-haos73, final start at 06:53:23 Sydney. This supports the reported current installed identity; it is operator-supplied evidence, not direct HA access by this reviewer.

### Unreleased local Solar stability candidate - 20 October 2026

Branch `fix/solar-export-stability`, workspace `C:\Projects\sigenergy_optimizer-solar-stability`, starts at main `e4601735842c81ef3e328ab1198b707a7bab9495`. The authorized local candidate bridges brief Solar dips strictly before 15 seconds after the older fresh, coherent PV/load report proving measured surplus above 0.5 kW, following successful final Solar application. Both reports must advance to renew proof; held/cached evidence, 0.2–0.5 kW continuation and forecasts cannot renew it. Hard-gate or application failure invalidates proof immediately. Expiry requests closure under current authority, retaining deadline re-evaluation and bounded three-second retries after failed application. Independent limits and physical settlement requirements remain mandatory. See CONTROL_CONTRACT.md for exact conditions.

A sanitized deterministic characterization produced seven 25-to-zero kW closures at baseline; candidate ticks retain permission through the short dips with advancing strong measured reports. Mocked application with real ticks is not a complete trace replay or physical inverter proof; separate fake-actuator tests cover expiry fallback. The initial PV collapse remains unexplained. Reported installed baseline remains .73 / source 46d36358d38137231dff081176a372c3aa1f4cee. Candidate is local, unreleased, undeployed and not live-verified.

Final validation on this candidate: full offline suite 1,106 tests / 1,235 subtests passed, zero failures, 206 warnings in 206.22 seconds; focused checks 115 tests / 191 subtests passed. Independent targeted safety review found no remaining blockers after expiry/failure scheduling and refreshed-export-readback corrections. Tests used fake HA, synthetic report provenance and simulated/fake actuator outcomes; they do not prove live settlement. This isolated branch is the reviewed development checkpoint for integration; no release publication, deployment or live settings change is included. All 40 previously fingerprinted protected files and the original tests-only characterization remain unchanged. Release preparation and separately supervised live proof remain required; do not infer deployment from integration or the local test result.

### Retained publication and live-proof evidence

The supplied 20 October trace contains 371 rows from 08:25:04 to 09:01:26 Sydney: 356 helper-success, 8 failed and 7 pending. Seven failures show fallback, pending, then success after 9–10 seconds. The last row reports Automated/MSC, PV export, battery charging and trusted status. Eight early success rows lacked trusted status. These records do not establish all physical limits or settlement outcomes.

O1–O9 remain open for their remaining live, evidence or policy gates; narrow code corrections are recorded in the current-state register. O10 records a confirmed stale trace-archive symptom and O11 parked intermittent MSC observations; causes remain unproven. The operator parked archive and MSC follow-up and paused the reminder, suspecting HA or hardware without confirming that cause. Short physical Demand Window import spikes remain deferred, not confirmed as a bug, and separate from O7 exact-full PV-only proof.

Protected .65 / 2.3.54-haos65 source and public amd64/arm64 images remain available. A separate Supervisor backup report had 49 errors across 7 files and reported backup.json missing; this does not establish that all backups are invalid. The actual .65 restore/reinstall path remains unproven. Do not infer restore readiness from public source/image availability.

For the earlier publication/documentation checkpoint, retained validation was the .72 full-suite result of 1,073 tests / 1,134 subtests, zero failures, 206 warnings in 170.97 seconds; .73 source-pinning/release checks passed 16 tests and local trace characterization was recorded as 56/12. Those historical results were not rerun for that documentation-only update. The later Solar stability candidate has its separate new full-suite result above.

Do not use release.sh: it preserves the existing haos suffix, updates only three of five version markers, stages all changes and can commit/tag/push. Keep installation and live changes separate from this documentation update.

## Historical Stage B checkpoint (16 October, before merge/publication)

- Writable worktree `C:\Projects\sigenergy_optimizer-authority-stage-b`; branch `fix/control-authority-safety`, origin `https://github.com/Belot77/sigenergy-optimizer`. Completed Stage B checkpoint: `ae4a974692aae1300c97845fcc32d4cfa6c2bdea` (`ae4a974692aa`), committed and pushed. At that historical checkpoint PR #20 was open against `main`; it was subsequently merged and .71 was published, verified on 17 October.
- Release candidate **2.3.60-haos71** is prepared with all five release markers aligned. This release-preparation commit contains only those markers and four approved documents; Stage B safety code/tests remain identical to the completed checkpoint. At that historical checkpoint the candidate was not tagged or published; publication was subsequently verified. Installation and live acceptance are not established here.
- Stage B implementation completed, including narrow Medium-over-Evening Boost priority correction. Supplied independent focused review passed corrections A/B/C. Retained final validation: **1,036 tests / 1,084 subtests, zero failures**; compileall and diff check passed. No full-suite/compileall rerun for documentation.
- **No supervised live acceptance. Stage B remains NO-GO for deployment.** Review/test success does not prove live settlement.

## Completed corrections and durable boundaries

- **A - Contradictory actuator evidence:** conflicting actuator observations cannot prove settlement. Deliberate discharge requires the intended export target, with fresh provenance-bearing evidence strictly after its own dispatch boundary; a smaller value sufficient for a safety close is not proof of a deliberate discharge target.
- **B - Independent ESS restrictions:** successful fallback cannot restore ESS charge/discharge capability above independently owned restrictions. Solar relinquishment restores only the otherwise safe normal charge request; Demand Window import blocking and independent PV restrictions remain effective.
- **C - Pending Force ownership:** unchanged Automated selector reports prove freshness, not a new operator selection. A pending authenticated Force request yields to a verified selector state transition strictly after its request, with coherent change/update/report timestamps; supersession stops subsequent writes/retries.

Preserve current Automated/Unknown/confirmed Manual-Force distinctions, dispatch-time authority, observed Remote EMS ON, independent Demand/ESS/PV restrictions, request-specific settlement, fallback and bounded retries. Preserve unattended restart auto-enable after current Automated verification; no persistent OFF registry or mandatory restart handback redesign. Manual/Force targets, including 25 kW, and authenticated `/set_ess` remain unchanged.

## Live identity, rollback and outstanding risks

The operator supplied 20 October startup evidence for runtime .73 and source 46d36358d38137231dff081176a372c3aa1f4cee; Supervisor reported local build 71 to 73, BUILD_VERSION=2.3.62-haos73, final start 06:53:23 Sydney. This supports current reported identity but is not direct HA access by the reviewer. Earlier .70 and .71 identity reports are superseded by this startup evidence.

- The 20 October live trace sample contains 371 records (08:25:04–09:01:26 Sydney): 356 helper-success, 8 failed and 7 pending. Seven failures progressed through fallback, pending, then success after 9–10 seconds; eight early succeeded rows lacked trust. The last row reports Automated/MSC with trusted PV export and battery charging. These are reported telemetry/application records, not proof of all physical limits or settlement.
- .65 / 2.3.54-haos65, source 9965e79133f38d5b9943dcf5a9b04ed6fdab1239, and its public amd64/arm64 image remain available. A separate Supervisor backup report recorded 49 errors across 7 files and a missing backup.json; this does not mean all backups are invalid. The actual .65 restore/reinstall selection remains unproven.
- Physical inverter export maximum reportedly 15 kW. Physical grid-export enforcement and ESS limits are separate controls. Reported 15 October Morning Dump floor 15%, timing option 1.0 hour (sunrise through one hour after), Morning Slow near 2 kW, export near 15 kW, Evening Boost disabled and PV forecast about 130 kWh are historical operator context, not renewed verification.
- O1–O9 remain open for residual live acceptance, physical evidence or operator-policy gates. O1, O3 and O6 have narrow code corrections in .71/.72; this does not close their surrounding live and adjacent-behavior questions. O10 is the stale archive/tail symptom; O11 is the parked intermittent MSC observation. The operator parked archive and MSC follow-up and paused the reminder; a suspected HA/hardware cause is unproven.
- Phase 1 and applicable Phase 2 live-proof requirements remain incomplete. Retain the 13-second historical observation gap, unexercised scenarios, Evening Boost stability and physical acceptance as recorded in CURRENT_STATE.md and ROADMAP.md.
- Protected dirty reference C:\Projects\sigenergy_optimizer-evening-priority (ten existing modifications) and Stage A worktree remain untouched. Never reset, stash, discard, overwrite, commit, delete or wholesale-copy its optimizer.

## Historical continuation sequence (superseded by current trace work)

The operator authorised one normal `.71` release-preparation commit and push on `fix/control-authority-safety`. The earlier 25-file development checkpoint is completed at `ae4a974692aa`; its pre-commit approval and dirty-state descriptions are superseded. At that pre-publication checkpoint PR #20 remained open and unmerged; it was subsequently merged. The publication step below is historical and completed; installation/live acceptance remain unverified.

1. Historical publication step completed: PR #20 was merged and tag/release `v2.3.60-haos71` was published, verified on 17 October. The former publication-approval/tag-absence instructions are superseded.
2. Obtain separate approval for supervised installation and live acceptance with .65 rollback ready.
3. Capture actual inverter state and physical-flow evidence.
4. Close or explicitly retain unresolved operational bugs based on evidence.
5. Proceed to the short control-ownership audit and existing approved roadmap.

Before any separately approved live acceptance, verify actual source/build, effective settings, current authority and .65 rollback readiness; plan supervision and explicit stop/rollback conditions. Capture timestamped requested/observed EMS, PV MAX, import/export ceilings, ESS limits, SoC, battery/PV/grid flows and reason/owner. Service-call success is not settlement.

Preserve the full approved roadmap order: ownership audit -> architecture -> project cleanup -> full GUI/UX -> Climate Manager integration. Climate Manager broadly works and is not the current priority.

Historical release-preparation validation: run the existing release-version consistency tests, compileall with an external cache, complete diff review and exact nine-file scope/marker-only checks. Retain the final full-suite evidence above; do not rerun the full suite for version-only preparation. Git tag/release absence and public GHCR version-manifest absence were reconfirmed before preparation; GitHub package listing lacks `read:packages` permission. That pre-publication recheck instruction is superseded by the 17 October verification of the completed .71 publication; any future candidate requires its own separately authorized publication review.
