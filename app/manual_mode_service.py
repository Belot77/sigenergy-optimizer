from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .models import Decision, SolarState

logger = logging.getLogger(__name__)


def manual_mode_targets(
    optimizer,
    mode_label: str,
    mode_max_self: str,
    mode_cmd_discharge_pv: str,
    mode_cmd_charge_grid: str,
    mode_cmd_charge_pv: str,
    state: Optional[SolarState] = None,
    include_block_flow_ess_limits: bool = False,
) -> Optional[dict[str, float | str]]:
    cfg = optimizer.cfg
    if mode_label in {cfg.automated_option, cfg.manual_option, ""}:
        return None

    import_cap, export_cap = optimizer.get_power_caps_kw(state)
    block = cfg.block_flow_limit_value
    pv_max = cfg.pv_max_power_value

    # Use hardware caps/config baselines here; number-entity max attributes can be
    # temporarily reduced during slow-charge windows and must not leak into manual
    # mode reset targets.
    ess_charge = max(import_cap, cfg.ess_charge_limit_value)
    ess_discharge = max(export_cap, cfg.ess_discharge_limit_value)

    # Prefer explicit number-entity max attributes when available; these are
    # closer to what HA will actually accept for set_value.
    if state and optimizer._valid_hw_cap_kw(state.ess_charge_limit_entity_max_kw):
        ess_charge = max(ess_charge, float(state.ess_charge_limit_entity_max_kw))
    if state and optimizer._valid_hw_cap_kw(state.ess_discharge_limit_entity_max_kw):
        ess_discharge = max(ess_discharge, float(state.ess_discharge_limit_entity_max_kw))

    if mode_label == cfg.block_flow_option:
        if optimizer._manual_ess_charge_override_kw is not None:
            ess_charge = float(optimizer._manual_ess_charge_override_kw)
        if optimizer._manual_ess_discharge_override_kw is not None:
            ess_discharge = float(optimizer._manual_ess_discharge_override_kw)

    if mode_label == cfg.full_export_option:
        return {
            "ems_mode": mode_cmd_discharge_pv,
            "grid_export_limit": export_cap,
            "grid_import_limit": block,
            "pv_max_power_limit": pv_max,
            "ess_charge_limit": ess_charge,
            "ess_discharge_limit": ess_discharge,
        }
    if mode_label == cfg.full_import_option:
        return {
            "ems_mode": mode_cmd_charge_grid,
            "grid_export_limit": block,
            "grid_import_limit": import_cap,
            "pv_max_power_limit": pv_max,
            "ess_charge_limit": ess_charge,
            "ess_discharge_limit": ess_discharge,
        }
    if mode_label == cfg.full_import_pv_option:
        return {
            "ems_mode": mode_cmd_charge_pv,
            "grid_export_limit": block,
            "grid_import_limit": import_cap,
            "pv_max_power_limit": pv_max,
            "ess_charge_limit": ess_charge,
            "ess_discharge_limit": ess_discharge,
        }
    if mode_label == cfg.block_flow_option:
        targets = {
            "ems_mode": mode_max_self,
            "grid_export_limit": block,
            "grid_import_limit": block,
            "pv_max_power_limit": pv_max,
        }
        if include_block_flow_ess_limits:
            targets["ess_charge_limit"] = ess_charge
            targets["ess_discharge_limit"] = ess_discharge
        return targets
    return None


def freeze_decision_to_live_mode(
    state: SolarState,
    decision: Decision,
    mode_label: str,
) -> None:
    decision.ems_mode = state.current_ems_mode
    decision.export_limit = state.current_export_limit
    decision.import_limit = state.current_import_limit
    decision.pv_max_power_limit = state.current_pv_max_power_limit
    decision.ess_charge_limit = (
        state.current_ess_charge_limit
        if state.current_ess_charge_limit is not None
        else decision.ess_charge_limit
    )
    decision.ess_discharge_limit = (
        state.current_ess_discharge_limit
        if state.current_ess_discharge_limit is not None
        else decision.ess_discharge_limit
    )
    decision.export_reason = f"Manual mode active ({mode_label})"
    decision.import_reason = "manual"
    decision.outcome_reason = f"Manual mode active ({mode_label}); optimizer writes paused"


