# Roadmap

This roadmap is ordered by dependency. Later work must not bypass the stated validation and live-proof gates.

## Phase 1 audit remediation and renewed acceptance

Status: **active**. Phase 1 was reopened after a proven live Morning Slow defect and broader control-authority audit. Complete in this order:

1. Characterization tests. Complete.
2. Authority and fail-closed remediation. Complete, automated-validated, committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0`, and pushed to `origin/fix/phase1-audit-remediation`; not yet live-tested.
3. Morning control repair, including separation of Morning Slow policy from grid-transfer deadband. Complete and automated-validated; committed locally at `d3294cb`, not yet pushed, deployed, or live-tested.
4. Battery-export safety. Complete and automated-validated; committed locally at `91b0075`, not yet pushed, deployed, or live-tested.
5. Telemetry trust.
   - 4A Tariff trust — **complete, automated-validated, and pushed** at `d3e1d56`; not deployed or live-tested.
   - 4B SoC/battery-energy trust — **complete, automated-validated, and pushed** at `19a6279`; not deployed or live-tested.
   - 4C Live PV/load trust — **complete, automated-validated, and pushed** at `85cfb1d`; not deployed or live-tested. Static PV/load trust defects are repaired without weakening fail-closed battery-export protection; genuine fresh zero PV/load remains trusted.
   - 4D Forecast/solar-clock trust — **complete and automated-validated locally** at `44c63e8`; not pushed, deployed, or live-tested. Existing forecast/sun freshness bases are retained; no new horizon, intended-day, issue-age, or sun-tolerance policy was created.
6. Actuator and fallback hardening — **NEXT**. Characterize and address, without preselecting a control policy:
   - export-ceiling chatter after telemetry-trust hardening, including the observed/reproduced `25.0 kW -> closed -> 25.0 kW` sequence;
   - fresh direct battery-discharge threshold chatter around `0.10 kW`, distinct from derived-flow/coherence defects;
   - actuator/readback/flow settlement behavior without treating service-call success as observed inverter state;
   - failed-cycle fallback reliability, fallback command checking, and partial/asymmetric actuator failures.

   The eventual solution must preserve fail-closed protection for simultaneous battery discharge plus grid export and must not implicitly authorize battery export from ordinary positive FiT. No larger threshold, specific deadband, fixed timer, N-cycle hysteresis, or exact settlement duration is yet approved.
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
