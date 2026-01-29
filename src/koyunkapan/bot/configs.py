import os

DATA_DIR = os.environ.get("KOYUNKAPAN_DATA_DIR")
LOG_FILE = os.path.join(DATA_DIR, "app.log")
DB_FILE = os.path.join(DATA_DIR, "app.db")

MIN_SLEEP_MINUTES = 5
MAX_SLEEP_MINUTES = 15
INBOX_CHECK_INTERVAL = 60
WORKING_HOURS = [str(i).zfill(2) for i in range(24)]

POST_LIMIT = 10
SEARCH_LIMIT = 10
MAX_KEYWORDS = 25
RANDOM_POST_COUNT = 10
TOP_COMMENT_LIMIT = 10
SIMILARITY_THRESHOLD = 1.35
MIN_SUBMISSION_THRESHOLD = 20
TIER_2_SUBREDDIT_COUNT = 5

SUBREDDIT_WEIGHTS = {
    "amip": 1.0,
    "KGBTR": 1.5,
    "delik": 1.0,
    "dewrim": 1.0,
    "bokteri": 1.0,
    "Eleteria": 1.0,
    "pedlesme": 1.0,
    "CuteTopia": 1.0,
    "WeebTurks": 1.0,
    "Cikopolis": 1.0,
    "rockmuzik": 1.0,
    "StresOdasi": 1.0,
    "TurkishCats": 1.0,
    "Turkishdogs": 1.0,
    "SacmaBirSub": 1.0,
    "kopyamakarna": 1.0,
    "aptalSoruYok": 1.0,
    "TurkeyJerky": 1.0,
    "YIKIKHAYATLAR": 1.0,
    "yalnizucubeler": 1.0,
    "BAYIRDOMUZLARI": 1.0,
    "CursedYemekler": 1.0,
    "MutfakDertlileri": 1.0,
}

FORBIDDEN_FLAIR = "Ciddi"
FORBIDDEN_COMMENTS = ("[removed]", "[deleted]", "", " ", None)