async def apply_manual_mode_targets(
    optimizer,
    targets: dict[str, float | str],
    mode_label: Optional[str] = None,
) -> dict[str, bool]:
    cfg = optimizer.cfg
    ha = optimizer.ha

    async def _wait_for_mode(entity_id: str, expected: str, timeout_s: float = 4.0) -> bool:
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            current = str(await ha.get_state_value(entity_id, "") or "")
            if current == expected:
                return True
            await asyncio.sleep(0.3)
        return False

    async def _set_number_with_retry(entity_id: str, value: float, retries: int = 3) -> bool:
        ok = await ha.set_number(entity_id, value)
        if ok:
            return True
        for attempt in range(1, retries):
            # Allow EMS mode transition and HA integration state to settle.
            await asyncio.sleep(0.7)
            ok = await ha.set_number(entity_id, value)
            if ok:
                logger.info(
                    "Manual set_number retry succeeded for %s on attempt %d",
                    entity_id,
                    attempt + 1,
                )
                return True
        return False

    async def _select_mode_with_retry(entity_id: str, expected: str, retries: int = 4) -> bool:
        for attempt in range(retries):
            ok = await ha.select_option(entity_id, expected)
            if not ok:
                await asyncio.sleep(0.5)
                continue
            settled = await _wait_for_mode(entity_id, expected, timeout_s=3.0)
            if settled:
                if attempt > 0:
                    logger.info(
                        "Manual mode settle succeeded for %s on attempt %d",
                        expected,
                        attempt + 1,
                    )
                return True
            await asyncio.sleep(0.6)
        return False

    target_mode = str(targets["ems_mode"])
    ok_mode = await _select_mode_with_retry(cfg.ems_mode_select, target_mode)
    if not ok_mode:
        logger.warning(
            "Manual mode target apply: EMS mode did not settle to '%s'; applying non-mode limits anyway",
            target_mode,
        )

    ok_exp = await ha.set_number(cfg.grid_export_limit, float(targets["grid_export_limit"]))
    ok_imp = await ha.set_number(cfg.grid_import_limit, float(targets["grid_import_limit"]))
    ok_pv = await ha.set_number(cfg.pv_max_power_limit, float(targets["pv_max_power_limit"]))

    ok_chg = True
    if cfg.ess_max_charging_limit and "ess_charge_limit" in targets:
        retries = 4 if mode_label == cfg.block_flow_option else 2
        ok_chg = await _set_number_with_retry(
            cfg.ess_max_charging_limit,
            float(targets["ess_charge_limit"]),
            retries=retries,
        )

    ok_dis = True
    if cfg.ess_max_discharging_limit and "ess_discharge_limit" in targets:
        retries = 4 if mode_label == cfg.block_flow_option else 2
        ok_dis = await _set_number_with_retry(
            cfg.ess_max_discharging_limit,
            float(targets["ess_discharge_limit"]),
            retries=retries,
        )

    if not all([ok_mode, ok_exp, ok_imp, ok_pv, ok_chg, ok_dis]):
        logger.error(
            "Manual mode target apply had failures: mode=%s exp=%s imp=%s pv=%s chg=%s dis=%s",
            ok_mode,
            ok_exp,
            ok_imp,
            ok_pv,
            ok_chg,
            ok_dis,
        )
    return {
        "ems_mode": ok_mode,
        "grid_export_limit": ok_exp,
        "grid_import_limit": ok_imp,
        "pv_max_power_limit": ok_pv,
        "ess_charge_limit": ok_chg,
        "ess_discharge_limit": ok_dis,
    }


async def apply_manual_mode_selection(optimizer, mode_label: str) -> None:
    """Push EMS settings for a manual mode selection."""
    cfg = optimizer.cfg
    ha = optimizer.ha

    async with optimizer._control_lock:
        ok_mode_select = await ha.select_option(cfg.sigenergy_mode_select, mode_label)
        if not ok_mode_select:
            raise RuntimeError(
                f"Failed to set mode selector {cfg.sigenergy_mode_select} to '{mode_label}'"
            )
        if mode_label == cfg.automated_option:
            optimizer._manual_mode_override = None
            optimizer._manual_ess_charge_override_kw = None
            optimizer._manual_ess_discharge_override_kw = None
        else:
            optimizer._manual_mode_override = mode_label
            if mode_label in {
                cfg.block_flow_option,
                cfg.full_export_option,
                cfg.full_import_option,
                cfg.full_import_pv_option,
            }:
                # Preset modes should start from current capability defaults,
                # not stale ESS overrides from prior manual edits.
                optimizer._manual_ess_charge_override_kw = None
                optimizer._manual_ess_discharge_override_kw = None
        if optimizer._last_state is not None:
            optimizer._last_state.sigenergy_mode = mode_label

        if mode_label == cfg.automated_option:
            logger.info("Mode -> Automated")
            return

        logger.info("Manual mode -> %s", mode_label)

        if mode_label == cfg.manual_option:
            refreshed_state = await optimizer._read_state()
            refreshed_state.sigenergy_mode = mode_label
            optimizer._last_state = refreshed_state
            optimizer._manual_ess_charge_override_kw = None
            optimizer._manual_ess_discharge_override_kw = None
            decision = optimizer._decide(refreshed_state)
            optimizer._freeze_decision_to_live_mode(refreshed_state, decision, mode_label)
            optimizer._last_decision = decision
            return

        current_state = await optimizer._read_state()
        targets = optimizer._manual_mode_targets(
            mode_label,
            current_state,
            include_block_flow_ess_limits=(mode_label == cfg.block_flow_option),
        )
        if targets:
            write_results = await optimizer._apply_manual_mode_targets(
                targets,
                mode_label=mode_label,
            )
            failed = [name for name, ok in write_results.items() if not ok]
            if mode_label == cfg.block_flow_option:
                optimizer.set_manual_ess_overrides(
                    charge_kw=float(targets.get("ess_charge_limit")) if "ess_charge_limit" in targets else None,
                    discharge_kw=float(targets.get("ess_discharge_limit")) if "ess_discharge_limit" in targets else None,
                )
            else:
                optimizer._manual_ess_charge_override_kw = None
                optimizer._manual_ess_discharge_override_kw = None
            refreshed_state = await optimizer._read_state()
            refreshed_state.sigenergy_mode = mode_label
            optimizer._last_state = refreshed_state
            decision = optimizer._decide(refreshed_state)
            optimizer._freeze_decision_to_live_mode(refreshed_state, decision, mode_label)
            optimizer._last_decision = decision
            if failed:
                raise RuntimeError(
                    f"Manual mode target writes failed for: {', '.join(failed)}"
                )
