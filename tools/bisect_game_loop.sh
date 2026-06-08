#!/usr/bin/env bash
# git bisect run script for "cannot pickle 'sqlite3.Connection' object" in
# CWS game loop.
#
# Exit 0 -> good (game loop tick does NOT error)
# Exit 1 -> bad (game loop tick errors with pickle Connection)
# Exit 125 -> skip (cannot test this commit)

set -u
cd "$(dirname "$0")/.."
LOG=/tmp/bisect-server.log
DATA=/private/tmp/claude-501/cws-bisect-data
PORT_BE=8088
PORT_VITE_ENV=
PYTHON=.venv/bin/python

[ -x "$PYTHON" ] || { echo "no .venv python"; exit 125; }

rm -rf "$DATA"
mkdir -p "$DATA"

cat > "$DATA/settings.json" <<EOF
{
  "schema_version": 2,
  "ui": { "locale": "zh-CN", "audio": { "bgm_volume": 0.5, "sfx_volume": 0.5 } },
  "simulation": { "auto_save_enabled": false, "max_auto_saves": 5 },
  "llm": {
    "profile": {
      "base_url": "https://api.minimaxi.com/v1",
      "model_name": "MiniMax-M2.7-highspeed",
      "fast_model_name": "MiniMax-M2.7-highspeed",
      "mode": "default",
      "max_concurrent_requests": 10,
      "has_api_key": true,
      "api_format": "openai"
    }
  },
  "new_game_defaults": {
    "content_locale": "zh-CN",
    "init_npc_num": 4,
    "sect_num": 1,
    "npc_awakening_rate_per_month": 0.01,
    "world_lore": ""
  }
}
EOF
cp "$HOME/cws-playtest-v1.0/secrets.json" "$DATA/secrets.json" 2>/dev/null || cat > "$DATA/secrets.json" <<EOF
{"api_key": "${MINIMAX_API_KEY:-}"}
EOF

# Kill any leftover on bisect port
lsof -tiTCP:$PORT_BE 2>/dev/null | xargs -r kill -9 2>/dev/null
sleep 1

# Start server (use --scenario=liuchao if this version supports it; else fall back)
SERVER_HOST=127.0.0.1 SERVER_PORT=$PORT_BE CWS_DATA_DIR="$DATA" CWS_NO_BROWSER=1 \
  $PYTHON src/server/main.py --scenario=liuchao > "$LOG" 2>&1 &
SERVER_PID=$!

trap 'kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null' EXIT

# Wait for server up (max 60s)
for i in $(seq 1 60); do
  if curl -s --max-time 2 "http://127.0.0.1:$PORT_BE/api/v1/query/runtime/status" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -s --max-time 2 "http://127.0.0.1:$PORT_BE/api/v1/query/runtime/status" >/dev/null 2>&1; then
  echo "server failed to start"
  grep -i "error\|traceback" "$LOG" | head -5
  exit 125
fi

# Start game
curl -sX POST "http://127.0.0.1:$PORT_BE/api/v1/command/game/start" -d '{}' \
  -H 'Content-Type: application/json' >/dev/null

# Wait up to 120s for init complete OR pickle error
for i in $(seq 1 24); do
  if grep -q "cannot pickle 'sqlite3.Connection'" "$LOG" 2>/dev/null; then
    echo "BAD: pickle error detected"
    exit 1
  fi
  status=$(curl -s --max-time 3 "http://127.0.0.1:$PORT_BE/api/v1/query/runtime/status" \
    | $PYTHON -c "import sys,json; d=json.load(sys.stdin)['data']; print(f\"{d.get('status')},{d.get('progress')}\")" 2>/dev/null || echo "")
  case "$status" in
    ready,100)
      # Init done; let game loop run for 90s and check
      sleep 90
      if grep -q "cannot pickle 'sqlite3.Connection'" "$LOG" 2>/dev/null; then
        echo "BAD: pickle error during loop"
        exit 1
      fi
      # Did world advance?
      ws=$(curl -s --max-time 3 "http://127.0.0.1:$PORT_BE/api/v1/query/world/state" \
        | $PYTHON -c "import sys,json; d=json.load(sys.stdin)['data']; print(f\"{d.get('year')},{d.get('month')}\")" 2>/dev/null || echo "")
      ev=$(curl -s --max-time 3 "http://127.0.0.1:$PORT_BE/api/v1/query/events?limit=200" \
        | $PYTHON -c "import sys,json; print(len(json.load(sys.stdin)['data']['events']))" 2>/dev/null || echo 0)
      echo "world=$ws events=$ev"
      # Good if (events > 6) OR (year/month != 1,1)
      if [ "$ws" != "1,1" ] || [ "$ev" -gt 6 ]; then
        echo "GOOD: world advanced"
        exit 0
      else
        echo "BAD: world stuck"
        # tail last bit of log for diagnosis
        tail -30 "$LOG"
        exit 1
      fi
      ;;
  esac
  sleep 5
done

echo "SKIP: init never completed in 120s"
tail -20 "$LOG"
exit 125
