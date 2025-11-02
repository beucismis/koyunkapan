#!/bin/bash

python3 -m koyunkapan.bot.core
flask --app koyunkapan.dashboard.main:app run --debug
