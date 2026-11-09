#!/bin/sh
# Pakai: sh run.sh <skrip.py> — salin kn.py + skrip ke kontainer kn-tmp-b2a-be lalu jalankan; keluaran → out/<skrip>.txt
export MSYS_NO_PATHCONV=1
D=C:/Users/abc/AppData/Local/Temp/claude/d999a0fd1df8a838/4f003146-8d75-4e0b-9783-daa1d8e525b4/scratchpad/b2a
docker cp "$D/kn.py" kn-tmp-b2a-be:/tmp/b2a/kn.py
docker cp "$D/$1" kn-tmp-b2a-be:/tmp/b2a/$1
docker exec -w /tmp/b2a kn-tmp-b2a-be python -W ignore $1 > "$D/out/$1.txt" 2>&1
tail -c ${2:-6000} "$D/out/$1.txt"
