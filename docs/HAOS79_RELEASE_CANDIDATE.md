# HAOS .79 published release and verification receipt

**2.3.68-haos79 is published.** [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.68-haos79)
was published on 26 October 2026 at 08:08:21 Sydney (25 October 21:08:21 UTC).
It is the latest stable release. Publication and image/source identity are
verified; HA installation, live settings and physical acceptance are separate.

## Exact Git and build identity

- Tag: `v2.3.68-haos79`.
- Tag/container source: `ea516ef6cabd9918dbea675694a9de3aa207c8af`.
- Approved/tag tree: `8e7e6cf6cdcbb6196383352c2a351f055aed5912`.
- Metadata [PR #41](https://github.com/Belot77/sigenergy-optimizer/pull/41), normal
  merge `44419af295a47be24d5f06af3ed7cba83b2f27bb`, at 08:07:43 Sydney
  (25 October 21:07:43 UTC). Its parents are source merge `fbe3bfcc...` and
  release source `ea516ef...`; its tree exactly equals the approved tag tree.
- [Tag workflow 40233491965](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40233491965)
  completed successfully for that exact tag/source. Build job ran from 08:01:25
  to 08:03:51 Sydney (25 October 21:01:25 to 21:03:51 UTC).

Reviewed O2/O6 source `ad0e89fdc72d9bb6d52b03aada0456e629bd2963` normally
merged through [PR #40](https://github.com/Belot77/sigenergy-optimizer/pull/40)
at `fbe3bfcc14312952748f1991eec7836977adfcb5`, at 07:31:05 Sydney on 26 October
(25 October 20:31:05 UTC). That source merge retained the exact reviewed/tested
tree `6a70c7c55321372969d87e522e57e27a2271b0ce`.

Release preparation changed only five established version markers and seven
documents. Markers are FastAPI version in `app/main.py`, `_RUNTIME_SIGNATURE`
in `app/optimizer.py`, and add-on `config.yaml`, `build.yaml`, `buildstamp.txt`.
No other production/test/configuration-value/workflow change was bundled.
This final receipt branch `docs/haos79-publication-proof` in
`C:\Projects\sigenergy_optimizer-receipt-haos79` starts at metadata merge
`44419af...` and changes those seven documents only. No branch was deleted;
all original workspaces, unfinished work and protected data remain preserved.

## Published behavior and bounds

O2 still closes immediately after a failed strict aggregate budget, then requires
fresh qualification before Solar reacquisition. First admission and independent
export priorities remain intact. O6 qualifies only restrictive Solar charging
after completed genuinely owned relieved Morning charging at the normal safe
bound. Solar export and raw Morning priority remain intact. Both require each
PV/load report stream to advance across at least 30 seconds, plus 30 seconds
monotonic time, with 60-second per-source age/gap limits. Existing hard closures,
hardware limits, provider authority, Manual/Force, import restrictions and observed
MSC settlement remain effective. See [engineering evidence](SOLAR_REENTRY_STABILITY.md).

This packages the reviewed behavior. It adds no minimum-charge policy,
forecast-fill guarantee, reserve/price adjustment or further stabilization rule.
Waiting may increase normal charging and reduce useful export. Longer cycles,
physical sensor causes and inverter behavior remain unproven.

## Offline validation

Retained merged-source validation: **1,415 tests / 1,380 subtests passed**, zero
failures, 206 existing warnings, 241.93 seconds. Focused controls passed 165 / 184
in 14.97 seconds. Independent source/helper/test reviews are GO. The later single
test EOF newline cleanup is AST-identical; no logic changed. All **16 release /
version/source-pinning checks passed in 9.83 seconds**. Canonical comparison
proved exactly one marker substitution per established file, with no other
production/test/workflow drift. Windows CRLF conversion was normalized only for
comparison; files were not mass-reformatted. Independent metadata/documentation
review was GO. No full suite was repeated for marker/docs preparation or receipt.

## Registry and source verification

Registry: `ghcr.io/belot77/sigenergy-optimizer`. Version `2.3.68-haos79` and `latest`
resolve to index:

`sha256:cbaa5f68e4830737abba90666e486b9db848b3a853d1c9138c33a93f3b02bdad`

| Platform | Manifest | Config |
| --- | --- | --- |
| linux/amd64 | `sha256:55e89402174ad2dc0b4ea47d107fd44227a12ff3494dd718d6dba8badf3e0a55` | `sha256:899e59af4b1939c8668d81addaebf2df4deb69cdc54c4f1d0b889290e3cd5cfd` |
| linux/arm64 | `sha256:cb0b99dc6b5cbd1958339ea85e7dec1876e5cf691f3683d7e26b803cfb0fb264` | `sha256:1f23dd4fb1a96e4c444e985df666bbc7a3d76dbff65035bb4c7de47cc8638fe1` |

Both configs identify version `2.3.68-haos79` and revision `ea516ef...`.
Each has eleven layers: **all 22 compressed hashes/sizes and uncompressed diff IDs
were verified**. In-memory overlay reconstruction checked fourteen target files
per platform against exact tag bytes:

`/app/.source_commit`, `/run.sh`, `/app/templates/index.html`, and eleven under
`/app/app/`: `main.py`, `optimizer.py`, `models.py`, `routers/api.py`,
`state_store.py`, `import_topup_ledger.py`, `storage_worker.py`, `earnings.py`,
`decision_trace_store.py`, `trace_clock.py`, `solar_reentry.py`.

The source pin is the full exact tag source plus LF. `/run.sh` matches the add-on
launcher at mode 0755 and includes `--no-proxy-headers`. Both configs use
`Cmd=["/run.sh"]`, no entrypoint, and working directory `/app`.
Shared fourteen-file fingerprint:

`sha256:a5a6945fc54c5a872a97b717d377cb88b57c6c0e7d8a9704174bc33324f2e3f8`

Fingerprint algorithm: SHA-256 of sorted absolute image path, NUL, file bytes,
NUL for each target. Two explicitly annotated unknown/unknown attestation
descriptors were excluded; no unexplained runtime platform was ignored.

Verification completed at 08:05:52 Sydney (25 October 21:05:52 UTC). Final helper
SHA-256: `6057a2940f35e3831edb9858f13e2656acbc25325a0d90f81fa766c9b37380e1`.
Complete local proof JSON SHA-256:
`7949d65737c0b18ef9e3d056f7d05505ed4162269203608ad4036e2d0bcb39d3`.
Raw verification artifacts and image layers remain outside Git.

Independent helper/proof review is **GO**. All **68 synthetic cases** passed and
were independently rerun, covering descriptor binding, whiteouts/opaque overlays,
unsafe target writes, ancestor/alias/link handling and modes. The reviewer also
independently fetched registry metadata and reconciled both configs/manifests,
all 22 layer descriptors/diff IDs, and all fourteen Git target hashes/sizes/modes.
Complete layer-blob validation relies on the reviewed helper execution; the
reviewer did not duplicate full layer downloads. Normal verified TLS and anonymous
registry access were used. No filesystem extraction or container execution occurred.
This proves the scoped source/image identities, not full-filesystem equivalence,
runtime behavior, HA compatibility in situ or physical inverter acceptance.

Previous [2.3.67-haos78](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.67-haos78),
source `3ccf99cc69a4586715aadcbdd2f1282aeea77bf0`, retains immutable index
`sha256:35292feb279a4b33e4c86f5482d690a9704c91d7178038b115c3bc434ead991a`.
Version/latest .79 and immutable .78 were freshly rechecked before PR #41 merge.
A separate public-only check at 08:13:30 Sydney on 26 October (25 October
21:13:30 UTC) again confirmed both indexes, GitHub latest stable release, exact
tag source and approved tree. No full layer download was repeated.

## Historical preparation and publication sequence

Local preparation on `release/2.3.68-haos79` in
`C:\Projects\sigenergy_optimizer-release-haos79` started from verified main
`fbe3bfcc...`. At preflight, .79 tag, release, metadata PR and GHCR version were
absent; .78 was latest and its immutable digest matched. Those absence checks
were historical preflight, superseded by completed publication above.
The operator then approved the exact tree, metadata commit/push/PR, tag/build,
source/digest verification, normal metadata merge, GitHub release and final receipt.
The exact metadata source was tagged, both images verified, PR #41 merged with
that exact tree, then the GitHub release published. Branch pushes alone do not
trigger the tag-only build workflow. The operator confirmed **Auto update off**
on 26 October before publication; no direct HA query is claimed.

## Acceptance, limits and rollback

The operator reported mostly .77 then .78 on the morning of 25 October. Supplied
traces lack exact runtime/source identity; last full supplied startup/source proof
remains historical .75. No installed .79 build or physical acceptance is claimed.
No HA installation or live settings were performed by this publication/receipt.

Before separately approved installation, retain a usable binary- and data-aware
backup/restore plan. Preserve the full database, ledger intervals/coverage and
trace history/protected clock epochs. Do not truncate, reprice or fabricate
history, or assume an older binary can safely consume newer ledger data.
The previous immutable .78 image remains available; that alone does not establish
a data-compatible downgrade. A source rollback needs a scoped reviewed revert.
No live downgrade or data restoration is performed here.

After an approved installation, expect exactly:

```text
Runtime signature=2.3.68-haos79
Container source commit=ea516ef6cabd9918dbea675694a9de3aa207c8af
```

Monitor-only/dry-run proof should compare raw candidates, pending/qualified states,
per-source timestamps, final owners and requested limits without actuator writes.
Separately approved supervised live proof must compare actual flows/readbacks
across O2 budget failure/recovery and O6 relieved-Morning handoffs, retain immediate
hard closures and verify provider loss, independent limits and MSC transitions.
Stop on unsafe discharge/export/import, lost authority, repeated failure or renewed
harmful switching and return to the operator's chosen safe mode.

O18 fill/minimum-charge strategy, O5/O9 reserve/configuration review, broader O6
depletion/floor questions, parked O11 and existing live/Boost acceptance remain
open. Publication grants no new live-control or Boost-enable permission.
