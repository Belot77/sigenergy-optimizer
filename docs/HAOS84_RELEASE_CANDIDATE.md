# HAOS .84 release candidate and verification receipt

Version: **2.3.73-haos84**. Publication is explicitly authorized and in progress;
no installation, HA query or live settings change has been performed.

## Source and behavior

Source [PR #57](https://github.com/Belot77/sigenergy-optimizer/pull/57), head
`4b71f54a66fd4556675b9289f6f003463de4d971`, normally merged at
`61f17278499467ee79c7c4a4e1c7733517154400`. This includes the reviewed pending-MSC
epoch correction, qualified unchanged-ceiling maintenance and bounded passive
settlement evidence. Charge-readback PR #55 and Boost-helper PR #56 are also
included. See [the control contract](CONTROL_CONTRACT.md#reuse-of-proven-msc-settlement-for-unchanged-surplus-permission).

A completed request candidate grants no permission alone. Later fresh real-reader
and joint authority/mode/export proof must match the original request boundaries,
identity and unchanged bounded target. One-time startup anchoring requires a final
live exact-target guard and later readback. This path never reopens a reduced
ceiling or increases its target. Continuity, config, authority, failure and
cancellation invalidate evidence. Charging owners are rechecked after added
proof awaits. Pending retry/latest-request rules, three-second waits and
independent protections remain unchanged.

## Offline validation

The final guarded source suite passed **1,574 tests / 1,520 subtests**, zero
failures, 206 warnings, 268.32 seconds. Focused checks passed 56 / 41. Dotenv was
disabled and StateStore guards allowed only 75 memory / 1,914 isolated temporary
constructions. Initial broader failures led to stronger actual-reader provenance
and initialization of new fields in a lightweight event-loop fixture; existing
Solar/event-loop assertions remain intact. Independent safety/source and docs
reviews: GO. Reviewers did not independently rerun the application suite.

Author and independent OCI-verifier synthetic runs each passed **73 offline
checks**, including the added diagnostics file target. Real-reader private
provenance was confirmed absent from FastAPI/dataclass encoding using a
synthetic token. Protected database contents were never opened.

Release/version/source-pinning and focused MSC/Boost checks passed **93 tests /
104 subtests**, zero failures (202 warnings, 18.81 seconds). The same isolation
guards allowed 0 memory / 116 temporary StateStore constructions.

## Publication procedure and pending proof

Five established version markers change from .83 to .84 (FastAPI, runtime,
add-on version, build label and buildstamp). No other production change belongs
to this release metadata step. The exact annotated tag `v2.3.73-haos84` will point
to its reviewed metadata commit, which is also the expected container source.
Image proof must verify both platforms, compressed layers, diff IDs, source pin,
launch settings and all **15 final targets per platform**, including
`/app/app/msc_settlement_evidence.py`, against canonical tagged Git bytes.
Do not use `release.sh`. Publication/merge/build/image identities will be appended
in the final receipt. Previous immutable .83 must remain unchanged.

## Installation and remaining limits

Installation and live-control settings require separate authorization. Confirm
startup `Runtime signature=2.3.73-haos84` and the exact tagged container source
when installed. Observe request/report chronology, failures/recovery, authority
and owner handoffs, and requested limits versus actual flows. Successful service
calls, software proof and passing tests do not prove physical settlement.

This addresses reproduced software cases and adds evidence for other failures;
it does not establish every historical MSC cause or repair genuinely unavailable
or conflicting device reports. Pending retry churn remains a separate semantic
question under the existing latest-request contract. Source rollback is an
approved scoped revert; live rollback requires a verified backup/reinstall path
and separate approval. All existing unfinished work remains preserved.
