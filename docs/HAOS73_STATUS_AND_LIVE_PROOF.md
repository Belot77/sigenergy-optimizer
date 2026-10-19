# .73 status, recent fixes and scoped live proof

Updated: 20 October 2026. Dates and operational times use Australia/Sydney unless explicitly marked UTC.

## What is established

- Latest published release: **2.3.62-haos73**, tag/source `v2.3.62-haos73` / `46d36358d38137231dff081176a372c3aa1f4cee`. [GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.62-haos73) publication was 19 October at 18:02 Sydney (`2026-10-19T07:02:00Z`).
- PR #24 merged the same reviewed tree into main at `d8d78320c43096bbae30210bf8bcaa60ec3313d0`. Tag-build run `39211551717`, attempt 1, succeeded for amd64/arm64. Verified OCI index: `sha256:a2313bed130c77d7fa4139b03adf67c4282f7a59c1ed116d8d64083e9cfc6f59`.
- Supplied startup logs at 20 October 06:53:25 identify runtime `.73` and that exact full source SHA. Supplied Supervisor logs show the local `.71` to `.73` build with matching `BUILD_VERSION`, then final start at 06:53:23. This establishes supplied installed-build identity; no agent installation or independent authenticated HA access is claimed.
- `.73` includes source pinning and carries `.72` optimizer behavior unchanged. Relative to the operator's earlier `.71` build, the four `.72` corrections below are newly carried control/diagnostic changes.
- The supplied live-memory trace contains 371 outcomes from 08:25:04 to 09:01:26: **356 succeeded, eight failed, seven pending**. The latest row reports successful application, observed Automated/MSC and trusted coherent flows supporting PV export with battery charging. Eight early helper-success rows lacked trusted MSC/flow observations. These totals are application outcomes, not 356 independent physical validations.
- Current row creation is demonstrated: successful live rows at 08:54:03 and 08:54:08 bracket a stale archive download at 08:54:07. Application-outcome recording works in memory; persistent history still does not provide current acceptance evidence.

The release is installed and has observed operating episodes. Full or scoped live acceptance must still be recorded explicitly; installation and test success alone do not establish it.

## Fixes implemented during 14–20 October

This is the last seven calendar days in Sydney, not a claim that every item was authored in the Work chat. Only committed/published code fixes are listed. The `.70` exact-full Demand Window correction and earlier four-tier arbitration work predate this window; they remain inherited behavior with outstanding proof.

| Released | Problem corrected | Result and boundary |
| --- | --- | --- |
| `.71`, 16 October | Conflicting actuator evidence or the wrong export target could count as settlement | Deliberate discharge needs consistent, fresh evidence after its own dispatch and the intended export target. Service success or a smaller safety-close value is insufficient. |
| `.71`, 16 October | Fallback/recovery could undo independently owned ESS restrictions | Independent ESS charge/discharge restrictions survive recovery; it releases only the temporary restriction it owns. |
| `.71`, 16 October | Repeated unchanged Automated selector reports could supersede pending authenticated Force | Supersession requires a genuine, coherent later selector transition; old-request writes/retries stop when superseded. Manual/Force behavior remains protected. |
| `.71`, 16 October | Medium and Evening Boost priority | The narrow Medium-over-Evening Boost priority defect is corrected. Broader Boost oscillation/reserve behavior is not thereby fixed. |
| `.72`, 19 October | Solar Override bypass of selected/protected SoC floors | Battery-backed export requires SoC strictly above both effective floors. Independently qualified PV-only MSC remains separate. |
| `.72`, 19 October | Morning Dump selected discharge without qualified export, or fell through to cheap grid charging while import/export were blocked | Discharge needs qualified `BATTERY_EXPORT` and a bounded target above 0.01 kW. Blocked active Dump explicitly uses MSC. Qualified negative-import-price Dump behavior and inactive-Dump charging are preserved. |
| `.72`, 19 October | Missing application-outcome trace rows on pending/failed/ordinary exception paths | Live metadata records the application outcome and fallback/pending status with recorder-failure isolation. It does not repair persistent archive freshness or prove physical settlement. |
| `.72`, 19 October | Positive sub-1-cent FiT was explained as non-positive or ambiguously rounded | Diagnostic wording states below minimum and retains boundary precision. Tariff eligibility rules were not changed. |
| `.73`, 19 October | Add-on builds could fetch moving main instead of the requested release source | Full `SOURCE_REF` must match the resolved checkout, or `BUILD_VERSION` resolves its release tag. Detached source and full SHA are recorded. Supplied `.73` build/runtime evidence matches the intended source. |

