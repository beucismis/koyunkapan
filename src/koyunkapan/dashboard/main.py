import asyncio
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


@app.teardown_request
def close_db(exception=None) -> None:
    asyncio.run(database.close())


@app.route("/healthcheck")
async def healthcheck() -> flask.Response:
    return flask.jsonify(status="healthy", version=__version__, timestamp=datetime.now(UTC))


from . import views
