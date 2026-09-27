# SigEnergy Optimizer AI Handover

Last consolidated: 2026-09-27

Read root and project `AGENTS.md`, then `CURRENT_STATE.md`, `CONTROL_CONTRACT.md`, `DECISIONS.md`, and `ROADMAP.md`. Verify the exact worktree, branch, HEAD, and status before editing.

## Live baseline and rollback

- Current live release: `2.3.49-haos60`, commit `a625ca16e59a3a0ff89fd724510355ef53b79315`.
- Documented known-good rollback: `2.3.46-haos57`, commit `7144fd3d52069e3e8ef1e4df9bc8943bdd65dbe7`.
- The near-full MSC/PV-only correction is committed as `47c591be6bf920a82995b9f402c3efb202ffa5fe` and published as `2.3.50-haos61` from source commit `76db9e43588f0e9862d73e4e8402c0b5ce9773a7`. Tag `v2.3.50-haos61` exists at that source commit, GitHub Actions run `36282075721` succeeded, and the release commit is promoted to `main`.
- Published image: `ghcr.io/belot77/sigenergy-optimizer:2.3.50-haos61`, OCI index digest `sha256:db35c1a062932aede5024dea587ce8b31d121679070453505c29fc14ac3b801e`; amd64 and arm64 images were verified with the expected release version and source revision.
- `.61` is not installed, restarted, or live-accepted. Publication and `main` promotion do not prove live inverter behavior.

## Active checkpoint

- Worktree: `C:\Projects\sigenergy_optimizer-phase1-remediation`
- Branch: `fix/phase1-audit-remediation`
- Live `.60` source commit: `a625ca16e59a3a0ff89fd724510355ef53b79315`.
- Repair commit: `47c591be6bf920a82995b9f402c3efb202ffa5fe`.
- Published release identity: `2.3.50-haos61`; immutable tag `v2.3.50-haos61` at `76db9e43588f0e9862d73e4e8402c0b5ce9773a7`.
- Candidate paths committed by the repair: `app/optimizer.py`, `tests/test_export_value_gate_advisory.py`, and `tests/test_phase1_near_full_pv_only_safeguard_characterization.py`.
- Reconciled checkpoint documentation: `CURRENT_STATE.md`, `AI_HANDOVER.md`, `ROADMAP.md`, `DECISIONS.md`, `CONTROL_CONTRACT.md`, and `CHANGELOG.md`. Preserve the pre-existing edits in `AI_HANDOVER.md`, `ROADMAP.md`, and `DECISIONS.md`.
- The code/test candidate and documentation checkpoint are committed. The release-preparation commit synchronized the five version markers and release documentation without changing optimizer behavior. Source commit `76db9e43588f0e9862d73e4e8402c0b5ce9773a7` is tagged, built, published, and promoted to `main`; installation, restart, and controlled live acceptance remain pending.

## Near-full causal defect and repair

When available-discharge-energy telemetry became untrusted, legacy normalization substituted zero and produced a synthetic full-capacity refill requirement (`40.3 kWh`). Solar independently used trusted rated capacity and SoC headroom (`2.418 kWh` at 94% and `1.1284 kWh` at 97.2%), passed its safety gates, but lost final arbitration to the raw Battery Full Safeguard.

The candidate preserves that raw safeguard and its diagnostics. A second arbitration is permitted only when the raw closure was specifically caused by the untrusted-energy synthetic fill, the same safeguard does not block trusted SoC headroom, Solar independently qualifies, Automated and exact MSC are observed, trusted battery/grid flow is PV-only-safe, and all competing deliberate-export and independent safety owners are absent. The accepted source must be exactly `solar_surplus_pv_high`. The outcome remains `MSC_SURPLUS_CEILING` in Maximum Self Consumption with battery-export owner `none`; it cannot request stored-battery discharge.

## Validation

`python -B -m pytest -p no:cacheprovider` collected 663 tests: 661 passed and only these two intentionally frozen Phase 2 tests failed:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

Focused results: near-full `11 passed, 15 subtests passed`; Solar/full-battery `74 passed, 85 subtests passed`; advisory `96 passed, 65 subtests passed`; independent safety/ownership `238 passed, 230 subtests passed`, plus only the two frozen failures. There were 193 existing Pydantic v2 deprecation warnings. `python -m compileall -q app` and `git diff --check` passed. This proves the local repository candidate, not live behavior.

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

## Approved sequencing and parked work

- The repaired Phase 1 release is tagged, published, and promoted to `main`, but must be separately installed and live-accepted before Phase 2. The two Phase 2 transition-settlement failures remain frozen until then.
- The short control-ownership audit follows Phase 2. The preserved order after that is architecture refactor -> project cleanup -> full GUI/UX redesign and functional corrections -> Climate Manager integration -> integration-specific UI polish. The full GUI/UX redesign is not the earlier Package 9 settings/UI cleanup.
- Any proposal to move Climate Manager before the architecture and full GUI/UX phases, or to split Climate-specific UI work into an earlier phase, requires an explicit operator sequencing decision; this checkpoint does not change the approved order.
- Earlier roadmap edits preserved hard-fallback house-supply repair, Morning Dump / Morning Slow refill-feasibility protection, and Morning Slow 15 kW physical-export relief. Their completion status is not established by this checkpoint and must be reconciled before Phase 1 is declared complete.
- Evening Boost redesign remains a separate, not-implemented production initiative. Its agreed future policy is recorded in `CONTROL_CONTRACT.md` and `DECISIONS.md`; actual import-cost, higher-value-FiT, and physical-capability interactions still require engineering review.
- The 27 September morning trace showed aggregate Solar budget threshold switching. Treat it as a separate observed Phase 1 follow-up, not as behavior fixed by the near-full correction.
- Package 6B, additional diagnostics, deterministic replay, load/forecast modelling, and experimental dynamic solar scheduling remain later work.

## Exact next action

Use a separately controlled Home Assistant repository refresh, installation/restart, and live-acceptance session for published release `2.3.50-haos61`. Do not begin Phase 2, Evening Boost implementation, or the unresolved morning Solar-budget switching investigation before the repaired Phase 1 live gate passes.
