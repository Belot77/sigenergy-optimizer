"""Pure validation of the Solcast restart handoff receipt."""

import json

import pytest

from app.solar_provider_handoff import SolarProviderHandoff, evidence_digest


BOOT_ID = "d441a955-63d7-4449-a1ba-f71361deaa92"
OTHER_BOOT = "2edc8ce9-b844-476f-94f5-e7fbd8e67f8d"
SOURCE = ("sensor.test_solcast_today", "sensor.test_solcast_last_polled")
SAVED_WALL = 1_767_225_600.0
SAVED_MONOTONIC = 5_000.0


@pytest.fixture
def handoff() -> SolarProviderHandoff:
    return SolarProviderHandoff(
        boot_id=BOOT_ID,
        source=SOURCE,
        day="2026-01-01",
        poll=SAVED_WALL - 60.0,
        deadline=SAVED_WALL + 120.0,
        forecast_digest=evidence_digest([[SAVED_WALL, 3.1], [SAVED_WALL + 1800, 4.2]]),
        witness_digest=evidence_digest(["synthetic-ha-revision"]),
        saved_wall=SAVED_WALL,
        saved_monotonic=SAVED_MONOTONIC,
    )


def test_roundtrip_keeps_source_and_deadline(handoff):
    encoded = handoff.to_json()
    assert json.loads(encoded)["schema_version"] == 1
    assert SolarProviderHandoff.from_json(encoded) == handoff


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("schema_version", 2),
        ("schema_version", True),
        ("schema_version", 1.0),
        ("boot_id", "boot-a"),
        ("boot_id", BOOT_ID.upper()),
        ("boot_id", "00000000-0000-0000-0000-000000000000"),
        ("source", "sensor.test_solcast_today"),
        ("source", [SOURCE[0]]),
        ("source", [SOURCE[0], SOURCE[0]]),
        ("source", [SOURCE[0], "urn:test"]),
        ("source", [SOURCE[0], ["sensor.test_solcast_last_polled"]]),
        ("day", "2026-02-30"),
        ("day", "20260101"),
        ("forecast_digest", "a" * 63),
        ("witness_digest", "f" * 63 + "g"),
        ("poll", SAVED_WALL + 1),
        ("poll", True),
        ("poll", 0),
        ("saved_wall", "1767225600"),
        ("deadline", SAVED_WALL),
        ("deadline", float("nan")),
        ("deadline", float("inf")),
        ("deadline", 10**400),
        ("saved_monotonic", -1),
    ],
)
def test_corrupt_receipt_values_are_rejected(handoff, field, bad_value):
    data = json.loads(handoff.to_json())
    data[field] = bad_value
    assert SolarProviderHandoff.from_json(json.dumps(data)) is None


@pytest.mark.parametrize("raw", [None, "", "{}", "[]", "{", "null", " " * 2049, b"{}"])
def test_absent_and_malformed_receipts_are_rejected(raw):
    assert SolarProviderHandoff.from_json(raw) is None


def test_unknown_missing_and_duplicate_fields_are_rejected(handoff):
    data = json.loads(handoff.to_json())
    assert SolarProviderHandoff.from_json(json.dumps({**data, "future_field": 1})) is None
    del data["source"]
    assert SolarProviderHandoff.from_json(json.dumps(data)) is None
    duplicate = handoff.to_json().replace('"schema_version":1', '"schema_version":2,"schema_version":1')
    assert SolarProviderHandoff.from_json(duplicate) is None


@pytest.mark.parametrize(
    ("boot_id", "wall_elapsed", "monotonic_elapsed", "expected"),
    [
        (BOOT_ID, 0, 0, True),
        (BOOT_ID, 30, 30, True),
        (BOOT_ID, 35, 30, True),
        (BOOT_ID, 25, 30, True),
        (BOOT_ID, 36, 30, False),
        (BOOT_ID, 24, 30, False),
        (BOOT_ID, -1, 0, False),
        (BOOT_ID, 0, -1, False),
        (BOOT_ID, 119, 119, True),
        (BOOT_ID, 120, 119, False),
        (BOOT_ID, 119, 120, False),
        (BOOT_ID, 120, 120, False),
        (BOOT_ID, float("nan"), 30, False),
        (BOOT_ID, 30, float("inf"), False),
        (OTHER_BOOT, 30, 30, False),
        (None, 30, 30, False),
    ],
)
def test_same_boot_clock_and_original_expiry(handoff, boot_id, wall_elapsed, monotonic_elapsed, expected):
    assert handoff.clock_is_current(
        boot_id,
        handoff.saved_wall + wall_elapsed,
        handoff.saved_monotonic + monotonic_elapsed,
    ) is expected


def test_evidence_digest_normalizes_object_key_order_and_rejects_non_finite_values():
    digest = evidence_digest({"second": 2, "first": [1, "solar"]})
    assert digest == evidence_digest({"first": (1, "solar"), "second": 2})
    assert digest != evidence_digest({"first": (1, "solar"), "second": 3})
    with pytest.raises(ValueError):
        evidence_digest([float("nan")])
