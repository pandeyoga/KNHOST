// F18 — Tutup Buku (Manajer; Admin sebagai orang kedua): Daftar Periksa & Pratinjau bulan lalu (Oktober, BACA SAJA),
// tutup buku bulan kosong (September) → usul Buka Periode (kontrol ganda) → Posting Gagal → Admin menolak usul dan
// membuka kembali (Reopen) September. Akhir uji: status periode PT Sukacita SAMA dengan sebelum uji (diperiksa).
//   node docs/pelatihan/2026-11-18_keuangan/uji/F18_tutup_buku.js
// Kenapa September, bukan Oktober: jurnal gaji Oktober (latihan penggajian) bisa masih dibatalkan/diulang peserta lain;
// menutup Oktober akan menolak jurnal mundur mereka. September 2026 tidak berisi transaksi latihan apa pun.
// KN_TUTUP=2026-09 (bawaan) · KN_PERIKSA=2026-10 (bawaan) dapat diganti.
const { Run, api, assert, mongo, rp, sleep } = require("./lib");
const { KSC, potret, bersihkanGambar, menu, labaRugiDb, dekat, BULAN, pilih } = require("./buku_lib");

const PERIKSA = process.env.KN_PERIKSA || "2026-10";
const TUTUP = process.env.KN_TUTUP || "2026-09";
const [PY, PM] = PERIKSA.split("-");
const [TY, TM] = TUTUP.split("-");
const LBL_PERIKSA = `${BULAN[Number(PM) - 1]} ${PY}`;
const LBL_TUTUP = `${BULAN[Number(TM) - 1]} ${TY}`;
const akhir = (y, m) => new Date(Date.UTC(Number(y), Number(m), 0)).toISOString().slice(0, 10);
const ALASAN = "Latihan F18 — contoh koreksi salah akun beban";

async function pilihPT(r) {
  const sw = r.tid("entity-switcher");
  if (!(await sw.count())) return;
  const lbl = await r.text("entity-switcher");
  if (/Sukacita/.test(lbl) && !/Semua/.test(lbl)) return;
  await sw.click();
  await r.tid(`entity-option-${KSC}`).click();
  await r.idle(1200);
}

async function pilihPeriode(r, y, m) {
  await pilih(r, "closing-period-type", "month");
  await pilih(r, "closing-month", m);
  await pilih(r, "closing-year", y);
}

