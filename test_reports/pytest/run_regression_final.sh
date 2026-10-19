#!/bin/bash
cd /app/backend
set -a; . ./.env; set +a
export REACT_APP_BACKEND_URL=http://localhost:8001
OUT=/app/test_reports/pytest/regression_final.log
: > $OUT
for f in $(ls tests | grep -E "^test_(l0[0-9]|l1[0-4]|ln|lanjutan|iter233)"); do
  r=$(timeout 240 python -m pytest tests/$f -n0 -q -p no:cacheprovider 2>&1 | tail -1)
  echo "$f :: $r" >> $OUT
done
echo DONE >> $OUT
