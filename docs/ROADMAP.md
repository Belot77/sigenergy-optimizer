# Roadmap

This roadmap is ordered by dependency. Later work must not bypass the stated validation and live-proof gates.

## Phase 1 audit remediation and renewed acceptance

Status: **active**. Phase 1 was reopened after a proven live Morning Slow defect and broader control-authority audit. Complete in this order:

1. Characterization tests. Complete.
2. Authority and fail-closed remediation. Complete, automated-validated, committed at `9538cc84c1235f33d52ebc2ecdf1b6b9c64896b0`, and pushed to `origin/fix/phase1-audit-remediation`; not yet live-tested.
3. Morning control repair, including separation of Morning Slow policy from grid-transfer deadband. **NEXT.**
4. Battery-export safety.
5. Telemetry trust.
6. Actuator and fallback hardening.
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
