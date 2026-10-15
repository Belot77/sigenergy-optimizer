# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-15

Read `C:\Projects\AGENTS.md`, worktree `AGENTS.md`, `docs/CURRENT_STATE.md`, `docs/AI_HANDOVER.md`, and `docs/CONTROL_CONTRACT.md` when controls are in scope. Inspect only minimum relevant files. GitHub is committed source truth, PowerShell is local dirty-state truth, HA is live truth, and actual operator settings govern tuning.

## Current checkpoint
- Stage A independent review **GO** (15 October 2026). Isolated local worktree `C:\Projects\sigenergy_optimizer-authority-stage-a`; branch `test/control-authority-safety-characterization`; pre-checkpoint base `08f4daf53941bd850a4fe392b458c42b1df68b47`. Read `git rev-parse HEAD` after checkpoint for actual commit SHA; no push/merge/deploy is authorised.
- Reviewed files: `tests/test_phase1_d7_liveness_characterization.py` and `tests/test_control_authority_safety_characterization.py`. Stage A evidence: 25 pass, 47 **intentionally failing** baseline safety regressions, D7 correction pass, independent protections 77 tests/89 subtests pass, zero unexpected failures. Fixture E timing probe and all seven independent-review corrections accepted. No additional tests-only redesign required.
- Stage A isolated branch is intentionally red until Stage B corrects production; do not skip, xfail, delete or weaken regressions for green results. Documentation files for the checkpoint: `docs/CURRENT_STATE.md` and `docs/AI_HANDOVER.md` only. Nothing staged/pushed elsewhere by this checkpoint.
- Protected dirty reference: `C:\Projects\sigenergy_optimizer-evening-priority`, branch `test/evening-medium-priority-characterization`, base `08f4daf...`, ten independently verified uncommitted changes. **NO-GO** for production/commit/deploy. Never reset, stash, overwrite, discard, delete or wholesale-copy it. Narrow Medium-over-Evening Boost correction is reviewed sound and should be integrated carefully in Stage B.

## Live identity and protections
- Last **operator-reported** live: `2.3.59-haos70`, source `08f4daf53941bd850a4fe392b458c42b1df68b47`. Not newly verified in HA. Protected known-good rollback `2.3.54-haos65`, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`.
- Reported 15 October: Morning Dump physically activated; deliberate 15% SoC floor, timing option 1.0 hour before sunrise (actual implementation sunrise through one hour after); Morning Slow ~2 kW, export ~15 kW, Evening Boost disabled, forecast ~130 kWh. Do not infer remaining settings from defaults.
- Phase 1 exact-full Demand Window PV-only physical acceptance and other Phase 1 items open. Phase 2 only scoped `.68` evidence; 13-second trace gap and unexercised cases unresolved. Four-tier and `.70` physical acceptance not closed. Keep .65 rollback ready.

## Next engineering phase (unapproved)
- Stage B is the **coherent authority and actuator safety production correction** for established 47 regressions. Expected core code `app/optimizer.py` and `app/ha_client.py` plus required targeted tests; no extra API/production scope without separate approval. Confirm writable worktree/branch/HEAD/cleanliness first.
- Preserve Automated/Unknown/confirmed Manual-Force authority, independent Demand/ESS/PV restrictions, dispatch-time checks, post-request observed settlement, fallback, cancellation and bounded retries. Preserve ordinary unattended EMS restart/auto-enable after *current* Automated verification and observed Remote EMS ON; no persistent OFF registry or mandatory restart handback redesign. Respect authenticated Manual/Force and `/set_ess` behaviour.
- Keep the reviewed Medium-over-Evening Boost priority correction surgical, and never wholesale-copy the protected optimizer. Stage B requires targeted red-to-green tests, independent protection suites, one final full suite, compileall/diff check, independent review and later separate supervised physical acceptance.
- No production changes, push, merge, tag, release, add-on update/restart, HA/inverter write or deployment is authorised by Stage A commit. The next action is **separate Stage B scope and write approval**.

Maintain `docs/CURRENT_STATE.md` as current truth, this handover at checkpoints, control contract only when approved semantics change, roadmap when sequencing changes and changelogs for behaviour changes. Do not leave stale current/live identities in these two documents.
