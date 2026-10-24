# O17 local ingress trust boundary

Date: 24 October 2026. This is the O17 component record for the reviewed
integration worktree `C:\Projects\sigenergy_optimizer-storage-ingress`, branch
`fix/storage-ingress-integration`, based on
`df5c64c04dac67885270bfa15be89db6a6dc2d0d`. O17 was originally implemented on
`fix/ingress-trust-boundary`; its 295 / 89 broader and 70 / 6 focused test results,
and independent source/test/documentation review GO, apply to that component
branch. The on-disk combined suite passed 1,355 tests / 1,305 subtests (206 warnings,
232.02 seconds); focused checks passed 126 / 8 (202 warnings, 13.54 seconds).
Independent combined source/test/documentation review is GO, with no High/Medium blocker.
This records pre-commit verification; Git/PR establish the resulting commit identity. No merge, release, installation, or live action is included.

O15 storage isolation is included as the second component; its standalone evidence
is recorded in [the storage execution component record](STORAGE_EXECUTION_ISOLATION.md).

## Before and after

With the existing default flags (`allow_loopback_without_api_key=True` and
`require_api_key_for_all_mutations=False`), any nonempty `X-Ingress-Path`,
`X-Hassio` or `X-Home-Assistant` header formerly bypassed mutation API-key
validation, regardless of the connecting client. A configured or explicitly
wrong API key did not stop this exemption. Enabled guarded configuration reads
delegate to the same authentication helper. Header claims also labeled audit
events as HA UI traffic.

The candidate requires both the actual transport peer `172.30.32.2` and a
nonempty `X-Ingress-Path`. Equivalent IPv4-mapped IPv6 addresses are normalized;
absent, malformed, other IPv4/IPv6 and non-string peer values fail closed.
Neither forwarded client addresses nor generic HA-like headers establish trust.
The same predicate determines audit actor/source attribution.

Both supported Uvicorn launches (`Dockerfile` and add-on `run.sh`) explicitly
set `--no-proxy-headers`. Without this invariant, an overbroad
`FORWARDED_ALLOW_IPS=*` can rewrite `request.client` to a client-supplied trusted
address and defeat a peer-only fix. Tests exercise each launcher's selected
Uvicorn middleware pipeline with wildcard forwarded trust, without a socket.

The existing flags and API-key policy remain intact. Normal HA ingress retains
HA authentication without another login or mandatory UI API key. Explicit
strict-mutation mode still requires a key, as before. Local loopback and enabled
configuration-read exemptions retain their existing separate policy.

## Scope and trust assumptions