Source anchors: `.71` tag `9f3f02a5c1c82786c85026a3848574cca3cf891f` (Stage B checkpoint `ae4a974692aae1300c97845fcc32d4cfa6c2bdea`); `.72` source `3afefcd113d2c6f3eadd5aadd52fbda1a8b35f28` (combined code `4e4b17c2d3bb362716d6b4e5ddb60659faf7beec`); source-pinning implementation `1042ee95c94c56eb64ff0a5ae123ca863c49cd25`, inherited by `.73`.

Retained validation is in [CURRENT_STATE.md](CURRENT_STATE.md): Stage B 1,036 tests / 1,084 subtests; combined `.72` 1,073 / 1,134; `.73` preparation 16 focused source/version tests; separate local archive characterization 56 tests / 12 subtests. No suite is rerun or represented as live proof by this documentation checkpoint.

## Remaining issues

The canonical identifiers remain in [the current issue register](CURRENT_STATE.md#outstanding-operational-bug-register). A corrected code defect can remain open for physical proof without implying that the same defect is still present.

| Category | Remaining work |
| --- | --- |
| Corrected code, live proof outstanding | O1 Medium/Boost overlap; O3 Solar selected/protected floor boundaries and related ownership/ceiling reports; O6 Dump guard/fallback plus remaining Slow handover/depletion/floor-cycling reports. |
| Unresolved behavior | O2 unexplained export interruptions/cycling and Solar threshold switching; O4 Boost oscillation/SoC behavior. The historical 12:22 Solar ownership flip is explained offline, not every interruption. Do not assume all cycling is caused by MSC settlement. |
| Operator policy | O5 overnight reserve and tomorrow-PV awareness; related Boost/reserve expectations. Proposed 30-cent tuning is not approved. |
| Acceptance/evidence backlog | O7 exact-full Demand Window PV-only proof; O8 historical 13-second observation gap and unexercised safety cases; O9 short ownership/configuration audit. |
| Parked diagnostic defect | O10 persistent archive/download freshness and inconsistent coverage. At 08:54:07 its latest row was 19 October 07:58:42, age 24h55m25s; every returned row was outside the nominal last 24 hours. Earlier omitted rows returned byte-identical. Persistence/recovery/index/export state remains unresolved. |
| Parked settlement observation | O11 intermittent MSC verification failures. Seven complete failed-fallback, pending-MSC and later-success sequences recovered in 9–10 seconds in the supplied window. The latest sequence is 09:00:35 / 09:00:39 / 09:00:44. Cause and long-term stability remain open; the 07:38 event is outside this sample. |
| Development tooling defect | `release.sh` preserves the haos suffix, updates only three of five markers, stages everything and can commit/tag/push. Keep bypassing it until separately repaired and reviewed. |
| Platform/rollback observations | Supervisor/app restarts and 49 read errors across seven archive files missing `backup.json`. These do not prove an optimizer code cause, invalidate all backups, or identify a usable rollback backup. |

**Operator disposition:** O10 and O11 are parked, not fixed or accepted. HA/hardware involvement remains a hypothesis. The follow-up reminder is paused. Short physical Demand Window import spikes are separately deferred and are not a confirmed software defect; that does not close O7.

## What still needs live proof for .73

Start with the upgrade delta from `.71`: Solar floors, Morning Dump behavior, reason wording and application-outcome visibility. Installed source identity is already evidenced. Legacy safety and policy cases below remain inherited acceptance obligations, not new `.73` control changes.

Use natural operating examples first. Record each scenario as **passed for the stated conditions**, **unexercised**, **failed**, or **explicitly deferred**. There is no requirement to force every price, SoC or fault condition today.

| Scenario | Evidence needed for a scoped pass | Current disposition |
| --- | --- | --- |
| Installed build/source | Runtime version and full source match the published tag; local `BUILD_VERSION` build resolves that source | Evidenced for supplied `.73` installation. |
| Ordinary MSC/PV-only operation and outcome recording | Current rows, observed authority/MSC, coherent PV/load/battery/grid flows and application outcome | One working window evidenced; not all limits or long-term behavior. Archive reliability remains parked. |
| Solar Override at each effective floor | Above both actual selected-tier and protected floors, battery export obeys all other guards. At/below either floor, no battery-export owner/discharge EMS; separately qualified MSC PV-only export may continue | Dedicated boundary evidence outstanding. Do not infer effective site floors from defaults. |
| Morning Dump qualified and blocked cases | Qualified positive bounded target/floor/window; blocked active Dump uses MSC with import closed, including naturally occurring negative import prices. Preserve qualified Dump priority; observe handover to Morning Slow and actual charging | Dedicated scoped evidence outstanding; do not manufacture negative prices or discharge the battery to force a case. |
| Positive FiT below one cent | Actual positive tariff below minimum is explained accurately, including units and displayed precision | Natural example outstanding; extreme numeric boundaries retain offline coverage. |
| Medium/High/Spike, Low and Boost overlap | Actual configured floors/reserve/import-cost guards; no ordinary Low battery sale; Medium priority when Boost also qualifies | O1/O4 and tier-specific acceptance outstanding. Disabled/unexercised Boost is not an overlap pass. |
| Demand Window at exactly full SoC | At 100% SoC and qualified cheap-FiT surplus, observed MSC/PV-only export without deliberate battery export; import blocking preserved. Capture applicable ON/OFF cases | O7 open. Short import-spike deferral is separate; unavailable-state fault testing is not authorised here. |
| Entering/leaving deliberate battery export | Intended export target settles before discharge EMS. On return, closure request, later observed closure, MSC request, later exact MSC observation and then permitted reopening; continuous timestamped evidence | Historical O8 gap cannot be recovered. New dedicated sequences and applicable safety cases remain outstanding; recurrent MSC investigation is parked. |
| Manual/Force and independent restrictions | Actual operator takeover respected; unchanged Automated reports do not cancel pending Force; genuine later selector transition stops old retries. Independent Demand/ESS/PV restrictions survive transitions/fallback; recovery releases only its own restriction | Observe ordinary use or separately approved supervised cases. Supplied traces lack complete independently observed ESS-limit settlement. |
| Restart or telemetry loss/recovery | Unknown authority/settlement stays restrictive; fresh verified Automated ownership and observed Remote EMS ON precede automatic writes; no stale evidence permits opening | Natural or separately approved observation needed. Do not restart, inject faults or alter settings for this document. |

For each case, retain a short timestamped **before/during/after** record of effective policy settings, authority/Remote EMS, owner/reason, requested **and observed** EMS/export/import/PV/ESS limits, SoC, PV/load/battery/directional-grid powers, and report timestamps/trust. Requested ceilings and HTTP 200 responses are not physical settlement.

The reported physical inverter export maximum is 15 kW; Manual/Force and software ceilings can separately be 25 kW. Neither a requested ceiling nor a sample exporting 6.4 kW proves physical maximum enforcement. Keep the controls separate and verify actual device settings/readbacks without changing them.

Before deliberately exercising live cases, establish a usable dated rollback method and saved effective settings with the exact target source. The `.65` source/image reference alone is insufficient. Agree stop/rollback conditions for an unintended owner/discharge, floor breach, lost independent restriction, contradictory/unavailable observations, or failure to settle within the agreed supervised window.

This is an observation/acceptance plan, not permission to install, restart, roll back, change tariffs/helpers, invoke controls or alter battery/grid settings. Parked issues stay parked unless the operator explicitly resumes them. Record scoped acceptance rather than declaring the whole release fully proven while gaps remain.

## Next development sequence

Maintain the Phase 1/2 dispositions and approved sequencing exceptions. Prepare the short control-ownership/configuration audit; resolve or explicitly dispose of material findings before architecture consolidation, project cleanup, full GUI/UX, then Climate Manager integration. This documentation checkpoint does not authorise those implementation phases or discard any unfinished work.

## Evidence and privacy

This document summarises supplied startup/Supervisor/application logs and live/archive traces plus verified public Git references. No raw logs, trace rows, credentials, private endpoints, entity identifiers, backups or runtime files are committed. The separate local characterization tests/note remain in their original worktree and are not part of this documentation change.

The browser's internal `Z:\` launcher error (`1326`) still blocks independent live access. Repository access uses `C:\Projects`; no security settings, drive mappings or credentials were changed.
