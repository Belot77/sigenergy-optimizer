# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-15

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `ROADMAP.md`, and `DECISIONS.md`. Verify the exact branch tip, worktree status, and remote synchronization directly with Git before editing.

## Live baseline and rollback

Live is `2.3.45-haos56`. It proved the Morning Dump telemetry/forecast repair, Morning Slow activation with actual charging around `2 kW`, static battery-capacity trust, and detailed Solcast trust/coverage.

Renewed Phase 1 acceptance remains withheld because `.56` exhibited genuine exact-full Cheap-FiT desired export-ceiling chatter `25 -> 0 -> 25 -> 0 kW`. The rollback ladder remains the immediate fresh `.55` backup, then deeper `.54`/`.53` fallbacks; `.54` has known exact-full and Solar Surplus defects and is not preferred. No rollback is underway.

GitHub `main` is `1566beb3252119aabc060b39420581ca3a550631`, the `2.3.45-haos56` candidate checkpoint.

## Active checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Functional repair: `9e5517ea85dea286608d564cbe2cdeaa18a2e03e` (`Stabilize exact-full cheap-FiT MSC ceiling`), pushed and synchronized before candidate preparation.
- Candidate: `2.3.46-haos57`, being prepared as uncommitted version/release metadata and documentation only.
- No `.57` tag, build, publication, installation, restart, or live acceptance has occurred.

Protected worktrees remain unchanged. Never modify, reset, or stash `C:\Projects\sigenergy_optimizer` or `C:\Projects\sigenergy_optimizer-pv-hotfix`. The Phase 2 worktree remains frozen.

## Exact-full Cheap-FiT repair

The `.56` chatter was independent of the earlier `ordinary_msc_flow_ok` repair. Under exact 100% SoC, Cheap-FiT, observed Automated plus exact Maximum Self Consumption, trusted safe flow, no battery-export owner, and zero actual PV surplus, `live_pv_plausible_for_msc_ceiling` toggled as sub-1 kW PV moved above and below the former `load - 0.1 kW` adequacy boundary.

Commit `9e5517e` preserves trusted finite PV/load telemetry and strict positive live PV above `0.05 kW`, but removes the unstable requirement that PV meet the productive-solar threshold or remain within `0.1 kW` of load. Observed ownership, exact-full target, `ordinary_msc_flow_ok`, simultaneous discharge/export closure, unknown-flow closure, forecast/standby/demand protections, Manual/Force, Morning Dump, Morning Slow, Solar Surplus, normal PV MAX, and Phase 2 semantics are unchanged. The high value remains an MSC ceiling and creates no deliberate battery-export owner. Diagnostics expose `live_pv_plausible_for_msc_ceiling` and `pv_surplus_common_conditions`.

Automated validation passed: exact-full characterization **6 passed**; MSC baseline/overlay plus chatter protection **52 passed, 2 frozen Phase 2 tests deselected**; final suite **482 collected, 480 passed**, with only the two expected frozen Phase 2 failures. Compileall and `git diff --check` passed with no unexpected findings.

## Remaining live acceptance

After `.57` is separately published and installed, obtain natural live proof of both:

1. Exact-full 100% SoC Cheap-FiT remains at the high MSC ceiling through PV/load deficit changes that previously caused `25/0` chatter.
2. Solar Surplus enters above `0.5 kW`, continues above `0.2 kW` once genuinely active, stops at or below `0.2 kW`, re-enters only above `0.5 kW`, and does not chatter the ceiling.

Do not state that Phase 1 is complete. Packages 7 through 9 remain future work after current live acceptance. Phase 2 remains frozen, including its two expected transition-settlement failures.

## Next action

Review the uncommitted `2.3.46-haos57` candidate checkpoint and decide whether to commit it. Push, tag-triggered build/publication, installation/restart, and live observation each require separate approval. After publication and installation, the exact next operational action is read-only natural monitoring of the two acceptance items above; do not manufacture state changes.
