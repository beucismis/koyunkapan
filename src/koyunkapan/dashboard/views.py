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

    try:
        with open(configs.LOG_FILE, "r", encoding="utf-8") as f:
            logs = list(deque(f, 100))
    except FileNotFoundError:
        logs = [f"Log file not found at: {configs.LOG_FILE}"]
    except Exception as e:
        logs = [f"Error reading log file: {e}"]

    total_replies = await models.Reply.all().count()
    most_active_subreddits = (
        await models.Reply.all()
        .annotate(count=Count("id"))
        .group_by("subreddit__name")
        .order_by("-count")
        .limit(10)
        .values("subreddit__name", "count")
    )
    popular_replies = (
        await models.Reply.all()
        .annotate(count=Count("id"))
        .group_by("text")
        .order_by("-count")
        .limit(10)
        .values("text", "count")
    )

    return flask.render_template(
        "index.html",
        replies=replies,
        logs=logs[-100:],
        total_replies=total_replies,
        most_active_subreddits=most_active_subreddits,
        popular_replies=popular_replies,
    )
