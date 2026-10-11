# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-11

Read root/project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md` and the relevant decision/roadmap sections. Verify identity and status before editing; preserve dirty work.

- Active worktree: `C:/Projects/sigenergy_optimizer-four-tier`; branch `feature/four-tier-battery-export`; HEAD `0aa616c55a87f204d30193d8006f2e57ba265941`. Other worktrees remain protected.
- Dirty pre-commit checkpoint: fifteen tracked implementation/test/metadata files, six checkpoint docs (21 modified tracked files) and untracked `tests/test_four_tier_battery_export.py`; 22 proposed commit files. Nothing in the four-tier delta is committed, pushed, released or live-accepted.
- Last **reported** live: `2.3.57-haos68`, source baseline `0aa616c55a87f204d30193d8006f2e57ba265941`; no new live query. Known-good rollback: `2.3.54-haos65`, `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`.
- Final validation: **941 tests passed / 1045 subtests passed / zero failures / 206 warnings**. Compileall (`app`, `tests`, cache outside worktree) and diff check passed. Warnings: 201 deprecated Pydantic Field extras, four `.dict()` calls, one class-based Config; local timezone-data fallback to UTC is a separate environment limitation. The tariff characterization now proves Low MSC-only permission and separately qualified Medium export, including strict Medium-floor closure; invalid-telemetry tests are unchanged.
- Independent **ChatGPT GitHub safety audit remains pending**. Prior `.68` acceptance/reviews do not cover four-tier changes.

Ordinary deliberate battery export starts at Medium. Low is price classification/PV-only context and cannot own battery export, including at 100% SoC or with legacy opt-ins and persisted floors below 100%. The compatible Low key defaults to 100% but never enables Low sale. Medium/High/Spike floors remain 40/20/10%, independently validated as finite numeric 0-100 values (no booleans), with no selected-tier fallback. Preserve ramp arithmetic, reserves, trusted evidence, import-cost veto and physical limits. Solar/ordinary MSC remain PV-only; independently qualified Morning Dump/Evening Boost and Manual/Force retain separate authority. Only fully permitted positive bounded High/Spike proposals may preempt eligible Morning owners.

`battery_export_owner` is proposal provenance; `battery_export_final_owner` is the final decision owner, `none` under a blocking veto. Proposals and Value Gate advisory results never authorize actuation. Preserve the complete `.68` observed close -> observed closure -> MSC request -> later observed exact MSC -> permitted reopening sequence, all independent restrictive controls, MSC/Solar/Morning/Demand Window and Manual/Force.

`.68` scoped Phase 2 live acceptance is reported passed; its **13-second observation gap remains unproven**, and broader/unexercised acceptance remains open. Phase 1 remains open for deferred Evening Boost stability and Solar threshold-switching disposition. Four-tier live acceptance is outstanding. Site 15 kW physical-boundary and 120-minute Solar-margin tuning are not software defaults (0.0 and 60).

Next: obtain explicit permission to commit/push the validated checkpoint, then independent ChatGPT GitHub audit, explicit GO/NO-GO, and separately authorized HA installation. Candidate `2.3.58-haos69` / proposed tag `v2.3.58-haos69` is prepared on all five metadata surfaces after fresh upstream conflict checks; no tag/build/release was created. Follow `CURRENT_STATE.md` for observation/stop/rollback gates and `ROADMAP.md` for parked work; no live changes are authorized by this checkpoint.
