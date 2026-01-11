import asyncio
import configparser
import os
import random
import re
import time
import warnings

import asyncpraw
from asyncpraw.exceptions import APIException
from asyncpraw.models import Comment, Message, Submission
from asyncprawcore.exceptions import RequestException, ServerError, TooManyRequests

from . import configs, database, models, utils
from .logger import Logger
from .utils import handle_api_exceptions

log = Logger()
warnings.filterwarnings("ignore")


class Bot:
    def __init__(self, reddit_instance: asyncpraw.Reddit) -> None:
        self.reddit = reddit_instance
        self.keywords = []
        self.subreddit_names = []

    async def setup(self) -> None:
        subreddits = list(configs.SUBREDDIT_WEIGHTS.keys())
        weights = list(configs.SUBREDDIT_WEIGHTS.values())
        subreddit_name = random.choices(subreddits, weights=weights, k=1)[0]
        self.subreddit = await self.reddit.subreddit(subreddit_name)
        self.subreddit_obj, created = await models.Subreddit.get_or_create(name=subreddit_name)
        self.flairs = await models.Flair.filter(subreddit=self.subreddit_obj).values_list("fid", flat=True)
        self.replies = await models.Reply.filter(subreddit=self.subreddit_obj).values_list("submission_id", flat=True)
        self.subreddit_names = await models.Subreddit.all().values_list("name", flat=True)

        if not self.flairs:
            await self.init_flair_replies()

    @handle_api_exceptions()
    async def init_flair_replies(self) -> None:
        new_flairs = []
        existing_flair_fids = await models.Flair.filter(subreddit=self.subreddit_obj).values_list("fid", flat=True)
        existing_flair_fids = set(existing_flair_fids)

        async for flair in self.subreddit.flair.link_templates:
            if flair["id"] not in existing_flair_fids:
                new_flairs.append(
                    models.Flair(
                        fid=flair["id"],
                        subreddit=self.subreddit_obj,
                        name=flair["text"],
                    )
                )

        if new_flairs:
            await models.Flair.bulk_create(new_flairs)
            log.info(f"Added {len(new_flairs)} new flairs to the database.")

    @handle_api_exceptions()
    async def fetch_new_submissions(self) -> None:
        self.submissions = []
        seen_ids = set()

        def _is_valid(submission):
            return submission.id not in self.replies and submission.link_flair_text != configs.FORBIDDEN_FLAIR

        async def _collect(generator):
            async for submission in generator:
                if submission.id not in seen_ids and _is_valid(submission):
                    self.submissions.append(submission)
                    seen_ids.add(submission.id)

        await _collect(self.subreddit.new(limit=configs.POST_LIMIT))
        await _collect(self.subreddit.hot(limit=configs.POST_LIMIT))

        log.info(f"{len(self.submissions)} potential submission collected.")

    @handle_api_exceptions()
    async def select_random_submission(self) -> Submission | None:
        for _ in range(configs.RANDOM_POST_COUNT):
            if not self.submissions:
                return None

            submission = random.choice(self.submissions)
            await submission.load()

            if submission.num_comments >= configs.RANDOM_POST_COUNT:
                return submission

        return None

    @handle_api_exceptions()
    async def extract_keywords_from_submission(self, submission: Submission) -> None:
        self.keywords = []
        submission.comment_sort = "best"

        for word in submission.title.split():
            self.keywords.append(word.lower())

        await submission.load()

        for top_level_comment in submission.comments.list()[: configs.TOP_COMMENT_LIMIT]:
            if (
                top_level_comment.body
                and top_level_comment.body.strip()
                and top_level_comment.body not in configs.FORBIDDEN_COMMENTS
            ):
                comment_first_line = top_level_comment.body.splitlines()[0]

                for word in comment_first_line.split():
                    self.keywords.append(word.lower())

        self.keywords = list(dict.fromkeys(self.keywords))[: configs.MAX_KEYWORDS]

    @handle_api_exceptions()
    async def find_similar_submissions(self, title: str, is_nsfw: bool) -> list[Submission] | None:
        results = []
        query = f"{(' OR ').join(title.split())} nsfw:{'yes' if is_nsfw else 'no'}"
        log.info(f"Query: '{query}'")

        async for post in self.subreddit.search(query, limit=configs.SEARCH_LIMIT):
            results.append(post)

        return results

    async def collect_comments_from_submissions(
        self, submissions: list[Submission], original_submission: Submission
    ) -> list[Comment]:
        comments = []

        for submission in submissions:
            if submission.id == original_submission.id:
                continue

            submission.comment_sort = "best"

            for attempt in range(3):
                try:
                    await submission.load()

                    for top_level_comment in submission.comments.list()[: configs.TOP_COMMENT_LIMIT]:
                        try:
                            comment_text = top_level_comment.body.splitlines()[0].lower()

                            if comment_text not in configs.FORBIDDEN_COMMENTS and len(comment_text) > 0:
                                comments.append(top_level_comment)
                        except IndexError:
                            log.warning(f"Comment '{top_level_comment.id}' has an empty body, skipping.")
                            continue
                    break

                except (APIException, TooManyRequests) as e:
                    if (isinstance(e, APIException) and e.error_type == "RATELIMIT") or isinstance(e, TooManyRequests):
                        message = e.message if isinstance(e, APIException) else str(e)
                        log.warning(f"Rate limit exceeded on submission {submission.id}: {message}. Retrying...")

                        try:
                            sleep_time_str = re.search(r"(\d+)\s+(minutes|seconds)", message)

                            if sleep_time_str:
                                sleep_time = int(sleep_time_str.group(1))

                                if sleep_time_str.group(2) == "minutes":
                                    sleep_time *= 60

                                log.info(f"Sleeping for {sleep_time} seconds due to rate limit.")
                                await asyncio.sleep(sleep_time)
                            else:
                                await asyncio.sleep(5 * (2**attempt))
                        except (AttributeError, IndexError):
                            await asyncio.sleep(5 * (2**attempt))
                    else:
                        log.error(f"API Exception on submission {submission.id}: {e}")
                        break
                except (RequestException, ServerError) as e:
                    log.warning(f"Request/Server Exception on submission {submission.id}: {e}. Retrying...")
                    await asyncio.sleep(5 * (2**attempt))
                except Exception as e:
                    log.error(
                        f"An unexpected error of type {type(e).__name__} occurred on submission {submission.id}: {e}"
                    )
                    break

        log.info(f"'{len(comments)}' similar comments collected.")
        return comments

    def find_best_comments(self, comments: list[Comment]) -> list[Comment]:
        if comments:
            comment_scores = [
                (
                    comment,
                    utils.calculate_sentence_difference(comment.body.splitlines()[0].lower(), self.keywords),
                )
                for comment in comments
            ]

            if not comment_scores:
                log.warning("Could not calculate scores for any comments.")
                return []

            min_score = min(score for comment, score in comment_scores)
            similar_comments = [
                comment for comment, score in comment_scores if score <= min_score * configs.SIMILARITY_THRESHOLD
            ]

            if similar_comments:
                similar_comments.sort(key=lambda c: c.score, reverse=True)
                return similar_comments

        log.warning("No suitable match found among similar comments.")
        return []

    @handle_api_exceptions()
    async def submission_comment(self, submission: Submission, comments: list[Comment]) -> None:
        if not comments:
            log.warning(f"No suitable comments found for submission '{submission.id}'.")
            return

        best_comment = None

        for comment in comments:
            try:
                comment_text = comment.body.splitlines()[0].lower()
                is_used = await models.Reply.filter(reference_comment_id=comment.id).exists()

                if not is_used:
                    best_comment = comment
                    break
            except IndexError:
                log.warning(f"Comment '{comment.id}' has an empty body, skipping.")
                continue

        if not best_comment:
            log.warning(f"All suitable comments for submission '{submission.id}' have already been used.")
            return

        comment_text = best_comment.body.splitlines()[0].lower()

        if not comment_text.strip():
            log.warning(f"Comment text for submission '{submission.id}' is empty or whitespace, skipping.")
            return

        bot_comment = await submission.reply(comment_text)

        try:
            flair = await models.Flair.get(fid=submission.link_flair_template_id, subreddit=self.subreddit_obj)
        except Exception:
            flair = None

        await models.Reply.create(
            text=comment_text,
            submission_id=submission.id,
            comment_id=bot_comment.id,
            reference_submission_id=best_comment.submission.id,
            reference_comment_id=best_comment.id,
            reference_author=str(best_comment.author),
            flair=flair,
            subreddit=self.subreddit_obj,
        )

        log.info(f"Successfully commented on post with ID '{submission.id}'.")

    @handle_api_exceptions()
    async def process_post(self, submission_id: str | None = None) -> None:
        if submission_id:
            submission = await self.reddit.submission(id=submission_id)
        else:
            await self.fetch_new_submissions()
            submission = await self.select_random_submission()

        log.info("Random submission selected.")

        if not submission:
            log.warning("No suitable submission found for processing.")
            return

        log.info(f"--- Process Started: '{submission.id}' ---")
        await self.extract_keywords_from_submission(submission)
        log.info("Searching for similar submissions...")
        similar_submissions = await self.find_similar_submissions(submission.title, submission.over_18)

        if similar_submissions:
            comments = await self.collect_comments_from_submissions(similar_submissions, submission)
            best_comments = self.find_best_comments(comments)
        else:
            best_comments = self.find_best_comments([])

        await self.submission_comment(submission, best_comments)
        log.info("--- Process Completed ---")

    async def select_random_comment(self, submission: Submission) -> Comment | None:
        comments = submission.comments.list()

        if not comments:
            return None

        for _ in range(configs.RANDOM_POST_COUNT):
            comment = random.choice(comments)

            if comment.body and comment.body.strip() and comment.body not in configs.FORBIDDEN_COMMENTS:
                return comment

        return None

    @handle_api_exceptions()
    async def _search_submissions(self, query: str) -> list[Submission]:
        submissions = []

        async def search_in_subreddit(subreddit_name):
            subreddit = await self.reddit.subreddit(subreddit_name)

            async for submission in subreddit.search(query, limit=configs.POST_LIMIT):
                submissions.append(submission)

        await asyncio.gather(*(search_in_subreddit(name) for name in self.subreddit_names))
        return submissions

    async def _collect_source_comments(
        self, submissions: list[Submission], processed_comment_ids: set
    ) -> list[Comment]:
        all_potential_source_comments = []
        limit_reached = False

        for submission in submissions:
            if limit_reached:
                break

            for attempt in range(3):
                try:
                    await submission.load()
                    await submission.comments.replace_more(limit=0)

                    for comment in submission.comments.list():
                        if limit_reached:
                            break

                        if comment.id not in processed_comment_ids and comment.body not in configs.FORBIDDEN_COMMENTS:
                            all_potential_source_comments.append(comment)
                            processed_comment_ids.add(comment.id)

                            if len(all_potential_source_comments) > 200:
                                limit_reached = True
                    break

                except (APIException, TooManyRequests) as e:
                    if (isinstance(e, APIException) and e.error_type == "RATELIMIT") or isinstance(e, TooManyRequests):
                        message = e.message if isinstance(e, APIException) else str(e)
                        log.warning(f"Rate limit exceeded on submission {submission.id}: {message}. Retrying...")

                        try:
                            sleep_time_str = re.search(r"(\d+)\s+(minutes|seconds)", message)

                            if sleep_time_str:
                                sleep_time = int(sleep_time_str.group(1))

                                if sleep_time_str.group(2) == "minutes":
                                    sleep_time *= 60

                                log.info(f"Sleeping for {sleep_time} seconds due to rate limit.")
                                await asyncio.sleep(sleep_time)
                            else:
                                await asyncio.sleep(5 * (2**attempt))
                        except (AttributeError, IndexError):
                            await asyncio.sleep(5 * (2**attempt))
                    else:
                        log.error(f"API Exception on submission {submission.id}: {e}")
                        break
                except (RequestException, ServerError) as e:
                    log.warning(f"Request/Server Exception on submission {submission.id}: {e}. Retrying...")
                    await asyncio.sleep(5 * (2**attempt))
                except Exception as e:
                    log.error(
                        f"An unexpected error of type {type(e).__name__} occurred on submission {submission.id}: {e}"
                    )
                    break

        return all_potential_source_comments

    async def _collect_replies(self, source_comments: list[Comment]) -> list[Comment]:
        all_replies = []

        for i, source_comment in enumerate(source_comments):
            if i > 0 and i % 20 == 0:
                await asyncio.sleep(10)

            for attempt in range(3):
                try:
                    await source_comment.load()

                    for reply in source_comment.replies:
                        if reply.body and reply.body.strip() and reply.body not in configs.FORBIDDEN_COMMENTS:
                            all_replies.append(reply)
                    break

                except (APIException, TooManyRequests) as e:
                    if (isinstance(e, APIException) and e.error_type == "RATELIMIT") or isinstance(e, TooManyRequests):
                        message = e.message if isinstance(e, APIException) else str(e)
                        log.warning(f"Rate limit exceeded on comment {source_comment.id}: {message}. Retrying...")

                        try:
                            sleep_time_str = re.search(r"(\d+)\s+(minutes|seconds)", message)

                            if sleep_time_str:
                                sleep_time = int(sleep_time_str.group(1))

                                if sleep_time_str.group(2) == "minutes":
                                    sleep_time *= 60

                                log.info(f"Sleeping for {sleep_time} seconds due to rate limit.")
                                await asyncio.sleep(sleep_time)
                            else:
                                await asyncio.sleep(5 * (2**attempt))
                        except (AttributeError, IndexError):
                            await asyncio.sleep(5 * (2**attempt))
                    else:
                        log.error(f"API Exception on comment {source_comment.id}: {e}")
                        break
                except (RequestException, ServerError) as e:
                    log.warning(f"Request/Server Exception on comment {source_comment.id}: {e}. Retrying...")
                    await asyncio.sleep(5 * (2**attempt))
                except Exception as e:
                    log.error(
                        f"An unexpected error of type {type(e).__name__} occurred on comment {source_comment.id}: {e}"
                    )
                    break

        return all_replies

    async def _find_best_reply(self, replies: list[Comment]) -> Comment | None:
        if not replies:
            return None

        replies.sort(key=lambda r: r.score, reverse=True)

        for reply in replies:
            is_used = await models.Reply.filter(reference_comment_id=reply.id).exists()

            if not is_used:
                return reply

        return None

    @handle_api_exceptions()
    async def mark_as_read(self, item: Message) -> None:
        await item.mark_read()

    async def reply_to_mention(self, mention: Message) -> bool:
        log.info(f"New reply request received: {mention.id}")

        try:
            if not mention.parent_id.startswith("t1_"):
                log.warning(f"Parent of mention {mention.id} is not a comment, skipping.")
                return False

            original_comment = await self.reddit.comment(mention.parent_id)
            await original_comment.load()
            keywords = original_comment.body.split()
        except (APIException, RequestException, ServerError) as e:
            log.error(f"Failed to fetch original comment for mention {mention.id}: {e}")
            return False

        if not keywords:
            log.warning("Comment to reply to is empty.")
            return False

        search_queries = utils.get_keyword_combinations(keywords)
        log.info(f"{len(search_queries)} different search queries created.")
        submissions = []
        subreddit_to_search = original_comment.subreddit

        try:
            for query in search_queries:
                async for submission in subreddit_to_search.search(query, limit=configs.POST_LIMIT):
                    submissions.append(submission)

                if len(submissions) > 200:
                    break
        except (APIException, RequestException, ServerError) as e:
            log.error(f"Error searching for submissions in {subreddit_to_search.display_name}: {e}")
            return False

        all_potential_source_comments = []
        processed_comment_ids = {original_comment.id}

        if submissions:
            source_comments = await self._collect_source_comments(submissions, processed_comment_ids)
            if source_comments:
                all_potential_source_comments.extend(source_comments)

        log.info(f"Collected {len(all_potential_source_comments)} potential source comments.")

        if not all_potential_source_comments:
            log.warning("No potential source comments found.")
            return False

        all_replies = await self._collect_replies(all_potential_source_comments)

        if not all_replies:
            log.warning("No replies found for the given source comments.")
            return False

        best_reply = await self._find_best_reply(all_replies)

        if best_reply:
            log.info(f"Highest-rated reply found: '{best_reply.id}' with score {best_reply.score}")

            if not best_reply.body.strip():
                log.warning(f"Reply text for mention '{mention.id}' is empty or whitespace, skipping.")
                return False

            comment_text = best_reply.body.strip()[:10000]
            bot_comment = await mention.reply(comment_text)

            if not bot_comment:
                log.error(f"Failed to send reply to mention {mention.id}")
                return False

            log.info(f"Reply sent to comment with ID '{mention.id}'.")
            subreddit_name = original_comment.subreddit.display_name
            subreddit_obj, created = await models.Subreddit.get_or_create(name=subreddit_name)

            await models.Reply.create(
                text=best_reply.body,
                submission_id=original_comment.submission.id,
                comment_id=bot_comment.id,
                reference_submission_id=best_reply.submission.id,
                reference_comment_id=best_reply.id,
                reference_author=str(best_reply.author),
                subreddit=subreddit_obj,
            )
            return True

        else:
            log.warning("No suitable reply found in any search results.")
            return False


