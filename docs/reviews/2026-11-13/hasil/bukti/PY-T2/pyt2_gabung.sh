#!/bin/bash
# PY-T2 — gabung W (basis B=5f193df) ke T (HEAD terbaru cabang): sama dengan B → salin; beda → merge-file tiga arah.
S=/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad; W=$S/wt27; T=$S/wt29; B=5f193df
HEAD=$(git -C /home/user/KNHOST rev-parse HEAD)
cd $T && git checkout -q -- . && git clean -fdq && git checkout -q --detach $HEAD && cp /home/user/KNHOST/backend/.env backend/.env
echo "HEAD tujuan: $(git -C $T rev-parse --short HEAD)"
cd $W
git status --porcelain -uall | awk '{print $2}' | grep -v "^docs/reviews/2026-11-13/hasil/" | grep -v "^backend/.env$" > $S/pyt2_files.txt
: > $S/pyt2_konflik.txt
while read f; do
  mkdir -p $T/$(dirname $f)
  if ! git -C $W cat-file -e $B:$f 2>/dev/null; then
    if git -C $T cat-file -e HEAD:$f 2>/dev/null; then echo "BARU-DI-KEDUANYA $f" >> $S/pyt2_konflik.txt; fi
    cp -p $W/$f $T/$f; echo "baru  $f"; continue
  fi
  if [ "$(git -C $W rev-parse $B:$f)" = "$(git -C $T rev-parse HEAD:$f 2>/dev/null)" ]; then
    cp -p $W/$f $T/$f; echo "salin $f"
  else
    git -C $W show $B:$f > $S/pyt2_m_base.tmp; git -C $T show HEAD:$f > $S/pyt2_m_head.tmp
    if git merge-file -p $S/pyt2_m_head.tmp $S/pyt2_m_base.tmp $W/$f > $T/$f; then echo "gabung $f"
    else echo "BENTROK $f" | tee -a $S/pyt2_konflik.txt; fi
  fi
done < $S/pyt2_files.txt
echo "--- bentrok:"; cat $S/pyt2_konflik.txt
