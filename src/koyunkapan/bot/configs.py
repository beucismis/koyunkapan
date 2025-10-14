import os


DATA_DIR = os.environ.get("KOYUNKAPAN_DATA_DIR")
LOG_FILE = os.path.join(DATA_DIR, "app.log")
DB_FILE = os.path.join(DATA_DIR, "app.db")

MIN_SLEEP_MINUTES = 5
MAX_SLEEP_MINUTES = 20
INBOX_CHECK_INTERVAL = 60
WORKING_HOURS = [str(i).zfill(2) for i in range(24)]

POST_LIMIT = 50
SEARCH_LIMIT = 25
MAX_KEYWORDS = 25
RANDOM_POST_COUNT = 10
TOP_COMMENT_LIMIT = 10
SIMILARITY_THRESHOLD = 1.35

SUBREDDIT_NAMES = [
    "KGBTR",
    "bokteri",
    "Eleteria",
    "CuteTopia",
    "WeebTurks",
    "Cikopolis",
    "TurkishCats",
    "Turkishdogs",
    "SacmaBirSub",
    "kopyamakarna",
    "BAYIRDOMUZLARI",
    "CursedYemekler",
]

FORBIDDEN_FLAIR = "Ciddi"
FORBIDDEN_COMMENTS = ("[removed]", "[deleted]", "", " ", None)
