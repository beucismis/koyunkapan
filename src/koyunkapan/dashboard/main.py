import secrets
from datetime import UTC, datetime

import flask

from . import __version__

app = flask.Flask(__name__)
app.secret_key = secrets.token_hex(24)


@app.route("/healthcheck")
async def healthcheck() -> flask.Response:
    return flask.jsonify(status="healthy", version=__version__, timestamp=datetime.now(UTC))


from . import views
