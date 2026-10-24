# Decision trace clock recovery

Local candidate on `fix/trace-clock-recovery`, based on `e387010b83f7b017460870b1b456025f49f7e0a5`. This changes passive diagnostics only. It does not change optimizer decisions, HA services, settlement clocks, settings, or the system clock. Publication, installation and live acceptance require their separate evidence.

## Failure and safe recovery

The old implementation retains a prior UTC anchor after a reboot or backup restoration, but pairs it with a new monotonic reference. A wall clock six days ahead of that obsolete anchor cannot converge within the 300-second continuity tolerance. Capture remains suspended and successful flush calls can leave an unchanged stale archive. This reproduces a mechanism consistent with the operator's restored-backup report; it does not establish hardware causation.

A different or unknown OS boot now requires independent UTC corroboration even when the apparent downtime is within 300 seconds. A healthy restart on the same verified OS boot continues using its persisted monotonic anchor without network access. A same-boot bad wall-clock sample remains suspended; agreement with its retained monotonic timeline can still recover ordinary continuity.

When continuity cannot be established, only an archive worker attempts corroboration, at most once per 900 seconds in a running process. A disposable Python subprocess queries these two fixed public HTTPS origins:

- Google: `https://www.google.com/generate_204`
- Cloudflare: `https://www.cloudflare.com/`

Requests use HEAD, independent random nonces, and no-cache/no-store headers. Normal certificate and hostname verification remain mandatory. Redirects and environment proxies are disabled. No private configuration, entity identifiers, authentication, trace rows or response bodies are sent or stored. Each request must finish within three monotonic seconds; the pair has a ten-second budget, with a twelve-second parent process timeout that also bounds stuck DNS and child cleanup.

Both successful responses need exactly one canonical GMT HTTP Date. Missing/malformed/duplicate Dates, nonzero or malformed Age, redirects, 304, TLS/network failures and timeouts fail closed. Each Date must fall within five seconds of the wall-clock request bracket; source agreement is limited to five seconds plus the pair's elapsed time. Wall time must track monotonic elapsed time within one second during each request and the full pair. The parent validates the public source identities, dates, elapsed bounds and whole-probe clock stability again.

HTTP Date is a server approximation. Two independent authenticated origins provide corroboration of current UTC; stable local samples alone do not establish UTC. The implementation never bypasses TLS to compensate for a badly wrong host clock. If corroboration is unavailable, the old archive remains suspended and is retried; installation cannot guarantee recovery on a network that blocks either source. Optimizer control continues independently. Downloads never trigger corroboration.

## Preserved evidence and crash safety

Before a new UTC anchor can authorize any append or age-based deletion, all recognized existing segment files are copied byte for byte into `decision_trace/clock-history/<epoch>/`. This includes incomplete trailing bytes and corrupt records. Repair of those active files is deferred until preservation succeeds. The snapshot also retains the exact status bytes captured by the completed preservation attempt, when present, and a manifest with source names, byte counts, committed byte ranges, SHA-256 hashes, prior UTC anchor and corroboration provenance. Earlier failed starts may already have rewritten active guard/session metadata; this does not guarantee the first pre-upgrade boot ID, session ID or monotonic fields. Full decision-segment bytes and sticky gap evidence remain protected.

The epoch ID derives from stable prior-anchor and segment metadata/content, excluding the changing session/status bytes. Copying uses a deterministic `<epoch>.pending` directory. Files and directories are synced, then the complete directory is atomically published and every expected file/hash is validated. Existing published snapshots are verified before reuse after interruption. Only then is the new anchor/status atomically saved. An interrupted copy, full disk, failed sync, unsafe symlink, inconsistent snapshot, failed status commit or excess resource limit prevents acknowledgement and pruning. A restart sees either the old suspended anchor or the new anchor backed by a complete preserved epoch. Pending history is never treated as ordinary compaction temporary data.

The active archive then resumes its normal 24-hour retention and identity-based duplicate suppression. Historical `possible_gap` and reasons remain sticky. Future rows left in the live deque by a bad clock are rejected; lost cycles are not reconstructed. Fresh persistence resumes on the normal diagnostic schedule, which can take one interval after initialization.

Preserved epochs are outside normal downloads, compaction and retention. They remain on disk across restarts and upgrades; they are not automatically deleted. Normal downloads contain the active 24-hour view and retain the gap indicator. Historical inspection is a separate local, privacy-aware operation. With the default state database location, the path inside the add-on is `/data/decision_trace/clock-history/<epoch>/`; a custom `STATE_DB_PATH` places `decision_trace` beside that database. Through separately authorized local add-on filesystem or backup access, copy the complete published epoch directory, including `manifest.json`, and verify file lengths/SHA-256 hashes against that manifest before inspection. A `.pending` directory is incomplete evidence, not a published epoch. This patch adds no history-download API. Treat preserved traces as runtime data and never commit or upload them to source control. No runtime data was used for these tests.

Preservation is bounded to 25 segments and 512 MiB per recovery attempt. It needs additional disk space for one complete copy. A partial pending copy can use disk space until a successful retry completes it. If limits or free space prevent preservation, persistence remains suspended and the diagnostic failure is logged. Published snapshots are not overwritten to repair validation failure. Corroboration failure and recovery are logged without private response details.

## Validation and operational checks

A public metadata-only smoke check on 24 October validated both fixed HEAD endpoints and the full subprocess/parent proof path. Cloudflare `/cdn-cgi/trace` rejected HEAD with 404 during preparation; the final fixed root endpoint returned 200 with a fresh canonical Date and no Age. This check establishes availability from the development host at that time, not access from HAOS.

The tests-first baseline produced two failures: a restored six-day archive never recovered with the supplied proof seam, and a short reboot incorrectly cleared uncertainty without proof. The focused trace suites subsequently passed 84 tests / 36 subtests with 202 existing warnings in 11.22 seconds. Tests use temporary synthetic files and mocked external services, not HA or real public endpoints.

Coverage includes same/different/unknown boots and persisted attestation requirements across repeated restarts; stale restored archives; unavailable/disagreeing/cached/malformed/TLS/slow time evidence; worker-only probes, retry limits, download isolation and cancellation during a worker probe; full-byte corrupt history; interrupted copy/publication/status sync; restart reuse and snapshot tampering; disk/resource failures; future-clock rows; interrupted append and duplicate suppression. Existing lifecycle and download tests retain event-loop, cancellation, archive-lease, retention and control-isolation coverage. These checks do not prove live installation or physical behavior.

For monitor-only, dry-run and live-control modes alike, verification is diagnostic: confirm exact installed source, allow the existing flush interval, check current record timestamps, sticky gap status and the preserved history manifest. No control mode, entity or clock adjustment is needed for this patch. When corroboration fails, retain the archive and inspect the bounded diagnostic warning and host time/network health through separately authorized access.

The safe prepublication rollback is to withhold this branch. After integration, use a reviewed scoped revert of the trace change; leave preserved epochs intact. A rollback may restore the old suspension behavior. No rollback here rewrites production traces or changes live controls.
