import asyncio
import re
from collections import deque
from datetime import datetime, timezone
from typing import Union

import flask
import werkzeug

from . import main
from koyunkapan.bot import configs, models


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

    uptime_string = "N/A"

    try:
        process = await asyncio.create_subprocess_exec(
            "systemctl",
            "--user",
            "status",
            "koyunkapan-bot.service",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if stdout:
            output = stdout.decode()
            output_lines = output.splitlines()
            service_output = "\n".join(output_lines[:10])

            match = re.search(r"since (.*?);", output)
            if match:
                start_time_str = match.group(1)
                start_time = datetime.strptime(start_time_str.strip(), "%a %Y-%m-%d %H:%M:%S %Z")
                start_time = start_time.replace(tzinfo=timezone.utc)

                uptime_delta = datetime.now(timezone.utc) - start_time

                days = uptime_delta.days
                hours, remainder = divmod(uptime_delta.seconds, 3600)
                minutes, _ = divmod(remainder, 60)

                uptime_string = f"{days} days, {hours} hours, {minutes} minutes"
        else:
            service_output = stderr.decode()

    except Exception as e:
        service_output = f"Error fetching status: {e}"
        uptime_string = "Error"

    return flask.render_template(
        "index.html", replies=replies, logs=logs[-100:], service_output=service_output, uptime=uptime_string
    )
