"""Rakit Panduan UAT E2E (HTML) lalu cetak PDF A4 lanskap lewat Chrome headless.

Pemakaian (dari folder mana pun):
    python build.py          -> HTML + PDF (2 tahap: nomor halaman daftar isi dicari lewat PyMuPDF di container backend)
    python build.py --html   -> hanya HTML
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from page import CSS  # noqa: E402
import sections  # noqa: E402

OUT_DIR = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
NAME = "Panduan_UAT_E2E_ERP_Kain_Nusantara_v2.0"


def build_html():
    import importlib
    importlib.reload(sections)
    body = "\n".join(sections.all_sections())
    return (f'<!doctype html><html lang="id"><head><meta charset="utf-8">'
            f'<title>Panduan UAT End-to-End — ERP Kain Nusantara v2.0</title><style>{CSS}</style></head>'
            f'<body>{body}</body></html>')


def chrome():
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"):
        if os.path.exists(p):
            return p
    raise SystemExit("Chrome/Edge tidak ditemukan")


def render(hp, pdf):
    url = "file:///" + hp.replace("\\", "/")
    subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", url], check=True, capture_output=True)


def find_pages():
    json.dump(sections.TITLES, open(os.path.join(HERE, "toc_titles.json"), "w", encoding="utf-8", newline="\n"), ensure_ascii=False)
    rel = os.path.relpath(os.path.join(OUT_DIR, NAME + ".pdf"), REPO).replace("\\", "/")
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    r = subprocess.run(["docker", "compose", "-f", os.path.join(REPO, "docker-compose.dev.yml"), "exec", "-T", "backend",
                        "python", "/app/docs/uat/2026-10-21/src/pagefind.py", "/app/" + rel],
                       capture_output=True, text=True, env=env)
    print(r.stdout.strip() or r.stderr.strip()[:400])


def main():
    hp = os.path.join(OUT_DIR, NAME + ".html")
    pdf = os.path.join(OUT_DIR, NAME + ".pdf")
    passes = 1 if "--html" in sys.argv else 2
    for k in range(passes):
        html = build_html()
        with open(hp, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
        if "--html" in sys.argv:
            break
        render(hp, pdf)
        if k == 0:
            find_pages()
    print("HTML:", hp)
    if os.path.exists(pdf):
        print("PDF :", pdf, os.path.getsize(pdf), "bytes")


if __name__ == "__main__":
    main()
