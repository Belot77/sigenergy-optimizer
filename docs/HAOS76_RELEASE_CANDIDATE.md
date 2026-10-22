# HAOS .76 local release candidate and verification plan

Prepared 23 October 2026. Candidate only: no candidate commit, tag, image build, GitHub Release or installation is claimed. Published .75 remains current.

## Source and scope

- Candidate: `2.3.65-haos76`; planned tag `v2.3.65-haos76`.
- Workspace: `C:\Projects\sigenergy_optimizer-release-haos76`; branch `release/2.3.65-haos76`.
- Base: main/PR #31 normal merge `632a42081d9ff93b270ffcca048604031ec4fed1`, merged 23 October at 08:54:29 Sydney.
- Reviewed fix: `bcfdb75b33c8ae1db3c7f534cb8952f144d9c3cd`; both trees are `b051e77dda3b3cfb38dfa1df1f0696c6bce027b3`.

The included control correction keeps independently active Standby Holdoff and Morning Dump import permission closed before fallback settlement waits and throughout recovery, including Morning Dump's blocked-export MSC branch. Demand ON/unknown blocking, ordinary economic-zero recovery, genuine Morning preemption, authority, and separate PV/ESS restrictions remain intact. Two settings surfaces clarify Low positive-FiT PV-only permission and summary/status timing; configuration behavior is unchanged.

Release preparation changes only these five version markers and the matching release/status documentation:

| File | Marker |
| --- | --- |
| `app/main.py` | FastAPI `version` |
| `app/optimizer.py` | `_RUNTIME_SIGNATURE` |
| `sigenergy_optimizer_addon/config.yaml` | add-on `version` |
| `sigenergy_optimizer_addon/build.yaml` | `io.hass.version` |
| `sigenergy_optimizer_addon/buildstamp.txt` | clone-cache build stamp |

Every marker must equal `2.3.65-haos76`. After reversing those exact substitutions and normalizing checkout line endings, production content must equal the verified base. Tests, UI, Dockerfile, workflow, control contract and permanent instructions must remain unchanged from that base. Do not use `release.sh`; it updates only three markers and can stage, commit, tag and push broadly.

## Validation

Retained combined control validation: 1,149 tests / 1,287 subtests passed, zero failures, 206 existing warnings, in 211.18 seconds. Seven focused import-owner regressions passed, including both real settlement waiters and settled/unsettled cases; six settings-UI checks passed separately. Independent control review found no High/Medium blocker. These tests use fake HA and do not establish physical inverter behavior.

Version-only checks: all 16 tests in `tests/test_release_version_consistency.py` and `tests/test_addon_source_pinning.py` passed in 9.43 seconds. Independent normalized comparison proved exactly five single-marker substitutions and no other production changes; the permitted scope is five markers plus six release/status documents. Independent release-metadata review was GO for the local candidate with no blocker. No full-suite repeat was performed for this marker/documentation-only preparation.

## Prior release and operator evidence

Latest GitHub Release is `.75` / `2.3.64-haos75`, tag/source `413e1691bb58e0b942098ab43f44e873df157a2b`, published 21 October at 13:24:59 Sydney. Anonymous public-registry checks on 23 October confirmed that its version-specific OCI index and `latest` both resolve to `sha256:ed2a984b457bfddb2b74050d437f98337944076e9144a8d1a19f577d8e82d898`. The .76 image tag returned HTTP 404, and GitHub has no .76 tag, release, remote release branch or PR at preflight time. Recheck that exact .75 version digest before and after any later publication; moving `latest` or major/minor aliases does not change the prior version-specific artifact.

The latest full operator startup proof identifies `.75` at that exact source on 21 October at 13:28:25 Sydney. The supplied live-memory sample and stale archives retain their limits in CURRENT_STATE.md. The operator reports a failing HDD, but archive causation and current application-failure causes remain unproven; parked archive/MSC work is not reopened. O4 Boost physical stability, O5 reserve policy and Phase 1/2 live proof remain outstanding. Rollback execution is unverified; public artifact availability is not restore proof. Browser/Node tools have the documented Z: launcher error; do not weaken Windows security or obtain credentials from runtime files.

## Publication sequence - separate authorization required

1. Review and commit the exact marker/documentation candidate, push its branch, and record the full candidate commit. Recheck main, tag/release absence and previous image identity; do not tag an unreviewed or changed source.
2. Push `v2.3.65-haos76` at the exact candidate commit only with publication authorization. The tag-only workflow pins `SOURCE_REF` to that commit and builds/pushes amd64 and arm64 images. It also updates `latest` and major/minor image aliases, so tagging is a publication action.
3. Require both architecture builds to succeed. Verify OCI index and platform manifests, version/revision labels, embedded `.source_commit`, and embedded application bytes against exact tagged Git blobs. Record new digests and reconfirm the immutable `.75` version digest. A tag or completed build alone is not a GitHub Release.
4. Only after artifact verification, open and normally merge the version-metadata/documentation PR. Prove its merged tree equals the reviewed candidate before advertising .76 in main's add-on metadata.
5. Publish the GitHub Release for the already verified tag with concise behavior/limitation notes. Confirm release and image identity independently. This sequence does not authorize installation or settings changes.

## Installation and physical verification - separate gates

Before installation establish current installed/source identity, effective settings and observed operator authority, a usable rollback path, supervision and explicit stop conditions. Do not infer current settings from 21 October reports, new defaults or stale archive data. No extra Boost enablement follows from publication.

Monitor-only/dry-run verification uses isolated fake-HA decisions to inspect active Standby/Morning Dump ownership and zero requested import without live dispatch. The Value Gate dry-run flag is advisory, not a global actuator-disable switch. Fault injection stays in fake HA.

Any later supervised live check must capture requested, observed and settled EMS/MSC, import/export ceilings, PV MAX, ESS limits, SoC and measured grid/battery/PV flows with current timestamps and owner/reason. Confirm independent import blocks remain while their owner is active and ordinary recovery remains available when no such owner applies. Service success, a 0.01 kW permission or a trace status alone is not physical settlement. Stop on lost authority/trust, unexpected permission, failed settlement or renewed flapping and retain operator ownership. Boost acceptance and reserve-policy questions remain separate.

Before commit the candidate can be withheld. Any committed rollback is a separately reviewed scoped revert preserving other fixes; any live rollback requires its actual verified restore/reinstall method. No reset, clean, branch/worktree deletion or live edit is part of this preparation.
