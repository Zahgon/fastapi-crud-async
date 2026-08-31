import atexit

from flask import Flask

from app import openapi, routing
from app.api import notes, ping
from app.asyncsupport import run_async
from app.db import database, engine, metadata

metadata.create_all(engine)

app = Flask(__name__, static_folder=None)
routing.install(app)


def startup():
    run_async(database.connect())


def shutdown():
    run_async(database.disconnect())


app.register_blueprint(openapi.router)
app.register_blueprint(ping.router)
app.register_blueprint(notes.router, url_prefix="/notes")

startup()
atexit.register(shutdown)
