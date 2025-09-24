import os


DATA_DIR = os.environ.get("KOYUNKAPAN_DATA_DIR")
LOG_FILE = os.path.join(DATA_DIR, "app.log")
DB_FILE = os.path.join(DATA_DIR, "app.db")

POST_LIMIT = 50
SEARCH_LIMIT = 20
MAX_KEYWORDS = 20
RANDOM_POST_COUNT = 5
TOP_COMMENT_LIMIT = 5
SIMILARITY_THRESHOLD = 1.35

SUBREDDIT_NAMES = [
    "test",
    "KGBTR",
    "sinema",
    "bokteri",
    "Eleteria",
    "CuteTopia",
    "WeebTurks",
    "Cikopolis",
    "TurkishCats",
    "Turkishdogs",
    "SacmaBirSub",
    "kopyamakarna",
    "CursedYemekler",
]

FORBIDDEN_FLAIR = "Ciddi"
FORBIDDEN_COMMENTS = ("[removed]", "[deleted]", "", " ", None)

WORKING_HOURS = [str(i).zfill(2) for i in range(24)]
