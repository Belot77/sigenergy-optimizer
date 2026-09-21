# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-21

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md`, and `ROADMAP.md`. Verify the exact worktree, branch, HEAD, and status before editing.

## Live baseline and rollback

- Current live release: `2.3.46-haos57`, commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- Candidate being prepared locally: `2.3.47-haos58`. It is not yet committed, tagged, built, published, installed, restarted, or live-tested.
- Known-good deeper rollback: `2.3.42-haos53`, tag `v2.3.42-haos53`, commit `19f3c70d24dc086737d5956a1c66cad230287edd`.
- The exact-full repair in `.57` was live-proven earlier; later remediation and Solar changes are branch-only.

## Active checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Pre-preparation committed HEAD: `4687f5e8cb65048870368395889ce217f0156afe`.
- The worktree was clean before local candidate preparation began. Do not assign a final candidate commit SHA until the candidate diff is reviewed and committed.
- The repository implementation gate was validated at `1e0c61d129fecf0c073ab87eaf5340d60cd81541`; later documentation synchronization did not change production or test behavior.

The Phase 1 repository implementation gate passed. Completed work includes D1-D7 telemetry/freshness/trust hardening, F1/R9 restrictive-close hardening, retained 120-second dynamic readback trust based on live cadence evidence, `/set_ess` hardening, configuration validation/persistence, settings/UI cleanup, Evening Boost safety repair, export-notification correction, and the Solar Surplus redesign and diagnostics. Package 6B implementation remains deferred.

## Validation

`python -B -m pytest -p no:cacheprovider` collected 646 tests: 644 passed and only these two intentionally frozen Phase 2 tests failed:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

There were 193 existing Pydantic v2 deprecation warnings. `python -m compileall -q app` and `git diff --check` passed. This proves the repository checkpoint, not live behavior.

## Protected behavior

- Manual and Force remain operator-owned.
- Demand Window primarily owns import blocking and uses a 360-second freshness boundary; uncertain state fails closed for import without gaining export or PV-curtailment ownership.
- Dynamic inverter/grid-limit readbacks retain the 120-second trust boundary and require fresh non-negative provenance.
- Service-call success is not settlement proof. Independent restrictive closes remain independent.
- Ordinary positive-FiT, Exact-full, and Solar PV-only ceilings never manufacture deliberate battery-export authority.
- Morning Slow charging, Morning Dump deliberate export, Evening Boost, Exact-full, and Solar remain distinct policies.

Protected reference worktrees must not be modified: `C:\Projects\sigenergy_optimizer` is intentionally dirty; `C:\Projects\sigenergy_optimizer-pv-hotfix` is the rollback reference; `C:\Projects\sigenergy_optimizer-phase2-transition` remains frozen until Phase 1 live acceptance. Exact last-known references are in `CURRENT_STATE.md`.

## Solar Surplus final Phase 1 contract

Solar Surplus remains Maximum Self Consumption and grants only PV export permission. It retains normal PV MAX, owns neither import nor an ESS charge cap, never owns `BATTERY_EXPORT`, and never deliberately selects discharge EMS. Policy-active status is not proof of physical inverter/grid export.

Entry requires FiT at least `1 cent/kWh`, trusted coherent PV/load observations, measured surplus strictly above `0.5 kW`, trusted Remaining Today forecast, trusted SoC and rated capacity, a trusted same-day future sunset, and a Solar-specific safety factor `K >= 1`. Owned continuation requires measured surplus strictly above `0.2 kW`; after stopping, full entry is required again.

The aggregate forecast must be strictly greater than `K x (current trusted load x hours to sunset + rated capacity x SoC headroom to 100%)`. If fill need remains, trusted detailed Solcast intervals and trusted effective charge capability must separately prove enough opportunity before sunset. Timing deducts load, bounds charge opportunity by capability, and applies the same safety factor; aggregate and detailed forecasts are not summed. Unsafe or missing evidence fails closed.

`solar_surplus_forecast_safety_factor` defaults to `1.20`. Legacy start/stop forecast multipliers remain configurable for compatibility but are not used for redesigned eligibility. Morning Slow excludes Solar; Morning Dump and other deliberate-export owners win; Demand Window retains import ownership; Exact-full remains separate; Manual/Force cannot inherit Solar continuation.

Diagnostics expose final `solar_surplus_policy_active`, fail reason, aggregate budget, timing evidence, measured surplus/threshold, and safety factor while distinguishing policy ownership from physical export settlement.

## Parked and out of scope

- The two Phase 2 transition-settlement failures remain frozen.
- Package 6B implementation remains deferred.
- The short ownership audit follows Phase 2; Climate Manager follows that audit.
- Replay tooling, load modelling, diagnostics beyond the completed Solar surface, and dynamic scheduling remain later work.

## Exact next action

Review the local `2.3.47-haos58` candidate-preparation diff. Candidate commit and push are the next boundary and require approval. Tag, build, and publication require separate approval afterward; installation, restart, and controlled live acceptance are also separate protected boundaries. Do not begin Phase 2 until live acceptance passes.
