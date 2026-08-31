import json

import pytest
from werkzeug.test import EnvironBuilder

from app.api import crud
from app.main import app
from app.responses import status_line


def test_ping_body_is_compact_and_has_no_trailing_newline(test_app):
    response = test_app.get("/ping")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.content == b'{"ping":"pong!"}'


def test_head_is_not_implied_by_get(test_app):
    response = test_app.head("/ping")

    assert response.status_code == 405
    assert response.headers["allow"] == "GET"


def test_trailing_slash_is_stripped_with_a_temporary_redirect(test_app):
    response = test_app.get("/ping/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "http://testserver/ping"
    assert "content-type" not in response.headers
    assert response.content == b""


def test_missing_trailing_slash_is_added_with_a_temporary_redirect(test_app):
    response = test_app.get("/notes?limit=1", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "http://testserver/notes/?limit=1"
    assert response.content == b""


@pytest.mark.parametrize("path", ["/", "/nope", "/nope/", "/notes//", "/notes/1/extra"])
def test_unknown_paths_report_not_found(test_app, path):
    response = test_app.get(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize(
    "method, path, allow",
    [
        ["POST", "/ping", "GET"],
        ["OPTIONS", "/ping", "GET"],
        ["PUT", "/notes/", "POST"],
        ["OPTIONS", "/notes/", "POST"],
        ["PATCH", "/notes/1/", "GET"],
    ],
)
def test_method_not_allowed_advertises_the_first_declared_route(
    test_app, method, path, allow
):
    response = test_app.request(method, path)

    assert response.status_code == 405
    assert response.headers["allow"] == allow
    assert response.json() == {"detail": "Method Not Allowed"}


def test_absent_body_is_reported_as_missing(test_app):
    response = test_app.post("/notes/")

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {"loc": ["body"], "msg": "field required", "type": "value_error.missing"}
        ]
    }


def test_malformed_json_is_reported_as_a_decode_error(test_app):
    response = test_app.post("/notes/", content="{oops")

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", 1]
    assert error["type"] == "value_error.jsondecode"


@pytest.mark.parametrize(
    "content_type",
    ["text/plain", "application/x-www-form-urlencoded"],
)
def test_bodies_that_are_not_json_are_not_decoded(test_app, content_type):
    response = test_app.post(
        "/notes/",
        content=json.dumps({"title": "something", "description": "something else"}),
        headers={"content-type": content_type},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "loc": ["body"],
                "msg": "value is not a valid dict",
                "type": "type_error.dict",
            }
        ]
    }


def test_json_suffixed_content_types_are_decoded(test_app, monkeypatch):
    async def mock_post(payload):
        return 1

    monkeypatch.setattr(crud, "post", mock_post)

    response = test_app.post(
        "/notes/",
        content=json.dumps({"title": "something", "description": "something else"}),
        headers={"content-type": "application/vnd.api+json"},
    )

    assert response.status_code == 201


def test_unhandled_errors_are_reported_as_plain_text(test_app, monkeypatch):
    async def mock_get(id):
        raise RuntimeError("boom")

    monkeypatch.setattr(crud, "get", mock_get)

    response = test_app.get("/notes/1/")

    assert response.status_code == 500
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text == "Internal Server Error"


NON_ASCII_NOTE = {"title": "naïve café", "description": "ünïcödé — and an em dash"}
NON_ASCII_BYTES = (
    b'{"title":"na\xc3\xafve caf\xc3\xa9",'
    b'"description":"\xc3\xbcn\xc3\xafc\xc3\xb6d\xc3\xa9 \xe2\x80\x94 and an em dash",'
    b'"id":1}'
)


def test_non_ascii_is_created_as_raw_utf8(test_app, monkeypatch):
    async def mock_post(payload):
        return 1

    monkeypatch.setattr(crud, "post", mock_post)

    response = test_app.post("/notes/", content=json.dumps(NON_ASCII_NOTE))

    assert response.status_code == 201
    assert response.content == NON_ASCII_BYTES
    assert response.headers["content-length"] == str(len(NON_ASCII_BYTES))


def test_non_ascii_is_read_back_as_raw_utf8(test_app, monkeypatch):
    async def mock_get(id):
        return {"id": 1, **NON_ASCII_NOTE}

    monkeypatch.setattr(crud, "get", mock_get)

    response = test_app.get("/notes/1/")

    assert response.status_code == 200
    assert response.content == NON_ASCII_BYTES
    assert response.headers["content-length"] == str(len(NON_ASCII_BYTES))


def test_non_ascii_is_listed_as_raw_utf8(test_app, monkeypatch):
    async def mock_get_all():
        return [{"id": 1, **NON_ASCII_NOTE}]

    monkeypatch.setattr(crud, "get_all", mock_get_all)

    response = test_app.get("/notes/")

    assert response.status_code == 200
    assert response.content == b"[" + NON_ASCII_BYTES + b"]"


