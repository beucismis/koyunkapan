#!/bin/bash

# https://tortoise.github.io/migration.html

export PYTHONPATH=$(pwd)/src
export DB_URL="sqlite://$(pwd)/data/app.db"

# aerich init -t src.koyunkapan.bot.database.TORTORISE_ORM

aerich migrate
aerich upgrade
