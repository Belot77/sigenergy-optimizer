# HAOS .78 published release and verification receipt

Published **2.3.67-haos78** on 24 October 2026 at 07:57:03 UTC (18:57:03 Sydney):
[GitHub Release](https://github.com/Belot77/sigenergy-optimizer/releases/tag/v2.3.67-haos78).
Tag/container source `3ccf99cc69a4586715aadcbdd2f1282aeea77bf0`;
tree `2542e3600ef3280f1dd166953804f708f8b1137d`.
This establishes publication and image/source identity, not installation or physical acceptance.

## Source and release sequence

- O15/O17 reviewed source `6deb930da9cfc8e03724405a1bb42f95937f3f25`:
  [PR #37](https://github.com/Belot77/sigenergy-optimizer/pull/37), normal merge
  `e12da76d9c11e6d92286ecaf9c98a7c3497e0872`, exact tested tree
  `5a63925bc07dc6ccf93a3b9d5f4f5b2e57d0b2b7`.
- Release branch `release/2.3.67-haos78` in
  `C:\Projects\sigenergy_optimizer-release-haos78` starts from that merge.
  Release commit/tag source changes exactly five synchronized version markers and
  seven release/status documents; no other production/test/workflow drift.
- [Actions run 40075754355](https://github.com/Belot77/sigenergy-optimizer/actions/runs/40075754355)
  succeeded for the exact tag. Build job: 07:51:05–07:53:08 UTC
  (18:51:05–18:53:08 Sydney); build/push step: 1 minute 30 seconds.
- Images were verified before [metadata PR #38](https://github.com/Belot77/sigenergy-optimizer/pull/38)
  normally merged at `5b84d7f976e9d9db07fbeefd98aa90089a2f40be` on
  24 October at 07:56:24 UTC (18:56:24 Sydney). Merge tree equals the exact tag.
  GitHub release publication followed at 07:57:03 UTC.
- Publication and final receipt documentation were explicitly approved.
  Installation and live settings changes remain separate operator actions.
  All original unfinished worktrees remain preserved.

## Image proof

- Version and `latest` OCI index:
  `sha256:35292feb279a4b33e4c86f5482d690a9704c91d7178038b115c3bc434ead991a`.
- amd64 manifest/config:
  `sha256:a277a41e9f080e1e5e1d4f3455e8abfebba77e21a2aec2ac3922316862b824b5` /
  `sha256:bb04b71cc3eb67ff92d6a5e65a9e1127ac0efc20a02a7dd2154a5cc583829fc3`.
- arm64 manifest/config:
  `sha256:e18dad21e678b40be6faea16a2211d9819791ec3b12a00c9255701c205ec1fb9` /
  `sha256:717a56ca69b22d037c61630fa4abbbc002bfd59fa2973230cdc6a306716864b1`.
- Both platforms identify version `2.3.67-haos78` and exact source
  `3ccf99cc69a4586715aadcbdd2f1282aeea77bf0`. All 22 compressed layer
  hashes/sizes and uncompressed diff IDs match their manifests/configs.
- Thirteen-file fingerprint (SHA-256 of sorted absolute image path + NUL +
  file bytes + NUL):
  `sha256:b84b39d53f7a6e9581d49d4a77d3b2a9643b1bf704f1edb825ef1e734a5fc9a1`.
- Immutable .77 version index remains
  `sha256:0a743b4f32c0df7cd87d387f8870435d71ee5330f11c77999305cd665dd9e883`.

Verified files per platform: `/app/.source_commit`, `/run.sh`,
`/app/templates/index.html`, and ten files under `/app/app/`:
`main.py`, `optimizer.py`, `models.py`, `routers/api.py`,
`state_store.py`, `import_topup_ledger.py`, `storage_worker.py`,
`earnings.py`, `decision_trace_store.py` and `trace_clock.py`.
The pin is the full SHA plus LF; all other bytes match exact Git blobs.
Image command is `["/run.sh"]` with no entrypoint override; the executable
launcher contains `--no-proxy-headers`. The root Dockerfile's separate
Uvicorn command has the same flag; no root-image build is claimed.

Read-only verification replayed layers with whiteout/override handling without
filesystem extraction. Independent helper review required rejecting every
non-directory ancestor of a target. That correction was independently reviewed
GO and the complete corrected proof passed; the preliminary proof is superseded.
Version/latest and immutable .77 indexes were rechecked at completion.
Two non-runtime attestation descriptors were excluded from platform counts.
Normal TLS validation was retained; anonymous registry tokens stayed in memory.

## Validation and resulting behavior

The exact merged-source suite passed **1,355 tests / 1,305 subtests**, zero failures,
206 existing warnings, 232.02 seconds; focused checks passed 126 / 8
(202 warnings, 13.54 seconds). All 16 release/source-pinning checks passed in
9.58 seconds. Independent source/test/docs and release-metadata reviews were GO
with no High/Medium blocker. Reviewers did not rerun tests or access HA.
No full-suite repeat was run for marker/documentation-only preparation.

O15 isolates production SQLite work on one bounded worker while the event loop
owns ledger observations and exact acknowledgements. Busy, failed or unconfirmed
storage retains unknown-cost protections. API outcomes distinguish rejected
admission from accepted mutations with unconfirmed outcomes; accepted writes
can complete after timeout. The API wait bound is per database wait, not per
endpoint. Threads cannot interrupt wedged OS I/O.

O17 requires actual Supervisor peer `172.30.32.2` and nonempty
`X-Ingress-Path` for the existing ingress key exemption. Supported launchers
disable proxy-header rewriting. Normal HA login and existing strict/key/read/status
policies retain their boundaries; custom proxies use the existing key path.
Installed exposure/flags and independently exposed listeners remain unverified.

The .77 transaction, immutable ledger and trace clock-recovery protections remain
intact. Unknown history can pause applicable automatic battery sales beyond the
current day; independent PV-only and Manual/Force semantics remain separate.
No price/reserve threshold, export limit, MSC settlement or control authority
policy changed. Ordinary runtime Logs availability and historical HDD/trace/MSC
causation are not established as fixed.

## Operator acceptance and rollback

The operator reported .76 installed after replacement-SSD restoration on 24 October.
Last full supplied startup/source proof remains .75. The fresh 24 October archive
shows partial persistence only, without runtime identity or another-restart proof.

Install the published release through normal HA procedures
with a usable backup/restore method. Verify runtime `2.3.67-haos78` and
container source `3ccf99cc69a4586715aadcbdd2f1282aeea77bf0` against the tag before acceptance.
Keep Boost off during initial identity, configuration and cadence checks.
Monitor-only/dry-run checks should verify ordinary HA ingress access, denied
spoofed-header requests using synthetic authorized clients, bounded storage
failure behavior, fresh traces and honest unknown-cost state without changing
inverter controls. UI authentication checks need no live dispatch.

Any supervised control acceptance must retain current authority, independent
limits, Manual/Force priority, observed MSC settlement and explicit stop conditions.
O5 reserve policy, O11 parked follow-up and applicable live gates remain open.

Withhold installation until the operator is ready to verify the published build.
Any source rollback requires a separately reviewed scoped revert; preserve the
published tags and image identities. Preserve the complete database, O16
interval/coverage data, trace segments and protected clock epochs.
Do not delete, truncate, reprice or fabricate coverage. An older binary is not
automatically ledger-safe; any installed downgrade needs a binary- and data-aware
restore/reinstall plan. No live installation or downgrade is performed here.

See [storage boundaries](STORAGE_EXECUTION_ISOLATION.md),
[ingress boundaries](INGRESS_TRUST_BOUNDARY.md),
[ledger rollback limits](IMPORT_LEDGER_INTEGRITY.md) and
[trace recovery](TRACE_CLOCK_RECOVERY.md). Passing tests does not prove physical
settlement, installed topology, disk health or recovery across another restart.
