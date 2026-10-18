# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-18

Read `C:\Projects\AGENTS.md`, worktree `AGENTS.md`, this handover, `CURRENT_STATE.md` and relevant `CONTROL_CONTRACT.md` sections. Inspect only minimum relevant files. Git records repository identity; HA and operator evidence establish live state.

## Current 2.3.61-haos72 local release candidate (18 October 2026)

**PR #21 merged; local .72 release preparation is complete.** The merge commit is `5275e9cd3803ba991351c790be6b7187c3941981`, with parents published baseline `9f3f02a5c1c82786c85026a3848574cca3cf891f` and approved PR head `38f59fb9ad9b88652996be27a72dabbd1f8cc424`; merge tree `74cfe88df238653e262ff258d3e059abc67b05ff`. The latest published release remains `.71 / 2.3.60-haos71`; its tag remains at the baseline. Candidate `.72 / 2.3.61-haos72` is on `release/2.3.61-haos72`, local-only and uncommitted, based on the merge commit. The two release consistency tests passed and `compileall app tests` passed with an isolated temporary cache. Final checks passed: exactly 12 modified files (five release-marker files and seven documents), marker-only source deltas, unchanged protected code/tests/contract, and `git diff --check`. Preflight found candidate tag `v2.3.61-haos72` absent. GHCR namespace conflict was not verified and remains a separate publication-gate check. No tag, build, publication, installation or live action is claimed.

- Current workspace: `C:\Projects\sigenergy_optimizer-release-haos72`; branch `release/2.3.61-haos72`, HEAD/base `5275e9cd3803ba991351c790be6b7187c3941981`; origin `https://github.com/Belot77/sigenergy-optimizer`. Existing review/component worktrees and untracked review artifacts remain preserved. No release-preparation commit, staging or push has occurred.
- Release checks used Python 3.12.10 at `C:\Projects\sigenergy_optimizer-dev\.venv\Scripts\python.exe`: `pytest -q -p no:cacheprovider --disable-warnings --tb=short tests/test_release_version_consistency.py` passed 2 tests in 0.06 seconds, with bytecode and plugin autoload disabled. Syntax compilation used an isolated temporary cache. The known default-sandbox Z: enumeration issue did not block approved local execution; no drive mappings or security settings changed.
- The unchanged `release.sh` helper preserves the old suffix and updates only three markers; this candidate updates all five directly. Do not use that helper for this candidate without separate review. Runtime control code is unchanged after the merge; only the runtime/API version labels and add-on metadata differ. Commit/push, tagging/build/publication, installation and live actions remain separate authorization gates.
- The merged code contains four reviewed changes: Solar Override requires trusted SoC strictly above the selected and protected floors for deliberate battery export while preserving separately qualified PV-only MSC; Morning Dump requires qualified `BATTERY_EXPORT` and bounded target above 0.01 kW for discharge EMS, with explicit MSC fallback when active Dump blocks export; application outcome/pending/exception/fallback trace metadata is recorded with diagnostic failure isolation; and positive sub-1¢ FIT reason text is more precise without changing tariff gates. No control thresholds or policy settings changed.
- The code-bearing checkpoint remains `4e4b17c2d3bb362716d6b4e5ddb60659faf7beec`; PR #21 is merged with reviewed head `38f59fb9ad9b88652996be27a72dabbd1f8cc424`. No submitted reviews or GitHub CI pass are claimed. Retained combined offline validation is **1,073 tests / 1,134 subtests, zero failures, 206 warnings, 170.97 seconds**; it predates this metadata/documentation preparation and was not rerun. These results do not prove installation or physical settlement.
- The operator's short physical-import-spike deferral remains separate from O7 exact-full PV-only proof. O1-O9 and their evidence/policy/live gates remain open. No raw trace is copied.
- Current HA installation remains unverified: the last direct operator report is `.70`, while a supplied external review says `.71`; no HA About/startup/source-build evidence was supplied. `.65` remains the protected known-good rollback. Historical settings and flows remain unverified.

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
