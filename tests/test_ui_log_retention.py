"""Regression coverage for dashboard and console log routing."""

from __future__ import annotations

import asyncio
import collections
import logging
from types import SimpleNamespace

import pytest

from app import main
from app.routers import api


@pytest.fixture
def isolated_log_buffer(monkeypatch):
    buffer = collections.deque(maxlen=500)
    monkeypatch.setattr(api, "_LOG_BUFFER", buffer)
    return buffer


def _http_record(status: int, version: str = "HTTP/1.1") -> logging.LogRecord:
    # Exercise the common httpx LogRecord shape, where the status is in args.
    return logging.LogRecord(
        "httpx", logging.INFO, "", 0,
        'HTTP Request: %s %s "%s %d %s"',
        ("GET", "https://example.test/path", version, status, "OK"),
        None,
    )


@pytest.mark.parametrize("version", ["HTTP/1.1", "HTTP/2", "HTTP/3"])
@pytest.mark.parametrize("status", [200, 201, 204, 299])
def test_successful_httpx_responses_do_not_enter_ui_buffer(
    isolated_log_buffer, status, version
):
    api._handler.handle(_http_record(status, version))

    assert list(isolated_log_buffer) == []


@pytest.mark.parametrize(
    "name,level,message",
    [
        ("httpx", logging.INFO, 'HTTP Request: GET https://example.test/x "HTTP/2 400"'),
        ("httpx", logging.INFO, 'HTTP Request: GET https://example.test/x "HTTP/2 300"'),
        ("httpx", logging.INFO, 'HTTP Request: GET https://example.test/x "HTTP/2 429"'),
        ("httpx", logging.INFO, 'HTTP Request: GET https://example.test/x "HTTP/2 503"'),
        ("httpx", logging.INFO, 'HTTP Request: GET https://example.test/x?hint=200 "HTTP/2 500"'),
        ("httpx", logging.INFO, 'HTTP Request: GET https://example.test/x "HTTP/2 200 OK" extra'),
        ("httpx", logging.INFO, "request completed without a status line"),
        ("httpx", logging.WARNING, 'HTTP Request: GET https://example.test/x "HTTP/2 200"'),
        ("app.routers.api", logging.INFO, 'HTTP Request: GET https://example.test/x "HTTP/2 200"'),
        ("app.routers.api", logging.WARNING, "application warning"),
        ("app.routers.api", logging.ERROR, "application error"),
        ("httpx", logging.DEBUG, "debug detail"),
    ],
)
def test_non_success_and_other_diagnostics_remain_visible(
    isolated_log_buffer, name, level, message
):
    record = logging.LogRecord(name, level, "", 0, message, (), None)
    api._handler.handle(record)

    assert len(isolated_log_buffer) == 1
    assert message in isolated_log_buffer[0]


def test_http_success_suppression_does_not_mutate_shared_record(isolated_log_buffer):
    record = _http_record(200, "HTTP/2")
    original = record.__dict__.copy()

    api._handler.handle(record)

    assert record.__dict__ == original
    assert not isolated_log_buffer


def test_malformed_http_record_does_not_crash_handler_or_drop_by_filter(isolated_log_buffer):
    record = logging.LogRecord(
        "httpx", logging.INFO, "", 0,
        'HTTP Request: GET https://example.test/x "HTTP/2 %s %s"',
        (200,), None,
    )

    # The filter must fail open when formatting cannot establish a status.
    assert api._handler.filter(record)
    api._handler.handle(record)


def test_success_flood_preserves_recent_diagnostics_and_ring_limit(isolated_log_buffer):
    warning = logging.LogRecord("app", logging.WARNING, "", 0, "still visible warning", (), None)
    error = logging.LogRecord("app", logging.ERROR, "", 0, "still visible error", (), None)
    api._handler.handle(warning)
    api._handler.handle(error)
    for index in range(650):
        api._handler.handle(_http_record(200))

    assert len(isolated_log_buffer) == 2
    assert any("still visible warning" in line for line in isolated_log_buffer)
    assert any("still visible error" in line for line in isolated_log_buffer)
    assert isolated_log_buffer.maxlen == 500


