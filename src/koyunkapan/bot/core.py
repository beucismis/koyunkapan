import asyncio
import random
import time
import warnings

import asyncpraw
import numpy as np
from asyncpraw.models import Comment, Message, Submission
from asyncprawcore import ServerError

from . import configs, database, models, utils
from .logger import Logger


log = Logger()
warnings.filterwarnings("ignore")


class Bot:
    def __init__(self, reddit_instance: asyncpraw.Reddit) -> None:
        self.reddit = reddit_instance
        self.posts, self.comments, self.keywords = [], [], []

    async def setup(self) -> None:
        subreddit_name = random.choice(configs.SUBREDDIT_NAMES)
        self.subreddit = await self.reddit.subreddit(subreddit_name)
        self.subreddit_obj, created = await models.Subreddit.get_or_create(name=subreddit_name)

        if created:
            log.info(f"Subreddit '{subreddit_name}' database created.")
        else:
            log.info(f"Subreddit '{subreddit_name}' database found.")

        self.flairs = await models.Flair.filter(subreddit=self.subreddit_obj).values_list("fid", flat=True)
        self.replies = await models.Reply.filter(subreddit=self.subreddit_obj).values_list("submission_id", flat=True)

        if not self.flairs:
            await self.init_flair_replies()

    async def init_flair_replies(self) -> None:
        log.info("Creating reply database for flairs...")

        try:
            new_flairs = []
            existing_flair_fids = await models.Flair.filter(subreddit=self.subreddit_obj).values_list("fid", flat=True)
            existing_flair_fids = set(existing_flair_fids)

            async for flair in self.subreddit.flair.link_templates:
                if flair["id"] not in existing_flair_fids:
                    new_flairs.append(models.Flair(fid=flair["id"], subreddit=self.subreddit_obj, name=flair["text"]))

            if new_flairs:
                await models.Flair.bulk_create(new_flairs)
                log.info(f"Added {len(new_flairs)} new flairs to the database.")

        except asyncpraw.exceptions.APIException as e:
            log.error(f"An API error occurred while fetching flairs: {e}")
        except Exception as e:
            log.error(f"An unexpected error occurred while fetching flairs: {e}")

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

    async def select_random_submission(self) -> Submission | None:
        for _ in range(configs.RANDOM_POST_COUNT):
            if not self.submissions:
                return None

            submission = random.choice(self.submissions)
            await submission.load()

            if len(submission.comments.list()) >= configs.RANDOM_POST_COUNT:
                return submission

        return None

    async def extract_keywords_from_submission(self, submission: Submission) -> None:
        self.keywords = []
        submission.comment_sort = "best"

        for word in submission.title.split():
            self.keywords.append(word.lower())

        await submission.load()

        for top_level_comment in submission.comments.list()[: configs.TOP_COMMENT_LIMIT]:
            if top_level_comment.body not in configs.FORBIDDEN_COMMENTS:
                comment_first_line = top_level_comment.body.splitlines()[0]
                for word in comment_first_line.split():
                    self.keywords.append(word.lower())

        self.keywords = list(dict.fromkeys(self.keywords))[: configs.MAX_KEYWORDS]

    async def find_similar_submissions(self, title: str, is_nsfw: bool) -> list[Submission] | None:
        results = []

        try:
            query = f"{(' OR ').join(title.split())} nsfw:{'yes' if is_nsfw else 'no'}"
            log.info(f"Query: '{query}'")

            async for post in self.subreddit.search(query, limit=configs.SEARCH_LIMIT):
                results.append(post)
            return results

        except ServerError as e:
            log.error(f"Server error occurred while searching for similar submissions: {e}")
            return None

    async def collect_comments_from_submissions(
        self, submissions: list[Submission], original_submission: Submission
    ) -> list[Comment]:
        comments = []

        for submission in submissions:
            submission.comment_sort = "best"
            await submission.load()

            if submission.id == original_submission.id:
                continue

            for top_level_comment in submission.comments.list()[: configs.TOP_COMMENT_LIMIT]:
                comment_text = top_level_comment.body.splitlines()[0].lower()

                if comment_text not in configs.FORBIDDEN_COMMENTS and len(comment_text) > 0:
                    comments.append(top_level_comment)

        log.info(f"'{len(comments)}' similar comments collected.")
        return comments

    def find_best_comment(self, submission: Submission, comments: list[Comment]) -> Comment | None:
        if comments:
            comment_scores = [
                (comment, utils.calculate_sentence_difference(comment.body.splitlines()[0].lower(), self.keywords))
                for comment in comments
            ]

            if not comment_scores:
                log.warning("Could not calculate scores for any comments.")
                return None

            min_score = min(score for comment, score in comment_scores)
            similar_comments = [
                comment for comment, score in comment_scores if score <= min_score * configs.SIMILARITY_THRESHOLD
            ]

            if similar_comments:
                similar_comments.sort(key=lambda c: c.score, reverse=True)
                best_comment = similar_comments[0]
                log.info(
                    f'Most suitable comment found: "{best_comment.body.splitlines()[0].lower()}" with score {best_comment.score}'
                )
                return best_comment

        log.warning("No suitable match found among similar comments.")
        return None

    async def submission_comment(self, submission: Submission, comment: Comment | None) -> None:
        if not comment:
            log.warning(f"No suitable comment found for submission '{submission.id}'.")
            return

        comment_text = comment.body.splitlines()[0].lower()

        if comment_text:
            try:
                bot_comment = await submission.reply(comment_text)

                try:
                    flair = await models.Flair.get(fid=submission.link_flair_template_id, subreddit=self.subreddit_obj)
                except Exception:
                    flair = None

                await models.Reply.create(
                    text=comment_text,
                    submission_id=submission.id,
                    comment_id=bot_comment.id,
                    reference_submission_id=comment.submission.id,
                    reference_comment_id=comment.id,
                    reference_author=comment.author,
                    flair=flair,
                    subreddit=self.subreddit_obj,
                )

                log.info(f"Successfully commented on post with ID '{submission.id}'.")

            except asyncpraw.exceptions.APIException as e:
                log.error(f"An API error occurred while commenting: {e}")
            except Exception as e:
                log.error(f"An unexpected error occurred while commenting: {e}")

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
        log.info(f"Title: '{submission.title}'")
        log.info(f"URL: https://reddit.com{submission.permalink}")

        await self.extract_keywords_from_submission(submission)
        log.info("Searching for similar submissions...")
        similar_submissions = await self.find_similar_submissions(submission.title, submission.over_18)

        if similar_submissions:
            comments = await self.collect_comments_from_submissions(similar_submissions, submission)
            best_comment = self.find_best_comment(submission, comments)
        else:
            best_comment = self.find_best_comment(submission, [])

        await self.submission_comment(submission, best_comment)
        log.info("--- Process Completed ---")

    async def reply_to_mention(self, mention: Message) -> None:
        log.info(f"New reply request received: {mention.id}")

        try:
            original_comment = await self.reddit.comment(mention.id)
            await original_comment.load()
            keywords = original_comment.body.split()

            if not keywords:
                log.warning("Comment to reply to is empty.")
                return

            search_queries = utils.get_keyword_combinations(keywords)
            log.info(f"{len(search_queries)} different search queries created.")

            subreddit_names = await models.Subreddit.all().values_list("name", flat=True)

            all_potential_source_comments = []
            processed_comment_ids = {original_comment.id}

            for i, query in enumerate(search_queries):
                log.info(f"Search {i + 1}/{len(search_queries)}: '{query}'")

                submissions = []
                for subreddit_name in subreddit_names:
                    subreddit = await self.reddit.subreddit(subreddit_name)
                    async for submission in subreddit.search(query, limit=configs.POST_LIMIT):
                        submissions.append(submission)

                for submission in submissions:
                    await submission.load()
                    await submission.comments.replace_more(limit=None)

                    for comment in submission.comments.list():
                        if comment.id not in processed_comment_ids and comment.body not in configs.FORBIDDEN_COMMENTS:
                            all_potential_source_comments.append(comment)
                            processed_comment_ids.add(comment.id)

            log.info(f"Collected {len(all_potential_source_comments)} potential source comments.")

            best_reply_found = None

            for source_comment in all_potential_source_comments:
                try:
                    await source_comment.refresh()
                    for reply in source_comment.replies:
                        if reply.body not in configs.FORBIDDEN_COMMENTS:
                            if best_reply_found is None or reply.score > best_reply_found.score:
                                best_reply_found = reply
                except Exception as e:
                    log.error(f"Error processing source comment {source_comment.id} for replies: {e}")

            if best_reply_found:
                log.info(f"Highest-rated reply found: '{best_reply_found.id}' with score {best_reply_found.score}")
                log.info(f"URL: https://www.reddit.com{best_reply_found.permalink}")

                existing_replies = [r.body for r in original_comment.replies]
                if best_reply_found.body not in existing_replies:
                    await original_comment.reply(best_reply_found.body)
                    log.info(f"Reply sent to comment with ID '{mention.id}'.")
                else:
                    log.warning(
                        f"Best reply found ('{best_reply_found.id}') has already been used for this comment chain."
                    )
            else:
                log.warning("No suitable reply found in any search results.")

        except Exception as e:
            log.error(f"An unexpected error occurred in reply_to_mention for mention {mention.id}: {e}")


