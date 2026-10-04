# Changelog

## Unreleased candidate - 2026-10-05

- Dynamic Solar ESS charge-ceiling freshness uses successful Solcast API Last Polled advances and retained scheduled deadlines instead of Forecast Today's shared 600-second HA observation age. Startup and discontinuities require a baseline followed by a successful advance; schedule changes and early manual refreshes cannot extend an outstanding deadline.
- Added sticky source epochs, deadline/midnight reevaluation through the existing event loop, charge-write authority rechecks and compact provider Decision Trace evidence. Existing ownership, strict forecast/control safeguards and actuator settlement semantics remain unchanged.
- Added configurable `solcast_api_last_polled_sensor` and exposed **Forecast observation maximum age (seconds)** under Forecast Safety. The existing key and 600-second default remain compatible; invalid runtime ages are rejected. This setting cannot extend dynamic Solar provider authority.

This candidate is uncommitted, unreleased and undeployed. Live release and rollback remain `2.3.54-haos65` / `9965e79`. Phase 1 live acceptance is pending; Evening Boost remediation and Phase 2 are outside this change.