def test_retained_application_logs_still_use_newest_first_500_entry_cap(isolated_log_buffer):
    for index in range(510):
        record = logging.LogRecord("app", logging.INFO, "", 0, "diagnostic %d", (index,), None)
        api._handler.handle(record)

    assert len(isolated_log_buffer) == 500
    assert "diagnostic 509" in isolated_log_buffer[0]
    assert "diagnostic 10" in isolated_log_buffer[-1]
    assert all(not line.endswith("diagnostic 9") for line in isolated_log_buffer)


def test_console_handler_still_receives_successful_http_record(isolated_log_buffer):
    console_output = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            console_output.append(self.format(record))

    console = CaptureHandler()
    console.setFormatter(logging.Formatter("%(message)s"))
    record = _http_record(200)
    try:
        api._handler.handle(record)
        console.handle(record)
    finally:
        console.close()

    assert not isolated_log_buffer
    assert len(console_output) == 1
    assert "HTTP/1.1 200" in console_output[0]


def test_logs_endpoints_serve_retained_diagnostics(isolated_log_buffer):
    api._handler.handle(_http_record(200))
    api._handler.handle(logging.LogRecord("app", logging.WARNING, "", 0, "retained warning", (), None))
    request = SimpleNamespace()

    recent = asyncio.run(api.get_logs(request))
    download = asyncio.run(api.download_logs(request))

    assert recent.status_code == 200
    assert "retained warning" in recent.body.decode()
    assert "HTTP/1.1 200" not in recent.body.decode()
    assert download.status_code == 200
    assert "retained warning" in download.body.decode()
    assert "HTTP/1.1 200" not in download.body.decode()
    assert "attachment; filename=sigenergy_logs_" in download.headers["content-disposition"]


@pytest.fixture
def isolated_app_logging(monkeypatch, isolated_log_buffer):
    # Uvicorn's default console handlers belong to uvicorn.*, while the API's
    # dashboard ring is the sole root handler after the application import.
    root = logging.getLogger()
    app_logger = logging.getLogger("app")
    monkeypatch.setattr(root, "handlers", [api._handler])
    monkeypatch.setattr(root, "level", logging.INFO)
    monkeypatch.setattr(app_logger, "handlers", [])
    monkeypatch.setattr(app_logger, "level", logging.NOTSET)
    monkeypatch.setattr(app_logger, "propagate", True)
    yield root, app_logger, isolated_log_buffer
    for handler in app_logger.handlers:
        handler.close()


def test_solar_handoff_reaches_console_and_dashboard_once(capsys, isolated_app_logging):
    _, app_logger, dashboard = isolated_app_logging
    main._add_solar_handoff_console_logging()
    main._add_solar_handoff_console_logging()

    messages = (
        "Solar restart handoff shutdown: capture_attempted",
        "Solar restart handoff save: saved",
        "Solar restart handoff restore: revalidated",
    )
    logging.getLogger("app.main").info(messages[0])
    logging.getLogger("app.optimizer").info("Solar restart handoff save: %s", "saved")
    logging.getLogger("app.optimizer").warning(messages[2])
    logging.getLogger("app.optimizer").info("Ordinary optimizer update")
    logging.getLogger("other").info("Solar restart handoff emitted elsewhere")
    logging.getLogger("httpx").info('HTTP Request: GET https://example.test/x "HTTP/2 200"')

    output = capsys.readouterr()
    assert len(app_logger.handlers) == 1
    assert output.out == ""
    assert len(output.err.splitlines()) == len(messages)
    for message in messages:
        assert output.err.count(message) == 1
        assert sum(message in entry for entry in dashboard) == 1
    assert any("Ordinary optimizer update" in entry for entry in dashboard)
    assert all("HTTP Request:" not in entry for entry in dashboard)


@pytest.mark.parametrize("location", ["app", "root"])
def test_preserves_preconfigured_console(location, capsys, isolated_app_logging):
    root, app_logger, dashboard = isolated_app_logging
    host = app_logger if location == "app" else root
    console = logging.StreamHandler()
    host.addHandler(console)
    message = "Solar restart handoff load: loaded"
    try:
        main._add_solar_handoff_console_logging()
        logging.getLogger("app.optimizer").info(message)
        assert capsys.readouterr().err.count(message) == 1
        assert sum(message in entry for entry in dashboard) == 1
        assert console in host.handlers
    finally:
        host.removeHandler(console)
        console.close()
