#!/usr/bin/env bash
# Push /app ke GitHub. Pakai: GH_TOKEN=github_pat_xxx bash scripts/push_github.sh [branch] ["pesan commit"]
# Token hanya dipakai di perintah push (header sekali pakai), tidak disimpan ke .git/config atau file.
set -euo pipefail
cd /app
: "${GH_TOKEN:?GH_TOKEN belum diisi}"
BRANCH="${1:-$(git branch --show-current)}"
MSG="${2:-Update $(date +%F) dari Emergent}"
REMOTE_URL="$(git remote get-url origin)"
AUTH="$(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
GIT_AUTH=(-c "http.https://github.com/.extraheader=AUTHORIZATION: basic ${AUTH}")

git add -A
git reset -q -- frontend/yarn.lock 2>/dev/null || true
if git diff --cached --quiet; then
  echo "Tidak ada perubahan baru untuk di-commit."
else
  git commit -q -m "$MSG"
  echo "Commit baru: $(git log -1 --oneline)"
fi

echo "== Cek remote ${REMOTE_URL} (${BRANCH})"
git "${GIT_AUTH[@]}" fetch -q origin "$BRANCH"
if ! git merge-base --is-ancestor "origin/${BRANCH}" HEAD; then
  echo "GAGAL: origin/${BRANCH} punya commit yang tidak ada di lokal. Tidak di-push (tanpa force)." >&2
  exit 1
fi
echo "Commit yang akan di-push:"
git log --oneline "origin/${BRANCH}..HEAD"
git "${GIT_AUTH[@]}" push origin "HEAD:${BRANCH}"
echo "== Selesai: $(git ls-remote origin "refs/heads/${BRANCH}")"
