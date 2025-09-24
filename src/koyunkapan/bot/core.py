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
        self.replies = await models.Reply.filter(flair__subreddit=self.subreddit_obj).values_list("text", flat=True)

        if not self.flairs:
            await self.init_flair_replies()

    async def init_flair_replies(self) -> None:
        log.info("Creating reply database for flairs...")

        try:
            async for flair in self.subreddit.flair.link_templates:
                # if flair["id"] not in self.replies:
                await models.Flair.create(fid=flair["id"], name=flair["text"], subreddit=self.subreddit_obj)
        except Exception as e:
            log.error(f"Error while fetching flairs: {e}")

    async def fetch_new_submissions(self) -> None:
        self.submissions = []

        def is_valid(submission):
            return submission.id not in self.replies and submission.link_flair_text != configs.FORBIDDEN_FLAIR

        async for submission in self.subreddit.new(limit=configs.POST_LIMIT):
            if is_valid(submission) and submission not in self.submissions:
                self.submissions.append(submission)
        async for submission in self.subreddit.hot(limit=configs.POST_LIMIT):
            if is_valid(submission) and submission not in self.submissions:
                self.submissions.append(submission)

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
    ) -> None:
        self.comments = []

        for submission in submissions:
            submission.comment_sort = "best"
            await submission.load()

            if submission.id == original_submission.id:
                continue

            for top_level_comment in submission.comments.list()[: configs.TOP_COMMENT_LIMIT]:
                comment_text = top_level_comment.body.splitlines()[0].lower()

                if comment_text not in configs.FORBIDDEN_COMMENTS and len(comment_text) > 0:
                    self.comments.append(top_level_comment)

        log.info(f"'{len(self.comments)}' similar comments collected.")

    def find_best_comment(self, submission: Submission) -> Comment | None:
        if self.comments:
            scores = np.array(
                [
                    utils.calculate_sentence_difference(comment.body.splitlines()[0].lower(), self.keywords)
                    for comment in self.comments
                ]
            )
            min_score = np.min(scores)
            best_indices = np.where((scores == min_score) | (scores <= min_score * configs.SIMILARITY_THRESHOLD))[0]

            if best_indices.size > 0:
                chosen_index = random.choice(best_indices)
                best_comment = self.comments[chosen_index]
                log.info(f'Most suitable comment found: "{best_comment.body.splitlines()[0].lower()}"')
                return best_comment

        log.warning("No suitable match found among similar comments.")
        return

        if submission.link_flair_template_id and submission.link_flair_template_id in self.replies_data:
            flair_replies = self.replies_data[submission.link_flair_template_id]["replies"]

            if flair_replies:
                chosen_reply = random.choice(flair_replies)
                log.info(f"Using flair-specific reply: '{chosen_reply}'")
                return chosen_reply

        log.warning("No suitable comment found.")
        return None

    async def submission_comment(self, submission: Submission, comment: Comment) -> None:
        comment_text = comment.body.splitlines()[0].lower()

        if comment_text:
            try:
                # --- --- --- --- --- --- --- --- --- --- --- ---
                bot_comment = await submission.reply(comment_text)
                # --- --- --- --- --- --- --- --- --- --- --- ---

                try:
                    flair = await models.Flair.get(fid=submission.link_flair_template_id, subreddit=self.subreddit_obj)
                except Exception as e:
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

            except Exception as e:
                log.error(f"An error occurred while commenting: {e}")

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
            await self.collect_comments_from_submissions(similar_submissions, submission)

        best_comment = self.find_best_comment(submission)
        await self.submission_comment(submission, best_comment)
        log.info("--- Process Completed ---")

    async def reply_to_mention(self, mention: Message) -> None:
        comments = []
        all_comments = set()
        submissions = []
        best_reply_source = None

        log.info(f"New reply request received: {mention.id}")
        original_comment = await self.reddit.comment(mention.id)
        keywords = original_comment.body.split()

        if not keywords:
            log.warning("Comment to reply to is empty.")
            return

        search_queries = utils.get_keyword_combinations(keywords)
        log.info(f"{len(search_queries)} different search queries created.")

        for i, query in enumerate(search_queries):
            cache = []
            log.info(f"Search {i + 1}/{len(search_queries)}: '{query}'")

            async for submission in original_comment.subreddit.new(limit=configs.POST_LIMIT):
                submissions.append(submission)

            for submission in submissions:
                await submission.load()
                await submission.comments.replace_more(limit=None)

                for comment in submission.comments.list():
                    comments.append(comment)

            log.info(f"'{len(submissions)}' submissions yielded '{len(comments)}' comments for replying.")

            for c in comments:
                if (
                    c.body not in configs.FORBIDDEN_COMMENTS
                    and c.id != original_comment.id
                    and c.id not in all_comments
                ):
                    cache.append(c)
                    all_comments.add(c.id)

            log.info(f"'{len(cache)}' comments found.")

            for c in sorted(cache, key=lambda x: x.created_utc, reverse=True):
                try:
                    c.refresh()
                    if c.replies:
                        best_reply_source = c
                        break
                except Exception as e:
                    log.error(f"Error while updating comment: {e}")

            if best_reply_source:
                break

        if best_reply_source:
            log.info(f"Suitable reply source found: '{best_reply_source.id}'")
            log.info(f"URL: https://www.reddit.com{best_reply_source.permalink}")

            valid_replies = [r.body for r in best_reply_source.replies if r.body not in configs.FORBIDDEN_COMMENTS]

            if valid_replies:
                reply_text = random.choice(valid_replies)
                await original_comment.reply(reply_text)
                log.info(f"Reply sent to comment with ID '{mention.id}'.")
            else:
                log.warning("No valid reply found in the reply source.")
        else:
            log.warning("No suitable reply found in any search results.")


async def check_inbox(bot: Bot) -> None:
    while True:
        await bot.setup()
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
        current_hour = time.strftime("%H")

        if current_hour in configs.WORKING_HOURS:
            try:
                log.info("Processing a random post...")
                await bot.process_post()
            except Exception as e:
                log.error(f"An exception occurred during the main process: {e}")

        else:
            log.info(f"Outside working hours ({configs.WORKING_HOURS}). Bot is inactive.")

        min_sleep_seconds = configs.MIN_SLEEP_MINUTES * 60
        max_sleep_seconds = configs.MAX_SLEEP_MINUTES * 60
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