(async () => {
  const r = await new Run("F18", "Tutup Buku — daftar periksa, tutup, buka periode, posting gagal (Manajer)").start();
  bersihkanGambar(r);
  const adm = await api("admin");
  const mgr = await api("manager");
  const keadaan = async () => {
    const cl = await adm.get(`/finance/closing?entity_id=${KSC}`, KSC);
    const ul = await adm.get(`/finance/period-unlocks?entity_id=${KSC}`, KSC);
    return { tertutup: cl.filter((c) => c.status === "closed").map((c) => c.period_key).sort(),
      usulHidup: ul.filter((u) => ["pending", "approved"].includes(u.status)).map((u) => u.period_key).sort(), cl, ul };
  };
  let awal = null;
  try {
    // ── Persiapan (API): bersihkan sisa uji yang terputus, catat keadaan awal ─────────────────────────────────────
    let k0 = await keadaan();
    for (const u of k0.ul.filter((x) => x.status === "pending" && String(x.reason || "").startsWith("Latihan F18")))
      await adm.post(`/finance/period-unlocks/${u.id}/reject`, { reason: "Sisa uji F18 sebelumnya" }, KSC);
    const sisaUji = k0.ul.some((u) => u.period_key === TUTUP && String(u.reason || "").startsWith("Latihan F18"));
    for (const c of k0.cl.filter((x) => x.status === "closed" && x.period_key === TUTUP && sisaUji))
      await adm.post(`/finance/closing/${c.id}/reopen`, {}, KSC);   // tertinggal dari uji F18 yang terputus
    awal = await keadaan();
    assert(!awal.tertutup.includes(TUTUP), `${LBL_TUTUP} sudah tertutup sebelum uji — buka kembali dulu (Admin) atau pakai KN_TUTUP lain`);
    const jeTutup = mongo(`return db.journal_entries.countDocuments({entity_id:"${KSC}",status:{$ne:"void"},date:{$gte:"${TUTUP}-01",$lte:"${akhir(TY, TM)}T23:59:59"}})`);
    assert(jeTutup === 0, `${LBL_TUTUP} berisi ${jeTutup} jurnal — bukan bulan kosong, uji dihentikan agar tidak mengunci transaksi`);
    r.note(`Keadaan awal PT Sukacita: tertutup [${awal.tertutup.join(", ") || "—"}] · usul hidup [${awal.usulHidup.join(", ") || "—"}]`);

    await r.step(1, "Manajer", "Masuk sebagai manajer, PT Sukacita → Akuntansi & Pajak › Tutup Buku (tab Daftar Periksa & Tutup)",
      "Tiga tab: Daftar Periksa & Tutup · Buka Periode · Posting Gagal; kartu PERIODE TERTUTUP & TOTAL RIWAYAT; label PT 'Sukacita'",
      async () => {
        await r.login("manager");
        await pilihPT(r);
        await menu(r, "akuntansi", "closing");
        await r.tid("closing-view").waitFor();
        for (const t of ["closing", "period-unlock", "posting-failures"]) await r.tid(`hub-tab-${t}`).waitFor();
        const ent = await r.text("closing-entity-label");
        assert(/Sukacita/.test(ent), `PT: ${ent}`);
        const kpi = await r.text("closing-kpi");
        await potret(r, "tutup-buku-awal", [r.tid("nav-closing"), r.tid("hub-tab-closing"), r.tid("closing-entity-label")]);
        return `${ent} · ${kpi}`;
      });

    await r.step(2, "Manajer", `Pilih *Jenis Periode* Bulanan · *Bulan* ${BULAN[Number(PM) - 1]} · *Tahun* ${PY} → [Pratinjau] → baca 'Daftar Periksa Sebelum Tutup Buku'`,
      "Daftar butir (status Siap / Perlu dilihat / …) dengan angka dari sistem: persediaan vs buku besar, akun sementara (suspense), posting gagal, dokumen belum terjurnal, dll. Butir 'Perlu dilihat' tidak menghalangi, tetapi ikut disebut di dialog konfirmasi",
      async () => {
        await pilihPeriode(r, PY, PM);
        await r.tid("closing-preview-btn").click();   // daftar periksa dimuat bersama Pratinjau (PK-43)
        await r.tid("closing-checklist-items").waitFor({ timeout: 30000 });
        await r.idle(800);
        const ck = await mgr.get(`/finance/closing/checklist?period_type=month&period_key=${PERIKSA}&entity_id=${KSC}`, KSC);
        const items = ck.items || [];
        const out = [];
        for (const it of items) {
          const st = await r.text(`closing-check-${it.key}-status`);
          out.push(`${it.label || it.key}: ${st}`);
        }
        assert(items.length > 0 && out.length === items.length, `butir layar ${out.length} ≠ API ${items.length}`);
        await potret(r, "daftar-periksa-oktober", [r.tid("closing-month"), r.tid("closing-preview-btn"), r.tid("closing-checklist-summary")]);
        return `${await r.text("closing-checklist-summary")} · ${out.join(" | ")}`;
      });

    await r.step(3, "Manajer", `Gulir ke hasil Pratinjau ${LBL_PERIKSA} di bawah daftar periksa — JANGAN klik [Tutup Buku] untuk bulan ini`,
      `Kotak Pendapatan · Beban · Laba/Rugi Bersih → Laba Ditahan = laba-rugi jurnal ${LBL_PERIKSA}; tabel 'Jurnal Penutup (Pratinjau)' menutup tiap akun pendapatan/beban ke Laba Ditahan (tombol [Tutup Buku] yang disorot TIDAK diklik)`,
      async () => {
        await r.tid("closing-preview").waitFor({ timeout: 20000 });
        await r.tid("closing-preview").scrollIntoViewIfNeeded();
        await r.idle(800);
        const t = (await r.text("closing-preview"));
        const pv = await mgr.get(`/finance/closing/preview?period_type=month&period_key=${PERIKSA}&entity_id=${KSC}`, KSC);
        const lr = labaRugiDb(`${PERIKSA}-01`, akhir(PY, PM));
        assert(dekat(pv.net_income, lr.net) && dekat(pv.revenue_total, lr.revenue) && dekat(pv.expense_total, lr.cogs + lr.opex),
          `pratinjau ≠ jurnal: ${pv.revenue_total}/${pv.expense_total}/${pv.net_income} vs ${lr.revenue}/${lr.cogs + lr.opex}/${lr.net}`);
        for (const v of [pv.revenue_total, pv.expense_total, pv.net_income])
          assert(t.includes(rp(Math.abs(v)).replace("Rp ", "")), `nilai ${rp(v)} tidak tampil di pratinjau`);
        const lines = pv.closing_lines || [];
        if (lines.length) {
          const d = lines.reduce((s, l) => s + Number(l.debit || 0), 0), c = lines.reduce((s, l) => s + Number(l.credit || 0), 0);
          assert(dekat(d, c), `jurnal penutup pratinjau tidak seimbang ${d} ≠ ${c}`);
        }
        await potret(r, "pratinjau-oktober", [r.tid("closing-close-btn")]);
        return `pendapatan ${rp(pv.revenue_total)} · beban ${rp(pv.expense_total)} · laba/rugi ${rp(pv.net_income)} · ${lines.length} baris jurnal penutup`;
      });

    let closingId = "";
    await r.step(4, "Manajer (demo pelatih)", `Pilih *Bulan* ${BULAN[Number(TM) - 1]} · *Tahun* ${TY} → [Pratinjau] → [Tutup Buku]`,
      `Pratinjau 'Tidak ada saldo laba/rugi untuk ditutup pada periode ini.'; dialog merah 'Tutup buku ${LBL_TUTUP} — Sukacita?' menjelaskan jurnal penutup → Laba Ditahan dan periode terkunci`,
      async () => {
        await pilihPeriode(r, TY, TM);
        await r.tid("closing-preview-btn").click();
        await r.tid("closing-preview").waitFor({ timeout: 20000 });
        await r.idle(600);
        const pv = await r.text("closing-preview");
        assert(/Tidak ada saldo laba\/rugi/.test(pv), `pratinjau ${LBL_TUTUP}: ${pv.slice(0, 200)}`);
        await r.tid("closing-close-btn").click();
        await r.tid("closing-confirm").waitFor();
        const msg = await r.text("closing-confirm");
        assert(msg.includes(LBL_TUTUP) && /Sukacita/.test(msg), `dialog: ${msg.slice(0, 200)}`);
        await potret(r, "dialog-tutup-buku", [r.tid("closing-confirm-confirm")]);
        return msg.slice(0, 220);
      });

    await r.step(5, "Manajer (demo pelatih)", "Di dialog klik [Tutup Buku]",
      `Pesan hijau 'Periode ${LBL_TUTUP} berhasil ditutup. Jurnal penutup: —' (bulan kosong → tanpa jurnal penutup); Riwayat Tutup Buku: ${LBL_TUTUP} · Bulanan · Rp 0 · Tertutup; kartu PERIODE TERTUTUP bertambah 1. Jurnal bertanggal ${LBL_TUTUP} kini ditolak`,
      async () => {
        await r.tid("closing-confirm-confirm").click();
        await r.tid("closing-notice").waitFor({ timeout: 30000 });
        const notice = await r.text("closing-notice");
        assert(new RegExp(`${LBL_TUTUP} berhasil ditutup`).test(notice), `pesan: ${notice}`);
        const cl = await adm.get(`/finance/closing?entity_id=${KSC}`, KSC);
        const rec = cl.find((c) => c.period_key === TUTUP && c.status === "closed");
        assert(rec, "catatan penutupan tidak ada di server");
        closingId = rec.id;
        const st = await adm.get(`/finance/closing/status?date=${TUTUP}-15&entity_id=${KSC}`, KSC);
        assert(st.closed === true || st.is_closed === true, `status tanggal ${TUTUP}-15: ${JSON.stringify(st)}`);
        const row = await r.text(`closing-row-${rec.id}`);
        assert(/Tertutup/.test(row), `baris riwayat: ${row}`);
        await r.tid(`closing-row-${rec.id}`).scrollIntoViewIfNeeded();
        await potret(r, "riwayat-tertutup", [r.tid("closing-notice"), r.tid(`closing-row-${rec.id}`), r.tid("closing-kpi-closed")]);
        return `${notice} · riwayat: ${row}`;
      });

    let usulId = "";
    await r.step(6, "Manajer", `Tab [Buka Periode] → *Periode Tertutup* ${LBL_TUTUP} · *Alasan (wajib)* '${ALASAN}' → [Ajukan Usul]`,
      "Pesan hijau 'Usul buka periode dikirim. Perlu disetujui admin/manager LAIN (kontrol ganda)…'; baris usul berstatus Menunggu; tombol [Setujui] milik Anda abu-abu + tulisan 'perlu orang lain'",
      async () => {
        await r.tid("hub-tab-period-unlock").click();
        await r.tid("period-unlock-view").waitFor();
        await r.idle(800);
        await pilih(r, "plu-period-select", `month:${TUTUP}`);
        await r.tid("plu-reason-input").fill(ALASAN);
        await r.tid("plu-request-btn").click();
        await r.tid("plu-notice").waitFor({ timeout: 20000 });
        const notice = await r.text("plu-notice");
        const ul = await adm.get(`/finance/period-unlocks?entity_id=${KSC}`, KSC);
        const u = ul.find((x) => x.period_key === TUTUP && x.status === "pending" && x.reason === ALASAN);
        assert(u, "usul tidak tercatat di server");
        usulId = u.id;
        await r.tid(`plu-row-${u.id}`).waitFor();
        const row = await r.text(`plu-row-${u.id}`);
        const dis = await r.tid(`plu-approve-${u.id}`).isDisabled();
        assert(dis, "tombol Setujui aktif untuk pengusul sendiri");
        assert(/perlu orang lain/.test(row), `baris usul: ${row}`);
        await potret(r, "usul-buka-periode", [r.tid("plu-request-btn"), r.tid(`plu-approve-${u.id}`)]);
        return `${notice} · ${row}`;
      });

    await r.step(7, "Manajer", "Tab [Posting Gagal]",
      "Daftar dokumen yang jurnalnya gagal tercatat (bila ada: jenis, nomor, penyebab, tombol [Ulang Posting]); kosong = 'Tidak ada dokumen dengan jurnal gagal. Semua posting tercatat.' Jumlahnya sama dengan kartu 'Posting gagal' di Beranda Keuangan",
      async () => {
        await r.tid("hub-tab-posting-failures").click();
        await r.tid("posting-failures-view").waitFor();
        await r.idle(1200);
        const pf = await mgr.get(`/finance/posting-failures?page=1&page_size=50&entity_id=${KSC}`, KSC);
        const total = Number(pf.total || (pf.items || []).length || 0);
        const t = await r.text("posting-failures-view");
        if (!total) assert(await r.tid("pf-empty").count(), `API 0 tetapi layar: ${t.slice(0, 160)}`);
        else assert(!(await r.tid("pf-empty").count()) && t.includes(String((pf.items[0] || {}).number || "")), `API ${total} baris, layar: ${t.slice(0, 200)}`);
        await potret(r, "posting-gagal", [r.tid("hub-tab-posting-failures"), r.tid("pf-empty")]);
        return `${total} dokumen gagal · ${(await r.text("pf-filter").catch(() => "")).replace(/\s+/g, " ")}`;
      });

    await r.step(8, "Admin (pelatih, orang kedua)", "Masuk sebagai admin, PT Sukacita → Tutup Buku › Buka Periode → baris usul → [Tolak] → alasan → [Tolak Usul]",
      "Status usul berubah menjadi Ditolak dengan alasannya; periode tetap tertutup (tidak ada jendela buka). Bila [Setujui]: pita merah 'periode dibuka' tampil untuk SEMUA pengguna selama jendela — karena itu tidak dilakukan saat latihan",
      async () => {
        await r.login("admin");
        await pilihPT(r);
        await r.go("period-unlock");
        await r.tid(`plu-row-${usulId}`).waitFor({ timeout: 20000 });
        await r.tid(`plu-reject-${usulId}`).click();
        await r.tid("period-reject-confirm").waitFor();
        await r.tid("period-reject-confirm-reason").fill("Latihan selesai — tidak ada koreksi");
        await r.tid("period-reject-confirm-confirm").click();
        await r.tid("plu-notice").waitFor({ timeout: 20000 });
        await r.idle(800);
        const row = await r.text(`plu-row-${usulId}`);
        const ul = await adm.get(`/finance/period-unlocks?entity_id=${KSC}`, KSC);
        const u = ul.find((x) => x.id === usulId);
        assert(u && u.status === "rejected", `status usul di server: ${u && u.status}`);
        await potret(r, "usul-ditolak", [r.tid(`plu-row-${usulId}`)]);
        return row;
      });

    await r.step(9, "Admin (pelatih)", `Tab [Daftar Periksa & Tutup] → Riwayat Tutup Buku: baris ${LBL_TUTUP} → [Buka Kembali] → dialog [Buka Kembali]`,
      `Pesan 'Periode ${LBL_TUTUP} dibuka kembali (jurnal penutup dianulir).'; status baris menjadi 'Dibuka'; kartu PERIODE TERTUTUP kembali seperti semula. Hanya Admin (izin Buka kembali tutup buku) yang melihat tombol [Buka Kembali]`,
      async () => {
        await r.tid("hub-tab-closing").click();
        await r.tid(`closing-row-${closingId}`).waitFor({ timeout: 20000 });
        await r.tid(`closing-reopen-${closingId}`).click();
        await r.tid("confirm-modal").waitFor();
        await r.tid("confirm-modal-confirm").click();
        await r.tid("closing-notice").waitFor({ timeout: 30000 });
        const notice = await r.text("closing-notice");
        assert(/dibuka kembali/.test(notice) && !/menunggu orang kedua/.test(notice), `pesan: ${notice}`);
        await r.idle(800);
        const row = await r.text(`closing-row-${closingId}`);
        assert(/Dibuka/.test(row), `baris riwayat: ${row}`);
        const st = await adm.get(`/finance/closing/status?date=${TUTUP}-15&entity_id=${KSC}`, KSC);
        assert(!(st.closed === true || st.is_closed === true), `tanggal ${TUTUP}-15 masih tertutup: ${JSON.stringify(st)}`);
        await potret(r, "riwayat-dibuka-kembali", [r.tid("closing-notice"), r.tid(`closing-row-${closingId}`)]);
        return `${notice} · ${row}`;
      });

    await r.step(10, "Pemeriksa", "Bandingkan keadaan periode PT Sukacita dengan sebelum latihan",
      "Daftar periode tertutup dan usul buka periode yang hidup SAMA dengan sebelum uji (tidak ada periode tertinggal tertutup)",
      async () => {
        await sleep(500);
        const akhirK = await keadaan();
        assert(JSON.stringify(akhirK.tertutup) === JSON.stringify(awal.tertutup), `tertutup awal [${awal.tertutup}] ≠ akhir [${akhirK.tertutup}]`);
        assert(JSON.stringify(akhirK.usulHidup) === JSON.stringify(awal.usulHidup), `usul hidup awal [${awal.usulHidup}] ≠ akhir [${akhirK.usulHidup}]`);
        return `tertutup [${akhirK.tertutup.join(", ") || "—"}] · usul hidup [${akhirK.usulHidup.join(", ") || "—"}] — sama dengan awal`;
      });
  } catch (e) {
    r.note("GALAT: " + (e && e.message ? e.message : e));
  } finally {
    // Jaring pengaman: apa pun yang terjadi, jangan tinggalkan periode latihan tertutup / usul menggantung.
    try {
      const cl = await adm.get(`/finance/closing?entity_id=${KSC}`, KSC);
      for (const c of cl.filter((x) => x.status === "closed" && x.period_key === TUTUP && !(awal && awal.tertutup.includes(TUTUP)))) {
        await adm.post(`/finance/closing/${c.id}/reopen`, {}, KSC);
        r.note(`pengaman: ${c.period_label} dibuka kembali`);
      }
      const ul = await adm.get(`/finance/period-unlocks?entity_id=${KSC}`, KSC);
      for (const u of ul.filter((x) => x.status === "pending" && x.reason === ALASAN)) {
        await adm.post(`/finance/period-unlocks/${u.id}/reject`, { reason: "Pengaman uji F18" }, KSC);
        r.note(`pengaman: usul ${u.period_label} ditolak`);
      }
    } catch (e) { r.note("pengaman gagal: " + e.message); }
    await r.finish();
  }
})();
