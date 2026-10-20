# HAOS .74 release candidate and supervised proof

Prepared 20 October 2026. Status: **unpublished; not installed or live-verified**.

## Source and scope

Candidate version: `2.3.63-haos74`; planned tag: `v2.3.63-haos74`.
Branch: `release/2.3.63-haos74`; workspace: `C:\Projects\sigenergy_optimizer-release-haos74`.
Base: merged PR #26, main `550c8eeee8239dfb3515d3a6c4b174f35e58f139`, tree `999b2cb4b405a409bf1f17df80d9ba85de5f016a`.
The reviewed control checkpoint is `fa9d926a734ceefd2426000d9edb92c037ac93a6`.

Preparation changes only these five markers and release documentation:

| File | Marker |
| --- | --- |
| `app/main.py` | FastAPI version |
| `app/optimizer.py` | Runtime signature |
| `sigenergy_optimizer_addon/config.yaml` | Add-on version |
| `sigenergy_optimizer_addon/build.yaml` | `io.hass.version` |
| `sigenergy_optimizer_addon/buildstamp.txt` | Clone-cache build stamp |

Control logic, tests, Dockerfile, workflow and permanent instructions retain the reviewed main contents. Existing unfinished work remains protected. Do not use `release.sh`; it stages broadly and can commit, tag and push.

## Behavior and retained evidence

The change preserves an existing Solar MSC export permission through a short dip, strictly before 15 seconds after the older qualifying PV/load source report. Both reports must advance, show measured surplus above 0.5 kW and produce successfully applied final Solar ownership to renew proof. Held/cached/midband/forecast evidence cannot renew it. Exact conditions and independent safety boundaries are in [CONTROL_CONTRACT.md](CONTROL_CONTRACT.md).

Sanitized incident inputs produced seven baseline 25-to-zero kW request closures; corrected ticks retain permission through those short dips with renewed strong measured reports. Expiry, failed/pending/cancelled application, stale or unsafe evidence, manual takeover and independently reduced export readback have targeted checks. Initial physical PV-collapse cause remains unproven.

The control checkpoint passed 1,106 tests / 1,235 subtests, zero failures, 206 warnings in 206.22 seconds. Focused checks passed 115 tests / 191 subtests. Independent targeted safety review passed after expiry/readback corrections. Those results belong to the unchanged control checkpoint; a full suite is not repeated merely for version markers. Candidate-specific checks cover marker alignment, clone-cache inputs and source pinning. Local tests and helper success do not prove inverter settlement.

Candidate-specific verification passed **16 release-marker/source-pinning tests in 9.05 seconds**. Exact normalized-source comparison proves that each of the five marker files differs from main by one version replacement only; tests, Dockerfile, workflow and permanent instructions are unchanged. Independent release-scope review found no blockers. Docker is unavailable in this local environment; no container build is claimed. The tag-triggered amd64/arm64 build and image source/digest verification remain publication gates.

## Publication boundary

Latest published release and operator-reported installation remain `.73` / `2.3.62-haos73`, source `46d36358d38137231dff081176a372c3aa1f4cee`. No `.74` tag, image or installation is created by preparation.

The sole workflow runs on `v*` tag pushes and publishes amd64/arm64 images, including `latest`. Branch pushes and PR creation do not publish an image. Merging release metadata changes the advertised add-on version, while a version-tag push triggers image publication. Neither action alone proves successful installation.

Before separately approved publication, verify the exact final candidate commit and merged tree, confirm no conflicting `.74` tag/release/image, and coordinate version advertisement with tag-driven image availability. Preserve `.73` tag/image identity. Verify workflow success for both architectures and image version/source labels against the exact approved source; record resulting image digests before installation. Do not assume that publication approval authorizes HA installation or settings changes.

## Supervised live verification and rollback

Monitor-only analysis and offline/dry-run checks must use read-only evidence and fake services; no live write follows from a passing simulation. Existing operator Manual/Force ownership remains authoritative.

Before any live installation, separately verify current About/runtime/source identity, effective settings and current control authority, the operator's update preference, a usable saved configuration/backup and an executable rollback path. Historical `.65` public source/images exist, but its actual restore/reinstall selection remains unproven. A prior backup report had errors; do not presume a usable backup from source/image availability. Current `.73` reinstallation readiness also needs evidence. Do not change security settings or inspect sensitive `.storage`, credentials or backup contents.

With installation and live control separately approved and supervised:

1. Record exact `.74` runtime/source identity and requested versus observed MSC, export/import/PV/ESS ceilings, battery SoC and measured flows.
2. Capture advancing PV/load report times, strong-proof gate, hold-active gate and deadline. Confirm short dips retain only existing bounded MSC permission, without deliberate battery discharge or widening an independently reduced ceiling.
3. Confirm persistent low surplus expires, requests conservative closure and records its observed settlement. If application fails, capture fallback and bounded retries without interpreting helper success as settlement.
4. Confirm hard-gate loss and operator takeover promptly remove automatic permission. Keep provider/fill charge authority, Demand import blocks and independent ESS/PV restrictions intact. Do not induce risky conditions solely to obtain proof; unobserved scenarios remain open.
5. Stop on unsafe battery discharge with export, lost authority/trust, failed settlement or renewed flapping. Preserve evidence and use the operator's chosen safe mode; perform an actual rollback only under the separately agreed plan.

Other parked archive/MSC investigations, short physical Demand Window spikes, Solar provider/relief questions and Evening Boost concerns are not closed by this release. Do not enable unrelated features as part of Solar acceptance.
