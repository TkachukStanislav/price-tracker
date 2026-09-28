import json
import logging

from app.core.logging import JsonFormatter


def make_record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Товар #%s: %s",
        args=(7, "stale"),
        exc_info=None,
    )
    record.__dict__.update(extra)
    return record


def test_json_formatter_outputs_one_json_object():
    line = JsonFormatter("core_api").format(make_record())

    entry = json.loads(line)
    assert entry["service"] == "core_api"
    assert entry["level"] == "WARNING"
    assert entry["logger"] == "app.test"
    assert entry["message"] == "Товар #7: stale"
    assert "timestamp" in entry


def test_json_formatter_includes_extra_fields():
    line = JsonFormatter("core_api").format(
        make_record(queue="price_updated_events", message_id="msg-1")
    )

    entry = json.loads(line)
    assert entry["queue"] == "price_updated_events"
    assert entry["message_id"] == "msg-1"


def test_json_formatter_includes_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        record = make_record()
        record.exc_info = __import__("sys").exc_info()

    entry = json.loads(JsonFormatter("core_api").format(record))

    assert "ValueError: boom" in entry["exception"]
