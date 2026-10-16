# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-16

Read `C:\Projects\AGENTS.md`, worktree `AGENTS.md`, this handover, `CURRENT_STATE.md` and relevant `CONTROL_CONTRACT.md` sections. Inspect only minimum relevant files. Git records repository identity; HA and operator evidence establish live state.

## Current Stage B checkpoint

- Writable worktree `C:\Projects\sigenergy_optimizer-authority-stage-b`; verified branch `fix/control-authority-safety`, HEAD `2a60a62097d16344711a64cf96e5e52d177556e0`, origin `https://github.com/Belot77/sigenergy-optimizer`.
- Current worktree is dirty with exactly **25 modified, unstaged files: 19 source/test files plus six approved documents**; nothing staged or untracked. The original 19 remain uncommitted and byte-preserved during documentation work. No staging, commit, publication or live action is authorised by documentation completion.
- Stage B implementation completed, including narrow Medium-over-Evening Boost priority correction. Supplied independent focused review passed corrections A/B/C. Retained final validation: **1,036 tests / 1,084 subtests, zero failures**; compileall and diff check passed. No full-suite/compileall rerun for documentation.
- **No supervised live acceptance. Stage B remains NO-GO for deployment.** Review/test success does not prove live settlement.

## Completed corrections and durable boundaries

- **A - Contradictory actuator evidence:** conflicting actuator observations cannot prove settlement. Deliberate discharge requires the intended export target, with fresh provenance-bearing evidence strictly after its own dispatch boundary; a smaller value sufficient for a safety close is not proof of a deliberate discharge target.
- **B - Independent ESS restrictions:** successful fallback cannot restore ESS charge/discharge capability above independently owned restrictions. Solar relinquishment restores only the otherwise safe normal charge request; Demand Window import blocking and independent PV restrictions remain effective.
- **C - Pending Force ownership:** unchanged Automated selector reports prove freshness, not a new operator selection. A pending authenticated Force request yields to a verified selector state transition strictly after its request, with coherent change/update/report timestamps; supersession stops subsequent writes/retries.

Preserve current Automated/Unknown/confirmed Manual-Force distinctions, dispatch-time authority, observed Remote EMS ON, independent Demand/ESS/PV restrictions, request-specific settlement, fallback and bounded retries. Preserve unattended restart auto-enable after current Automated verification; no persistent OFF registry or mandatory restart handback redesign. Manual/Force targets, including 25 kW, and authenticated `/set_ess` remain unchanged.

## Live identity, rollback and outstanding risks

- Latest operator-reported live `2.3.59-haos70`, source `08f4daf53941bd850a4fe392b458c42b1df68b47`; not freshly HA-verified. Protected known-good rollback `2.3.54-haos65`, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not alter either.
- Physical inverter grid-export maximum reportedly 15 kW. Physical grid-export enforcement and ESS limits are separate controls. Reported 15 October Morning Dump floor 15%, timing option 1.0 hour (implementation sunrise through one hour after), Morning Slow near 2 kW, export near 15 kW, Evening Boost disabled and PV forecast about 130 kWh are historical operator context, not renewed verification.
- Continue all nine open entries in `CURRENT_STATE.md` O1-O9: Medium/Boost live acceptance; unexplained export interruptions/cycling; Solar Override activation/ownership/ceiling discrepancies; Boost oscillation/SoC; overnight reserve and tomorrow-PV policy; Morning Dump/Slow interactions/depletion; exact-full Demand Window PV-only proof; 13-second observation gap; short ownership/configuration audit. No proven cause for unexplained observations, no approval for proposed 30-cent tuning, and no closure from automated tests.
- Phase 1 remains open; scoped `.68` Phase 2 evidence, the 13-second gap, unexercised scenarios and four-tier/hotfix physical acceptance remain limited as recorded in `CURRENT_STATE.md` and `ROADMAP.md`.
- Protected dirty reference `C:\Projects\sigenergy_optimizer-evening-priority` (ten existing modifications) and Stage A worktree remain untouched. Never reset, stash, discard, overwrite or wholesale-copy the protected optimizer.

## Exact continuation sequence

Documentation review passed on 16 October 2026. The exact next action is to obtain explicit approval to stage the identified 25 files and create one local development checkpoint commit; no Git mutation is authorised yet.

1. Review this documentation-only change.
2. Obtain separate approval for staging and committing the development checkpoint.
3. Obtain separate approval for any publication, release or installation.
4. Plan supervised live acceptance with .65 rollback ready.
5. Capture actual inverter state and physical-flow evidence.
6. Close or explicitly retain unresolved operational bugs based on evidence.
7. Proceed to the short control-ownership audit and existing approved roadmap.

Before any separately approved live acceptance, verify actual source/build, effective settings, current authority and .65 rollback readiness; plan supervision and explicit stop/rollback conditions. Capture timestamped requested/observed EMS, PV MAX, import/export ceilings, ESS limits, SoC, battery/PV/grid flows and reason/owner. Service-call success is not settlement.

Preserve the full approved roadmap order: ownership audit -> architecture -> project cleanup -> full GUI/UX -> Climate Manager integration. Climate Manager broadly works and is not the current priority.

After an approved commit, report the actual new SHA, exact committed file list and verified Git cleanliness. The HEAD and dirty-state statements above describe this pre-commit checkpoint; they do not identify the future commit. Any later documentation reconciliation must preserve this distinction and requires its own scoped approval; do not amend or silently create a second commit.

Recommended next Codex session: **CURRENT; Medium reasoning; Standard speed** for the approved local checkpoint operation; use NEW only if this session is unavailable or confused. Any later safety-sensitive live-acceptance planning requires its own approved scope; do not infer approval from this recommendation.
