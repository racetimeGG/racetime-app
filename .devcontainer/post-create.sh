#!/bin/bash
set -e

echo "==> Installing Python dependencies..."
pip install --user -r requirements.txt

echo "==> Installing Node.js dependencies..."
npm install

echo "==> Waiting for MySQL to be ready..."
sleep 10

echo "==> Running database migrations..."
python manage.py migrate

echo "==> Loading fixtures (if database is empty)..."
if python manage.py fixtures 2>&1 | grep -q "Duplicate entry"; then
    echo "    Fixtures already loaded, skipping..."
else
    echo "    Fixtures loaded successfully!"
fi
