# Erratum tahap historis d6da

Hipotesis D4-FE-02 entity-switch overwrite pada draf tahap ini ditarik: AppViewRouter key={selectedEntity} menyebabkan remount. Probe historis berbagi setters dan tidak merepresentasikan lifecycle itu. Hasilnya disimpan untuk histori, bukan bukti confirmed bug. Current D4-FE-02 menguji respons period30→90 pada entitas sama, yang tidak remount, dan mempunyai counterexample tersendiri. Hipotesis biaya redacted tidak dimasukkan sebagai bug UI normal. Current D4-DASH-01 juga mengakui kasus103 sudah diperbaiki dan hanya mempertahankan kasus3003 yang terbukti.
