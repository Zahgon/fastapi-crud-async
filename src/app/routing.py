from urllib.parse import urlsplit

from flask import Response, current_app, request
from werkzeug.datastructures import Headers
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import RequestRedirect

from app.responses import HTTPException, json_response, status_line
from app.validation import RequestValidationError, validation_error_response

# Methods the application actually declares, plus PATCH so that a request for an
# undeclared verb can still be traced back to the routes sharing its path.
_PROBE_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")

# The previous server emitted headers in this order; keeping it makes responses
# byte-comparable with the pre-migration capture.
_HEADER_ORDER = ("Allow", "Content-Length", "Content-Type", "Location")


def implies_head(view):
    """Mark a view as registered the way the documentation routes used to be.

    The previous server built its application endpoints and its documentation
    endpoints out of two different route classes. The application class took
    the declared method set verbatim, so ``HEAD /ping`` was a 405; the plain
    route class behind ``/openapi.json``, ``/docs``, ``/docs/oauth2-redirect``
    and ``/redoc`` added ``HEAD`` to any route declaring ``GET``, so those four
    answered ``HEAD`` and advertised it on a 405. Marking the view records
    which of the two a route belongs to.
    """
    view.implies_head = True
    return view


def install(app):
    """Give the Flask app the routing semantics of the previous router."""
    # `/notes//` collapsed to `/notes/` would be a redirect; it used to be a 404.
    # The flag is read when the map builds its matcher, so the map is replaced
    # rather than mutated. This has to happen before any route is registered.
    app.url_map = app.url_map_class(merge_slashes=False)

    app.before_request(_reject_implicit_methods)
    app.after_request(_normalise_response)

    app.register_error_handler(RequestValidationError, _handle_validation_error)
    app.register_error_handler(HTTPException, _handle_http_exception)
    app.register_error_handler(NotFound, _handle_not_found)
    app.register_error_handler(MethodNotAllowed, _handle_method_not_allowed)
    app.register_error_handler(Exception, _handle_server_error)


def _reject_implicit_methods():
    # Werkzeug implies HEAD on every GET rule. The previous router's application
    # routes did not, and answered `HEAD /ping` with a 405; its documentation
    # routes did, so those are left alone.
    rule = request.url_rule
    if (
        rule is not None
        and request.method == "HEAD"
        and not _implies_head(rule.endpoint)
    ):
        raise MethodNotAllowed()


def _implies_head(endpoint):
    return getattr(current_app.view_functions.get(endpoint), "implies_head", False)


def _normalise_response(response):
    if response.status_code == 308:
        # Werkzeug's "add the missing trailing slash" redirect was a 307 with an
        # empty body and no content type.
        response.status = status_line(307)
        response.set_data(b"")
        response.headers.pop("Content-Type", None)
    _order_headers(response)
    return response


def _order_headers(response):
    ordered = [
        (name, value)
        for name in _HEADER_ORDER
        for value in response.headers.getlist(name)
    ]
    remaining = [
        (name, value)
        for name, value in response.headers.items()
        if name not in _HEADER_ORDER
    ]
    response.headers = Headers(ordered + remaining)


def _handle_validation_error(error):
    return validation_error_response(error.errors)


def _handle_http_exception(error):
    return json_response({"detail": error.detail}, status_code=error.status_code)


def _handle_not_found(error):
    redirect = _trailing_slash_redirect()
    if redirect is not None:
        return redirect
    return json_response({"detail": "Not Found"}, status_code=404)


def _handle_method_not_allowed(error):
    headers = {}
    allow = _allow_header()
    if allow:
        headers["Allow"] = allow
    return json_response(
        {"detail": "Method Not Allowed"}, status_code=405, headers=headers
    )


def _handle_server_error(error):
    current_app.logger.exception("Unhandled application error")
    return Response(
        "Internal Server Error",
        status=status_line(500),
        content_type="text/plain; charset=utf-8",
    )


def _trailing_slash_redirect():
    """Redirect `/ping/` to `/ping`, mirroring the previous slash handling.

    Werkzeug already adds a missing trailing slash; only the stripping half is
    missing. All trailing slashes are removed at once, so `/notes//` becomes
    `/notes`, which matches nothing and stays a 404.
    """
    if request.path == "/" or not request.path.endswith("/"):
        return None

    candidate = request.path.rstrip("/")
    if not candidate or not _route_exists(candidate):
        return None

    parts = urlsplit(request.url)
    location = parts._replace(path=parts.path.rstrip("/"), fragment="").geturl()

    response = Response(b"", status=status_line(307))
    response.headers.pop("Content-Type", None)
    response.headers["Location"] = location
    return response


def _route_exists(path):
    adapter = current_app.url_map.bind_to_environ(request.environ)
    for method in _PROBE_METHODS:
        try:
            adapter.match(path, method=method)
        except MethodNotAllowed:
            return True
        except (NotFound, RequestRedirect):
            continue
        else:
            return True
    return False


def _allow_header():
    """Report the methods of the first declared route matching the path.

    The previous router answered a 405 with the methods of the first route whose
    path matched, not with the union across every matching route: `PATCH
    /notes/1/` advertises `GET` even though PUT and DELETE are also registered.
    """
    adapter = current_app.url_map.bind_to_environ(request.environ)
    endpoints = []
    for method in _PROBE_METHODS:
        try:
            endpoint, _ = adapter.match(request.path, method=method)
        except (NotFound, MethodNotAllowed, RequestRedirect):
            continue
        if endpoint not in endpoints:
            endpoints.append(endpoint)

    if not endpoints:
        return None

    # `view_functions` is insertion ordered, so it preserves declaration order.
    declaration_order = list(current_app.view_functions)
    first = min(endpoints, key=declaration_order.index)

    methods = set()
    for rule in current_app.url_map.iter_rules(first):
        methods |= rule.methods - {"HEAD", "OPTIONS"}
    if _implies_head(first):
        methods.add("HEAD")
    return ", ".join(sorted(methods))
