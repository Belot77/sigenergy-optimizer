# HAOS .83 local release candidate

## Status and exact baseline

Version: `2.3.72-haos83`; proposed tag: `v2.3.72-haos83`.
Approved local branch: `release/2.3.72-haos83` in
`C:/Projects/sigenergy_optimizer-release-haos83`.
Base main: `140ecf474253d520a503e4dbe1259b4c9c2e4bf4`.
Base tree: `25c8cd1f98a780be17a392b0a53a4a587a1ba086`.
Source [PR #52](https://github.com/Belot77/sigenergy-optimizer/pull/52) merged
normally at that main commit, with parents
`2c186bb78da9379e08aeb660583d22d5d918ce66` and
`57949e728a635fd1488f567d04ce8bd916b39fc8`. Its reviewed and merged trees match.

This is local metadata/documentation preparation, not a published release.
No .83 commit, branch push, tag, image build, metadata merge, GitHub release,
installation or live setting change has been authorized or performed.
Do not use `release.sh`. Original unfinished work and the separate tests-only
Morning characterization remain preserved.

The latest published release was freshly verified as **2.3.71-haos82**:
[release and image proof](HAOS82_RELEASE_CANDIDATE.md), tagged source
`af174d2745f283e3f2e297d57e72d58fada62cb2`. That receipt remains historical.
Latest supplied startup evidence identifies .81 source
`247095a4f9905932c3f5716f3d1be6cee7b3c7f8`; installed .82/.83 identity is not
claimed. Auto update was last confirmed off on 26 October, not freshly checked.

## Source behavior and retained limits

Morning Slow physical relief previously restored the full normal charge cap from
a binary threshold/counterfactual decision. Reported command/readback/flow sequences
showed repeated 2/21 kW switching and export collapsing near zero. The merged fix
permits only bounded Morning partial charging after completed command, distinct
setting readback and later coherent-flow evidence. Counterfactual export is now
diagnostic only for this path. Forecast refill keeps independent full-normal
relief, and import charging retains priority.

The source fix includes separate proposal/committed command state, same-target
epoch retention, stale/lagged/report-regression checks, bounded retry and current
authority/failure resets. Matching 0.001 kW setting evidence distinguishes
adjacent 0.01 kW commands. Generic ESS, MSC and export settlement tolerances stay
unchanged. See [the complete policy and verification contract](MORNING_SLOW_PARTIAL_RELIEF.md).

A maximum charging setting is not a guaranteed charging rate or export floor.
HA reporting precision and physical inverter response/stability remain unverified.
Neither this controller nor its 15/0.5 kW operator reference establishes hard
network-limit enforcement. Solar feedback allocation and recurring MSC error
causes remain open; this candidate does not claim to fix them. Prior .82 cost,
O19 fallback-import and O21 house-serving recovery behavior stays included.

## Narrow release preparation

Exactly one `2.3.71-haos82` to `2.3.72-haos83` substitution is intended per marker:

- `app/main.py`: FastAPI version.
- `app/optimizer.py`: optimizer runtime signature.
- `sigenergy_optimizer_addon/config.yaml`: add-on version.
- `sigenergy_optimizer_addon/build.yaml`: `io.hass.version` label.
- `sigenergy_optimizer_addon/buildstamp.txt`: buildstamp.

Remaining changes are release/status docs only. Canonical Git comparison with
the base, undoing exactly these single substitutions, proves no other production
drift. This proof was repeated independently. Tests, dependencies, workflows, permanent instructions,
configuration defaults and control-contract semantics remain unchanged.

## Offline validation and independent review

Retained source full suite: **1,525 tests / 1,450 subtests passed**, zero failures,
206 warnings, 254.31 seconds. Final source new-module checks passed 21 / 11,
202 warnings, 1.25 seconds. Independent source/test and documentation reviews
were GO for local readiness. The merged tree exactly equals that tested tree.
These are source results before release-marker substitutions, not image/runtime
or physical acceptance.

Final candidate release/version/source-pinning and Morning checks passed
**37 tests / 11 subtests**, zero failures, 202 warnings, in 11.53 seconds:
`test_release_version_consistency.py`, `test_addon_source_pinning.py` and
`test_morning_slow_partial_relief.py`.

Dotenv was disabled before app imports. StateStore constructors were restricted
to memory or isolated system-temporary paths; guards recorded 0 in-memory and
28 temporary-path constructions. Runtime database contents and credentials were
not opened. No full suite was repeated for five mechanical version substitutions.
Independent release metadata/documentation review is **GO for local preparation**.
All candidate source behavior remains the already reviewed PR #52 implementation;
publication, image identity and physical acceptance remain unverified.

## Publication gates outside this approval

A separate reviewed publication approval is required before creating a metadata
commit, branch/PR, exact source tag, image or GitHub release. The unchanged build
workflow runs on `v*` tag pushes and publishes `latest`, so a tag itself crosses
the publication boundary. Do not push one during local preparation.

Any later publication must verify the exact tag commit, both runtime platforms,
version/source labels, image digests and final source/launcher bytes and modes.
The normal metadata merge must preserve the exact reviewed/tagged tree. Only then
may approved release and receipt actions complete. No .83 build or image proof
exists yet; do not reuse .82 proof as .83 evidence.

Installation and live settings require separate approval. Before acceptance,
verify installed runtime/source identity, actual HA charge-setting resolution,
request/readback/later-flow ordering, behavior through sun/load changes, owner
handoffs and recovery. Offline fake-HA dry-runs are not an assumed global
nonapplying inverter mode. The financial export-value dry-run setting is not a
switch disabling all control. Use separately approved passive/monitor observations
and supervised live checks; source tests alone do not prove physical acceptance.

## Rollback and safety

Current rollback is to withhold this uncommitted candidate. Published .82 and
live HA are untouched. Any later source rollback should use an approved scoped
revert; any live rollback needs a verified reinstall/backup method and separate
approval. Never reset, clean, delete, overwrite or discard existing work.
No tokens, raw logs, runtime databases or backups belong in the release commit.
