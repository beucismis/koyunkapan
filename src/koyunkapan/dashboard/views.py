import subprocess
from typing import Union

import flask
import werkzeug

from . import main
from koyunkapan.bot import database, configs, models


@main.app.route("/")
async def index() -> Union[str, werkzeug.wrappers.Response]:
    await database.init()
    replies = await models.Reply.all().values("text", "submission_id", "comment_id", "subreddit__name")

    with open(configs.LOG_FILE, "r", encoding="utf-8") as f:
        logs = f.readlines()

    try:
        result = subprocess.run(
            ["systemctl", "--user", "status", "koyunkapan-bot.service"],
            capture_output=True,
            text=True,
            check=False,
        )
        output_lines = result.stdout.splitlines()
        service_output = "\n".join(output_lines[:12])
    except Exception as e:
        service_output = f"Error fetching status: {e}"

    return flask.render_template("index.html", replies=replies, logs=logs[-100:], service_output=service_output)
