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

## Running with Docker

```
git clone https://github.com/beucismis/koyunkapan
cd koyunkapan/
docker build -t koyunkapan .
docker run -d -p 3131:5000 -v ~/data:/data --name koyunkapan koyunkapan
```

## License

`koyunkapan` is distributed under the terms of the [MIT](LICENSE.txt) license.
