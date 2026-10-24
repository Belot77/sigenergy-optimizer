from __future__ import annotations

from datetime import datetime, time, timedelta
from unittest.mock import patch

from app.import_topup_ledger import ImportTopupLedger


def seed_complete_import_history(optimizer, when: datetime) -> ImportTopupLedger:
    """Seed synthetic inactive coverage through ``when`` using real ledger APIs."""
    local_when = datetime.fromtimestamp(when.timestamp(), tz=optimizer._tz)
    midnight = datetime.combine(local_when.date(), time.min, tzinfo=optimizer._tz)
    before_midnight = midnight - timedelta(seconds=1)
    source = optimizer._import_topup_source()
    ledger = ImportTopupLedger(
        optimizer._state_store,
        started_at=before_midnight,
        source=source,
    )

    def observe_inactive(at: datetime) -> None:
        ledger.record(
            now=at,
            source=source,
            daily_import_kwh=0.0,
            grid_import_kw=0.0,
            import_price=None,
            price_trusted=False,
            import_active=False,
        )

    # These two samples model an already-running process crossing midnight.
    # Existing persisted checkpoints belong to other synthetic optimizer
    # instances sharing this fixture store, so ignore them only for this seed.
    with patch.object(optimizer._state_store, "get_optimizer_import_checkpoint", return_value=None):
        observe_inactive(before_midnight)
        observe_inactive(midnight)

    current = midnight
    while current < local_when:
        seconds = min((local_when - current).total_seconds(), 300.0)
        current += timedelta(seconds=seconds)
        observe_inactive(current)

    optimizer._import_topup_ledger = ledger
    return ledger
