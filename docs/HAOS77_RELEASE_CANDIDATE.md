# HAOS .77 published release and verification receipt

Published **2.3.66-haos77** on 24 October 2026 at 01:54:00 UTC (12:54:00 Sydney): [GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.66-haos77). Tag/source `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`, tree `33d9b94399f87d27baf787a59403861988182ce9`. Source PR #34 merged at `b4377de9f38d1c305c23a0b1dca9cb509afc1a9f`; metadata PR #35 merged at `81c2752c4e031bb9786ec0d00f1dca4e22c59de9` with exactly the tagged tree.

Combined offline validation: **1,275 tests / 1,305 subtests passed**, zero failures, 206 existing warnings, 226.40 seconds. All 16 release/source-pinning checks passed in 9.35 seconds. Independent source and release review was GO with no High/Medium blocker; reviewers did not execute tests or access HA. Development-host dual-HTTPS corroboration smoke passed. These results establish publication and source identity, not installation or physical acceptance.

## Published source and images

- Combined source: `f4cc6ae80df2d279cfef067f1ddd957916f8b3fc`; [PR #34](https://github.com/Belot77/sigenergy-optimizer/pull/34), normal merge `b4377de9f38d1c305c23a0b1dca9cb509afc1a9f`, exact source tree `a8fc3a00fc7b0a9c0108b5123b5e7850bf1be9dd`.
- Metadata/tag source: `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`; [PR #35](https://github.com/Belot77/sigenergy-optimizer/pull/35), normal merge `81c2752c4e031bb9786ec0d00f1dca4e22c59de9`, exact tag/merge tree `33d9b94399f87d27baf787a59403861988182ce9`.
- [Actions run 40051528465](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40051528465) succeeded for exact tag source; build job ran 01:49:37–01:51:19 UTC (1m42s). Runner action/runtime migration notices were non-blocking; no workflow change is included.
- OCI index and `latest`: `sha256:0a743b4f32c0df7cd87d387f8870435d71ee5330f11c77999305cd665dd9e883`.
- amd64 manifest/config: `sha256:63469d28a72f86375dd32d0f3e51a0b4a9d8835c48448bc7bf7c74df54c5757c` / `sha256:b47381ce0841d523160f3e9dc106e68159a6d28e72a28f7fd763a9cd627a0d80`.
- arm64 manifest/config: `sha256:5d1ea5088b709d2c664d8cb4ceb2f1f7036c002acbe1970187d02cc693a12904` / `sha256:8ce3ea9aef1b2059e094051bc86e5e290c7498c45aad21375d3ca133c36322b3`.

Version and `latest` OCI index: `sha256:0a743b4f32c0df7cd87d387f8870435d71ee5330f11c77999305cd665dd9e883`. Both amd64 and arm64 images, version/revision labels, all 22 compressed layer digests and uncompressed diff IDs, `/app/.source_commit` and eight application files match the exact tag. Nine-file verification fingerprint (source pin plus eight files, sorted relative path + NUL + bytes + NUL): `sha256:19c830fb53506bca02a342882b6da90f5d14e9097f519c0a815dfc9892427774`. The immutable .76 version index remains `sha256:b7df9f21fce7ef14e7b4f602235486e17b35b710907656dd0b43e796889a6e9a`. Normal certificate validation was retained. Anonymous registry read tokens were held only in memory and are not recorded.

Both platform images identify version `2.3.66-haos77` and revision `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`. In each, source pin is that SHA plus LF. Verified Git-blob bytes cover `app/main.py`, `app/optimizer.py`, `app/models.py`, `app/routers/api.py`, `app/state_store.py`, `app/import_topup_ledger.py`, `app/decision_trace_store.py` and `app/trace_clock.py`. Layer verification handles whiteouts and overrides; two non-runnable attestation descriptors were excluded from platform counts.

## Resulting behavior and evidence limits

This release includes O14 configuration-activation transactions, O16 immutable import-cost accounting with direct-control/identity-boundary invalidation, and O10 trace clock recovery. Trace recovery corroborates UTC through two fixed HTTPS origins, durably preserves historical record bytes before active retention resumes, and retains gap evidence. It can take a normal 15-minute persistence interval after successful checks. Missing decisions cannot be reconstructed. Unknown accounting can pause applicable automatic battery sales until a newly covered day; independently qualified PV-only and Manual/Force semantics remain separate.

Configuration activation is serialized with existing control transactions, queued mutation authority is rechecked, and identity-bound evidence is retired. Direct validated Manual/ESS requests and actual accounting-identity changes make accounting permission unproven before writes/activation, including A→B→A and between-tick import changes. Rejected validation and unchanged identities retain existing evidence. Manual targets and independent safety/authority/settlement protections remain intact.

See [ledger design and data-aware rollback limits](IMPORT_LEDGER_INTEGRITY.md) and [clock proof, preservation and retry behavior](TRACE_CLOCK_RECOVERY.md). Trace history copies preserve full segment bytes and the status captured by a completed preservation attempt. Earlier failed starts may already have rewritten guard/session metadata; original pre-upgrade boot/session/monotonic fields are not guaranteed. Gap flags remain sticky.

## Operator installation and remaining gates

The operator reported .76 installed after HAOS 18.3 restoration onto a replacement SSD on 24 October. Last full supplied startup/source proof remains .75; .77 installation is left to the operator. No live HA, inverter, battery, export settings or Boost enablement changed during this release. O15 storage execution and O17 conditional ingress work remain separate; O5 policy, O11 parked follow-up and applicable physical acceptance gates remain open. Original O14/O16 worktrees and the frozen trace candidate remain preserved.

Install `2.3.66-haos77` through the normal HA update flow with a usable backup/restore path. Expected startup runtime is `2.3.66-haos77`; expected Container source commit is `7aa712f72ca2c0467e6740e3cb0f2191ba8d077e`. Trace recovery needs HTTPS access to Google and Cloudflare plus free space for its bounded preservation copy. It resumes on the normal persistence schedule when checks pass; no mode, entity or clock adjustment is required.

Startup/restart, relevant configuration activation or direct-control changes can leave import history unknown and pause applicable automatic battery sales beyond the current day. Never fabricate complete coverage. Protected trace epochs remain outside normal downloads and automatic deletion. If recovery cannot corroborate UTC or safely preserve bytes, it stays guarded while optimizer control continues independently.

After new ledger tables are written, an older binary is not automatically ledger-safe. Do not delete, truncate or reprice rows to force compatibility. On unexpected automatic behavior retain operator/Manual ownership and preserve the full database; any downgrade needs a separately reviewed binary- and data-aware restore/reinstall plan. Any source rollback is a scoped reviewed revert preserving the other fixes and protected history. No live downgrade or installation was performed here.