def test_non_ascii_outside_the_basic_plane_is_not_escaped(test_app, monkeypatch):
    async def mock_post(payload):
        return 7

    monkeypatch.setattr(crud, "post", mock_post)

    response = test_app.post(
        "/notes/",
        content=json.dumps({"title": "emoji 😀", "description": "kana カナ"}),
    )

    assert response.status_code == 201
    assert response.content == (
        b'{"title":"emoji \xf0\x9f\x98\x80","description":"kana \xe3\x82\xab\xe3\x83\x8a",'
        b'"id":7}'
    )


def test_non_ascii_validation_errors_are_not_escaped(test_app):
    # A decode error echoes the request document back inside its ctx block, so a
    # 422 reaches the serialiser carrying the request's own non-ASCII bytes.
    response = test_app.post("/notes/", content='{"title":"café"'.encode())

    assert response.status_code == 422
    assert b"caf\xc3\xa9" in response.content
    assert b"\\u00e9" not in response.content


def test_openapi_schema_is_served(test_app):
    response = test_app.get("/openapi.json")
    schema = response.json()

    assert response.status_code == 200
    assert schema["openapi"] == "3.0.2"
    assert sorted(schema["paths"]) == ["/notes/", "/notes/{id}/", "/ping"]
    assert schema["paths"]["/notes/"]["post"]["responses"]["201"]


@pytest.mark.parametrize(
    "path, marker",
    [
        ["/docs", "swagger-ui-bundle"],
        ["/docs/oauth2-redirect", "swaggerUIRedirectOauth2"],
        ["/redoc", '<redoc spec-url="/openapi.json">'],
    ],
)
def test_documentation_pages_are_served(test_app, path, marker):
    response = test_app.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert marker in response.text


DOCUMENTATION_ROUTES = ["/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"]


@pytest.mark.parametrize("path", DOCUMENTATION_ROUTES)
def test_documentation_routes_answer_head(test_app, path):
    # The previous server built these four out of its plain route class, which
    # added HEAD to any route declaring GET; only the application routes used
    # the class that took the declared methods verbatim.
    get = test_app.get(path)
    head = test_app.head(path)

    assert head.status_code == 200
    assert head.headers["content-type"] == get.headers["content-type"]
    assert head.headers["content-length"] == str(len(get.content))
    assert head.content == b""


@pytest.mark.parametrize("path", DOCUMENTATION_ROUTES)
@pytest.mark.parametrize("method", ["POST", "DELETE", "OPTIONS"])
def test_documentation_routes_advertise_head_when_refusing(test_app, method, path):
    response = test_app.request(method, path)

    assert response.status_code == 405
    assert sorted(response.headers["allow"].split(", ")) == ["GET", "HEAD"]
    assert response.json() == {"detail": "Method Not Allowed"}


@pytest.mark.parametrize("path", ["/ping", "/notes/", "/notes/1/"])
def test_application_routes_still_refuse_head(test_app, path):
    response = test_app.head(path)

    assert response.status_code == 405
    assert "HEAD" not in response.headers["allow"]


def _wsgi_status_line(method, path, body=None, content_type=None):
    """Return the status line the app hands to the WSGI server.

    The httpx test client cannot be used here: its WSGI transport drops the
    reason phrase and regenerates it from the status code, so it reports the
    phrase it expects rather than the one the application actually sent.
    """
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        return lambda chunk: None

    builder = EnvironBuilder(
        method=method, path=path, data=body, content_type=content_type
    )
    for _ in app(builder.get_environ(), start_response):
        pass
    return captured["status"]


@pytest.mark.parametrize(
    "method, path, expected",
    [
        ["GET", "/ping", "200 OK"],
        ["GET", "/ping/", "307 Temporary Redirect"],
        ["GET", "/nope", "404 Not Found"],
        ["POST", "/ping", "405 Method Not Allowed"],
        ["GET", "/notes/0/", "422 Unprocessable Entity"],
    ],
)
def test_reason_phrases_keep_their_canonical_casing(method, path, expected):
    # Werkzeug upper-cases the reason phrase when it is given a bare integer
    # status, which the previous server did not do.
    assert _wsgi_status_line(method, path) == expected


def test_created_reason_phrase_keeps_its_canonical_casing(monkeypatch):
    async def mock_post(payload):
        return 1

    monkeypatch.setattr(crud, "post", mock_post)

    status = _wsgi_status_line(
        "POST",
        "/notes/",
        body=json.dumps({"title": "foo", "description": "bar"}),
        content_type="application/json",
    )

    assert status == "201 Created"


def test_status_line_falls_back_for_unknown_codes():
    assert status_line(404) == "404 Not Found"
    assert status_line(599) == "599"
