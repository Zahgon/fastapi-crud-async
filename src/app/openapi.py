from flask import Blueprint, Response

from app.api.models import NoteDB, NoteSchema
from app.responses import json_response
from app.routing import implies_head

router = Blueprint("openapi", __name__)

_TITLE = "Flask"
_VERSION = "0.1.0"
_SUCCESS = "Successful Response"

_FAVICON_URL = "https://flask.palletsprojects.com/en/stable/_static/shortcut-icon.png"


def _ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def _json_content(schema):
    return {"application/json": {"schema": schema}}


def _response(description, schema):
    return {"description": description, "content": _json_content(schema)}


def _model_schema(model):
    schema = model.schema()
    return {
        "title": schema["title"],
        "required": schema["required"],
        "type": schema["type"],
        "properties": schema["properties"],
    }


_VALIDATION_ERROR_RESPONSE = _response("Validation Error", _ref("HTTPValidationError"))

_ID_PARAMETERS = [
    {
        "required": True,
        "schema": {"title": "Id", "exclusiveMinimum": 0.0, "type": "integer"},
        "name": "id",
        "in": "path",
    }
]

_NOTE_REQUEST_BODY = {"content": _json_content(_ref("NoteSchema")), "required": True}

SPEC = {
    "openapi": "3.0.2",
    "info": {"title": _TITLE, "version": _VERSION},
    "paths": {
        "/ping": {
            "get": {
                "summary": "Pong",
                "operationId": "pong_ping_get",
                "responses": {"200": _response(_SUCCESS, {})},
            }
        },
        "/notes/": {
            "get": {
                "tags": ["notes"],
                "summary": "Read All Notes",
                "operationId": "read_all_notes_notes__get",
                "responses": {
                    "200": _response(
                        _SUCCESS,
                        {
                            "title": "Response Read All Notes Notes  Get",
                            "type": "array",
                            "items": _ref("NoteDB"),
                        },
                    )
                },
            },
            "post": {
                "tags": ["notes"],
                "summary": "Create Note",
                "operationId": "create_note_notes__post",
                "requestBody": _NOTE_REQUEST_BODY,
                "responses": {
                    "201": _response(_SUCCESS, _ref("NoteDB")),
                    "422": _VALIDATION_ERROR_RESPONSE,
                },
            },
        },
        "/notes/{id}/": {
            "get": {
                "tags": ["notes"],
                "summary": "Read Note",
                "operationId": "read_note_notes__id___get",
                "parameters": _ID_PARAMETERS,
                "responses": {
                    "200": _response(_SUCCESS, _ref("NoteDB")),
                    "422": _VALIDATION_ERROR_RESPONSE,
                },
            },
            "put": {
                "tags": ["notes"],
                "summary": "Update Note",
                "operationId": "update_note_notes__id___put",
                "parameters": _ID_PARAMETERS,
                "requestBody": _NOTE_REQUEST_BODY,
                "responses": {
                    "200": _response(_SUCCESS, _ref("NoteDB")),
                    "422": _VALIDATION_ERROR_RESPONSE,
                },
            },
            "delete": {
                "tags": ["notes"],
                "summary": "Delete Note",
                "operationId": "delete_note_notes__id___delete",
                "parameters": _ID_PARAMETERS,
                "responses": {
                    "200": _response(_SUCCESS, _ref("NoteDB")),
                    "422": _VALIDATION_ERROR_RESPONSE,
                },
            },
        },
    },
    "components": {
        "schemas": {
            "HTTPValidationError": {
                "title": "HTTPValidationError",
                "type": "object",
                "properties": {
                    "detail": {
                        "title": "Detail",
                        "type": "array",
                        "items": _ref("ValidationError"),
                    }
                },
            },
            "NoteDB": _model_schema(NoteDB),
            "NoteSchema": _model_schema(NoteSchema),
            "ValidationError": {
                "title": "ValidationError",
                "required": ["loc", "msg", "type"],
                "type": "object",
                "properties": {
                    "loc": {
                        "title": "Location",
                        "type": "array",
                        "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                    },
                    "msg": {"title": "Message", "type": "string"},
                    "type": {"title": "Error Type", "type": "string"},
                },
            },
        }
    },
}

SWAGGER_UI_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
    <link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui.css">
    <link rel="shortcut icon" href="{favicon}">
    <title>{title} - Swagger UI</title>
    </head>
    <body>
    <div id="swagger-ui">
    </div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui-bundle.js"></script>
    <!-- `SwaggerUIBundle` is now available on the page -->
    <script>
    const ui = SwaggerUIBundle({{
        url: '/openapi.json',
    "dom_id": "#swagger-ui",
"layout": "BaseLayout",
"deepLinking": true,
"showExtensions": true,
"showCommonExtensions": true,
oauth2RedirectUrl: window.location.origin + '/docs/oauth2-redirect',
    presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
    }})
    </script>
    </body>
    </html>
    """.format(favicon=_FAVICON_URL, title=_TITLE)

REDOC_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
    <title>{title} - ReDoc</title>
    <!-- needed for adaptive design -->
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
{pad}
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
{pad}
    <link rel="shortcut icon" href="{favicon}">
    <!--
    ReDoc doesn't change outer page styles
    -->
    <style>
      body {{
        margin: 0;
        padding: 0;
      }}
    </style>
    </head>
    <body>
    <noscript>
        ReDoc requires Javascript to function. Please enable it to browse the documentation.
    </noscript>
    <redoc spec-url="/openapi.json"></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"> </script>
    </body>
    </html>
    """.format(favicon=_FAVICON_URL, title=_TITLE, pad="    ")

SWAGGER_UI_OAUTH2_REDIRECT_HTML = """
    <!doctype html>
    <html lang="en-US">
    <head>
        <title>Swagger UI: OAuth2 Redirect</title>
    </head>
    <body>
    <script>
        'use strict';
        function run () {
            var oauth2 = window.opener.swaggerUIRedirectOauth2;
            var sentState = oauth2.state;
            var redirectUrl = oauth2.redirectUrl;
            var isValid, qp, arr;

            if (/code|token|error/.test(window.location.hash)) {
                qp = window.location.hash.substring(1).replace('?', '&');
            } else {
                qp = location.search.substring(1);
            }

            arr = qp.split("&");
            arr.forEach(function (v,i,_arr) { _arr[i] = '"' + v.replace('=', '":"') + '"';});
            qp = qp ? JSON.parse('{' + arr.join() + '}',
                    function (key, value) {
                        return key === "" ? value : decodeURIComponent(value);
                    }
            ) : {};

            isValid = qp.state === sentState;

            if ((
              oauth2.auth.schema.get("flow") === "accessCode" ||
              oauth2.auth.schema.get("flow") === "authorizationCode" ||
              oauth2.auth.schema.get("flow") === "authorization_code"
            ) && !oauth2.auth.code) {
                if (!isValid) {
                    oauth2.errCb({
                        authId: oauth2.auth.name,
                        source: "auth",
                        level: "warning",
                        message: "Authorization may be unsafe, passed state was changed in server. The passed state wasn't returned from auth server."
                    });
                }

                if (qp.code) {
                    delete oauth2.state;
                    oauth2.auth.code = qp.code;
                    oauth2.callback({auth: oauth2.auth, redirectUrl: redirectUrl});
                } else {
                    let oauthErrorMsg;
                    if (qp.error) {
                        oauthErrorMsg = "["+qp.error+"]: " +
                            (qp.error_description ? qp.error_description+ ". " : "no accessCode received from the server. ") +
                            (qp.error_uri ? "More info: "+qp.error_uri : "");
                    }

                    oauth2.errCb({
                        authId: oauth2.auth.name,
                        source: "auth",
                        level: "error",
                        message: oauthErrorMsg || "[Authorization failed]: no accessCode received from the server."
                    });
                }
            } else {
                oauth2.callback({auth: oauth2.auth, token: qp, isValid: isValid, redirectUrl: redirectUrl});
            }
            window.close();
        }

        if (document.readyState !== 'loading') {
            run();
        } else {
            document.addEventListener('DOMContentLoaded', function () {
                run();
            });
        }
    </script>
    </body>
    </html>
        """


def _html_response(html):
    return Response(html, content_type="text/html; charset=utf-8")


@router.route("/openapi.json", methods=["GET", "HEAD"], provide_automatic_options=False)
@implies_head
def openapi_spec():
    return json_response(SPEC)


@router.route("/docs", methods=["GET", "HEAD"], provide_automatic_options=False)
@implies_head
def swagger_ui_html():
    return _html_response(SWAGGER_UI_HTML)


@router.route(
    "/docs/oauth2-redirect", methods=["GET", "HEAD"], provide_automatic_options=False
)
@implies_head
def swagger_ui_redirect():
    return _html_response(SWAGGER_UI_OAUTH2_REDIRECT_HTML)


@router.route("/redoc", methods=["GET", "HEAD"], provide_automatic_options=False)
@implies_head
def redoc_html():
    return _html_response(REDOC_HTML)
