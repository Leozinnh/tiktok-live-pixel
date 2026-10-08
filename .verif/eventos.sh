#!/usr/bin/env bash
# Um print por evento, com o quadro pintado, para olhar os EFEITOS.
#
# Config temporaria (banco/porta proprios): o pixelworld.db de verdade nao e
# tocado. Pinta um bloco de 18x8 celulas — uma cor por linha, um pintor por
# linha, que o freio de pintura e por pessoa — forca cada evento e fotografa.
set -u
cd /c/xampp/htdocs/tiktok-live-pixel || exit 1

TMP="C:/Users/Leonardo/AppData/Local/Temp"
CFG="$TMP/pw_ev.json"
LOG="$TMP/pw_ev.log"
DB="$TMP/pw_ev.db"
PERFIL="$TMP/pw_chrome_perfil"
rm -f "$DB" "$DB-wal" "$DB-shm" "$LOG" "$TMP"/pw_ev_*.png

python -c "
import json
c = json.load(open('config.json', encoding='utf-8'))
c['app']['db_path'] = r'$DB'
c['app']['log_dir'] = r'$TMP/pw_ev_logs'
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

# O bloco: linhas 4..11, colunas D..U (x 3..20), uma cor por linha.
CORES=(vermelho laranja amarelo verde azul roxo rosa branco)
LETRAS=(A B C D E F G H I J K L M N O P Q R S T U V W X Y Z)
for i in 0 1 2 3 4 5 6 7; do
  u="pintor$i"
  y=$((i + 4))
  linha=""
  for x in $(seq 3 20); do linha="$linha ${LETRAS[$x]}$y"; done

  api /api/inventario "{\"user\":\"$u\",\"pixels\":200}"
  api /api/simular "{\"type\":\"comentario\",\"user\":\"$u\",\"text\":\"/cor ${CORES[$i]}\"}"
  api /api/simular "{\"type\":\"comentario\",\"user\":\"$u\",\"text\":\"$linha\"}"
done

sleep 1

shoot() {
  "/c/Program Files/Google/Chrome/Application/chrome.exe" \
    --headless=new \
    --disable-gpu \
    --no-first-run --no-default-browser-check \
    --user-data-dir="$PERFIL" \
    --hide-scrollbars \
    --force-device-scale-factor=1 \
    --window-size=1080,1920 \
    --virtual-time-budget=9000 \
    --screenshot="$TMP/pw_ev_$1.png" \
    "http://127.0.0.1:8125/" 2>&1 | tail -1
}

# hora_do_pixel -> brilho; pixel_turbo -> rastro. A chave e a do catalogo.
shoot sem_evento
for par in "hora_do_pixel:brilho" "pixel_turbo:rastro" "caos:caos" "desafio:desafio" "arco_iris:arco_iris"; do
  api /api/evento "{\"key\":\"${par%%:*}\"}"
  shoot "${par##*:}"
done

for f in "$TMP"/pw_ev_*.png; do
  [ -f "$f" ] && echo "PRINT OK: $f"
done
