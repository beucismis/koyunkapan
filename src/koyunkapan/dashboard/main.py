import atexit
import secrets
from datetime import UTC, datetime

import flask

from koyunkapan import __version__
from koyunkapan.bot import database


app = flask.Flask(__name__)
app.secret_key = secrets.token_hex(24)


@app.before_request
async def init_db() -> None:
    await database.init()


def close_db() -> None:
    await database.close()


@app.route("/healthcheck")
async def healthcheck() -> flask.Response:
    return flask.jsonify(status="healthy", version=__version__, timestamp=datetime.now(UTC))


atexit.register(close_db)


from . import views
