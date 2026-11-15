#!/bin/bash
# Uji merah di kode lama: simpan berkas unit, pulihkan berkas B, jalankan uji, kembalikan berkas unit.
S=/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad; W=$S/wt27; B=$S/pyt2_swap
LOG=${1:-$S/pyt2_logs/merah_kode_lama.txt}
shift
TESTS=${@:-tests_mem/test_PYT2_riwayat_kompensasi.py}
rm -rf $B && mkdir -p $B
cd $W
git status --porcelain -uall | awk '{print $2}' | grep -v "^docs/reviews/" > $B/FILES.txt
while read f; do mkdir -p $B/files/$(dirname $f); cp -p $f $B/files/$f; done < $B/FILES.txt
while read f; do
  case "$f" in backend/tests_mem/test_PYT2_*|backend/tests/test_bp_PYT2_*) continue;; esac
  if git cat-file -e HEAD:$f 2>/dev/null; then git show HEAD:$f > $f; else rm -f $f; fi
done < $B/FILES.txt
cd $W/backend && timeout 1500 $S/venv311/bin/python -m pytest $TESTS -q -p no:cacheprovider -n 0 -W ignore -rA > $LOG 2>&1
cd $W
while read f; do mkdir -p $(dirname $f); cp -p $B/files/$f $f; done < $B/FILES.txt
git status --porcelain -uall | wc -l
