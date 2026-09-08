# Roadmap

This roadmap is ordered by dependency. Later work must not bypass the stated validation and live-proof gates.

## Phase 1 audit remediation and renewed acceptance

Status: **active**. Phase 1 was reopened after a proven live Morning Slow defect and broader control-authority audit. Complete in this order:

1. Characterization tests. Complete.
2. Authority and fail-closed remediation. Complete, automated-validated, committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0`, and pushed to `origin/fix/phase1-audit-remediation`; not yet live-tested.
3. Morning control repair, including separation of Morning Slow policy from grid-transfer deadband. Complete and automated-validated; committed at `d3294cb` and present on the remote remediation branch, not deployed or live-tested.
4. Battery-export safety. Complete and automated-validated; committed at `91b0075` and present on the remote remediation branch, not deployed or live-tested.
5. Telemetry trust.
   - 4A Tariff trust — **complete, automated-validated, and pushed** at `d3e1d56`; not deployed or live-tested.
   - 4B SoC/battery-energy trust — **complete, automated-validated, and pushed** at `19a6279`; not deployed or live-tested.
   - 4C Live PV/load trust — **complete, automated-validated, and pushed** at `85cfb1d`; not deployed or live-tested. Static PV/load trust defects are repaired without weakening fail-closed battery-export protection; genuine fresh zero PV/load remains trusted.
   - 4D Forecast/solar-clock trust — **complete, automated-validated, and pushed** at `44c63e8`; not deployed or live-tested. Existing forecast/sun freshness bases are retained; no new horizon, intended-day, issue-age, or sun-tolerance policy was created.
6. Package 5 actuator/fallback and chatter work.
   - Actuator/fallback reliability — **complete, automated-validated, and pushed to the remediation branch** at `4c9c0e2`, with documentation checkpoint `68bfa92`; not deployed, installed, restarted, live-tested, or live-accepted. Application outcomes, fallback results/exceptions, partial failures, remembered applied state, cycle diagnostics, and immediate ordinary-close readback are now handled without treating request success as observed inverter state.
   - Chatter/reopen characterization — **NEXT**. Investigate the fresh direct-battery boundary where about `0.094 kW` can permit the high ceiling and about `0.101 kW` can close it, producing possible `25 -> 0 -> 25 -> 0 kW` oscillation. Characterize safe MSC ceiling semantics with load-serving battery flow, meaningful simultaneous battery discharge plus grid-export fail-close, and reopen/statefulness behavior.
   - Treat the MSC high export ceiling as permission for genuine surplus as an investigation hypothesis grounded in the existing contract, not an approved new implementation rule. Preserve the correctly closed material load-serving case near 1.6 kW PV, 4.7 kW load, and 3.2 kW battery discharge, and the fail-closed simultaneous-flow case near 0.273 kW battery discharge and 1.837 kW grid export.
   - Do not select an arbitrary larger threshold, deadband, timer, N-cycle hysteresis, settlement duration, or reopen delay before characterization. Preserve fail-closed protection and do not implicitly authorize battery export from ordinary positive FiT.
   - Parked bounded investigation: verify the Morning Slow forecast-feasibility calculation against exact live provenance without treating the discrepancy as a confirmed defect or changing actual operator tuning/software defaults. Capture trusted forecast remaining, capacity, available energy, refill need, slow-charge end, hours left, base load, load need, safety multiplier, final `required_kwh`, and eligibility. This investigation must not contaminate the committed actuator/fallback checkpoint or move capability work ahead of unfinished Package 5 chatter work.
7. Capability model with separate domains and no configured enlargement of observed caps.
8. `/set_ess` hardening.
9. Configuration validation and persistence.
10. Settings and UI cleanup.
11. Outstanding policy decisions, including Morning Dump grace and Battery Full Safeguard behavior.
12. Documentation checkpoint.
13. Full validation and renewed Phase 1 live acceptance.
14. Phase 2 transition implementation.
15. Phase 2 live acceptance.
16. Final control-ownership audit.
17. Climate Manager integration.

Gate after package 13: all audit remediation must be complete, validated, and live-accepted before package 14 begins. Packages 14-17 remain frozen or queued as described below.

## Phase 2 transition-settlement safety

Status: **paused/frozen before production implementation**.

Implement the observed close -> later observe closed -> request MSC -> later observe exact MSC -> reopen sequence in `CONTROL_CONTRACT.md`. Entering deliberate battery export must settle its export target before discharge EMS. Service-call success never counts as observation.

Protect the two existing expected Phase 2 failures. Then run targeted transition tests, complete regression testing, a test release, and controlled live proof.

Gate: Phase 2 must be stable and live-accepted before downstream integration.

## Short final control-ownership audit

After Phase 2, confirm that every owner changes only its own actuator domains and that manual, force, freshness, price, reserve, and import-cost protections compose correctly. Resolve material findings before Climate Manager integration.

## Climate Manager integration

Integrate the stable `sensor.sigenergy_hvac_solar_permission` interface (`start`, `continue`, `blocked`, `unavailable`). SigEnergy Optimizer owns energy opportunity and safety; Climate Manager owns HVAC profiles, zones, targets, comfort/manual behavior, AC0, and AirTouch commands.

## Later work

Only after the preceding gates:

- operator diagnostics and ownership visibility improvements;
- deterministic replay tooling;
- evidence-driven load and forecast modelling;
- experimental dynamic solar scheduling on a separate branch, proved through replay, shadow comparison, and a bounded live trial before any merge.

These later items must not delay the Phase 1 remediation gate or bypass Phase 2 and the final ownership audit.
