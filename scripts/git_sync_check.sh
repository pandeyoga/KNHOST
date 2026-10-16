#!/usr/bin/env bash
# Cek sebelum "Save to GitHub": semua perubahan tercommit DAN riwayat lokal menurunkan
# main di GitHub (fast-forward). Riwayat yang bercabang dari "Initial commit" membuat push
# tidak membawa perubahan (penyebab sesi P16 lama hilang).
# Usage: bash scripts/git_sync_check.sh [--fix]   (--fix: commit + tumpuk ulang di atas GitHub main)
set -uo pipefail
cd /app
REPO="${KN_GITHUB_REPO:-https://github.com/pandeyoga/KNHOST}"
git fetch -q "$REPO" main || { echo "GAGAL fetch $REPO"; exit 1; }
REMOTE=$(git rev-parse FETCH_HEAD)
DIRTY=$(git status --porcelain | wc -l)
if git merge-base --is-ancestor "$REMOTE" HEAD; then FF=1; else FF=0; fi
echo "GitHub main : $REMOTE"
echo "HEAD lokal  : $(git rev-parse HEAD)"
echo "Belum commit: $DIRTY berkas"
echo "Fast-forward: $([ $FF = 1 ] && echo YA || echo TIDAK — riwayat bercabang)"
if [ "${1:-}" = "--fix" ] && { [ "$DIRTY" != 0 ] || [ $FF = 0 ]; }; then
  git add -A
  [ $FF = 0 ] && git reset --soft "$REMOTE" && git add -A
  git commit -q -m "${KN_COMMIT_MSG:-Sinkron pekerjaan sesi}" && echo "DIPERBAIKI → $(git log --oneline -1)"
  git merge-base --is-ancestor "$REMOTE" HEAD && echo "Fast-forward: YA"
fi
[ "$DIRTY" = 0 ] && [ $FF = 1 ]
