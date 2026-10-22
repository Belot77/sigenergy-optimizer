# HAOS .76 published release and verification receipt

Published 23 October 2026. This receipt establishes the release and artifact identity; it does not establish installation, physical acceptance or rollback readiness.

## Publication and source identity

- Release: [2.3.65-haos76](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.65-haos76), published 22 October 2026 at 22:12:46 UTC (23 October 09:12:46 Sydney); non-draft, non-prerelease, latest.
- Tag/source: `v2.3.65-haos76` at `e70d9ff016a546615367b6d69f4ac4602da7b23c`; tree `42439dff8ee6e02bc503b5e36e05fc965996fc31`.
- PR #32 [normally merged](https://github.com/Belot77/sigenergy-optimizer/pull/32) at `c226c98703263e3a0c5cd5ca811a2d39554ea315` on 23 October at 09:12:14 Sydney. Its parents are PR #31 merge `632a42081d9ff93b270ffcca048604031ec4fed1` and tag source `e70d9ff016a546615367b6d69f4ac4602da7b23c`; merged tree exactly matches the tag.
- GitHub Actions run `39862508030` succeeded at the exact tag source. The multi-architecture build job completed in 2m25s.

## Verified images

GHCR `ghcr.io/belot77/sigenergy-optimizer`, version and `latest` index: `sha256:b7df9f21fce7ef14e7b4f602235486e17b35b710907656dd0b43e796889a6e9a`.

| Platform | Manifest digest | Config digest |
| --- | --- | --- |
| amd64 | `sha256:153257933183c42fa99afdd21a8ab0d48837eb64623e136d7d0a07b3db17269e` | `sha256:2d344f0b9b0f7c67ef60e34fa95cf201ec271016521e0c645906349c5676f916` |
| arm64 | `sha256:8288d84e1bd41858d022caff8b91d11adab998b21f99ee7d1a92985c9be4b161` | `sha256:962363630260823239533ba7bcae81625f11d5b303e01d872bebbc8a043e8945` |

Both architecture labels identify the expected version and revision. In each image, `/app/.source_commit` equals the full source SHA followed by LF; `/app/app/main.py`, `/app/app/optimizer.py`, `/app/app/models.py`, and `/app/templates/index.html` match their exact tag Git blobs. All 11 compressed layer hashes and diff IDs were checked against the content-addressed manifests/configs, with whiteout/override replay. The five-file verification digest covers the source pin plus those four application files, computed over each sorted relative path, NUL, file bytes, NUL: `sha256:9e17b439b6a2dfc56fb238c9118d844d35fcb102e79e841678fdc2b07fd762a1`.

The immutable `.75` version-specific index remains `sha256:ed2a984b457bfddb2b74050d437f98337944076e9144a8d1a19f577d8e82d898`; `latest` now points to `.76`.

## Current installation and acceptance limits

Latest supplied installed startup/source proof remains `.75` / `413e1691bb58e0b942098ab43f44e873df157a2b` on 21 October. No `.76` installation, settings change, Boost enablement or physical acceptance is claimed. O13 code is published but physical behavior remains unverified. O4, O5, O10, O11 and applicable Phase 1/2 live-proof gates remain open. Archive/MSC follow-up remains parked; HDD causation is unproven. Actual rollback readiness is unverified.

## Historical prepublication plan (superseded by this receipt)

The following sections preserve the 23 October release-preparation scope and validation. Their statements that `.76` was a candidate, unpublished or awaiting separate publication are historical and superseded by the publication facts above.

### Source and scope

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

### Retained validation

Retained combined control validation: 1,149 tests / 1,287 subtests passed, zero failures, 206 existing warnings, in 211.18 seconds. Seven focused import-owner regressions passed, including both real settlement waiters and settled/unsettled cases; six settings-UI checks passed separately. Independent control review found no High/Medium blocker. These tests use fake HA and do not establish physical inverter behavior.

Version-only checks: all 16 tests in `tests/test_release_version_consistency.py` and `tests/test_addon_source_pinning.py` passed in 9.43 seconds. Independent normalized comparison proved exactly five single-marker substitutions and no other production changes; the permitted scope is five markers plus six release/status documents. Independent release-metadata review was GO for the local candidate with no blocker. No full-suite repeat was performed for this marker/documentation-only preparation.

### Prior release and operator evidence at preflight

At the 23 October preflight, `.75` / `2.3.64-haos75` was the latest GitHub Release at tag/source `413e1691bb58e0b942098ab43f44e873df157a2b`. The `.75` version-specific OCI index and `latest` then resolved to `sha256:ed2a984b457bfddb2b74050d437f98337944076e9144a8d1a19f577d8e82d898`; the `.76` tag was absent. This is historical prepublication evidence. The `.75` immutable version-specific digest was reconfirmed after `.76` publication and remains unchanged; `latest` now points to `.76` as recorded above.

The latest full operator startup proof identifies `.75` at that exact source on 21 October at 13:28:25 Sydney. The supplied live-memory sample and stale archives retain their limits in CURRENT_STATE.md. The operator reports a failing HDD, but archive causation and current application-failure causes remain unproven; parked archive/MSC work is not reopened. O4 Boost physical stability, O5 reserve policy and Phase 1/2 live proof remain outstanding. Rollback execution is unverified; public artifact availability is not restore proof. Browser/Node tools have the documented Z: launcher error; do not weaken Windows security or obtain credentials from runtime files.

### Historical publication sequence - completed

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
