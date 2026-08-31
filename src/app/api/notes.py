from flask import Blueprint

from app.api import crud
from app.api.models import NoteDB, NoteSchema
from app.asyncsupport import run_async
from app.responses import HTTPException, json_response
from app.validation import (
    read_json_body,
    validate_body,
    validate_path_id,
    validate_request,
)

router = Blueprint("notes", __name__)


# The declaration order below is load bearing: a 405 advertises the methods of
# the first route registered for the requested path.


def _serialised(note):
    # Keyed access avoids ``dict(note)``, which calls the deprecated
    # ``Row.keys()`` and emits a DeprecationWarning per row.
    return NoteDB(
        id=note["id"], title=note["title"], description=note["description"]
    ).dict()


@router.route("/", methods=["POST"], provide_automatic_options=False)
def create_note():
    payload = validate_body(NoteSchema, read_json_body())
    note_id = run_async(crud.post(payload))

    response_object = {
        "id": note_id,
        "title": payload.title,
        "description": payload.description,
    }
    return json_response(NoteDB(**response_object).dict(), status_code=201)


@router.route("/<id>/", methods=["GET"], provide_automatic_options=False)
def read_note(id):
    id = validate_path_id(id)
    note = run_async(crud.get(id))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return json_response(_serialised(note))


@router.route("/", methods=["GET"], provide_automatic_options=False)
def read_all_notes():
    notes = run_async(crud.get_all())
    return json_response([_serialised(note) for note in notes])


@router.route("/<id>/", methods=["PUT"], provide_automatic_options=False)
def update_note(id):
    body = read_json_body()
    id, payload = validate_request(
        lambda: validate_path_id(id),
        lambda: validate_body(NoteSchema, body),
    )

    note = run_async(crud.get(id))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    note_id = run_async(crud.put(id, payload))

    response_object = {
        "id": note_id,
        "title": payload.title,
        "description": payload.description,
    }
    return json_response(NoteDB(**response_object).dict())


@router.route("/<id>/", methods=["DELETE"], provide_automatic_options=False)
def delete_note(id):
    id = validate_path_id(id)
    note = run_async(crud.get(id))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    run_async(crud.delete(id))

    return json_response(_serialised(note))
