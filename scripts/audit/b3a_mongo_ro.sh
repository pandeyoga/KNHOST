#!/usr/bin/env bash
# Jalankan skrip mongosh BACA-SAJA terhadap kn_test_trial.
# pakai: bash mq.sh <berkas.js>
set -e
export MSYS_NO_PATHCONV=1
f="$1"
base=$(basename "$f")
docker cp "$f" "kn-dev-mongo-1:/tmp/b3a_$base" >/dev/null
docker exec kn-dev-mongo-1 mongosh --quiet kn_test_trial --file "/tmp/b3a_$base"
