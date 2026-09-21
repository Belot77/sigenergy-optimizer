# Current State

Last consolidated: 2026-09-21

**CURRENT TRUTH ONLY:** this file records the current operational and development checkpoint. Durable control semantics live in `CONTROL_CONTRACT.md`; sequencing lives in `ROADMAP.md`.

## Live release and rollback

- Current live release: `2.3.46-haos57`, from commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- Phase 1 candidate: `2.3.47-haos58`, commit `a945dfd6703bdfd2741752a405cf9682359ebf5e`. It is committed and pushed, but not tagged, built, published, installed, restarted, or live-tested.
- No rollback from `.57` has occurred.
- Known-good deeper rollback: `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`.

The exact-full Cheap-FiT repair in `.57` was live-proven earlier. The later Phase 1 remediation and Solar Surplus redesign described below are candidate-branch-only until `.58` is installed and accepted live.

## Active Phase 1 checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Candidate commit: `a945dfd6703bdfd2741752a405cf9682359ebf5e`.
- At this checkpoint the worktree was clean and the branch was pushed and synchronized `0/0` with `origin/fix/phase1-audit-remediation`.
- The repository implementation gate was validated at `1e0c61d129fecf0c073ab87eaf5340d60cd81541`; no production or test behavior changed afterward, only mechanical release identity and documentation.

Phase 1 repository implementation is checkpointed and its repository gate has passed. Material completed work includes Packages 1-5 and 6A, `/set_ess` hardening, configuration validation and persistence hardening, settings/UI cleanup, Evening Boost safety repair, D1-D7 telemetry/freshness/trust hardening, the export-notification correction, restrictive-close F1/R9 hardening, and the Solar Surplus redesign with operator-facing diagnostics. Package 6B investigation/design is complete; implementation remains deferred.

## Repository validation gate

Command: `python -B -m pytest -p no:cacheprovider`

- 646 collected.
- 644 passed.
- 2 failed: only the intentionally frozen Phase 2 transition-settlement tests listed below.
- 193 existing Pydantic v2 deprecation warnings.
- `python -m compileall -q app`: passed.
- `git diff --check`: passed.

This is a **PASS for the Phase 1 repository implementation checkpoint**. It is not live proof. `2.3.47-haos58` live acceptance remains pending.

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

Prepare candidate tagging, build, and publication for `2.3.47-haos58`, subject to separate approval. Installation, restart, and controlled Phase 1 live acceptance remain later separate protected boundaries. Do not begin Phase 2 until live acceptance passes.
