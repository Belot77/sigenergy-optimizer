# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-19

Read `C:\Projects\AGENTS.md`, worktree `AGENTS.md`, this handover, `CURRENT_STATE.md` and relevant `CONTROL_CONTRACT.md` sections. Inspect only minimum relevant files. Git records repository identity; HA and operator evidence establish live state.

## Current release and local source-pinning follow-up - 19 October 2026

**Published release: `.72 / 2.3.61-haos72`.** Tag `v2.3.61-haos72` points to `3afefcd113d2c6f3eadd5aadd52fbda1a8b35f28`; release ID `416723430` is published as latest. The tag-triggered build run `39167632752` succeeded on attempt 1 and published amd64/arm64 images with verified source/version labels; OCI index `sha256:0c4d2340f1ca0b6ba80a7c7655fbd0e2aabc135a70b6b60fbeddd881c2738312`. `.71` remains unchanged. The full publication receipt is `docs/PUBLICATION_RECEIPT_2.3.61-haos72_2026-10-19.json` in the release-preparation worktree. These facts establish publication, not installation or live acceptance.

- Current HA installed version/source remains unknown. The last direct operator report was `.70`; a supplied external report says `.71`. The operator confirmed auto-update is off but did not provide exact About/startup/source-build values or a rollback method. Treat this as reassurance only, not installed-identity proof.
- Protected `.65` reference: tag/source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`; public OCI index `sha256:dd7efe0fd9b192ae1fd996137c312e5f2aab12e01a285f6e75fb5a58dc8fe88c`, with amd64/arm64 configs labeled for `.65`. There is no GitHub Release for `.65`. The published add-on config does not select a prebuilt image, and its Dockerfile defaulted to cloning `main`; public image/source metadata alone does not prove HA backup restore or reinstall will select `.65`.
- Current local follow-up: worktree `C:\Projects\sigenergy_optimizer-source-pinning`, branch `fix/addon-source-pinning`, starting at published `.72` commit `3afefcd113d2c6f3eadd5aadd52fbda1a8b35f28`. The Dockerfile requires either a full `SOURCE_REF` SHA (compared exactly with `HEAD`) or `BUILD_VERSION` selecting `refs/tags/v<version>`; both paths fetch the selected ref, check out detached and record the full resolved SHA. It no longer falls back to moving `main`. The tagged GitHub release workflow already passes its exact commit SHA. `.72` artifacts and version markers are unchanged.
- Focused validation passed 14 source-pinning tests in 10.59 seconds, two release/version checks in 0.10 seconds, and the isolated full-SHA reader compatibility check. Independent final review reported GO for local implementation readiness. The full control suite and container/HA tests were not run. No HA installation, restart, service call or inverter/control setting change occurred or is authorized.
- Release-helper constraint: `release.sh` preserves an existing `haos` suffix and updates only three of the five established version markers. Do not use it for a future release without a separate fix and review. Create and verify a matching source tag before advertising a version or relying on a version-tag build; publication is a separate authorization gate.
- The four `.72` corrections and their boundaries remain as described below. O1-O9 remain open; the operator's short physical Demand Window import-spike deferral remains distinct from O7 exact-full PV-only proof.

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

The supplied external review says later discussion identified .71 as installed. No HA About/startup/source-build evidence was supplied or accessed here, so current installation remains unverified; .70 is retained only as the last directly recorded operator report, not a claim that it is still installed.

- Latest operator-reported live `2.3.59-haos70`, source `08f4daf53941bd850a4fe392b458c42b1df68b47`; not freshly HA-verified. Protected known-good rollback `2.3.54-haos65`, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not alter either.
- Physical inverter grid-export maximum reportedly 15 kW. Physical grid-export enforcement and ESS limits are separate controls. Reported 15 October Morning Dump floor 15%, timing option 1.0 hour (implementation sunrise through one hour after), Morning Slow near 2 kW, export near 15 kW, Evening Boost disabled and PV forecast about 130 kWh are historical operator context, not renewed verification.
- Continue all nine open entries in `CURRENT_STATE.md` O1-O9: Medium/Boost live acceptance; unexplained export interruptions/cycling; Solar Override activation/ownership/ceiling discrepancies; Boost oscillation/SoC; overnight reserve and tomorrow-PV policy; Morning Dump/Slow interactions/depletion; exact-full Demand Window PV-only proof; 13-second observation gap; short ownership/configuration audit. No proven cause for unexplained observations, no approval for proposed 30-cent tuning, and no closure from automated tests.
- Phase 1 remains open; scoped `.68` Phase 2 evidence, the 13-second gap, unexercised scenarios and four-tier/hotfix physical acceptance remain limited as recorded in `CURRENT_STATE.md` and `ROADMAP.md`.
- Protected dirty reference `C:\Projects\sigenergy_optimizer-evening-priority` (ten existing modifications) and Stage A worktree remain untouched. Never reset, stash, discard, overwrite or wholesale-copy the protected optimizer.

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
