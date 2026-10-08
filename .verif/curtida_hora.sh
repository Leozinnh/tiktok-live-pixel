#!/usr/bin/env bash
# Dois pedidos, dois prints:
#
# 1) TOAST DA CURTIDA — 50 curtidas do "leonardo" viram 1 pixel, e o aviso no
#    telao tem que sair com ❤️ e a palavra "curtiu", nao com a rosa de sempre.
#    As curtidas sao disparadas com a pagina JA no ar (o toast vive 5,2s).
# 2) HORA DO PIXEL — num quadro VAZIO a festa (moldura + chuva de pixels) tem
#    que aparecer; antes, sem celula pintada, so o banner se via. E um print
#    com o quadro pintado, para conferir que a chuva nao tapa o desenho.
#
# Config temporaria (banco/porta proprios): o pixelworld.db de verdade nao e
# tocado. A config sai do config.json do projeto — entao o 50 da curtida
# entra na conta aqui tambem.
set -u
cd /c/xampp/htdocs/tiktok-live-pixel || exit 1

TMP="C:/Users/Leonardo/AppData/Local/Temp"
CFG="$TMP/pw_curtida.json"
LOG="$TMP/pw_curtida.log"
DB="$TMP/pw_curtida.db"
PERFIL="$TMP/pw_chrome_perfil"
rm -f "$DB" "$DB-wal" "$DB-shm" "$LOG" "$TMP"/pw_curtida_*.png

python -c "
import json
c = json.load(open('config.json', encoding='utf-8'))
c['app']['db_path'] = r'$DB'
c['app']['log_dir'] = r'$TMP/pw_curtida_logs'
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
    --screenshot="$TMP/pw_curtida_$1.png" \
    "http://127.0.0.1:8125/" 2>&1 | tail -1
}

# 1) O toast. As curtidas chegam enquanto a pagina carrega: um pouco depois do
#    load, e de novo a cada 1,5s — o toast vive 5,2s, entao a tela nunca fica
#    sem um no momento do print.
(
  sleep 4
  for _ in 1 2 3 4; do
    api /api/simular '{"type":"curtida","user":"leonardo","quantity":50}'
    sleep 1.5
  done
) &
shoot toast
wait

# 2) Um bloco pintado, para a chuva sobre o desenho.
api /api/inventario '{"user":"pintor","pixels":100}'
api /api/simular '{"type":"comentario","user":"pintor","text":"/cor azul"}'
api /api/simular '{"type":"comentario","user":"pintor","text":"D5 E5 F5 G5 H5 J5 K5 L5 M5 N5 P5 Q5 R5"}'
sleep 2.2  # o freio de pintura e POR PESSOA: 2s entre uma jogada e a outra
api /api/simular '{"type":"comentario","user":"pintor","text":"D6 E6 F6 G6 H6 J6 K6 L6 M6 N6 P6 Q6 R6"}'

# 3) A HORA DO PIXEL no quadro pintado...
api /api/evento '{"key":"hora_do_pixel"}'
shoot hora_pintado

# 4) ...e num SEGUNDO telao, quadro vazio de verdade (outra aba nao serve: o
#    print e one-shot). Recomeca do zero: banco novo para o canvas nascer limpo.
kill $APP 2>/dev/null
rm -f "$DB" "$DB-wal" "$DB-shm"
python main.py --config "$CFG" --test --headless > "$LOG" 2>&1 &
APP=$!
for _ in $(seq 1 60); do
  curl -sf -o /dev/null "http://127.0.0.1:8125/api/estado" && break
  sleep 0.5
done
api /api/evento '{"key":"hora_do_pixel"}'
shoot hora_vazio

for f in "$TMP"/pw_curtida_*.png; do
  [ -f "$f" ] && echo "PRINT OK: $f"
done
