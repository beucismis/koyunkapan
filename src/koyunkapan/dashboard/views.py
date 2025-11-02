from collections import deque
from typing import Union

import flask
import werkzeug

from koyunkapan.bot import configs, models

from . import main


@main.app.route("/")
async def index() -> Union[str, werkzeug.wrappers.Response]:
    replies = await models.Reply.all().values("text", "submission_id", "comment_id", "subreddit__name")

    try:
        with open(configs.LOG_FILE, "r", encoding="utf-8") as f:
            logs = list(deque(f, 100))
    except FileNotFoundError:
        logs = [f"Log file not found at: {configs.LOG_FILE}"]
    except Exception as e:
        logs = [f"Error reading log file: {e}"]

    return flask.render_template(
        "index.html",
        replies=replies[-15:],
        total_replies=len(replies),
        logs=logs[-100:],
    )