[Official HA ingress guidance](https://contributors.home-assistant.io/apps/guides/ingress/)
describes HA session authentication, Supervisor source `172.30.32.2`, and the
`X-Ingress-Path` header. This is the supported HA add-on topology assumption.
The address is not a secret, and header possession alone proves nothing.
Actual installed flags, listener reachability and runtime identity were not
inspected. Add-on source still uses `ingress: true`, port 7123 and `ports: {}`.

This change closes the optional mutation/enabled guarded-read API-key bypass.
It does not implement the stronger listener-wide ingress-only network rule in
HA's guidance. Existing public status endpoints, status WebSocket, static/UI
access and optional reads remain unchanged. The status WebSocket accepts and
sends status; it does not receive control commands. A regression preserves that
existing read-only policy even with strict mutation mode enabled.

Custom proxies/direct API clients use the existing `X-API-Key` path. A custom
proxy must not masquerade as Supervisor, and overriding launch commands or
adding middleware that rewrites peers invalidates this trust assumption.
Disabling proxy rewriting can change server-reported client addresses in custom
proxy setups; forwarded headers remain untrusted metadata. No custom trusted
proxy list, new login, mandatory UI key or enterprise infrastructure is added.
The HA communication token remains a different credential from `ui_api_key`.

No optimizer strategy, entity identity, safety threshold, Manual/Force ownership,
monitor-only/dry-run/live-control behavior or HA command ordering is changed.

## Offline validation

The new 48-case module uses real FastAPI routes with in-process ASGI transport,
synthetic clients/settings and an optimizer double. It covers mutation and
enabled guarded-read rejection, normal and IPv4-mapped HA ingress, malformed
peers, strict/disabled exemption flags, valid/wrong/unconfigured keys, loopback,
audit attribution, both supported launch pipelines, and existing status
WebSocket policy. The existing trace-download ingress fixture now supplies the
Supervisor peer instead of a public client.

Tests-first unchanged-production result: **28 deliberate failures, 20 passes**,
202 existing warnings, 1.83 seconds. Production SHA-256 at that red checkpoint:

| Source | SHA-256 |
| --- | --- |
| `app/routers/api.py` | `66821308e19e6904b84622a83ce3f0de3ad632cba4019c76086b4f4c11f432f0` |
| `Dockerfile` | `1655f3c2045318b4a4d7fabd35cd717680c56f4d9445b52e705d3d7fc6f22958` |
| `sigenergy_optimizer_addon/run.sh` | `0f05d067897e56cc98b4e860ef898fcea9307521567f2fc7e05c7d26f844bd6b` |

Corrected focused run (`test_ingress_trust_boundary.py` and
`test_decision_trace_download.py`): **70 tests / 6 subtests passed**, 202 existing
warnings, 6.58 seconds. The broader 13-module run passed **295 tests / 89
subtests**, zero failures, 203 existing warnings, 27.30 seconds. It includes the
new ingress tests, API validation, configuration activation authority race /
transactions / Standby continuity, control authority safety, all five focused
trace suites, release version consistency and add-on source pinning. No full
suite run is claimed. Independent source/test/documentation review was GO with
no High/Medium blocker. Its focused rerun passed **70 tests / 6 subtests**, 202
existing warnings, 7.40 seconds, using `python -B -m pytest -p no:cacheprovider
tests/test_ingress_trust_boundary.py tests/test_decision_trace_download.py -q`.

Standalone O17 candidate production SHA-256 values:

| Source | SHA-256 |
| --- | --- |
| `app/routers/api.py` | `e479d52b655e8ca44ff26c75537c0c628ac96a4b661db9258993dba386ce74e9` |
| `Dockerfile` | `8aa91cd1bb4d5691e4fe8f5606c5a32b0b4a6792569e40a7842808e0296f4988` |
| `sigenergy_optimizer_addon/run.sh` | `ac437329561d3bcc6c470d8019abcd98bd5a1b5675cc687f6ba7a00923502c62` |

The combined integration API file has SHA-256
`28a5f4edf9668667bce4e7712794da9ece0a881698825c096dadc320dc53b6dc`;
its reviewed delta is the O15 API plus this component's exact ingress predicate
and `ipaddress` import. The two launcher files retain the standalone hashes above.

Engineer runs use Python `-B`, `PYTHONDONTWRITEBYTECODE=1`, pytest
`-p no:cacheprovider`, and an in-memory `BaseSettings.__init__` wrapper forcing
`_env_file=None` before importing the application/tests. No credential/runtime
files, HA instances or real network/control calls are involved.

## Rollback and later acceptance

Before commit, withhold this isolated candidate to retain the baseline. After
any future commit, use a separately reviewed scoped revert of the predicate,
launcher flags and associated tests/docs; preserve unrelated work. Reverting
also restores the conditional header-bypass risk, so keep ingress topology and
unmapped ports. No reset, discard or runtime configuration change is authorized.

After separate publication/installation approval, verify exact runtime source,
ordinary HA ingress access and synthetic/authorized direct API authentication.
Use monitor-only/dry-run operation for UI authentication acceptance; no live
dispatch is necessary. Existing supervised live-control acceptance gates remain
separate, including Manual/Force and observed actuator settlement. Unexpected
UI rejection or peer topology requires stopping acceptance and reviewing the
transport boundary rather than broadening header trust.
