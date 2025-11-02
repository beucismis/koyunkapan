#!/bin/bash

python3 -m koyunkapan.bot.core
flask --app koyunkapan.dashboard.main:app run --host=0.0.0.0 --debug
