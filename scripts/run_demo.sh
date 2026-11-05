#!/usr/bin/env bash
# Start the Musegix gateway and print the bolt.diy URL to open.
# Usage: bash scripts/run_demo.sh   (from the repo root; Ctrl-C stops the gateway)
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${GATEWAY_PORT:-8000}"
PY="${PYTHON:-python}"
BOLT_PORT="${BOLT_PORT:-5173}"

cd "$ROOT" || exit 1

"$PY" -m uvicorn gateway.app:app --host 0.0.0.0 --port "$PORT" &
GATEWAY_PID=$!
trap 'kill "$GATEWAY_PID" 2>/dev/null' EXIT INT TERM

# Wait up to 60 s for the gateway to answer.
ready=0
for _ in $(seq 1 60); do
  if curl -fs "http://127.0.0.1:${PORT}/v1/models" >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
    break
  fi
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  echo "Gateway did not start on port ${PORT}." >&2
  exit 1
fi

echo "Gateway:  http://127.0.0.1:${PORT}/v1  (health: /v1/models)"
echo "bolt.diy: http://localhost:${BOLT_PORT}"
echo "If bolt.diy is not running yet, start it in another terminal:"
echo "  cd external/bolt.diy && pnpm run dev"
echo "Press Ctrl-C to stop the gateway."

wait "$GATEWAY_PID"
