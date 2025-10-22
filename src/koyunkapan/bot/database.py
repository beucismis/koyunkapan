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


async def init() -> None:
    await Tortoise.init(db_url=f"sqlite://{database_file}", modules={"models": ["koyunkapan.bot.models"]})
    await Tortoise.generate_schemas()


async def close() -> None:
    await Tortoise.close_connections()
