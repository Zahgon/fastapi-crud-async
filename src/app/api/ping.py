from flask import Blueprint

from app.responses import json_response

router = Blueprint("ping", __name__)


@router.route("/ping", methods=["GET"], provide_automatic_options=False)
def pong():
    # some async operation could happen here
    # example: `notes = await get_all_notes()`
    return json_response({"ping": "pong!"})
