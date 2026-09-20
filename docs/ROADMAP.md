# Roadmap

This roadmap is ordered by dependency. Later work must not bypass the stated validation and live-proof gates.

## 1. Finish Phase 1 and obtain renewed live acceptance

Status: **active**.

Completed, committed, and pushed on `fix/phase1-audit-remediation`:

- Packages 1-5;
- Package 6A capability trust;
- Package 6B investigation/design only, with implementation deferred;
- Package 7 `/set_ess` hardening;
- Package 8 configuration validation and persistence;
- Package 9 settings/UI cleanup;
- Evening Boost safety repair;
- D1-D7 trust/freshness remediation;
- export-notification correction;
- post-D7 F1/R9 safety repair.

Remaining Phase 1 sequence:

1. Complete a fresh bounded Solar Surplus architecture/design using the approved net-energy budget and MSC/PV-only contract.
2. Implement and validate Solar Surplus without battery discharge merely to create export.
3. Run the consolidated final-candidate gate.
4. Prepare the release candidate.
5. Obtain final live acceptance of the complete Phase 1 candidate.

Gate: Phase 1 is not complete until the complete candidate is validated and live-accepted. Branch-only automated validation is not live proof.

## 2. Phase 2 transition-settlement safety

Status: **paused/frozen before production implementation**.

Implement the observed close -> later observe closed -> request MSC -> later observe exact MSC -> reopen sequence in `CONTROL_CONTRACT.md`. Entering deliberate battery export must settle its export target before discharge EMS. Service-call success never counts as observation.

Protect the two existing expected Phase 2 failures:

- `test_exact_msc_does_not_reopen_before_export_is_observed_closed`
- `test_return_from_discharge_waits_for_observed_close_before_requesting_msc`

Then run targeted transition tests, complete regression testing, a test release, and controlled live proof.

Gate: Phase 2 must be stable and live-accepted before downstream integration.

## 3. Short control-ownership audit

After Phase 2, confirm that every owner changes only its own actuator domains and that Manual, Force, freshness, price, reserve, and import-cost protections compose correctly. Resolve material findings before Climate Manager integration.

## 4. Climate Manager integration

Integrate the stable `sensor.sigenergy_hvac_solar_permission` interface (`start`, `continue`, `blocked`, `unavailable`). SigEnergy Optimizer owns energy opportunity and safety; Climate Manager owns HVAC profiles, zones, targets, comfort/manual behavior, AC0, and AirTouch commands.

## 5. Later work

Only after the preceding gates:

- operator diagnostics and ownership visibility improvements;
- deterministic replay tooling;
- evidence-driven load and forecast modelling;
- experimental dynamic solar scheduling on a separate branch, proved through replay, shadow comparison, and a bounded live trial before any merge.

These later items must not delay the Phase 1 gate or bypass Phase 2 and the ownership audit.
