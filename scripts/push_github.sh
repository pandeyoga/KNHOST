#!/usr/bin/env bash
# Pakai: GH_TOKEN=github_pat_xxx REPO_URL=https://github.com/user/repo.git bash scripts/push_github.sh [branch] ["pesan"]
# Token hanya dipakai sebagai header sekali pakai; tidak disimpan ke .git/config atau file.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
: "${GH_TOKEN:?GH_TOKEN belum diisi}"
BRANCH="${1:-main}"
MSG="${2:-Update $(date +%F)}"
git remote get-url origin >/dev/null 2>&1 || git remote add origin "${REPO_URL:?REPO_URL belum diisi}"
AUTH="$(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
G=(git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic ${AUTH}")
git add -A
git reset -q -- frontend/yarn.lock 2>/dev/null || true
git diff --cached --quiet || git commit -q -m "$MSG"
if "${G[@]}" fetch -q origin "$BRANCH" 2>/dev/null; then
  REMOTE="origin/${BRANCH}"
  if git merge-base --is-ancestor "$REMOTE" HEAD; then
    TARGET=HEAD
  elif [ -z "$(git diff "$REMOTE" HEAD)" ]; then
    echo "Isi sudah sama dengan remote, tidak ada yang di-push."; exit 0
  else
    TARGET=$(git commit-tree "HEAD^{tree}" -p "$REMOTE" -m "$MSG")
    echo "Riwayat berbeda, membuat commit $TARGET di atas $REMOTE"
  fi
else
  TARGET=HEAD
fi
"${G[@]}" push origin "${TARGET}:refs/heads/${BRANCH}"
"${G[@]}" fetch -q origin "$BRANCH"
[ -z "$(git diff HEAD "origin/${BRANCH}")" ] && echo "OK: isi GitHub identik dengan lokal" || echo "PERINGATAN: isi berbeda (commit lokal $(git rev-parse --short HEAD) vs GitHub $(git rev-parse --short origin/${BRANCH}))"
