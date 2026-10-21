"""Cari nomor halaman tiap judul bagian di PDF (dijalankan di container backend yang punya PyMuPDF)."""
import json
import os
import sys

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
pdf = sys.argv[1]
titles = json.load(open(os.path.join(HERE, "toc_titles.json"), encoding="utf-8"))
doc = fitz.open(pdf)
texts = [" ".join(doc[i].get_text().split()) for i in range(doc.page_count)]
found = {}
for t in titles:
    key = " ".join(t.split())[:40]
    for i in range(2, doc.page_count):     # lewati sampul & daftar isi
        if key in texts[i][:260]:
            found[t] = i + 1
            break
json.dump(found, open(os.path.join(HERE, "toc_pages.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
print("pages", doc.page_count, "found", len(found), "of", len(titles))
