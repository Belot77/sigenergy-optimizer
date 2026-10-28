# HAOS 2.3.74-haos85 publication receipt

## Published source and build

The [GitHub release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.74-haos85) was published at **2026-10-28T06:39:02Z** (17:39:02 AEDT). Build **40644593573** succeeded.

Source PR #60 merged normally at `aefba54dddcaace1e3b318bbf6cca2a282d6c3a3`, tree `7bbc4d998081bf8fa606c71a9392930bba09a0b4`. Metadata PR #61 merged normally at `ca569f1b8b44e892f2eec471cae573c175f36ad5`; parents are the source merge and release commit `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1`. The metadata tree is `3ed6e5a677f1af72cfac503be91fe725375ea15b`. The annotated `v2.3.74-haos85` tag object `8fc43ef082498766561acb15157175e48906adb3` points to source commit `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1` and that tree.

The successful build produced linux/amd64 manifest `sha256:033e75f038393164f0d856925dd2da8c2ded84d8dc324e388b49b391eb79a37f` and linux/arm64 manifest `sha256:4345a9faed15a000144b529e83713adbe951de820dc72520376a195e5412d494`. Each platform has 11 verified layers and 15 source byte/mode checks. Both platform proofs match source fingerprint `sha256:ad811c36d2a1f6708cbc9e5a6badfd53f4bdea73221e7df205f438db8e44d4be`.

At publication and post-publication checks, the version and `latest` tags resolved to index `sha256:68a15730cd18592d153a27f29e4e801c5581c28680e86c299cdd9f478c120329`. The previous .84 index remained `sha256:ce9f9c1abf04effd9ef33a0bfccc29282f9f81356f617cebd8a6b61e3c36f112`. Independent registry metadata and expected source bytes/modes review is GO. The independent reviewer did not redownload full layer bodies; the author-run OCI verifier checked all 22 layers and final source bytes/modes. Its offline synthetic suite passed **73 cases**, zero failures.

Proof records were retained at `C:/Users/belot/AppData/Local/Temp/sigenergy-haos85-proof-a49jks85`: `oci-proof.json`, `independent-proof.json` and `postpublication-proof.json`.

## Source changes and validation

PR #60 integrates these reviewed changes:

- Solar fill progress can receive a bounded charging allowance ahead of immediate export, subject to existing ownership, provider, coverage, deadline and safe-capability gates. The allowance is not a physical minimum.
- Only a completed total in the same trusted context can survive a pure time/SoC baseline rebase. Proposed, pending, failed, fallback, cancelled or invalidated work cannot create that receipt; downward feedback remains binding.
- Solar Dip accepts a current-read unchanged persistent mode helper with an old nonfuture report. Availability, freshness, expected value, finite chronology, device/Remote EMS and flow limits remain required.
- Accepted unchanged pending MSC/close epochs avoid duplicate writes only while the original reader, control/source identity and freshness lease remain valid. Expiry, contradiction or replacement requires a new latest-boundary dispatch. Pending stays uncommitted and intentional waiting remains distinct from genuine errors.
- Reserve diagnostics explain nominal-energy shortfalls. Raw reserve floors, current-load model, bounded HA helper and price policy are unchanged. Passive diagnostics grant no authority.

The five release markers were updated in `app/main.py`, `app/optimizer.py`, `sigenergy_optimizer_addon/config.yaml`, `sigenergy_optimizer_addon/build.yaml` and `sigenergy_optimizer_addon/buildstamp.txt`. No additional control behavior, runtime setting, dependency or workflow changed.

The source full suite passed **1,632 tests / 1,606 subtests**, zero failures. Independent source/test and documentation/scope reviews were GO.

Release validation used two disjoint guarded runs: **16 version/source-pinning tests** and **72 runtime-focused tests / 175 subtests**, all passing. The runtime run had 202 warnings and used 195 isolated temporary stores. A full suite was not repeated for the five metadata literals and receipt documents. The metadata commit changed the five established version markers from .84 to .85 and status documents; it added no further control behavior, setting, dependency or workflow change.

A charging allowance can reduce immediate export, but it is not a physical minimum and cannot guarantee absorption, deadline fill, full SoC or stable export. Provider baseline/advance and expiry, ownership, Manual/Force and independent restrictions remain binding. The changes do not establish a universal fix for historical MSC errors.

## Installation and acceptance status

Automatic updates were explicitly confirmed off on 28 October. Available operator startup evidence identifies installed .84 at 15:00:56 AEDT on 28 October. The expected .85 runtime identity is signature `2.3.74-haos85` with container source commit `72bd1fdfdc824b019a5eba43f991e3ef0ee5bbe1`; this matches the published tag/source pin and still requires startup verification. No .85 startup/source identity, settings change, HA query or physical acceptance is established by this receipt.

Before treating .85 as operationally accepted, obtain the actual runtime/source identity and supervised charging, export, MSC, Boost and provider evidence with defined stop conditions. Monitor requested caps and owners alongside independent setting reports, advancing coherent flows, provider/command chronology and outcomes. Service-call success and offline tests do not prove physical settlement. The immutable .84 index is retained, but an operator backup/reinstall rollback path has not been demonstrated.

## Risk and rollback

The Solar policy can allow less immediate export and relies on existing sensor, forecast, load, capability and deadline assumptions. The simulated trajectory is not a hardware model or proof under PV deficit. Preserve the current source and immutable .84 image while live acceptance remains open. Any source rollback requires a reviewed scoped revert that preserves unrelated work; do not claim a live reinstall path until it is demonstrated. All nine original/unfinished worktrees matched their recorded canonical hashes after publication. Protected database size and modification time also matched; contents were never read. Runtime databases and archives must remain untouched.
