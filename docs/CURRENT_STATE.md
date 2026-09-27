# Current State

Last consolidated: 2026-09-27

**CURRENT TRUTH ONLY:** this file records the current operational and development checkpoint. Durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Live release and rollback

- Current live release: `2.3.49-haos60`, from commit `a625ca16e59a3a0ff89fd724510355ef53b79315`.
- Documented known-good rollback: `2.3.46-haos57`, commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- Phase 1 near-full release: production, characterization, and advisory-fixture corrections are included in `2.3.50-haos61`, tagged at source commit `76db9e43588f0e9862d73e4e8402c0b5ce9773a7`, built and published by successful GitHub Actions run `36282075721`, and promoted to `main`.
- Published image: `ghcr.io/belot77/sigenergy-optimizer:2.3.50-haos61`, OCI index digest `sha256:db35c1a062932aede5024dea587ce8b31d121679070453505c29fc14ac3b801e`, with verified amd64 and arm64 images carrying the expected release version and source revision.
- `.61` has not been installed, restarted, or live-accepted. Publication and `main` promotion prove release identity only, not live inverter behavior.

The current live `.60` checkpoint does not contain the committed near-full repair described below. Repository validation proves the repository release source only; controlled installation, restart, and live acceptance remain pending in a separate session.

## Active Phase 1 checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Live `.60` source commit: `a625ca16e59a3a0ff89fd724510355ef53b79315`.
- Repair commit: `47c591be6bf920a82995b9f402c3efb202ffa5fe`.
- Published release identity: `2.3.50-haos61`; immutable release tag `v2.3.50-haos61` at `76db9e43588f0e9862d73e4e8402c0b5ce9773a7`.
- Candidate code/test paths committed by the repair: `app/optimizer.py`, `tests/test_export_value_gate_advisory.py`, and `tests/test_phase1_near_full_pv_only_safeguard_characterization.py`.
- Documentation checkpoint paths: `docs/CURRENT_STATE.md`, `docs/AI_HANDOVER.md`, `docs/ROADMAP.md`, `docs/DECISIONS.md`, `docs/CONTROL_CONTRACT.md`, and `docs/CHANGELOG.md`. The earlier edits in `AI_HANDOVER.md`, `ROADMAP.md`, and `DECISIONS.md` were preserved and reconciled rather than discarded.
- The code/test candidate and its documentation checkpoint are committed. Release preparation changed only the five synchronized version markers, the README version display, and release-status documentation. The resulting source commit `76db9e43588f0e9862d73e4e8402c0b5ce9773a7` is tagged as `v2.3.50-haos61`, published with the image identity above, and promoted to `main`. Installation, restart, and controlled live acceptance remain pending.

The defect was a conflict between two independently computed refill values. When available-discharge-energy telemetry became untrusted, legacy normalization substituted zero and produced a synthetic `40.3 kWh` refill requirement. Solar still had trusted SoC-derived headroom of about `2.418 kWh` at 94% SoC or `1.1284 kWh` at 97.2% SoC and independently passed its aggregate, detailed-timing, measured-surplus, ownership, and flow gates. The raw Battery Full Safeguard then won export arbitration and closed the otherwise safe MSC/PV-only ceiling.

The candidate retains the raw safeguard and its diagnostics. It re-arbitrates only when the initial closure is specifically the raw safeguard, available-energy telemetry is untrusted, the same safeguard passes with trusted SoC headroom, Solar independently qualifies, Automated and exact Maximum Self Consumption are observed, trusted battery/grid flow is PV-only-safe, and competing deliberate-export or safety owners are absent. The accepted candidate source must be exactly `solar_surplus_pv_high`; final intent remains `MSC_SURPLUS_CEILING`, battery-export ownership remains `none`, and downstream actuator protections are unchanged.

## Repository validation gate

Command: `python -B -m pytest -p no:cacheprovider`

- 663 collected.
- 661 passed.
- 2 failed: only the intentionally frozen Phase 2 transition-settlement tests listed below.
- 193 existing Pydantic v2 deprecation warnings.
- `python -m compileall -q app`: passed.
- `git diff --check`: passed.

Focused validation also passed: near-full characterization `11 passed, 15 subtests passed`; Solar/full-battery protection `74 passed, 85 subtests passed`; advisory `96 passed, 65 subtests passed`; independent safety/ownership `238 passed, 230 subtests passed`, plus only the two frozen failures.

This is a **PASS for the Phase 1 near-full behavior committed at `47c591be6bf920a82995b9f402c3efb202ffa5fe` and published as `2.3.50-haos61` from `76db9e43588f0e9862d73e4e8402c0b5ce9773a7`**. It is not live proof and does not change the live `.60` identity.

## Phase 1 trust and safety result

