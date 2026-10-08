#!/usr/bin/env bash
# Verificacao ponta a ponta: um presente de verdade percorre o app real e
# precisa deixar linha no console. Usa config temporaria (banco e porta
# proprios) para nao tocar no pixelworld.db do streamer.
#
# NOTA: os caminhos sao Windows (C:/...) de proposito. O `/tmp` do Git Bash
# nao existe para o Python do Windows, e ele resolve `/tmp/x` como `C:\tmp\x`.
set -u
cd /c/xampp/htdocs/tiktok-live-pixel || exit 1

TMP="C:/Users/Leonardo/AppData/Local/Temp"
CFG="$TMP/pw_e2e.json"
LOG="$TMP/pw_e2e_console.txt"
DB="$TMP/pw_e2e.db"
rm -f "$DB" "$DB-wal" "$DB-shm" "$LOG" "$CFG"

python -c "
import json
c = json.load(open('config.json', encoding='utf-8'))
c['app']['db_path'] = r'$DB'
c['app']['log_dir'] = r'$TMP/pw_e2e_logs'
c['server']['port'] = 8123
json.dump(c, open(r'$CFG', 'w', encoding='utf-8'), ensure_ascii=False)
" || { echo "FALHOU ao gerar a config"; exit 1; }

python main.py --config "$CFG" --test --headless > "$LOG" 2>&1 &
APP=$!

for _ in $(seq 1 60); do
  if curl -sf -o /dev/null "http://127.0.0.1:8123/api/estado"; then break; fi
  sleep 0.5
done

echo "=== POST presente simulado (Rose) ==="
curl -s -X POST "http://127.0.0.1:8123/api/simular" \
  -H "Content-Type: application/json" \
  -d '{"type":"presente","user":"@leonardo109333","gift":"Rose","quantity":1}'
echo

sleep 1.5
kill $APP 2>/dev/null
wait $APP 2>/dev/null

echo "=== LINHAS 'Presente' NO CONSOLE DO APP ==="
grep -a "Presente" "$LOG" || echo "(NENHUMA — falhou)"
echo "=== fim ==="
