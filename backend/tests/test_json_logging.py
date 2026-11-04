import json
import logging
import sys

from services.json_logging import JsonFormatter


def record(name="app", level=logging.INFO, msg="hello %s", args=("there",), **extra):
    rec = logging.makeLogRecord(
        {"name": name, "levelno": level, "levelname": logging.getLevelName(level), "msg": msg, "args": args}
    )
    rec.__dict__.update(extra)
    return rec


def formatted(rec) -> dict:
    line = JsonFormatter().format(rec)
    assert "\n" not in line
    return json.loads(line)


def test_non_ascii_text_is_escaped_so_any_console_encoding_works():
    line = JsonFormatter().format(record(msg="Résumé parsed → %s", args=("Zürich",)))

    assert line.isascii()
    assert json.loads(line)["message"] == "Résumé parsed → Zürich"


def test_message_level_and_extra_fields():
    entry = formatted(record(level=logging.WARNING, user_id=5, org_id="abc"))

    assert entry["message"] == "hello there"
    assert entry["level"] == "warn"
    assert entry["logger"] == "app"
    assert entry["user_id"] == 5 and entry["org_id"] == "abc"
    assert "args" not in entry and "msg" not in entry


def test_levels_use_railways_names():
    levels = {logging.DEBUG: "debug", logging.INFO: "info", logging.ERROR: "error", logging.CRITICAL: "error"}
    for level, name in levels.items():
        assert formatted(record(level=level))["level"] == name


def test_an_exception_stays_on_one_line():
    try:
        raise ValueError("boom")
    except ValueError:
        rec = record(level=logging.ERROR, exc_info=sys.exc_info())

    entry = formatted(rec)

    assert "ValueError: boom" in entry["exception"]


def test_uvicorn_access_log_becomes_fields():
    rec = record(
        name="uvicorn.access",
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:5000", "GET", "/v1/contacts?type=recruiter", "1.1", 200),
    )

    entry = formatted(rec)

    assert entry["message"] == '127.0.0.1:5000 - "GET /v1/contacts?type=recruiter HTTP/1.1" 200'
    assert entry["method"] == "GET" and entry["status_code"] == 200
    assert entry["path"] == "/v1/contacts?type=recruiter"


def test_unserializable_extras_are_stringified_and_color_copies_dropped():
    entry = formatted(record(when=object, color_message="\x1b[1mhello\x1b[0m"))

    assert entry["when"] == str(object)
    assert "color_message" not in entry
