# 2.3.76-haos87 publication receipt

## Publication and source identity

Release `v2.3.76-haos87` was published at 2026-10-29T22:49:07Z (30 October 09:49:07 AEDT): [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.76-haos87). Metadata [PR #68](https://github.com/Belot77/sigenergy-optimizer/pull/68) merged normally at `77be45d70b665283a49ce249111f1fa6c6732c69` at 2026-10-29T22:48:37Z, with parents `4ebdb82daf8a3c41efbab1f12366f413e382fbb2` and `6a43077be1a59512bf44b1bb1c41aed410992c37`; merge tree `de893cf6a0bae925025d22eb0099b5b6beb00b8f`. Annotated tag object `9a3ff193b8a79791a3eb333f75463365e939a9ba` resolves the tag to source `6a43077be1a59512bf44b1bb1c41aed410992c37` and tree `de893cf6a0bae925025d22eb0099b5b6beb00b8f`.

Build [40968005213](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40968005213) succeeded at the exact source on 2026-10-29T22:45:29Z (30 October 09:45:29 AEDT).

## OCI verification

Version and `latest` resolve to index `sha256:b0e703483652a3b5ead7a1eb968f10dee2571c9d613f6d72e29a210c01d790f6`. The amd64 manifest is `sha256:9fb2e71617d7e943fd64aff45dbe011fb18c1642022dd8e25dbb539aa6e11051`; arm64 is `sha256:2e36eabf2820d78eabeff254fcdcd61ae8e680375c8b55a3adb041aa4e7d95fa`. Both platforms passed 11 layer/diff-ID checks and 15 expected source byte/mode checks. Source fingerprint: `sha256:a80c8d7e425ec222b03ff731f0e9c50f810440f43776b96aa22131b163b999f2`.

The author verified all layer bodies and expected source bytes/modes. Independent registry metadata and source-expectation checks are GO; the independent verifier did not redownload all compressed layer bodies. Offline OCI verification passed 73 synthetic cases. Post-publication checks for the release/tag, remote source, normal merge parents/tree, version/latest index and previous immutable index are GO. The previous .86 index `sha256:68ae9242488169b25525c53ef106eae92197a3f398aa3210344a43c6601b9359` is unchanged.

## Shipped changes and validation

PR #66 separates provider-payload validity from daylight ownership: a valid below-horizon generation can establish or advance provider freshness, while the independent daylight gate still blocks Solar ownership and dispatch. PR #67 adds bounded recovery for two accepted restrictive-settlement origins: an accepted ordinary export-close whose later report misses its own short wait, and a restrictive fallback after delayed proof of an accepted discharge target. The recovery retains current identity/cause binding and request-correlated close/MSC proof; it does not change generic startup MSC-pending behavior. Its 15-second budget includes internal awaits; the event loop caps pending idle waits, including debounce, at one second, while actual cycles may take longer. Existing three-second primary wait, Boost 120-second requalification, Dump 15% floor and Boost 80% target are unchanged.

Retained guarded full suite: 1,676 tests / 1,672 subtests, zero failures. Focused five-module validation: 86 tests / 136 subtests. Independent safety validation: 11 tests / 28 subtests. Release version/source-pinning checks: 16 passed; six runtime modules: 96 tests / 141 subtests; offline OCI verifier: 73 cases. These are software and image checks, not physical acceptance.

## Installation and remaining evidence

The .87 image is published and ready for installation; no .87 installation has been verified. The expected runtime identity is `2.3.76-haos87` at source `6a43077be1a59512bf44b1bb1c41aed410992c37`. The last supplied installed identity remains .86 (`2.3.75-haos86`, source `74f21875e9a30e561d78644c4a5b0791becccc83`) at 29 October 09:55:23 AEDT. Auto-update was last confirmed off on 29 October. No HA installation or settings action was performed as part of publication.

Engineering/policy follow-up remains for O4 Boost qualification-retention policy and stability, O5 reserve/load/price assumptions, O6 broader floor/depletion behavior, and O9 overlapping ownership/status semantics. Published O2/O6/O18 corrections still await live acceptance. The O11 recovery in .87 addresses only its reproduced accepted restrictive-settlement cases; unexplained legacy MSC/application outcomes remain parked, not universally fixed. O20's non-positive-price Morning Dump redesign is parked; the old O8 observation gap is irrecoverable; short Demand Window import spikes are deferred, not confirmed as a defect.

After separate authorization, live proof should capture exact startup identity, dawn provider freshness separately from daylight ownership, Morning-to-Solar/export/charge progression and deadline behavior, accepted close/MSC requests with later correlated reports, and Evening Boost qualification under its existing 120-second rule. Installation, settings changes and supervised live acceptance are separate actions. Safest rollback is to retain immutable .86 and follow a reviewed reinstall/restore procedure; restore readiness itself has not been demonstrated. Each publication report should state what shipped, remaining engineering/policy work, missing live proof and the next authorized action.