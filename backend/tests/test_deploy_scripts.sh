#!/usr/bin/env bash
# Tests for deploy scripts: syntax check, key validation, and git divergence handling.
set -u
APP=/app
PASS=0; FAIL=0
ok() { echo "  OK  $*"; PASS=$((PASS+1)); }
bad() { echo " FAIL $*"; FAIL=$((FAIL+1)); }

echo "== 1) bash -n syntax check =="
bash -n "$APP/deploy/setup_vps_ai_import.sh" && ok "setup_vps_ai_import.sh syntax" || bad "setup_vps_ai_import.sh syntax"
bash -n "$APP/deploy/cek_vps.sh" && ok "cek_vps.sh syntax" || bad "cek_vps.sh syntax"
bash -n "$APP/deploy/update.sh" && ok "update.sh syntax" || bad "update.sh syntax"

echo "== 2) Key validation (jangan sentuh backend/.env) =="
BACKEND_ENV_BEFORE="$(md5sum "$APP/backend/.env" 2>/dev/null | awk '{print $1}')"
DEPLOY_ENV="$APP/deploy/.env"
# Backup any existing deploy/.env
BACKUP=""
if [ -f "$DEPLOY_ENV" ]; then BACKUP="$(mktemp)"; cp "$DEPLOY_ENV" "$BACKUP"; fi

run_key() {
  local key="$1" expect="$2" label="$3"
  # Reset dummy deploy/.env each run
  printf 'DOMAIN=example.test\n' > "$DEPLOY_ENV"
  chmod 600 "$DEPLOY_ENV"
  # Provide dummy XLSX var empty; do NOT provide ADMIN_PASSWORD; run headless.
  out="$(OPENAI_API_KEY="$key" bash "$APP/deploy/setup_vps_ai_import.sh" 2>&1)"
  rc=$?
  case "$expect" in
    reject_contoh)
      if [ $rc -ne 0 ] && echo "$out" | grep -qi "masih contoh/terlalu pendek"; then
        # Ensure it did NOT call docker/git before rejection
        if ! echo "$out" | grep -qE "git (fetch|reset)|docker compose build"; then
          ok "$label rejected before docker/git"
        else bad "$label rejected but touched docker/git"; fi
      else bad "$label expected 'contoh/terlalu pendek' rejection (rc=$rc)"; fi
      ;;
    reject_prefix)
      if [ $rc -ne 0 ] && echo "$out" | grep -qi "harus diawali sk-"; then ok "$label rejected wrong prefix"
      else bad "$label expected 'harus diawali sk-' rejection (rc=$rc): $(echo "$out" | tail -3)"; fi
      ;;
    accept)
      # Must PASS validation → so must NOT contain the two rejection messages
      if echo "$out" | grep -qiE "masih contoh/terlalu pendek|harus diawali sk-"; then
        bad "$label rejected by validation but should pass"
      else
        # Should have written the KEY to deploy/.env
        if grep -q "^OPENAI_API_KEY=$key$" "$DEPLOY_ENV"; then ok "$label passed validation & wrote deploy/.env"
        else bad "$label passed validation but deploy/.env not written properly"; fi
      fi
      ;;
  esac
}

run_key 'sk-proj-KUNCI_ANDA' reject_contoh "example key sk-proj-KUNCI_ANDA"
run_key 'sk-proj-...'         reject_contoh "placeholder sk-proj-..."
run_key 'abc'                 reject_prefix "wrong prefix 'abc'"
# Valid: sk-proj- + 60 random chars
RAND="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c60)"
run_key "sk-proj-$RAND" accept "valid long sk-proj- key"

# Restore deploy/.env
if [ -n "$BACKUP" ]; then mv "$BACKUP" "$DEPLOY_ENV"; else rm -f "$DEPLOY_ENV"; fi
BACKEND_ENV_AFTER="$(md5sum "$APP/backend/.env" 2>/dev/null | awk '{print $1}')"
[ "$BACKEND_ENV_BEFORE" = "$BACKEND_ENV_AFTER" ] && ok "backend/.env untouched" || bad "backend/.env MODIFIED"

echo "== 3) Git divergence simulation =="
TMP="$(mktemp -d)"
REMOTE="$TMP/remote.git"; A="$TMP/A"; B="$TMP/B"
git init --bare -q "$REMOTE"
git -c init.defaultBranch=main init -q "$A"
cd "$A"
git config user.email a@t.local; git config user.name A
echo "v1" > file.txt
mkdir -p deploy
cat > .gitignore <<'EOF'
.env
*.env
deploy/.env
EOF
git checkout -q -b main
git add . && git commit -q -m "init"
git remote add origin "$REMOTE"
git push -q -u origin main

# Clone into B (simulates VPS)
git clone -q "$REMOTE" "$B"
cd "$B"
git config user.email b@t.local; git config user.name B
# Create untracked ignored files (like deploy/.env)
mkdir -p deploy
echo "SECRET=abc" > deploy/.env
echo "OTHER=1"   > deploy/prod.env
chmod 600 deploy/.env

# Force-push new history on origin (simulate Save to GitHub)
cd "$A"
git checkout -q --orphan neo
git rm -rqf .
echo "v2" > file.txt
cat > .gitignore <<'EOF'
.env
*.env
deploy/.env
EOF
git add . && git commit -q -m "rewritten"
git branch -M main
git push -qf origin main

# Now try `git pull` in B → must fail (divergent)
cd "$B"
pull_out="$(git -c pull.ff=only fetch --all -q 2>&1; git pull 2>&1)"
pull_rc=$?
if [ $pull_rc -ne 0 ] || echo "$pull_out" | grep -qiE "divergent|refusing|non-fast-forward|would be overwritten|Need to specify how to reconcile"; then
  ok "git pull fails on divergent history (rc=$pull_rc)"
else
  # Some git versions may auto-configure; still: content wouldn't be right / conflict
  bad "git pull did NOT fail as expected: $pull_out"
fi

# Now recovery: git fetch origin main && git reset --hard origin/main
recovery_out="$(git fetch origin main -q 2>&1 && git reset --hard origin/main 2>&1)"
recovery_rc=$?
[ $recovery_rc -eq 0 ] && ok "recovery fetch+reset succeeded" || bad "recovery failed: $recovery_out"
# File content should be v2
grep -q "^v2$" file.txt && ok "file.txt updated to v2" || bad "file.txt not updated"
# Untracked ignored deploy/.env must still exist
[ -f deploy/.env ] && grep -q "SECRET=abc" deploy/.env && ok "deploy/.env preserved" || bad "deploy/.env lost"
[ -f deploy/prod.env ] && ok "deploy/prod.env preserved" || bad "deploy/prod.env lost"

echo "== 4) IMPORT_MASTER_PRODUK.md tidak menyarankan git pull =="
# Warnings against git pull are allowed; positive recommendation is not.
if grep -nE '^\s*git\s+pull' "$APP/deploy/IMPORT_MASTER_PRODUK.md"; then
  bad "found positive 'git pull' recommendation"
else
  ok "no positive 'git pull' command recommendation"
fi
if grep -q "git fetch origin main && git reset --hard origin/main" "$APP/deploy/IMPORT_MASTER_PRODUK.md"; then
  ok "recommends fetch+reset instead"
else bad "missing fetch+reset recommendation"; fi

echo
echo "==== RESULT: PASS=$PASS FAIL=$FAIL ===="
[ $FAIL -eq 0 ]
