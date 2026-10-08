#!/usr/bin/env bash
# Sobe o app em modo teste (config temporaria: banco/porta proprios) e tira
# um print da TELA como o OBS ve: 1080x1920, devicePixelRatio 1.
set -u
cd /c/xampp/htdocs/tiktok-live-pixel || exit 1

TMP="C:/Users/Leonardo/AppData/Local/Temp"
CFG="$TMP/pw_shot.json"
LOG="$TMP/pw_shot.log"
PNG="$TMP/pw_shot.png"
DB="$TMP/pw_shot.db"
PERFIL="$TMP/pw_chrome_perfil"
rm -f "$DB" "$DB-wal" "$DB-shm" "$LOG" "$PNG"

python -c "
import json
c = json.load(open('config.json', encoding='utf-8'))
c['app']['db_path'] = r'$DB'
c['app']['log_dir'] = r'$TMP/pw_shot_logs'
c['server']['port'] = 8125
json.dump(c, open(r'$CFG', 'w', encoding='utf-8'), ensure_ascii=False)
" || { echo "FALHOU ao gerar a config"; exit 1; }

python main.py --config "$CFG" --test --headless > "$LOG" 2>&1 &
APP=$!
trap 'kill $APP 2>/dev/null' EXIT

for _ in $(seq 1 60); do
  if curl -sf -o /dev/null "http://127.0.0.1:8125/api/estado"; then break; fi
  sleep 0.5
done

"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new \
  --disable-gpu \
  --no-first-run --no-default-browser-check \
  --user-data-dir="$PERFIL" \
  --hide-scrollbars \
  --force-device-scale-factor=1 \
  --window-size=1080,1920 \
  --virtual-time-budget=9000 \
  --screenshot="$PNG" \
  "http://127.0.0.1:8125/" 2>&1 | tail -3

[ -f "$PNG" ] && echo "PRINT OK: $PNG" || echo "PRINT FALHOU"
