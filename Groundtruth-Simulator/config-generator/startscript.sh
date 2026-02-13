#!/usr/bin/env sh
set -e

cd "$(dirname "$0")"

if [ ! -d node_modules ]; then
	npm ci
fi

python server.py &
exec npm run dev --hostname 0.0.0.0 --port 3000
