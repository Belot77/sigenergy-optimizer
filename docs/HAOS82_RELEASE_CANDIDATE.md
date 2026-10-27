# HAOS .82 published release and verification receipt

**2.3.71-haos82 is published.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.71-haos82)
published 27 October 2026 at 00:24:22 UTC. The fresh postpublication check below
confirmed it as the latest stable release. Source/image identity is verified;
HA installation, live settings and physical acceptance remain separate.

## Exact Git and build identity

- Repository: https://github.com/Belot77/sigenergy-optimizer.
- Annotated tag: v2.3.71-haos82; tag object
  bd54b02602302240ad9191ef1da510070d14b2aa.
- Peeled tag/container source: af174d2745f283e3f2e297d57e72d58fada62cb2.
- Tag tree: f858b292fd4e6d8b9b67c044bb314cbb9f9455de.
- Source [PR #49](https://github.com/Belot77/sigenergy-optimizer/pull/49) normally
  merged at ce70f4ca41be0992ab899e56f2ba3d20ef0482f7, with parents
  623bd5d95f757de1074cabc4ee25570f2ef80cfd and
  d8fef951b24fc3de95d983effbdd18066d905c6d; reviewed tree
  3dbca50c9b014e181db6c1505f1b352523d438f9.
- Metadata [PR #50](https://github.com/Belot77/sigenergy-optimizer/pull/50) normally
  merged at 4c3a2116d112f3eda97a950eb4893d32a0d77adf, 00:24:18 UTC, with parents
  ce70f4ca41be0992ab899e56f2ba3d20ef0482f7 and af174d2745f283e3f2e297d57e72d58fada62cb2.
  Its merge tree exactly equals the tag tree.
- [Build 40425641785](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40425641785)
  succeeded at the exact source. Build job 121930588286 ran 00:19:22-00:21:28 UTC;
  image push completed at 00:21:19 UTC.

Release preparation on release/2.3.71-haos82 in
C:/Projects/sigenergy_optimizer-release-haos82 changed only five established
version markers: FastAPI, optimizer runtime signature, add-on config.yaml,
build.yaml and buildstamp.txt; plus six release/status documents.
Mechanical Git-blob comparison confirmed exactly one version substitution per
marker file and no other source drift. No tests, dependencies, workflows,
control contract, permanent instructions or runtime data changed in preparation.

Final receipt branch docs/haos82-publication-proof in
C:/Projects/sigenergy_optimizer-haos82-publication-proof starts at the normal
metadata merge and changes only README, CHANGELOG, AI_HANDOVER, CURRENT_STATE,
ROADMAP and this receipt. Original unfinished worktrees remain preserved.
Do not use release.sh.

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
The earlier .80 UI log-retention fix and .81 passive allocation evidence remain
included; no additional logging or archive behavior changes are introduced here.

## Offline validation

Retained guarded source suite: **1,504 tests / 1,439 subtests passed**, zero failures,
206 warnings, 256.19 seconds. Focused checks passed 24 / 30 in 10.86 seconds.
Dotenv was disabled; StateStore constructors were limited to memory or isolated
temporary paths. The full run recorded 75 memory and 1,811 temporary-path
constructions. These numbers are construction counts, not memory sizes.
Independent source, strengthened-test and documentation reviews were GO.

Release marker/source-pinning and selected cost/fallback regressions passed
**55 tests / 30 subtests**, zero failures, 202 warnings, 23.12 seconds. Guards
recorded one memory and 59 temporary-path constructions. Independent release
marker/documentation review was GO. No full suite was repeated for the five
single-marker substitutions or this documentation-only receipt.

The copied OCI verifier differs from the prior helper only in three release
constants and an exact 0644 check for non-launcher targets. Existing exact 0755
launcher checks remain. Author and independent runs each passed all **71 offline
synthetic cases**, including valid mode acceptance and invalid execute/write-mode
rejection. The .81 helper reported 0644 non-launcher modes but did not enforce exact 0644;
this verifier does. The .81 receipt also described buffered downloads as streamed;
these layer bodies were buffered in memory.

## Image and source proof

Version/latest computed index, also checked against registry digest headers:
sha256:b286d224ee01bb54b5144cb6b3c642374d4e1c557df9c7074501f05179e51cb3 (1,609 bytes).
The two runtime descriptors are linux/amd64 and linux/arm64; two recognized
attestation descriptors reference those runtimes. No unexplained platform remains.

| Platform | Manifest SHA-256 | Config SHA-256 | Layers |
| --- | --- | --- | --- |
| linux/amd64 | sha256:661a9772772e2c1598b322a807ba380d56f18589989c8d4d88450ab7398577ff | sha256:b9264808eed6da2842d752f9d49284c7c26c756862460bf6cde6d50f209fc259 | 11 |
| linux/arm64 | sha256:5cb8217632ef25d2bf03a5f5fe06b92607b1aa23b23d4e65f7b94ae1a29b3d52 | sha256:0212305be50f5c13ce0c5e893c3e6aaebc71245fd47c158b90e345b19a21aec3 | 11 |

Each runtime manifest is 2,378 bytes; each config is 10,985 bytes.
All 22 compressed-layer hashes/sizes and uncompressed diff IDs passed.
Both platform source/version labels and generated source pin match the exact tag.
Fourteen final targets per platform match tagged Git/generated bytes:

- /app/.source_commit: full source SHA plus LF.
- /run.sh: exact 0755 mode, including --no-proxy-headers.
- /app/templates/index.html.
- /app/app/main.py, optimizer.py, models.py, routers/api.py, state_store.py,
  import_topup_ledger.py, storage_worker.py, earnings.py, decision_trace_store.py,
  trace_clock.py and solar_reentry.py.

The thirteen non-launcher targets are exact 0644. Their common fingerprint is
sha256:ab5740f3b8558247d59f02f71128b363bfebf72e9246defd27706d16b02755ea.
Algorithm: SHA-256 of sorted absolute image path + NUL + file bytes + NUL.
This verifies scoped final files and launch settings, not whole-filesystem
equivalence or runtime container execution.

Full verification completed at 2026-10-27T00:22:21.515810+00:00.
It used default verified TLS and an anonymous pull token held only in memory.
Layer bodies were downloaded and verified with buffering in memory. No files
were extracted and no container or app was run. Independent review separately
fetched index/manifests/configs and derived all Git target hashes, sizes and modes,
then compared every proof entry. That reviewer did not redownload all 22 layer
bodies. Independent final image proof review: **GO**.

Token-free local evidence is outside Git at
C:/Users/belot/AppData/Local/Temp/sigenergy-haos82-proof-20261027-owp8k6ou.
No tokens, raw logs or binary layers are committed.

| Evidence | SHA-256 |
| --- | --- |
| verify_oci.py | 6ed3e18d70409c6d1d3799cf94b98db75d88a8ec3cb81e27faa59907c163914d |
| synthetic_checks.py | 7d4b5584eeaa35953ee1424727ca9ce4d0cce4e734ba0dde1b6567e9491a2f83 |
| synthetic-report-final-v2.json | a8c8af1654628af7ca89210005746f37e8481d9b55577822849d1ae6b4cc610a |
| oci-proof.json | 78650410e8132097e61ce60063f8003893447d9ed62f040c760a48bb1fc3c9ab |
| expected-source-targets-af174d.json | 7728c1db3c7469201ec65d0bcf950a7ac107797f2c3f8b18643acf57658c5957 |
| independent-metadata-af174d.json | b25861c586cebd232000fbca7df9db3e31cf1b475eed417afcbf1a42627787f4 |
| independent-proof-comparison-af174d.json | 900bd895c2a98aef8a6ef908afdd437dae3d739a33eb07a15a8616d997a4f799 |
| postpublication-proof.json | 1fb6ec010c2819de6751d7930806c1d0eb3a2f63a06c7eb2f9ba8f62675474fa |

Fresh postpublication checks passed at 2026-10-27T00:24:50.480074+00:00.
The GitHub latest stable release is .82. Version/latest bodies and registry
digest headers match the index above. Immutable .81 remains
sha256:e3f58087681c0c08ab53b0b8263387e8388d0916796aea326fdf9344ba821526.
The .82 image/tag/release were absent at preflight; none was overwritten.

## Installation and rollback

The operator explicitly approved completing preparation, publication and the final
receipt commit/PR/normal merge. Installation and live settings remain separate.
Supplied 27 October startup identifies .80 source
acb576747e808e927bdd7d12346c507da9b188b6. No installed .82 identity is claimed.
Auto update was last confirmed off on 26 October; no direct HA query was made.

After separately approved installation, verify both startup lines:

Runtime signature=2.3.71-haos82
Container source commit=af174d2745f283e3f2e297d57e72d58fada62cb2

Use new rows after verified startup. Monitor-only and dry-run observations must
precede separately approved supervised live checks. Check known import floors
versus unknown warnings, current authority and Demand evidence, reserve/floor
protections, requested limits, report times and measured flows. Exercise safe
failure/recovery observations and distinguish primary failure from fallback
success. Stop on lost authority, unproven settlement or unsafe behavior.

Published .81 source/image remain available, but availability does not establish
the operator's usable backup or reinstall method. Operational rollback remains
unverified. Preserve runtime data and historical evidence. Any source rollback
requires a reviewed scoped new revert, never resets, force pushes or tag rewrites.
