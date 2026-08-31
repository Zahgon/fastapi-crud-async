import pytest

from app.api import crud
from app.api.models import NoteSchema
from app.asyncsupport import run_async


@pytest.fixture
def payload():
    return NoteSchema(title="integration", description="round trip")


@pytest.fixture(autouse=True)
def leave_the_table_as_it_was_found():
    # These are the only tests that write to the real database. The probe matrix
    # asserts on note ids and needs an empty table, so rows left behind here
    # would surface later as behavioural differences.
    before = {note["id"] for note in run_async(crud.get_all())}
    yield
    for note in run_async(crud.get_all()):
        if note["id"] not in before:
            run_async(crud.delete(note["id"]))


def test_post_returns_the_new_id(payload):
    note_id = run_async(crud.post(payload))

    assert isinstance(note_id, int)
    assert note_id > 0


def test_get_returns_the_stored_row(payload):
    note_id = run_async(crud.post(payload))

    note = run_async(crud.get(note_id))

    assert note["id"] == note_id
    assert note["title"] == "integration"
    assert note["description"] == "round trip"
    assert note["created_date"] is not None


def test_get_returns_nothing_for_an_unknown_id():
    assert run_async(crud.get(9_999_999)) is None


def test_get_all_includes_every_stored_row(payload):
    first = run_async(crud.post(payload))
    second = run_async(crud.post(payload))

    ids = [note["id"] for note in run_async(crud.get_all())]

    assert first in ids
    assert second in ids


def test_put_updates_the_row_and_returns_its_id(payload):
    note_id = run_async(crud.post(payload))

    updated = run_async(
        crud.put(note_id, NoteSchema(title="changed", description="also changed"))
    )

    assert updated == note_id
    note = run_async(crud.get(note_id))
    assert note["title"] == "changed"
    assert note["description"] == "also changed"


def test_delete_removes_the_row(payload):
    note_id = run_async(crud.post(payload))

    run_async(crud.delete(note_id))

    assert run_async(crud.get(note_id)) is None
