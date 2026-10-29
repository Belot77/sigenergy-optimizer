# 2.3.76-haos87 release candidate

Status: local release preparation after source PR #67. Release-specific metadata
commit, tag, image build, publication and independent publication verification
remain pending. No future source digest, tag object, image digest or build result
is asserted here.

## Source and changes

Source PR #67 merged normally at
`4ebdb82daf8a3c41efbab1f12366f413e382fbb2` (parents
`0e0fa8a5e2779d318390124a34ff9e1b8cabd4ed` and
`067dc1789ba31202956af3c6a88d79f24cc38c2e`), tree
`ec7c0fb0f33adba86568df4d2003f553e93fdcba`. PR #66 supplies the
provider-daylight correction; PR #67 adds accepted restrictive-settlement
recovery. The five established marker files are prepared for runtime
`2.3.76-haos87`.

Settlement recovery handles two originating cases: an accepted ordinary
export-close whose later report misses its short observation wait, and a
restrictive fallback after proof of the accepted discharge target was delayed. A
renewed retry stays tied to its originating cause/current identity and gets a new
close-request boundary and budget. Generic startup MSC-pending semantics remain
unchanged. The 15-second monotonic budget starts before the first restrictive
dispatch and includes awaits; it does not cancel an in-flight request or prove
physical response. Pending event-loop idle waits, including debounce, are capped
at one second, but actual cycles may be longer when HA/service/read awaits take
longer. The ordinary three-second primary target wait remains; already accepted
close/MSC requests are not duplicated while pending, and fresh correlated
close/MSC proof remains mandatory before permissive recovery.

The provider change permits coherent valid provider generations below the horizon
to establish or advance freshness, while the separate daylight gate continues to
block Solar ownership and dispatch. Existing generation, same-day coverage,
high-water, reconnect and deadline rules remain. Evening Boost's 120-second
requalification and Dump 15% / Boost 80% settings are unchanged.

## Validation and remaining status

The merged source retained a guarded full-suite result of 1,676 tests / 1,672
subtests, zero failures (206 warnings, 282.10 seconds); focused validation passed
86 tests / 136 subtests and independent safety validation passed 11 / 28.
Release version/source-pinning checks passed 16 tests in 9.81 seconds with no store use. Six runtime modules passed 96 tests / 141 subtests in 7.69 seconds (202 warnings; 168 isolated temporary stores; zero memory or rejected constructions). Dotenv, SQLite and StateStore guards were active; protected database metadata was unchanged and its contents were not read. The offline OCI verifier passed 73 synthetic cases. Independent publication-receipt review remains pending.

Published .86 remains the latest verified release until .87 publication checks
complete. The last operator-supplied identity confirms .86 runtime
`2.3.75-haos86`, source
`74f21875e9a30e561d78644c4a5b0791becccc83`, at 29 October 09:55:23 AEDT. This
does not establish .87 installation. Auto-update was last confirmed off on 29
October. Charge/readback/export limits, live settlement and sustained physical
Boost behavior remain unverified. Open engineering follow-up includes
intermittent MSC/application outcomes and Solar allocation/budget and Boost
stability questions; this release does not claim universal resolution of those
issues.

Safest rollback is to withhold the candidate or use a reviewed scoped revert;
keep immutable .86 available. Begin with isolated, non-live verification.
Installation, settings changes and supervised live acceptance are separate
actions and require their own authorization.
