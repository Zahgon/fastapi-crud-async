import json
from http import HTTPStatus

from flask import Response


def status_line(status_code):
    """Build a status line whose reason phrase keeps its canonical casing.

    Werkzeug upper-cases the reason phrase when it is handed a bare integer
    (``404 NOT FOUND``), while the previous server sent the canonical spelling
    (``404 Not Found``). Passing the phrase explicitly bypasses that.
    """
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        return str(status_code)
    return f"{status_code} {phrase}"


def json_response(content, status_code=200, headers=None):
    """Serialise ``content`` the way the previous router did.

    ``flask.jsonify`` sorts keys and appends a newline; both are visible on the
    wire, so the payload is rendered here with the previous router's own
    arguments instead. ``ensure_ascii=False`` is the load-bearing one: without
    it a non-ASCII title goes out as ``\\uXXXX`` escapes under a longer
    content-length, where the previous router sent raw UTF-8.
    """
    body = json.dumps(
        content,
        ensure_ascii=False,
        allow_nan=False,
        indent=None,
        separators=(",", ":"),
    ).encode("utf-8")
    return Response(
        body,
        status=status_line(status_code),
        headers=headers,
        content_type="application/json",
    )


class HTTPException(Exception):
    """Aborts a view with a ``{"detail": ...}`` body and an explicit status."""

    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
