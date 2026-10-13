# SigEnergy Optimizer AI Handover

Last consolidated: 2026-10-13

Read root/project `AGENTS.md`, then `CURRENT_STATE.md` and `CONTROL_CONTRACT.md`. Verify identity/status and preserve dirty work before acting.

- Current worktree: `C:/Projects/sigenergy_optimizer-demand-window-hotfix`; branch `fix/demand-window-exact-full-pv-only`. Completed code-bearing checkpoint: `67fae5db2451fbf3e706b10cf4e2dbad07b38bd9`, message `Fix Demand Window exact-full PV-only export under MSC`. It is not necessarily the future final branch HEAD after a documentation-only commit.
- Last operator-reported live is the original **2.3.58-haos69** release at `b90fdeafce5e40e206ffd17dce5e1a8c810519e6`. This supersedes the former current .68/pre-release .69 descriptions; no fresh HA/runtime query was made. Known-good rollback remains **2.3.54-haos65**, source `9965e79133f38d5b9943dcf5a9b04ed6fdab1239`. Do not promote .69 or the hotfix to rollback.
- The completed local commit contains exactly seven files: `CHANGELOG.md`, `app/optimizer.py`, `docs/AI_HANDOVER.md`, `docs/CHANGELOG.md`, `docs/CURRENT_STATE.md`, `docs/ROADMAP.md` and `tests/test_msc_baseline_overlay_contract.py`. Preflight for this documentation follow-up verified the expected branch, HEAD `67fae5db2451fbf3e706b10cf4e2dbad07b38bd9` and a clean worktree, with no modified, staged or untracked files.
- This separate follow-up changes only `docs/CURRENT_STATE.md`, `docs/AI_HANDOVER.md`, `docs/ROADMAP.md`, `docs/CHANGELOG.md` and root `CHANGELOG.md`; production and tests remain untouched. No GitHub publication, independent committed-SHA GitHub audit, merge, release, deployment or hotfix live acceptance has occurred.
- Confirmed defect: otherwise qualified exact-full cheap-positive-FiT PV-only export returned `0 kW / EXPORT_BLOCKED` only for trusted Demand Window ON. OFF and untrusted retained the high MSC surplus ceiling. The one-line production correction removes the unintended `not trusted_demand_window_active` exclusion from `pv_only_msc_transition_ready`; the only test addition is the exact 49-line characterization transferred from the read-only reference worktree.
- After correction, ON/OFF/untrusted receive the qualified configured, capability-bounded `MSC_SURPLUS_CEILING`. ON and untrusted still block import; EMS remains MSC, with no battery-export owner or deliberate discharge. Exact 100% qualification, below-full protection, observed Automated/exact MSC ownership, safe trusted flows and observed actuator settlement remain mandatory. Morning, Solar, ordinary export, Manual/Force and independent actual import-cost protections retain their semantics.
- Retained validation from the preceding hotfix task: targeted test **1 failed before production editing, then 1 passed** across all three Demand Window states; independent protections **466 tests / 611 subtests passed**; final full suite run once **946 tests / 1,079 subtests passed**, zero failures, **206 warnings**. Compileall for `app`/`tests` with external cache and `git diff --check` passed. This documentation-only task does not rerun tests or compileall.
- Local `Australia/Adelaide` timezone data is missing, causing UTC fallback in optimizer fixture logs. Installed timezone behaviour and physical/live settlement are not established by these tests. The recorded full-suite warnings are Pydantic deprecations.

Original .69 audit context: independent ChatGPT GitHub review reported GO for the prior corrected four-tier checkpoint `bec1095539b96dbb90b62bd6eb047471e41801f6`, resolving the two arbitration blockers. That historical review does not accept the new Demand Window delta. Ordinary deliberate battery sale still starts at Medium; Low remains PV-only classification, with its compatible 100% default. Independent Medium/High/Spike floors remain 40/20/10%, without tier fallback. Keep shared import-cost permission, guarded Morning preemption, advisory-only Value Gate and the distinction between proposal/final ownership and physical settlement.

Phase 1 remains incomplete: Evening Boost reserve/transition stability and Solar threshold-switching disposition remain unresolved/deferred. Phase 2 retains only reported scoped .68 acceptance; its **13-second observation gap** and broader/unexercised scenarios remain unproven. Four-tier physical/live acceptance and hotfix live proof remain outstanding. The original .69 release report does not close these gates. Actual operator settings have not been freshly queried and must not be inferred from software defaults.

Next actions:

1. Review this five-file documentation correction.
2. Obtain separate approval for its local documentation-only commit.
3. Only afterward consider separately authorised GitHub push and independent committed-source review.
4. Retain explicit release/deployment and live-acceptance gates; commit or push approval does not authorise live work.

No new hotfix release identity is assigned. Any later release/deployment requires separate authorisation, source/build and effective-setting/authority checks, .65 rollback readiness, supervised observation and explicit stop/rollback conditions. No staging, commit, push, tag, build, installation/restart or HA/inverter write is authorised by this documentation task. Stop after this documentation follow-up; retain all roadmap phase ordering and sequencing exceptions.
