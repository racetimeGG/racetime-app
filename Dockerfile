FROM jfloff/alpine-python:3.8 AS base

# mariadb-dev for mysqlclient, libressl-dev for channels, jpeg/zlib for Pillow
RUN apk add --no-cache jpeg-dev mariadb-dev libressl-dev zlib-dev

RUN adduser -DHh /opt/racetime app
RUN install -d -g app -o app /opt/racetime

ADD requirements.txt setup.py ./
RUN pip install -r requirements.txt && rm requirements.txt setup.py

ENV PYTHONUNBUFFERED 1

USER app
WORKDIR /opt/racetime

FROM base as racebot
ENTRYPOINT ["./.docker/start", "racebot"]

FROM base as web
EXPOSE 8000
ENTRYPOINT ["./.docker/start", "runserver", "0.0.0.0:8000"]
