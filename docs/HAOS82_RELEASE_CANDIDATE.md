# HAOS .82 release candidate and verification gates

Status: preparing 2.3.71-haos82 on 27 October 2026. Not yet published.
The operator approved preparation, commit/push/PR, exact tag and image publication,
source/digest verification, normal metadata/receipt PR merges and the GitHub release.
HA installation and live settings remain separate.

## Source and scope

Repository: https://github.com/Belot77/sigenergy-optimizer.
Source PR [#49](https://github.com/Belot77/sigenergy-optimizer/pull/49) normally merged
at ce70f4ca41be0992ab899e56f2ba3d20ef0482f7; reviewed source head
d8fef951b24fc3de95d983effbdd18066d905c6d, tree
3dbca50c9b014e181db6c1505f1b352523d438f9.

Release branch: release/2.3.71-haos82.
Workspace: C:/Projects/sigenergy_optimizer-release-haos82.
Change only five established version markers (FastAPI, runtime signature,
add-on config/build labels and buildstamp), plus README, CHANGELOG, AI_HANDOVER,
CURRENT_STATE, ROADMAP and this receipt. No additional control, tests,
dependencies, workflows, permanent instructions or runtime data are changed.
Preserve every original worktree. Do not use release.sh.

## Behavior and limits

Incomplete/unpriced import history alone warns rather than vetoing otherwise
qualified automatic battery export. Finite actual import prices available in the
existing summary retain their floor, including valid zero/negative prices.
Unknown/sticky ledger coverage and retained payload/retry accounting remain.
A summary/cache/query failure can leave no known floor; no last-known cache is
added. Accepted risk: unpriced energy may export at a loss.

O19 rechecks current Demand in the final fallback authority/settlement read.
Trusted OFF is required to reopen bounded import; ON, unknown or conflicting
evidence requests the existing 0.01 kW close.

O21 restores house-serving ESS discharge after current Automated/Remote
authority and fresh request-correlated export-closure and exact MSC proof.
Normal capability and the decision's ESS bound remain. Ordinary deliberate
export still requires its intended target and independent qualification.
The primary application remains failed even when separate fallback succeeds.
Failed proof, takeover or failed service requests leave recovery incomplete.

Capability, tariff and policy-owner values remain decision-time snapshots.
This release does not fix Solar allocation, identify recurring MSC error causes,
redesign Morning priority or establish physical inverter acceptance.
A requested limit or helper success is not proof of actual grid/battery flow.

## Validation

Retained source suite: 1,504 tests / 1,439 subtests passed, zero failures,
206 warnings, 256.19 seconds. Focused checks passed 24 / 30 in 10.86 seconds.
Dotenv disabled; StateStore limited to memory or isolated temporary paths.
Full source run recorded 75 memory and 1,811 temporary-path constructions.
Independent source, strengthened-test and documentation reviews are GO.

Release-specific marker/source-pinning and selected cost/fallback regressions:
55 tests / 30 subtests passed, zero failures, 202 warnings, 23.12 seconds.
Strict guards recorded one memory and 59 temporary-path StateStore constructions.
Independent marker/documentation review is GO; only five single-marker
substitutions and the stated six documents differ from the merged source.
No full suite needs repeating for five single-marker substitutions and docs.
A mechanical comparison must prove no other source drift before tagging.

## Publication proof to complete

Verify remote version branch/tag/release absence before creation. Create the
annotated v2.3.71-haos82 tag only at the reviewed metadata commit. The existing
workflow must build linux/amd64 and linux/arm64 with SOURCE_REF at that exact SHA.
Do not merge metadata or create the GitHub release until the image proof passes.

Verify version/latest OCI index equality, both runtime manifests/configs, every
compressed layer hash/size and uncompressed diff ID, source/version labels and
all fourteen final target bytes/modes against the tag. Use default TLS and an
anonymous token held only in memory. Do not extract files or execute containers.
Layer bodies are downloaded and verified with buffering in memory.
The copied helper enforces 0755 for /run.sh and 0644 for the other thirteen
targets. Author and independent runs each passed 71 offline synthetic cases,
including exact-mode acceptance and invalid execute/write-mode rejection.
Helper SHA-256: 6ed3e18d70409c6d1d3799cf94b98db75d88a8ec3cb81e27faa59907c163914d.
Only the three release constants and the narrow non-launcher mode check differ
from the prior helper. No runtime container is launched by verification.

The previous immutable .81 index must remain:
sha256:e3f58087681c0c08ab53b0b8263387e8388d0916796aea326fdf9344ba821526.
The published .81 source is 247095a4f9905932c3f5716f3d1be6cee7b3c7f8.
Do not overwrite existing tags, force push, or publish a mismatched image.

## Installation and rollback

Supplied 27 October startup evidence identifies installed .80 source
acb576747e808e927bdd7d12346c507da9b188b6. There is no supplied .82 startup proof.
Auto update was last confirmed off on 26 October; no direct HA query is claimed.

After separately approved installation, verify Runtime signature=2.3.71-haos82
and the exact Container source commit from the final receipt. Monitor-only
and dry-run checks must precede separately approved supervised live checks.
Observe current authority, Demand reports, reserve/floor evidence, requested
limits, report timestamps, actual flows and failed-application/fallback outcomes.
Stop on lost authority, unproven settlement or unsafe behavior.

Published prior sources/images remain available; this does not establish the
operator's usable backup or reinstall method. Operational rollback remains
unverified. Preserve runtime data and historical evidence. Any source rollback
requires a reviewed scoped new revert, never resets, force pushes or tag rewrites.
