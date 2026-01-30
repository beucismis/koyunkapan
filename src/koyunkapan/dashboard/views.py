from collections import deque
from typing import Union

import flask
import werkzeug
from tortoise.functions import Count

from koyunkapan.bot import configs, models

from . import main


@main.app.route("/")
async def index() -> Union[str, werkzeug.wrappers.Response]:
    replies = await models.Reply.all().values("text", "submission_id", "comment_id", "subreddit__name")

    subreddit_activity = (
        await models.Reply.all()
        .group_by("subreddit__name")
        .annotate(count=Count("id"))
        .order_by("-count")
        .values("subreddit__name", "count")
    )
    chart_labels = [item["subreddit__name"] for item in subreddit_activity]
    chart_data = [item["count"] for item in subreddit_activity]

    popular_references = (
        await models.Reply.all()
        .group_by("reference_submission_id")
        .annotate(count=Count("id"))
        .order_by("-count")
        .limit(10)
        .values("reference_submission_id", "count")
    )

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
        chart_labels=chart_labels,
        chart_data=chart_data,
        popular_references=popular_references,
    )
