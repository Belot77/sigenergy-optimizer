# HAOS .83 published release and verification receipt

**2.3.72-haos83 is published.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.72-haos83)
published 27 October 2026 at 04:13:16 UTC. A fresh postpublication check confirmed
it as the latest stable release. Source/image identity is verified; installation,
live settings and physical acceptance remain separate and were not performed.

## Exact Git and build identity

- Repository: https://github.com/Belot77/sigenergy-optimizer.
- Annotated tag: `v2.3.72-haos83`; tag object
  `d4ef5e979767286b0e2a99b6fc735b2044f7943f`.
- Peeled tag/container source: `51d370a559397e52e2b5f5012733b87fab7a8096`.
- Reviewed/tagged tree: `d0c370d71c1ac965c59de02901b6541b3e15fc96`.
- Source [PR #52](https://github.com/Belot77/sigenergy-optimizer/pull/52) normally
  merged at `140ecf474253d520a503e4dbe1259b4c9c2e4bf4`, parents
  `2c186bb78da9379e08aeb660583d22d5d918ce66` and
  `57949e728a635fd1488f567d04ce8bd916b39fc8`; reviewed/merged tree
  `25c8cd1f98a780be17a392b0a53a4a587a1ba086`.
- Metadata [PR #53](https://github.com/Belot77/sigenergy-optimizer/pull/53) normally
  merged at `ba3642cf66019614da0265e0b62426c124d910a7`, 04:13:00 UTC, parents
  `140ecf474253d520a503e4dbe1259b4c9c2e4bf4` and `51d370a559397e52e2b5f5012733b87fab7a8096`.
  Its merge tree exactly equals the reviewed/tagged tree.
- [Build 40448173242](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40448173242)
  succeeded at the exact source. Job 122004320828 ran 04:09:30-04:11:24 UTC.

Release preparation on `release/2.3.72-haos83` in
`C:/Projects/sigenergy_optimizer-release-haos83` changed exactly five established
version markers (FastAPI, optimizer signature, add-on config, build label, buildstamp)
and seven release/status documents. Canonical Git comparison proved exactly one
version substitution per marker and no other production drift. No tests, dependencies,
workflows, control-contract semantics, permanent instructions or runtime data changed.

Final receipt branch `docs/haos83-publication-proof` in
`C:/Projects/sigenergy_optimizer-haos83-publication-proof` starts at the normal metadata
merge and changes only seven documents. Original unfinished and tests-only worktrees
remain preserved. No reset, clean, overwrite, deletion or history rewrite was used.
Do not use `release.sh`.

## Behavior and retained limits

Morning Slow physical relief previously switched between the slow and full normal
charge caps, which could absorb PV that was being exported. The source fix replaces
that binary physical path with bounded partial increases supported by completed
commands, distinct fresh charge-limit readback and later advancing coherent flows.
Same-target writes retain their epoch. Proposed and committed targets stay separate.
The Morning-only 0.001 kW readback tolerance distinguishes adjacent 0.01 kW commands;
generic ESS, MSC and export settlement tolerances remain unchanged.

Forecast refill still has independent full-normal relief; import charging retains
priority. Manual/Force, policy ownership, fallback, authority and independent limits
remain enforced. See [the complete policy and numerical bounds](MORNING_SLOW_PARTIAL_RELIEF.md).
A maximum charge setting is not a guaranteed charging rate or export floor. This
controller does not establish hard network-limit enforcement. Earlier .82 cost,
O19/O21 fallback, UI logging and passive trace-evidence fixes remain included.
Solar feedback allocation and recurring MSC error causes remain separate open work.

## Offline validation and review

Retained guarded source suite: **1,525 tests / 1,450 subtests passed**, zero failures,
206 warnings, 254.31 seconds. Final source new-module checks passed 21 / 11.
These source results precede release-marker substitutions. Independent source/test
and documentation reviews were GO; the source merge preserved the tested tree.

Release/version/source-pinning/Morning checks: **37 tests / 11 subtests passed**,
zero failures, 202 warnings, 11.53 seconds. Dotenv was disabled before app imports;
StateStore constructors were restricted to memory/isolated temporary paths (0 memory /
28 temporary constructions in this run). Runtime database contents and credentials
were not opened. No full suite was repeated for five single-marker substitutions
or this documentation-only receipt. Independent committed metadata/scope review: GO.

The OCI verifier differs from the verified .82 helper in exactly three release
constants. Both author and independent runs passed all **71 offline synthetic cases**,
including overlay/whiteout, traversal/link, digest and exact mode checks.

## Image and source proof

Version/latest computed index, also checked against registry digest headers:
`sha256:55b20ab7f7e5f6c0c80f9ef0c55fee69537769fe686b8560b2997ea8a9d513b3` (1,609 bytes).
Two runtime descriptors are linux/amd64 and linux/arm64; two recognized attestation
descriptors reference those runtimes. No unexplained platform remains.

| Platform | Manifest SHA-256 | Config SHA-256 | Layers |
| --- | --- | --- | --- |
| linux/amd64 | sha256:85496a1b93d1bcb1b3d9718621017054b640a4af5d9e888261ebfa5a84ff6416 | sha256:abdccf45759d3f369c9322f87af3407f1ed9128234170e4d54d8f342f640b8c2 | 11 |
| linux/arm64 | sha256:bb1dca1334720b1ae5fba4b837b8b8321f9200330cd672ab878378f9f15262ce | sha256:e96385ef72e82ff203ed17a31111b7d6950eedf0884fb601bad75fb56a3991c4 | 11 |

Each runtime manifest is 2,378 bytes; amd64 config is 10,986 bytes and arm64 config
10,987 bytes. All 22 compressed-layer hashes/sizes and uncompressed diff IDs passed.
Both source/version labels and generated source pin match the exact tagged source.
Fourteen final targets per platform match tagged Git/generated bytes:

- `/app/.source_commit`: full tagged source SHA plus LF.
- `/run.sh`: exact 0755 mode, including `--no-proxy-headers`.
- `/app/templates/index.html`.
- `/app/app/main.py`, `optimizer.py`, `models.py`, `routers/api.py`, `state_store.py`,
  `import_topup_ledger.py`, `storage_worker.py`, `earnings.py`, `decision_trace_store.py`,
  `trace_clock.py` and `solar_reentry.py`.

The thirteen non-launcher files are exact 0644. Common final-file fingerprint:
`sha256:982d912d89967eedaf9b8475826c455d618eecc4f58a7aba2a82304f5ff0da66`.
Algorithm: SHA-256 of sorted absolute image path + NUL + file bytes + NUL.
This is scoped final-file and launch-setting proof, not whole-filesystem equivalence
or container execution. Canonical tagged Git bytes, not Windows CRLF worktree bytes,
were used for expectations.

Full layer proof completed at `2026-10-27T04:12:04.119041+00:00`. Default verified TLS and an
anonymous pull token held only in memory were used. Layer bodies were buffered in
memory, not extracted. No container or app was executed. Root independently fetched
index/manifests/configs and derived all Git target hashes, lengths and expected modes,
then compared every file and layer descriptor/diff-ID proof entry. That independent
pass did not redownload all layer bodies; completed at `2026-10-27T04:12:30.962495+00:00`.
Independent image metadata/source proof review: **GO**.

Token-free evidence remains outside Git at
`C:/Users/belot/AppData/Local/Temp/sigenergy-haos83-proof-e0608a001521466095d36332db8b6aa7`.
No tokens, raw logs or binary layers are committed.

| Evidence | SHA-256 |
| --- | --- |
| verify_oci.py | d49d3f093ec9cdbf4f018cac48aadbfbeb4bcec4c34cdd9171dc664ef20d6774 |
| synthetic_checks.py | 7d4b5584eeaa35953ee1424727ca9ce4d0cce4e734ba0dde1b6567e9491a2f83 |
| synthetic-report-final-v2.json | b9b4122c634d91e33e4d60a0e225fd913e00a900a0953c961ad44e11a1a05a99 |
| independent-synthetic-report.json | b9b4122c634d91e33e4d60a0e225fd913e00a900a0953c961ad44e11a1a05a99 |
| oci-proof.json | 90a4ee968949fb78b31a29f3cd60997bc60140140d9edd496662bda75786ec07 |
| independent_check.py | f4092be2e3f6735b8bcf42f5430e84bb9ea71a2457f4f8f79ea9e5c64cebcfa4 |
| independent-proof.json | bba5d19389fa73985f7e0e71daac455db73e473bbb38db67b6ab81e918cc86ab |
| postpublication-proof.json | 1591c1eb37f9d99decd35a8f24e130ec0026eb77c08ff81644862da279ee0f55 |

Fresh postpublication checks passed at `2026-10-27T04:13:44.723405+00:00`. GitHub latest stable
release is .83; version/latest bodies and digest headers match the index above.
Previous immutable .82 remains
`sha256:b286d224ee01bb54b5144cb6b3c642374d4e1c557df9c7074501f05179e51cb3`.
The new tag and release branch were absent before creation; no existing refs were overwritten.

## Installation, live acceptance and rollback

No HA query, install or live settings change was performed. Latest supplied 27 October
startup identifies .81 source `247095a4f9905932c3f5716f3d1be6cee7b3c7f8`; .82/.83 installed
identity is not claimed. Auto update was last confirmed off on 26 October.

Separately approved installation must confirm startup lines:

```text
Runtime signature=2.3.72-haos83
Container source commit=51d370a559397e52e2b5f5012733b87fab7a8096
```

Before physical acceptance, verify actual HA charge-setting resolution at hundredths
of a kW and command/readback/later-flow ordering. Observe sun/load changes, owner
handoffs, Manual/Force takeover, failure/recovery and forecast/import priority. Use
separately approved passive observations and supervised live checks. Offline fake-HA
dry-runs do not imply a global nonapplying inverter mode; financial export-value
dry-run is not a switch disabling all control. Passing tests, image proof and HTTP
success do not establish physical inverter settlement, safety precision or stability.

Source rollback requires an approved scoped revert. Live rollback requires a verified
backup/reinstall method and separate approval. Published .82 remains available at its
unchanged immutable digest; this receipt does not execute rollback or prove a usable
operator backup. Preserve all existing work and never reset, clean or discard it.
