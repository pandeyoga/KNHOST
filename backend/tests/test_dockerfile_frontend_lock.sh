#!/usr/bin/env bash
# Shell-only regression test for the "frontend.yarn.lock not found" VPS deploy bug.
# Validates:
#   1) deploy/Dockerfile.{frontend,backend} referenced COPY sources exist in repo
#   2) deploy/frontend-yarnlock.txt exists, identical to frontend/yarn.lock,
#      and NOT ignored by .gitignore or .dockerignore
#   3) Simulating Dockerfile RUN steps in a tmpdir succeeds (with lock present) -
#      after mv + node prune + sed, `yarn install --ignore-scripts` completes
#      with NO reference to assets.emergent.sh in resulting lock/package.json
#   4) Same simulation WITHOUT lock: mv|touch produces empty yarn.lock, sed doesn't fail
set -u
PASS=0; FAIL=0
ok(){ echo "  PASS: $1"; PASS=$((PASS+1)); }
ko(){ echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

REPO=/app
DF_FE=$REPO/deploy/Dockerfile.frontend
DF_BE=$REPO/deploy/Dockerfile.backend

echo "== 1. Dockerfile COPY sources exist =="
# Non-glob, non-optional (no [t]) COPY sources
missing_fe=0
for src in frontend/package.json frontend deploy/nginx-web.conf; do
    if [ -e "$REPO/$src" ]; then ok "Dockerfile.frontend COPY source present: $src";
    else ko "Dockerfile.frontend COPY source missing: $src"; missing_fe=1; fi
done
# Ensure Dockerfile.frontend no longer has a COPY/RUN directive for the phantom lock
# (comments mentioning it for historical context are fine).
if grep -vE '^\s*#' "$DF_FE" | grep -qE 'frontend\.yarn\.lock'; then
    ko "Dockerfile.frontend still references old 'frontend.yarn.lock' outside comments"
else ok "Dockerfile.frontend has no live reference to old 'frontend.yarn.lock'"; fi
# Optional-glob line uses [t]
if grep -qE 'frontend-yarnlock\.tx\[t\]' "$DF_FE"; then
    ok "Dockerfile.frontend uses optional glob deploy/frontend-yarnlock.tx[t]"
else ko "Dockerfile.frontend missing optional-glob for the lock"; fi

for src in backend/requirements.txt backend; do
    if [ -e "$REPO/$src" ]; then ok "Dockerfile.backend COPY source present: $src";
    else ko "Dockerfile.backend COPY source missing: $src"; fi
done

echo "== 2. deploy/frontend-yarnlock.txt integrity + not ignored =="
LOCK=$REPO/deploy/frontend-yarnlock.txt
YLOCK=$REPO/frontend/yarn.lock
if [ -f "$LOCK" ] && [ -f "$YLOCK" ]; then ok "both lock files exist"; else ko "lock files missing"; fi
if [ "$(md5sum <"$LOCK" | cut -d' ' -f1)" = "$(md5sum <"$YLOCK" | cut -d' ' -f1)" ]; then
    ok "deploy/frontend-yarnlock.txt is identical (md5) to frontend/yarn.lock"
else ko "deploy/frontend-yarnlock.txt differs from frontend/yarn.lock"; fi

# .gitignore: simulate via a temp git repo copying real .gitignore
TMPG=$(mktemp -d)
cp "$REPO/.gitignore" "$TMPG/.gitignore"
( cd "$TMPG" && git init -q && mkdir -p deploy && : > deploy/frontend-yarnlock.txt \
  && out=$(git check-ignore -v deploy/frontend-yarnlock.txt 2>&1 || true) \
  && if [ -z "$out" ]; then echo OK_GI; else echo "IGNORED:$out"; fi ) > "$TMPG/res" 2>&1
if grep -q '^OK_GI$' "$TMPG/res"; then ok ".gitignore does NOT ignore deploy/frontend-yarnlock.txt"
else ko ".gitignore ignores deploy/frontend-yarnlock.txt -> $(cat $TMPG/res)"; fi
rm -rf "$TMPG"

# .dockerignore: check patterns don't match deploy/frontend-yarnlock.txt.
# Patterns of concern: '*.md','*.png','*.jpeg','deploy/.env','deploy/backups','test_reports','memory','scripts','tests','docs','poc','.emergent','.git','**/node_modules','frontend/build','**/__pycache__','**/*.pyc','**/.pytest_cache','**/.ruff_cache','backend/*'
# None match 'deploy/frontend-yarnlock.txt'. Verify with a python matcher using pathspec if available; fall back to grep-based sanity.
python3 - "$REPO/.dockerignore" deploy/frontend-yarnlock.txt <<'PY' && ok ".dockerignore does NOT match deploy/frontend-yarnlock.txt" || ko ".dockerignore matches deploy/frontend-yarnlock.txt"
import sys, fnmatch, os
ignore_file, target = sys.argv[1], sys.argv[2]
patterns=[l.strip() for l in open(ignore_file) if l.strip() and not l.startswith('#')]
def match(p, path):
    # normalize ** to * for fnmatch
    if p.startswith('**/'):
        p2=p[3:]
        # match at any depth
        parts=path.split('/')
        for i in range(len(parts)):
            if fnmatch.fnmatch('/'.join(parts[i:]), p2): return True
        return False
    if '/' in p:
        return fnmatch.fnmatch(path, p) or path.startswith(p.rstrip('/')+'/')
    # bare pattern -> match basename or any component
    if fnmatch.fnmatch(os.path.basename(path), p): return True
    for part in path.split('/'):
        if fnmatch.fnmatch(part, p): return True
    return False
hit=[p for p in patterns if match(p, target)]
sys.exit(1 if hit else 0)
PY

echo "== 3. Simulate Dockerfile RUN steps WITH lock =="
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/build"
cp "$REPO/frontend/package.json" "$TMP/build/package.json"
cp "$LOCK" "$TMP/build/frontend-yarnlock.txt"
(
  set -e
  cd "$TMP/build"
  # mimic: if -f frontend-yarnlock.txt then mv ... else touch yarn.lock
  if [ -f frontend-yarnlock.txt ]; then mv frontend-yarnlock.txt yarn.lock; else touch yarn.lock; fi
  # node prune script from Dockerfile line 20
  node -e "const fs=require('fs');const p=JSON.parse(fs.readFileSync('package.json'));for(const k of ['dependencies','devDependencies']){if(p[k])delete p[k]['@emergentbase/visual-edits'];}fs.writeFileSync('package.json',JSON.stringify(p,null,2));"
  # sed removal from yarn.lock
  sed -i '/^"@emergentbase\/visual-edits@/,/^$/d' yarn.lock
) && ok "mv + node prune + sed complete" || ko "mv/node/sed step failed"

# no remaining references to the private package or assets.emergent.sh in lock/package.json
if grep -q 'assets\.emergent\.sh' "$TMP/build/yarn.lock" "$TMP/build/package.json"; then
    ko "assets.emergent.sh still present after prune -> $(grep -c assets.emergent.sh $TMP/build/yarn.lock $TMP/build/package.json)"
else ok "no assets.emergent.sh references in pruned lock/package.json"; fi
if grep -q '@emergentbase/visual-edits' "$TMP/build/package.json"; then
    ko "package.json still lists @emergentbase/visual-edits"
else ok "package.json no longer lists @emergentbase/visual-edits"; fi

echo "== 3b. yarn install --frozen-lockfile --ignore-scripts =="
(
  cd "$TMP/build"
  # Match exact flags from statement; add --ignore-scripts as requested by tests.
  yarn install --frozen-lockfile --ignore-scripts --non-interactive --network-timeout 600000
) > "$TMP/yarn.log" 2>&1
rc=$?
if [ $rc -eq 0 ]; then
    ok "yarn install --frozen-lockfile --ignore-scripts succeeded"
else
    echo "---- yarn log tail ----"; tail -n 40 "$TMP/yarn.log"; echo "-----------------------"
    ko "yarn install failed (rc=$rc)"
fi

echo "== 4. Simulate WITHOUT lock (fallback path) =="
TMP2=$(mktemp -d)
mkdir -p "$TMP2/build"
cp "$REPO/frontend/package.json" "$TMP2/build/package.json"
(
  set -e
  cd "$TMP2/build"
  if [ -f frontend-yarnlock.txt ]; then mv frontend-yarnlock.txt yarn.lock; else touch yarn.lock; fi
  node -e "const fs=require('fs');const p=JSON.parse(fs.readFileSync('package.json'));for(const k of ['dependencies','devDependencies']){if(p[k])delete p[k]['@emergentbase/visual-edits'];}fs.writeFileSync('package.json',JSON.stringify(p,null,2));"
  sed -i '/^"@emergentbase\/visual-edits@/,/^$/d' yarn.lock
) && ok "fallback mv|touch + node + sed succeeded (no lock)" || ko "fallback path failed"
if [ -f "$TMP2/build/yarn.lock" ] && [ ! -s "$TMP2/build/yarn.lock" ]; then
    ok "yarn.lock exists and is empty in fallback path"
else ko "yarn.lock missing/non-empty in fallback path (size=$(stat -c%s $TMP2/build/yarn.lock 2>/dev/null))"; fi
rm -rf "$TMP2"

echo
echo "==================="
echo "PASSED: $PASS   FAILED: $FAIL"
echo "==================="
[ "$FAIL" -eq 0 ]
