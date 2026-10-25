# HAOS .80 local release candidate

Prepared 26 October 2026. Proposed version **2.3.69-haos80**, tag
`v2.3.69-haos80`. Workspace `C:\Projects\sigenergy_optimizer-release-haos80`,
branch `release/2.3.69-haos80`, from freshly verified main
`bcd9fe51f7303467ed8e463805c30284110e6a95`.

**Local preparation only.** No commit, push, tag, image, GitHub release,
installation or live settings change is part of this checkpoint. The future
tag/container source is the separately approved metadata commit, not the source
merge above; no future source SHA or image digest is invented.

## Verified source and metadata scope

Reviewed logging source `512601da8083f88a260e343dd980c2c14183c814` normally merged
through [PR #43](https://github.com/Belot77/sigenergy-optimizer/pull/43) at
`bcd9fe51f7303467ed8e463805c30284110e6a95` at 10:00:11 Sydney on 26 October
(25 October 23:00:11 UTC). Both parents and reviewed/tested tree
`70805bd6f1f49eb47654b7c686c6a8d904371d13` were verified. Source and unfinished
workspaces remain preserved; no existing work is reset, cleaned or discarded.

Release scope is exactly five one-marker substitutions: `app/main.py` FastAPI
version, `app/optimizer.py` runtime signature, add-on `config.yaml`, `build.yaml`
and `buildstamp.txt`. Six documents change: README, CHANGELOG, AI_HANDOVER,
CURRENT_STATE, ROADMAP and this candidate. No other production/test/control-contract,
configuration-value, Dockerfile or workflow change is included.

## Before and after; limits

Previously, routine successful HTTP INFO messages could occupy all 500 UI log
records. The supplied download contained only successful requests across 84 seconds.
The merged filter now excludes recognized successful 2xx `httpx` INFO request
messages from the UI handler only. Non-2xx, unknown formats, other loggers and
warning/error messages keep existing behavior. Filtering fails open on unknown
formats/errors and does not mutate shared records. Console and other handlers,
global logger levels and inverter control remain unchanged. Custom/lowercase
method tokens outside the recognized pattern remain visible rather than hidden.

The newest-first ring still holds at most 500 retained records in process memory.
Later retained records can evict older errors, and restart clears the ring.
This is neither persistent logging nor recovery of lost records. Console logging
volume remains unchanged. This does not explain the supplied trace's 65 application
failures / 59 unsuccessful fallbacks, alter MSC settlement or retries, or establish
that any particular HA/inverter command failed. No raw log/trace files enter Git.

## Validation

Tests-first reproduction: 16 failures / 10 passes. The refined logging module
passed all 30 cases independently. Combined logging, HA-client, ingress,
application-outcome and fallback checks passed **122 tests / 10 subtests**, zero
failures, 202 existing warnings, **68.94 seconds**. Independent code/test/docs
review is GO. Syntax, exact six-file source-fix scope, whitespace/EOF and API AST
comparison passed; removing only the added filter class and handler attachment
restores the original API AST. All 500 supplied successful request messages were
recognized offline without copying raw logs into Git.

All **46 release/source-pinning/logging checks passed** with zero failures,
202 existing warnings, in **10.69 seconds**: sixteen release/source-pinning checks
and thirty logging cases. Canonical comparison confirms exactly five one-marker
substitutions plus six documents, with no other source/test/workflow drift.
Independent metadata/documentation review is GO. No full-suite
repeat is claimed: the .79 full-suite result is historical, and this narrow
logging fix has the focused validation above.

## Publication preflight and required image proof

Latest published remains [2.3.68-haos79](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.68-haos79),
source `ea516ef6cabd9918dbea675694a9de3aa207c8af`, published 26 October at
08:08:21 Sydney (25 October 21:08:21 UTC). Its verified version/latest index is
`sha256:cbaa5f68e4830737abba90666e486b9db848b3a853d1c9138c33a93f3b02bdad`.
At Git preflight the .80 tag, remote release branch and destination folder were
absent. Public GitHub checks also found no .80 tag/release/remote branch. At
10:07:04 Sydney on 26 October (25 October 23:07:04 UTC), anonymous GHCR checks
returned HTTP 200 for `2.3.68-haos79` and `latest`, both with the recorded .79
index digest verified against response SHA-256, and HTTP 404 for `2.3.69-haos80`.
Normal TLS validation was retained; the anonymous token stayed in memory only.
No package-management permission was needed. Recheck conflicts and current main
immediately before any approved publication.

Publication requires separate approval of exact metadata tree, commit/push/PR,
tag-triggered image build, normal metadata merge, GitHub release and final receipt.
Branch pushes do not trigger the tag-only workflow. Preserve .79's immutable
version index. Verify both amd64/arm64 version/revision labels, source pin,
compressed-layer hashes/sizes, uncompressed diff IDs and safe overlay reconstruction
before advertising .80. Do not reuse .79's proof as proof of the new image.

Fourteen target files per platform must match exact new tag bytes:
`/app/.source_commit`, `/run.sh`, `/app/templates/index.html` and eleven under
`/app/app/`: `main.py`, `optimizer.py`, `models.py`, `routers/api.py`,
`state_store.py`, `import_topup_ledger.py`, `storage_worker.py`, `earnings.py`,
`decision_trace_store.py`, `trace_clock.py`, `solar_reentry.py`.
The source pin is exact tag SHA plus LF. Preserve launcher mode 0755,
`--no-proxy-headers` and established container entry configuration.

Publication changes `latest` and the version offered to HA. Auto update was last
confirmed off by the operator on 26 October before .79 publication; no new direct
HA query is claimed. Installation and live settings remain separately controlled.

## Acceptance and rollback

No installed .80 identity or physical acceptance is claimed. The operator reported
.78 previously; last full supplied startup/source proof remains historical .75.
After separately approved installation, compare `Runtime signature=2.3.69-haos80`
and `Container source commit` with the exact tag source assigned at publication.

A read-only UI/download check should show retained app diagnostics without routine
successful polls, while add-on console output remains unchanged. Check that HTTP
errors and warnings remain visible. Controlled error cases belong in offline/fake-HA
tests; do not provoke live actuator or HTTP failures merely to test logging.
Read-only/monitor/dry-run comparisons should retain existing control outcomes,
request frequency, authority and settlement behavior. Live acceptance for previous
control fixes remains separate; this diagnostic update adds no control permission.

Before installation, retain a usable binary- and data-aware rollback plan, preserving
database/ledger coverage and trace history/protected clock epochs. An immutable
older image alone is not proof of data-compatible downgrade. Withhold this local
uncommitted metadata to roll back preparation; any later source rollback needs a
scoped reviewed revert. No live downgrade or data restoration is performed.

O18 fill strategy, O5/O9 reserve/settings review, broader O6 depletion/floor
questions, parked O11 and existing live/Boost acceptance remain open. Nothing here
changes battery floors, import/export policy, physical relief tolerances or retries.
