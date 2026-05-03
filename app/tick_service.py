"""
Tick orchestration service — the inner per-cycle loop extracted from optimizer.py.

A single call to `run_tick` acquires the control lock, reads HA state, builds
the decision, applies it, and fires all post-decision side-effects.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .optimizer import SigEnergyOptimizer


async def run_tick(optimizer: "SigEnergyOptimizer") -> None:
    """
    Execute one full optimizer cycle under the control lock.

    Steps:
      1. read_state  — bulk-read all HA entities into a SolarState snapshot
      2. decide      — pure decision logic, no side effects
      3. freeze      — apply manual mode override if active
      4. apply       — push decisions to HA via REST
      5. telemetry   — audit log, decision trace, history, price tracking
      6. notify      — HA push notifications and daily summaries
    """
    async with optimizer._control_lock:
        prev_decision = optimizer._last_decision
        prev_state = optimizer._last_state

        state = await optimizer._read_state()
        optimizer._last_state = state

        decision = optimizer._decide(state)

        effective_mode = optimizer._manual_mode_override or state.sigenergy_mode
        if effective_mode not in {optimizer.cfg.automated_option, ""}:
            optimizer._freeze_decision_to_live_mode(state, decision, effective_mode)

        optimizer._last_decision = decision

        await optimizer._apply(state, decision)
        optimizer._record_automation_audit(state, decision, prev_decision)
        optimizer._record_decision_trace(state, decision)
        await optimizer._handle_notifications(state, decision, prev_decision, prev_state)
        await optimizer._handle_daily_summaries(state, decision)
        optimizer._accumulate_history(state, decision)
        optimizer._record_price_tracking(state)
