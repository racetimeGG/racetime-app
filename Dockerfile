FROM python:3.14 AS base

RUN useradd -d /opt/racetime app
RUN install -d -g app -o app /opt/racetime

ADD requirements.txt setup.py ./
RUN pip install -r requirements.txt && rm requirements.txt setup.py

ENV PYTHONUNBUFFERED 1

USER app
WORKDIR /opt/racetime

FROM base AS racebot
ENTRYPOINT ["./.docker/start", "racebot"]

FROM base AS web
EXPOSE 8000
ENTRYPOINT ["./.docker/start", "runserver", "0.0.0.0:8000"]
