# Solar re-entry stability - local O2/O6 candidate

Date: 25 October 2026. Workspace
`C:\Projects\sigenergy_optimizer-solar-reentry`, branch
`fix/solar-charge-reentry-stability`, baseline freshly fetched `origin/main`
`c84a61b6a6ca1fb6d5f23c421f1f11ebf4a1ce49`.

The operator approved local fixes, regression tests, safety review and docs.
That approval excludes commit, push, merge, version bump, release, HA access and
live setting changes; later commit/publication approvals remain separate.
Published .78 remains unchanged. Characterization and backlog
workspaces, including all their uncommitted files, remain preserved.

## Before and after

O2 projected a short load increase across remaining daylight, immediately
releasing Solar on failed aggregate energy budget and restoring it at the next
passing decision. The six-second fixture alternated restrictive Solar, normal
21 kW permission and zero-charge Solar. Now the failed budget still closes
immediately, but Solar reacquisition requires the approved fresh interval. A
stable sequence can recover; this is not permanent suppression. Other qualified
policies retain their priorities, so pending O2 does not universally mean MSC
or 21 kW charging. The strict energy comparison itself is unchanged.

O6 Morning Slow eligibility varied with available-discharge energy. Relieved
Morning charging requested normal 21 kW; alternate independently valid Solar
decisions requested restrictive charging. Delaying Morning could change battery
export priorities. Delaying all Solar could introduce export-ceiling flapping.
The correction therefore delays only Solar's restrictive charge reacquisition
after completed relieved Morning charging. In the eight-row fixture, charge
requests become 0,21,21,21,21,21,21,21 kW, while export permission remains 25 kW.
Solar/Morning flags still truthfully follow selection; this is charge-command
stabilization, not a claim that raw eligibility stops changing. Genuine slow
charging without relief does not arm the new handoff rule.

## Evidence, bounds and application lifecycle

Two process-local guards share a small timing helper. Each keeps its cause
obligation separate from expiring qualification proof. Every existing gate
continues to run; no failed budget, trust, authority, tariff or safety result
is held open. Qualification requires each PV/load report stream to span at least
30 seconds and local monotonic elapsed time to span at least 30 seconds.
Per-source age and report/local-advancement gaps are bounded at 60 seconds.
Existing five-second PV/load coherence remains mandatory. Cached readings cannot
complete the interval, and clocks/report timestamps cannot regress.

The existing live HA input context supplies PV/load report provenance and
Automated/exact-MSC/Remote-EMS-ON observations. No new entity/configuration field
or available-energy trust condition is introduced for independent Solar. Context
tracks local day, sunset, capacity, capability, relevant settings and source
identity; O6 also tracks its existing provider epoch. O2 does not acquire a new
provider-freshness export prerequisite.

Failed gates, competing owners, configuration/source changes, Manual/Force and
failed/cancelled application retire time proof without silently clearing a
pending cause. Only a qualified final Solar selection and completed automatic
application without fallback retires the corresponding obligation. O6 arming
requires completed genuinely owned relieved Morning charging at its bounded
normal request. Generic no-op success and pending MSC transitions are insufficient.

Decision generations are checked after authority awaits, before relevant export
and charge writes, and at completion. O2 expiry uses existing conservative
fallback. O6 expiry restores the selected normal bounded charge request within
the serialized application, retaining valid export permission. Provider expiry,
fill deadline, hardware limits and MSC settlement remain independent. Exact-full
does not wait on partial-battery handoff qualification. Restart retains existing
initial admission rules; these obligations are not persisted.

## Validation checkpoint

Combined focused checks passed **165 tests / 184 subtests**, zero failures,
202 existing warnings, in 14.97 seconds. Independent peer review of production,
helper and opposite-authored regressions is GO after two corrected findings:
qualification cannot accrue through unsafe battery flow, and late helper awaits
cannot leave an expired generation applied without fallback/normal restoration.
The full offline suite passed **1,415 tests / 1,380 subtests**, zero failures,
206 existing warnings, in **241.93 seconds**. No source/test logic changed after
that run. On 26 October, staged-patch checking found and removed one extra EOF
blank line in the new Morning test; its Python AST is unchanged. No test repeat
was needed for that whitespace-only correction. Documentation review is GO after reconciling its two stale pending-review
statements. Syntax and whitespace checks pass; the exact 15-file scope contains
no version/configuration/workflow changes. SHA-256 checks confirm all six original
characterization files and three original backlog documents are unchanged.
These are software checks, not publication or physical acceptance.

Tests use explicit synthetic detailed forecasts/settings, real decision/provider/
arbitration/charge paths, temporary accounting and in-memory HA doubles. Source
report and monotonic clocks are controlled independently. Real typed application
results exercise admission/arming boundaries. No raw trace, runtime DB, log,
credential or local environment file is added to Git.

## Risks, acceptance and rollback

Thirty seconds filters the supplied six-second switching, but is not proven
optimal and cannot eliminate every longer cycle. Reports can leave unobserved
physical intervals. Qualification can increase normal charging and reduce useful
export; infrequent reports can postpone admission. It does not guarantee battery
fill after forecast downgrade. O18 minimum-charge/deferral policy, O5 reserve,
broader O6 depletion and parked O11 remain separate.

Offline tests establish software behavior only. Monitor-only/dry-run review must
compare raw candidates, pending/qualified state, generations, report timestamps,
final policy and charge owners without actuator writes. Separately approved
supervised live proof must first establish exact installed source, effective
settings/authority and rollback readiness. Compare requested/observed limits and
actual flows across budget failures, relieved Morning handoffs, stable recovery,
provider loss and MSC transitions. Stop on unsafe discharge/export/import, lost
authority, repeated failures or renewed harmful switching; return to the
operator's chosen safe mode. No live test or settings change is authorized here.

Local rollback is to withhold or revert this isolated correction, retaining
all original workspaces. No live rollback is needed for uncommitted local code.
Current installed identity and any future restore method require operator evidence.
