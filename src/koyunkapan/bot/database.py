from tortoise import Tortoise

from . import configs

database_file = configs.DB_FILE
TORTOISE_ORM = {
    "connections": {"default": f"sqlite://{database_file}"},
    "apps": {
        "models": {
            "models": ["koyunkapan.bot.models"],
            "default_connection": "default",
        },
    },
}
_db_initialized = False


async def init() -> None:
    global _db_initialized

    if _db_initialized:
        return

    await Tortoise.init(db_url=f"sqlite://{database_file}", modules={"models": ["koyunkapan.bot.models"]})
    await Tortoise.generate_schemas()
    _db_initialized = True


async def close() -> None:
    await Tortoise.close_connections()
