# Decision-trace cycling audit — 17–18 October 2026

This note records a bounded review of the supplied decision trace. It is observational evidence, not a live acceptance report or a root-cause finding for every export interruption.

## Source and limits

Source file: `sigenergy_decision_trace_24h_20261017T215448Z.jsonl`, 17,340 records spanning 17 October 08:54:51 to 18 October 08:50:57 Australia/Sydney. SHA-256: `ccaa643684d4e2c2620aba22faba99bb22f81dc3df99015bd44b5ac7fc7b196f`. No raw trace or runtime logs are copied here. EMS/import/export readbacks are present, but source build identity and observed ESS limits are absent. These gaps limit attribution and physical-state conclusions.

The operator deferred short physical import spikes associated with sudden changes/physics. They are not currently considered a confirmed Demand Window software bug, and no setting change is requested. This is separate from O7: proving exact-full PV-only surplus export without deliberate battery export or grid import remains an open live-acceptance requirement.

## Findings

- **Morning Dump intent/EMS mismatch:** 38 records from 07:10:51 to 07:13:34 show export blocked while discharge EMS was selected. This matches the earlier source's unconditional Morning Dump selection; the installed build was not identified, so the trace cannot establish the installed source. The combined local review candidate now requires qualified `BATTERY_EXPORT` intent and a positive bounded requested target before early discharge-EMS selection. It preserves floor, hysteresis, settings, priority and downstream settlement.
- **Configured floor pulses:** four short pulses at logged 15%/15.1% match the configured 15% floor; the floor was not breached. They do not establish a floor-control defect.
- **Cycling/ownership observations (O2):** 92 charge-owner transitions were present, including a stable-FiT example around 12:22. This documents cycling but does not establish its general cause.
- **12:22 current-load budget transition:** between 12:22:14 and 12:22:31 Sydney, remaining forecast stayed 59.6089 kWh, SoC 54.9%, fill need 18.1753 kWh, forecast factor 1.2 and provider status VALID. Load rose from 4.038 to 4.625 kW; remaining load rose from 28.296 to 32.384 kWh, and protected forecast rose from 55.766 to 60.671 kWh. Raw surplus crossed from +3.843 to −1.062 kWh while measured PV surplus fell from 14.12 to 5.925 kW, still above the 0.2 kW continuation threshold. The current-load energy budget's sign change explains this sample; it does not establish the cause of all physical cycling. PV-surplus hysteresis uses 0.5 kW for entry and 0.2 kW for continuation; the budget test remains strictly positive with no buffer.
- **Missing/zero-flow sample:** row 2032 at 17 October 12:22:37 Sydney showed PV and load both zero; the next record (2033) recovered. Physical cause is unproven.
- **Observability (O8):** earlier source logging omitted some pending/error outcomes; the combined local review candidate now records returned application outcomes and ordinary application exceptions. The sampled 526-second and 33-second gaps cannot be reconstructed or attributed conclusively, and do not prove the historical 13-second gap. Do not assume all gaps were caused by logging omissions.
- **P3 reason text:** a positive-FiT reason mismatch is a diagnostics issue, not evidence that export permission or control behavior is wrong. The separate FIT wording fix corrects positive sub-1¢ text without changing tariff gates.

## Unexercised paths and scope

This trace did not exercise Solar Override, Evening Boost, Medium-or-higher battery-export tiers, negative prices or actual-import-cost vetoes. It neither verifies nor falsifies those policies or the separate Solar Override floor fix. The integrated local branch contains that floor guard, the Morning Dump intent guard, trace outcome metadata, and the FIT reason correction; the original component worktrees remain preserved.

The evidence does not justify damping, latching, filtering or reserve-policy changes. Those require a separate operator policy decision and a bounded proposal. Do not infer a broad control defect or physical cause from these records alone.

## Offline characterization added during review

These are deterministic `real_decide` characterizations, not trace-derived live behavior and not policy changes:

- **Morning Dump SoC transitions:** with trusted forecast/refill evidence, SoC sequence 15.1%, 15%, 15.1%, 15%, 15.1% alternates Morning Dump 25 kW/discharge intent with closed 0 kW/MSC. General SoC hysteresis values 0%, 2% and 10% do not damp this sequence (one test, three subtests). The contract does not define a re-entry margin; any damping/latch change needs an operator policy decision.
- **Solar current-load budget transition:** with load 1.0 → 1.1 → 1.0 kW, fixed 7.5 kWh forecast, SoC 80%, capacity 10 kWh, 4-hour horizon and factor 1.2, measured PV-surplus thresholds remain in force while Solar MSC/charge ownership changes on/off/on without battery export (one characterization test passed). This demonstrates the current budget sensitivity in that setup, not a general defect or physical cause.
- **Morning Slow overlap review:** the cap helper uses the active Morning Slow flag even when Dump is eligible. Its ownership guard only withholds permissive relief conservatively, so no additional actionable bug was found; broader overlap effects remain unproven. In the 07:10 trace segment the Slow flag was inactive, so the 21 kW value cannot be attributed to that guard.

## Validation boundary

The 1,070-test / 1,124-subtest result predates the later negative-import Morning Dump regression. That regression reproduced two contradictory grid-charge decisions with both limits zero; the subsequently approved explicit MSC fallback now passes the exact regression and preservation controls. This is synthetic decision evidence, not a negative-price occurrence in the supplied trace or proof of physical charging. Final combined offline validation passed **1,073 tests / 1,134 subtests, zero failures**, with 206 warnings in 170.97 seconds. See `MORNING_DUMP_CORRECTION_REVIEW_2026-10-18.md`. Publication, installation and supervised live proof remain separate gates.
