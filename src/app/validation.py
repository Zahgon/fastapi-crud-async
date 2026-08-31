import email.message
import json
from functools import lru_cache

from flask import request
from pydantic import BaseModel, Field, ValidationError, create_model

from app.responses import json_response


class RequestValidationError(Exception):
    """Carries a list of pydantic-shaped error dicts for a 422 response."""

    def __init__(self, errors):
        super().__init__(errors)
        self.errors = errors


def validation_error_response(errors):
    return json_response({"detail": errors}, status_code=422)


class _PathId(BaseModel):
    id: int = Field(..., gt=0)


@lru_cache(maxsize=None)
def _body_model(model):
    # Wrapping the payload in a single ``body`` field reproduces the error
    # locations of the previous router, which validated the whole request body
    # as one field named "body".
    return create_model(f"{model.__name__}Body", body=(model, ...))


def _prefixed(errors, *prefix):
    return [{**error, "loc": [*prefix, *error["loc"]]} for error in errors]


def validate_path_id(raw):
    try:
        return _PathId(id=raw).id
    except ValidationError as exc:
        raise RequestValidationError(_prefixed(exc.errors(), "path")) from exc


def read_json_body():
    """Decode the request body using the previous router's content-type rules.

    An absent content-type means JSON, ``application/json`` and
    ``application/*+json`` mean JSON, and anything else is handed to the model
    as raw bytes so it fails with "value is not a valid dict".
    """
    body_bytes = request.get_data()
    if not body_bytes:
        return None

    content_type_value = request.headers.get("content-type")
    if content_type_value:
        message = email.message.Message()
        message["content-type"] = content_type_value
        if message.get_content_maintype() != "application":
            return body_bytes
        subtype = message.get_content_subtype()
        if subtype != "json" and not subtype.endswith("+json"):
            return body_bytes

    try:
        return json.loads(body_bytes)
    except json.JSONDecodeError as exc:
        raise RequestValidationError(
            [
                {
                    "loc": ["body", exc.pos],
                    "msg": str(exc),
                    "type": "value_error.jsondecode",
                    "ctx": dict(exc.__dict__),
                }
            ]
        ) from exc


def validate_body(model, body):
    # An absent body has to look "missing" rather than "not allowed to be
    # null", so the field is omitted instead of passed as None.
    fields = {} if body is None else {"body": body}
    try:
        return _body_model(model)(**fields).body
    except ValidationError as exc:
        raise RequestValidationError(_prefixed(exc.errors())) from exc


def validate_request(*validators):
    """Run every validator, collecting errors so path errors precede body ones."""
    values = []
    errors = []
    for validator in validators:
        try:
            values.append(validator())
        except RequestValidationError as exc:
            errors.extend(exc.errors)
            values.append(None)
    if errors:
        raise RequestValidationError(errors)
    return values