async def check_inbox(bot: Bot) -> None:
    while True:
        try:
            async for item in bot.reddit.inbox.unread(limit=None):
                if item.type == "comment_reply":
                    try:
                        success = await bot.reply_to_mention(item)
                        if success:
                            await bot.mark_as_read(item)
                        else:
                            log.warning(f"Failed to process mention {item.id}, marking as read to avoid loop.")
                            await bot.mark_as_read(item)
                    except Exception as e:
                        log.error(f"An unexpected error occurred while processing mention {item.id}: {e}")
                        await bot.mark_as_read(item)
        except (APIException, RequestException, ServerError) as e:
            log.error(f"An error occurred while checking inbox: {e}")

        await asyncio.sleep(configs.INBOX_CHECK_INTERVAL)


@handle_api_exceptions()
async def run_comment_processor(bot: Bot) -> None:
    while True:
        await bot.setup()

        if time.strftime("%H") in configs.WORKING_HOURS:
            log.info("Processing a random post...")
            await bot.process_post()

        min_sleep_seconds, max_sleep_seconds = (
            configs.MIN_SLEEP_MINUTES * 60,
            configs.MAX_SLEEP_MINUTES * 60,
        )
        sleep_duration = random.randint(min_sleep_seconds, max_sleep_seconds)
        await asyncio.sleep(sleep_duration)


async def main() -> None:
    config_path = os.path.join(configs.DATA_DIR, "praw.ini")
    config = configparser.ConfigParser()
    config.read(config_path)

    async with asyncpraw.Reddit(
        client_id=config.get("bot", "client_id"),
        client_secret=config.get("bot", "client_secret"),
        user_agent=config.get("bot", "user_agent"),
        username=config.get("bot", "username"),
        password=config.get("bot", "password"),
    ) as reddit:
        if reddit.read_only:
            log.warnings("Connected in read-only mode. Check praw.ini configuration.")
            return

        log.info(f"Logged in as '{await reddit.user.me()}'")

        await database.init()
        bot = Bot(reddit)

        inbox_task = asyncio.create_task(check_inbox(bot))
        processor_task = asyncio.create_task(run_comment_processor(bot))

        await asyncio.gather(inbox_task, processor_task)

    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
