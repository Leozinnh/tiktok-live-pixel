#!/usr/bin/env bash
# Um print do PAINEL (/control) com ganhos de todo tipo, para olhar o cartao
# "Atividade". Config temporaria: o pixelworld.db de verdade nao e tocado.
set -u
cd /c/xampp/htdocs/tiktok-live-pixel || exit 1

TMP="C:/Users/Leonardo/AppData/Local/Temp"
CFG="$TMP/pw_painel.json"
LOG="$TMP/pw_painel.log"
DB="$TMP/pw_painel.db"
PNG="$TMP/pw_painel.png"
PERFIL="$TMP/pw_chrome_perfil"
rm -f "$DB" "$DB-wal" "$DB-shm" "$LOG" "$PNG"

python -c "
import json
c = json.load(open('config.json', encoding='utf-8'))
c['app']['db_path'] = r'$DB'
c['app']['log_dir'] = r'$TMP/pw_painel_logs'
c['server']['port'] = 8125
json.dump(c, open(r'$CFG', 'w', encoding='utf-8'), ensure_ascii=False)
" || { echo "FALHOU ao gerar a config"; exit 1; }

python main.py --config "$CFG" --test --headless > "$LOG" 2>&1 &
APP=$!
trap 'kill $APP 2>/dev/null' EXIT

for _ in $(seq 1 60); do
  curl -sf -o /dev/null "http://127.0.0.1:8125/api/estado" && break
  sleep 0.5
done

api() { curl -sf -X POST "http://127.0.0.1:8125$1" -H 'Content-Type: application/json' -d "$2" -o /dev/null; }

api /api/simular '{"type":"presente","user":"ana","gift":"Rose","quantity":3}'
api /api/simular '{"type":"curtida","user":"bruno","quantity":45}'
api /api/simular '{"type":"seguir","user":"carla"}'
api /api/simular '{"type":"compartilhar","user":"duda"}'
api /api/simular '{"type":"curtida","user":"bruno","quantity":60}'

sleep 2

"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new \
  --disable-gpu \
  --no-first-run --no-default-browser-check \
  --user-data-dir="$PERFIL" \
  --hide-scrollbars \
  --force-device-scale-factor=1 \
  --window-size=1080,1920 \
  --virtual-time-budget=6000 \
  --screenshot="$PNG" \
  "http://127.0.0.1:8125/control" 2>&1 | tail -1

[ -f "$PNG" ] && echo "PRINT OK: $PNG" || echo "PRINT FALHOU"
