import os

DATA_DIR = os.environ.get("KOYUNKAPAN_DATA_DIR")
LOG_FILE = os.path.join(DATA_DIR, "app.log")
DB_FILE = os.path.join(DATA_DIR, "app.db")

MIN_SLEEP_MINUTES = 5
MAX_SLEEP_MINUTES = 15
INBOX_CHECK_INTERVAL = 60
WORKING_HOURS = [str(i).zfill(2) for i in range(24)]

POST_LIMIT = 20
SEARCH_LIMIT = 25
MAX_KEYWORDS = 25
RANDOM_POST_COUNT = 10
TOP_COMMENT_LIMIT = 10
SIMILARITY_THRESHOLD = 1.35

SUBREDDIT_WEIGHTS = {
    "KGBTR": 1.4,
    "bokteri": 1.0,
    "Eleteria": 1.0,
    "CuteTopia": 1.0,
    "WeebTurks": 1.0,
    "Cikopolis": 1.1,
    "TurkishCats": 1.0,
    "Turkishdogs": 1.0,
    "SacmaBirSub": 1.1,
    "kopyamakarna": 1.0,
    "BAYIRDOMUZLARI": 1.2,
    "CursedYemekler": 1.0,
}

FORBIDDEN_FLAIR = "Ciddi"
FORBIDDEN_COMMENTS = ("[removed]", "[deleted]", "", " ", None)
