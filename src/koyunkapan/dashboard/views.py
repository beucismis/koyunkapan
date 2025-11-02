import asyncio
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

    bot_status = "Down"
    bot_uptime = "N/A"

    try:
        command = "ps -ef | grep '[p]ython3 -m koyunkapan.bot.core'"
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if stdout:
            pid = stdout.decode().strip().split()[1]
            bot_status = "Running"

            process = await asyncio.create_subprocess_exec(
                "ps",
                "-p",
                pid,
                "-o",
                "etimes=",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if stdout:
                elapsed_seconds = int(stdout.decode().strip())
                days, remainder = divmod(elapsed_seconds, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, _ = divmod(remainder, 60)
                bot_uptime = f"{days} days, {hours} hours, {minutes} minutes"

    except Exception as e:
        bot_status = f"Error: {e}"

    return flask.render_template(
        "index.html",
        replies=replies,
        logs=logs[-100:],
        bot_status=bot_status,
        bot_uptime=bot_uptime,
    )