async def check_inbox(bot: Bot) -> None:
    while True:
        try:
            async for item in bot.reddit.inbox.unread(limit=None):
                await item.mark_read()
                await Message.mark_read(item)

                if item.type == "comment_reply":
                    await bot.reply_to_mention(item)
        except Exception as e:
            log.error(f"An error occurred while checking inbox: {e}")

        await asyncio.sleep(configs.INBOX_CHECK_INTERVAL)


async def run_post_processor(bot: Bot) -> None:
    while True:
        await bot.setup()
        current_hour = time.strftime("%H")

        if current_hour in configs.WORKING_HOURS:
            try:
                log.info("Processing a random post...")
                await bot.process_post()
            except Exception as e:
                log.error(f"An exception occurred during the main process: {e}")

        else:
            log.info(f"Outside working hours ({configs.WORKING_HOURS}). Bot is inactive.")

        min_sleep_seconds, max_sleep_seconds = configs.MIN_SLEEP_MINUTES * 60, configs.MAX_SLEEP_MINUTES * 60
        sleep_duration = random.randint(min_sleep_seconds, max_sleep_seconds)
        minutes, seconds = divmod(sleep_duration, 60)
        log.info(f"Waiting for {minutes} minutes and {seconds} seconds...")
        await asyncio.sleep(sleep_duration)


async def main() -> None:
    async with asyncpraw.Reddit(site_name="bot", config_interpolation="basic") as reddit:
        if reddit.read_only:
            log.warnings("Connected in read-only mode. Check praw.ini configuration.")
            return

        log.info(f"Logged in as '{await reddit.user.me()}'")

        await database.init()
        bot = Bot(reddit)

        inbox_task = asyncio.create_task(check_inbox(bot))
        processor_task = asyncio.create_task(run_post_processor(bot))

        await asyncio.gather(inbox_task, processor_task)

    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
