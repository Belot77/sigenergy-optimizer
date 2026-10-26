# HAOS .81 local release candidate

Date: 26 October 2026. Candidate **2.3.70-haos81** is local, uncommitted and
unpublished. The operator approved preparation only on
`release/2.3.70-haos81` in `C:\Projects\sigenergy_optimizer-release-haos81`.
No commit, push, tag, image publication, metadata merge, GitHub release,
installation or live-system change is included in this approval.

## Verified source and scope

Repository: `https://github.com/Belot77/sigenergy-optimizer`.
Freshly fetched main: `ff5993a7fd56e228bd1e776df1447cc085d5a8a5`.
[PR #46](https://github.com/Belot77/sigenergy-optimizer/pull/46) normally merged
reviewed head `6ad0175dd824e930954294b4a8a71f4524588dd5` at 17:35:44 Sydney
(06:35:44 UTC), preserving reviewed/tested tree
`a8eead0542ea3cacac6d85532a73a6c16362f467`.

Preparation changes only five established version markers:

- FastAPI version in `app/main.py`.
- Runtime signature in `app/optimizer.py`.
- `sigenergy_optimizer_addon/config.yaml`.
- `sigenergy_optimizer_addon/build.yaml`.
- `sigenergy_optimizer_addon/buildstamp.txt`.

Documentation scope is README, CHANGELOG, AI_HANDOVER, CURRENT_STATE, ROADMAP
and this candidate. No further production, test, configuration-value, workflow,
dependency, archive-store or control-contract changes are bundled. Original
worktrees and unfinished work remain preserved. Do not use `release.sh`.

Planned tag is `v2.3.70-haos81`. The future tag/container source will be the
separately approved metadata commit; it is not yet assigned and must not be
confused with the source merge above.

## Behavior and evidence limits

New trace rows distinguish requested charge ceiling from the pre-application
reported ESS charge setting and direct measured battery power. Five measured
flow observations retain their individual report timestamps and freshness flags.
Signed aggregate balance and Solar feedback boundaries help explain relief
reset/requalification and command-response uncertainty. Existing application
outcomes remain separate from these observations.

This is passive diagnostic evidence. It adds no HA request or actuator write,
changes no control target, tolerance, ownership, settlement or fallback rule,
and does not correct Solar allocation. The current negative aggregate balance
still rejects relief; permitted normal charging recovery remains in place.
The existing .80 UI log-retention filter is included unchanged.

ESS provenance comes from existing bulk metadata, which may appear stale.
HA report timestamps do not prove simultaneous physical sampling. Feedback
timestamps identify the armed Solar command boundary, not all successful writes
or physical settlement; recording can precede later failed-tick cleanup. Reported
setpoints and successful helper outcomes do not establish actual inverter response.
Missing data remains unknown. Historical trace rows are not backfilled.
See [the durable evidence contract](CONTROL_CONTRACT.md#passive-charge-allocation-evidence).

The supplied -74 W aggregate/+2 W direct sample does not justify a new meter-error
tolerance. O18 fill strategy/allocation, O5/O9, broader O6, parked O11 and existing
physical/Boost acceptance remain open. No unsafe-flow cause or physical energy
loss is inferred from the sampled trace or screenshot.

## Offline validation

Retained source validation: **204 tests / 196 subtests passed**, zero failures,
202 existing warnings, 42.15 seconds. Focused evidence/outcome checks passed
19 / 22 in 1.23 seconds. Eight new evidence tests cover readback provenance,
zero versus unknown, malformed values, failure isolation and archive round-trip.
Independent source/test, documentation and staged-scope reviews are GO.
Mechanical AST comparison confirmed baseline control code after removing only
the approved passive additions. These are source results, not physical proof.

All **54 release-marker/source-pinning/evidence/logging tests / 12 subtests
passed**, zero failures, 202 existing warnings, in **13.86 seconds**. Settings did
not load dotenv; bytecode and pytest cache were disabled. The source-pinning
cases use local Git fixtures, and evidence/archive checks use fake HA and
temporary storage. No full suite was repeated for marker/documentation changes.
Normalized byte comparison confirms exactly five single-marker substitutions
plus the six stated documents, with no other source drift. Syntax/whitespace
checks pass. Independent metadata/documentation review is **GO**, with no blocking
finding. The source results above remain separately attributed.

## Public preflight

At 17:58 Sydney (06:58 UTC) on 26 October, the proposed remote release branch,
tag and GitHub release were absent. Public GHCR manifest HEAD returned 404 for
`2.3.70-haos81`. Both `2.3.69-haos80` and `latest` returned the expected digest
header:

`sha256:91120b1039eec3915a37c6ff1a1210cf1cf5e79d97e3e1d9de31207206301a5a`.

These are absence/header checks, not a new image-body or layer proof. No image
layers were downloaded. The previous [published .80 receipt](HAOS80_RELEASE_CANDIDATE.md)
retains its separate full image/source verification.

## Publication, installation and rollback gates

Before any separately approved publication, recheck candidate scope, main,
branch/tag/release absence and current registry state. Publication must pin the
exact approved metadata commit, verify tag-triggered build success, both runtime
platforms, source pin and relevant source bytes, and reconcile version/latest
digests. Preserve existing immutable version tags. Normal metadata PR merge,
GitHub release and final receipt documentation require that publication scope.
No build or publication has occurred at this checkpoint.

The operator last reported installed .79, without renewed exact startup proof.
Auto update was last confirmed off on 26 October; no direct HA query is claimed.
Installation remains a separate action. After a separately approved installation,
verify runtime signature `2.3.70-haos81` and the exact approved future source SHA.
Request a trace generated by that verified build; do not interpret old records
as new evidence or treat an updated setpoint as proof of physical compliance.
No live control-mode or inverter setting changes are authorized here.

Local rollback is to withhold this uncommitted release branch. Published .80
and .79 source/images remain available, but availability does not prove the
operator's usable backup or reinstall method. A later installed rollback must
use separately verified operational recovery, without discarding existing data.
