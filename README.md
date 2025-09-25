# koyunkapan

Source code for u/koyunkapan. This repository is forked from the original [oldventura/koyunkirpan](https://github.com/oldventura/koyunkirpan). Thanks for the base code.

## Running

Create a `praw.ini` file in the project's root directory using `praw.ini.example` as a template.

```
git clone https://github.com/beucismis/koyunkapan
cd koyunkapan/
pip install .

KOYUNKAPAN_DATA_DIR=/home/user/data

# Bot
python3 -m koyunkapan.bot.core

# Dashboard
flask --app koyunkapan.dashboard.main:app run --port 3131 --debug
```

## Service

Check `[Service] > Environment` before running.

```
cp koyunkapan-bot.service koyunkapan-dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload

systemctl --user enable koyunkapan-bot.service
systemctl --user enable koyunkapan-dashboard.service

systemctl --user start koyunkapan-bot.service
systemctl --user start koyunkapan-dashboard.service
```

## License

`koyunkapan` is distributed under the terms of the [MIT](LICENSE.txt) license.
