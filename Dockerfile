FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV KOYUNKAPAN_DATA_DIR=/data

COPY . .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir .

EXPOSE 5000

CMD ["bash", "start.sh"]
