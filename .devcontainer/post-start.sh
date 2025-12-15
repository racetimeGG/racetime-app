#!/bin/bash
# postStartCommand - runs every time the container starts

# fix git permissions
git config --global --add safe.directory ${PWD}

# racebot
echo "==> Starting racebot..."
nohup python manage.py racebot --noreload > /tmp/racebot.log 2>&1 &
echo $! > /tmp/racebot.pid

# django
echo "==> Starting web server..."
nohup python manage.py runserver 0.0.0.0:8000 > /tmp/runserver.log 2>&1 &
echo $! > /tmp/runserver.pid

sleep 2
