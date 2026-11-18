#!/usr/bin/env bash
# Jalankan jalankan_rekon.sh di kontainer uji (kn-uji-pw:1, lihat docker/Dockerfile) terhadap tumpukan Docker lokal kn-dev
# (docker-compose.dev.yml). Repo dipasang di /work; cek buku memakai mongosh → mongodb://mongo:27017/<KN_DB>.
#
#   docker build -t kn-uji-pw:1 docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/docker      (sekali)
#   KN_PESERTA=85 bash docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/jalankan_rekon_docker.sh
set -u
REPO="$(cd "$(dirname "$0")/../../../../.." && pwd)"
export MSYS_NO_PATHCONV=1
docker run --rm --network "${KN_NET:-kn-dev_default}" -v "$REPO:/work" \
  -e KN_PESERTA="${KN_PESERTA:-85}" -e KN_HANYA="${KN_HANYA:-}" \
  -e KN_MONGO_URL="mongodb://mongo:27017/${KN_DB:-test_database}" \
  -w /work/docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi "${KN_IMG:-kn-uji-pw:1}" \
  bash -c 'node docker/teruskan_port.js & sleep 1; bash jalankan_rekon.sh'