- D1-D7 require trusted provenance, freshness, validity, and coherence for permissive forecast, PV/load, tariff, battery, demand-window, and actuator-position decisions.
- Demand Window uses its evidence-based 360-second freshness boundary and fails closed for import without gaining export or PV-curtailment ownership.
- Dynamic inverter/grid-limit readbacks retain the 120-second trust window. Live evidence showed unchanged grid-limit reports about 58-61 seconds apart, while Demand Window reports were about 295-299 seconds apart.
- Service-call success is not observed settlement. Deliberate export must establish its export target before discharge EMS is selected.
- F1/R9 preserve independent restrictive import-close attempts when export closure is unproven and reject negative grid-limit readbacks as actuator-position proof.
- `/set_ess`, configuration persistence/validation, settings/UI behavior, Evening Boost safety, and export notifications have their Phase 1 repairs.
- Export start/stop notifications use trusted measured grid flow, not a changed ceiling.

## Solar Surplus Phase 1 result

Solar Surplus is an MSC/PV-only export-permission policy. It remains in Maximum Self Consumption, retains normal PV MAX, never owns `BATTERY_EXPORT`, never deliberately requests discharge EMS, never owns an ESS charge cap in Phase 1, and does not own import. A high export ceiling is permission for genuine PV surplus, not an instruction to discharge or proof of physical export.

Eligibility requires FiT at least `1 cent/kWh`, trusted coherent measured PV/load with entry surplus strictly above `0.5 kW` or owned continuation strictly above `0.2 kW`, trusted Remaining Today forecast, trusted battery SoC and rated capacity, a trusted same-day future sunset, and a valid Solar-specific safety factor `K >= 1`. The aggregate Remaining Today forecast must be strictly greater than `K x (remaining load to sunset + battery fill need to 100%)`.

When fill need is greater than zero, trusted detailed Solcast intervals through sunset plus trusted effective charge capability must separately prove sufficient charging opportunity. Detailed timing deducts current load, bounds charging by effective capability, and applies the same safety factor conservatively; aggregate and detailed forecasts are not added together. Missing or unsafe evidence fails Solar closed. When fill need is exactly zero, detailed timing is not required.

The Solar-specific setting is `solar_surplus_forecast_safety_factor`, default `1.20`. Legacy `solar_surplus_start_multiplier` and `solar_surplus_stop_multiplier` remain stored/configurable for compatibility but no longer drive redesigned Solar eligibility.

Morning Slow owns its charging behavior and excludes Solar while active. Morning Dump and other explicit deliberate-export policies win over Solar. Demand Window retains import ownership. Exact-full remains a separate PV-only branch. Manual and Force remain operator-owned and cannot inherit Solar continuation.

Operator-facing diagnostics now distinguish `solar_surplus_policy_active` final ownership from physical export settlement and expose the fail reason, aggregate budget, timing evidence, measured surplus/active threshold, and safety factor.

The near-full candidate adds an auditable distinction between the raw Battery Full Safeguard and its effective Solar export-arbitration result. Untrusted available-energy telemetry never substitutes for Solar qualification, and failed Solar, ownership, MSC, battery-flow, or grid-flow evidence retains the raw fail-closed result.

Separate observed follow-up: the 27 September morning trace showed Solar's aggregate energy budget moving around its threshold with repeated export-ceiling switching. That behavior is not established as fixed by the near-full repair and requires its own evidence-led Phase 1 investigation. No switching correction is included in this candidate.

## Protected behavior and references

- Manual and Force modes remain user-owned.
- Demand Window primarily owns import blocking.
- Ordinary positive-FiT and Solar/Exact-full PV-only ceilings do not manufacture deliberate battery-export ownership.
- Normal PV MAX is not reduced merely because Demand Window is uncertain.
- Morning Slow charging ownership, Morning Dump deliberate-export ownership, Evening Boost protections, and exact-full behavior remain distinct.
- Service-call success never substitutes for trusted observed settlement.

Protected worktrees, recorded as last-known reference states rather than fresh verification from this docs task:

- `C:\Projects\sigenergy_optimizer`: branch `refactor/msc-baseline-overlays`, HEAD `bce8411d5274fe17fb8d883e8e7faf43e9ce8d43`; intentionally dirty and protected.
- `C:\Projects\sigenergy_optimizer-pv-hotfix`: `main`, HEAD `19f3c70d24dc086737d5956a1c66cad230287edd`; rollback reference.
- `C:\Projects\sigenergy_optimizer-phase2-transition`: branch `phase2/msc-transition-settlement`, HEAD `c624f0b4392634cf19276186ba46f4b80268627b`; frozen until Phase 1 live acceptance.

## Frozen Phase 2 contract

The two expected failures remain intentionally frozen:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

They are not Phase 1 failures and must not be described as solved. Phase 2 must not begin until the required Phase 1 candidate live acceptance passes.

## Exact next action

The next approval boundary is the separately controlled Home Assistant repository refresh, installation/restart, and live acceptance of published release `2.3.50-haos61`. Do not infer live inverter behavior from publication or `main` promotion, and do not begin Phase 2 until the repaired Phase 1 release is live-accepted. The separate morning Solar-budget switching observation remains unresolved and requires its own evidence-led Phase 1 investigation.
