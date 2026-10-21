# HAOS .75 release candidate and supervised acceptance plan

Prepared 21 October 2026. Status: release metadata/documentation preparation is in progress; `.75` is not yet published or installed. The latest published release remains `.74` / `2.3.63-haos74`.

## Source and scope

Target version: `2.3.64-haos75`; planned tag: `v2.3.64-haos75`.
Release branch: `release/2.3.64-haos75`; workspace: `C:\Projects\sigenergy_optimizer-release-haos75`.
Base: PR #28 merge `2ea64b4aaa4da1cb61627e74e53761662df41e5e`, completed 21 October at 02:12:13 UTC. It contains fix commit `3494cb2d15585107721a63871a2d3f78ebeaa81d`.
The approved candidate includes the Evening Boost reserve-trust correction and the re-entry qualification described below. The version marker and release-documentation changes are separate from the merged control fix.

The five synchronized version markers are:

| File | Marker |
| --- | --- |
| `app/main.py` | FastAPI `version` |
| `app/optimizer.py` | `_RUNTIME_SIGNATURE` |
| `sigenergy_optimizer_addon/config.yaml` | add-on `version` |
| `sigenergy_optimizer_addon/build.yaml` | `io.hass.version` |
| `sigenergy_optimizer_addon/buildstamp.txt` | clone-cache build stamp |

Each must be `2.3.64-haos75`. Marker changes should be the only production-file differences in release preparation. `tests/test_release_version_consistency.py` checks synchronized markers and clone-cache invalidation. `tests/test_addon_source_pinning.py` checks that tag resolution is pinned, missing/mismatched source fails closed, and image metadata records the checked-out source. Verify exact normalized source diffs and scope before commit. Do not use `release.sh`; it stages broadly and can commit, tag and push.

## Behavior and validation

The O12 reserve-trust correction requires both existing `load_power_trusted` and `sunrise_observation_trusted` evidence for Evening Boost eligibility and uses both observations in the overnight reserve calculation. The approved O4 re-entry rule requires fresh qualifying load-report timestamps spanning at least 120 seconds and at least 120 seconds of local monotonic elapsed time. These are minimums, not a promised admission time. Load reports must advance monotonically; a report gap over 60 seconds or local time over 60 seconds since the last advancing report resets qualification. Cached reports cannot mature the interval. Sunrise retains its existing trusted-future-horizon check and need not advance. Any gate failure or wall-clock/monotonic-clock rollback resets Boost context; existing failure closures stay immediate. Admission states distinguish permission from physical operation, and retaining qualification requires successful automatic application completion or verified MSC-pending state; generic no-op success is insufficient. O4 stability/live acceptance remains open, and O5 reserve policy remains unresolved. No new economic, SoC or power thresholds, safety hold, or reserve-policy redesign is included; the approved 120/60-second timing rules are the stated behavior change.

Final local offline validation of the combined source passed 1,142 tests / 1,287 subtests with zero failures, 206 warnings, in 209.04 seconds. The final focused suite passed 90 tests / 103 subtests with 202 warnings in 4.73 seconds. Release-specific checks passed all 16 tests in 9.89 seconds; exact normalized verification confirmed five synchronized marker replacements. Coverage includes fake-HA decisions, awaited-settlement races and simulated verified-MSC-pending outcomes; these do not prove physical operation or settlement. Independent review was GO for the local candidate with no High/Medium blockers; this is not a live GO. The pre-release `app/optimizer.py` file SHA-256 was `bd4a7a8debae41e134cb9082e3240a3dedbd742ea119a64626bc9f45e4303ce0`; the release version marker changes that file, so this is not the candidate Git revision.

## Publication sequence

The approved sequence avoids advertising an image version before that image exists:

1. Align the five markers and release documentation on this branch. Run the two release consistency tests and the source-pinning suite; compare the normalized marker/documentation diff with the reviewed base and confirm no control-source drift.
2. Commit the release candidate and push its branch. Create and push `v2.3.64-haos75` at that exact candidate commit to trigger `.github/workflows/build.yml`. The workflow runs only on `v*` tag pushes, passes `SOURCE_REF=${{ github.sha }}`, and builds/pushes `linux/amd64` and `linux/arm64`; it also updates version, major/minor and `latest` image tags.
3. Wait for the workflow to succeed for both architectures. Verify the OCI index and both platform manifests; confirm the version and full source-revision labels and embedded source identity match the exact tagged candidate. Record all resulting digests and preserve the `.74` tag/image identity. A tag or successful build alone does not publish a GitHub Release.
4. After image verification, open and normally merge the version-metadata/release-documentation PR. Verify the merged tree exactly matches the reviewed candidate tree; do not merge source changes in this metadata PR.
5. Publish the GitHub Release for the already-built tag with concise notes describing the two Evening Boost safeguards and their limits. Confirm `.75` is latest only after publication succeeds.

Remote preflight on 21 October found `main` at the PR #28 merge, with no open PRs or conflicting next-version tag/branch. Recheck identities immediately before tagging. The `.74` release remains latest and must remain available as the prior published version.

## Operator state and installation gate

On 21 October the operator reported `.74` installed, Evening Boost off and add-on auto-update off. The last supplied startup/source proof remains `.73` at `46d36358d38137231dff081176a372c3aa1f4cee`; exact `.74` runtime source and live acceptance have not been verified. The operator did not supply a rollback method. Direct Home Assistant access and an executable rollback path are not established in this workspace. Do not infer access, exact installed source or restore readiness from publication/image availability.

Publication can proceed independently of HA access. Keep Evening Boost disabled until `.75` is published, installed and separately verified under supervised live acceptance. Before installation, establish actual About/runtime/source identity, effective settings and current authority; confirm the operator's update preference, usable saved configuration/backup and executable rollback path. The published `.74` artifact is not by itself proof of restore capability. If access or rollback readiness cannot be verified, stop before installation while preserving the published release.

Begin with monitor-only/dry-run checks of load-report spacing and monotonic advancement, resets after gaps/clock rollback/failed gates, startup/manual-return delays, immediate failure closure, and automatic-application/verified-MSC-pending retention. These checks must not write controls and do not establish physical behavior.

During the already-authorized supervised live acceptance, once operational facts and access are verified, confirm exact `.75` source/runtime, Boost and auto-update settings, current operator authority, and timestamped requested, observed and settled EMS/MSC/export/import/PV/ESS limits and measured flows. Confirm the qualification behaves as documented, higher-priority owners remain unaffected, and a failed gate closes Boost promptly. Stop on lost trust/authority, unsafe discharge/export, failed settlement, unexpected control ownership or renewed flapping; stop Boost and retain manual ownership. Do not claim unobserved scenarios or policy questions are closed. No installation or live acceptance is claimed in this candidate document.
