// Alur retur pelanggan yang dipakai ulang skrip A3 (penjualan: store credit & refund; tukar barang).
// `alurRetur(r, ctx, { lanjut })` → { depan(tag, so, keluhan), selesaikan(tag, so, opsi) } — tiap fungsi menjalankan
// langkah layar ber-`Run.step` (Sales → Manajer → Sales → Gudang → Kepala Gudang → QC; Manajer selesaikan + cek buku).
const { api, assert, mongo, rp } = require("../lib");
const R = require("./retur_lib");

const URUT = ["draft", "pending_approval", "approved", "inspecting", "inspected", "credit_settled", "refund_settled", "settled"];
const lewat = (ret, st) => !!ret && URUT.indexOf(ret.status) >= URUT.indexOf(st);

function alurRetur(r, ctx, { lanjut = false } = {}) {
  const LANJUT = lanjut;
  const cust = ctx.cust;
  async function depan(tag, so, keluhan) {
    const id = () => (ctx.ret[tag] || {}).id;
    const segar = () => { if (id()) ctx.ret[tag] = R.returById(id()); return ctx.ret[tag]; };
    if (LANJUT) ctx.ret[tag] = R.returSo(so.so_id);

    await R.langkah(r, `${tag}1`, "Sales", "Masuk sebagai sales@ → menu [[Retur]] → tab [[Retur Pelanggan]] → [[Buat Retur]]",
      "Pop-up 'Buat Retur / Barang Sisa' terbuka", async (ulang) => {
        if (ulang) ctx.ret[tag] = R.returSo(so.so_id) || ctx.ret[tag];
        if ((LANJUT || ulang) && ctx.ret[tag]) return `lewati (sudah ada ${ctx.ret[tag].number})`;
        await r.login("sales");
        await R.bukaRetur(r, "returns", `${tag}-sales-retur`);
        await R.klikPotret(r, r.tid("create-return-btn"), `${tag}-sales-buat-retur`);
        await r.tid("create-return-form").waitFor();
      });

    await R.langkah(r, `${tag}2`, "Sales", `Cari & pilih pesanan ${so.so}; centang roll yang dikembalikan; isi alasan & sebab keluhan → [[Buat Retur]]`,
      "Retur SRET-… terbuka dengan status 'Menunggu Persetujuan'", async (ulang) => {
        if (ulang) ctx.ret[tag] = R.returSo(so.so_id) || ctx.ret[tag];
        if ((LANJUT || ulang) && ctx.ret[tag]) return `lewati (${ctx.ret[tag].number} ${ctx.ret[tag].status})`;
        await r.tid("return-order-search").fill(so.so.replace(/^.*\//, ""));
        await r.idle(900);
        await R.pilihRe(r, "return-order-select", new RegExp(so.so.replace(/[/]/g, "\\/")));
        // Roll terkirim yang masih bisa diretur (sumber sama dengan layar: /sales-returns/returnable).
        const bisa = await (await api("sales")).get(`/sales-returns/returnable?order_id=${so.so_id}`, R.KSC);
        const roll = (bisa.rolls || []).find((x) => x.remaining > 0);
        assert(roll, `${so.so} tidak punya roll terkirim yang bisa diretur`);
        const pre = `return-item-${roll.product_id}-roll-${roll.roll_id}`;
        const box = r.tid(`${pre}-check`);
        await box.waitFor({ timeout: 15000 });
        await box.check();
        await r.tid(`${pre}-reason`).fill(keluhan.alasan);
        if (await r.tid("return-complaint-code").count()) {
          await R.pilihRe(r, "return-complaint-code", keluhan.sebab).catch(async () => {
            await r.page.keyboard.press("Escape");
          });
        }
        await r.tid("return-notes-input").fill(keluhan.catatan);
        await r.shot(`${tag}-sales-form-isi`, { full: true });
        await R.klikPotret(r, r.tid("save-return-btn"), `${tag}-sales-simpan`);
        await r.tid("return-detail-view").waitFor({ timeout: 20000 });
        await r.idle(800);
        ctx.ret[tag] = await R.tunggu(() => R.returSo(so.so_id), "retur tidak tersimpan");
        assert(ctx.ret[tag].status === "pending_approval", `status retur ${ctx.ret[tag].status}`);
        await R.sorot(r.tid("return-number"));
        await r.shot(`${tag}-sales-retur-terbit`);
        return `${ctx.ret[tag].number} · ${ctx.ret[tag].items[0].quantity_returned} ${ctx.ret[tag].items[0].unit} · roll ${roll.roll_no}`;
      });

    await R.langkah(r, `${tag}3`, "Manajer", "Masuk sebagai manager@ → Retur › Retur Pelanggan → cari nomor retur → [[Detail →]] → [[Setujui (Manager)]]",
      "Status 'Disetujui'; panel 'QC retur · SPK inspeksi per roll' menampilkan SPK KSC/INS-… (lahir otomatis)", async (ulang) => {
        const ret = segar();
        if ((LANJUT || ulang) && lewat(ret, "approved")) return `lewati (${ret.status})`;
        await r.login("manager");
        await R.bukaRetur(r, "returns");
        await R.bukaDetailRetur(r, ret, `${tag}-manajer-buka-detail`);
        await r.shot(`${tag}-manajer-detail`, { full: true });
        await R.klikPotret(r, r.tid("approve-return-btn"), `${tag}-manajer-setujui`);
        const ok = await R.tunggu(() => { const x = segar(); return x.status === "approved" && x.inspection_id ? x : null; },
          "retur tidak menjadi 'Disetujui' + SPK");
        await r.idle(800);
        await r.tid("return-spk-panel").waitFor({ timeout: 15000 });
        await R.sorot(r.tid("return-spk-panel"));
        await r.shot(`${tag}-manajer-disetujui-spk`);
        return `${ok.number} disetujui · SPK ${ok.inspection_number || ok.inspection_id}`;
      });

    await R.langkah(r, `${tag}4`, "Sales", "sales@ buka retur → panel 'Pengembalian barang': *Cara barang kembali* = Diantar sendiri oleh pelanggan → [[Barang sudah dikirim/dijemput]]",
      "Tahap 'Barang dikirim/dijemput' tercentang; menunggu scan terima gudang", async (ulang) => {
        const ret = segar();
        if ((LANJUT || ulang) && (ret.shipped_to_store_at || lewat(ret, "inspected"))) return "lewati (sudah dikirim)";
        await r.login("sales");
        await R.bukaRetur(r, "returns");
        await R.bukaDetailRetur(r, ret);
        await r.tid("return-shipment-form").waitFor();
        await R.pilih(r, "return-shipment-method", "Diantar sendiri oleh pelanggan");
        await r.tid("return-shipment-note").fill("Pelanggan mengantar roll ke gudang Jakarta");
        await R.klikPotret(r, r.tid("return-shipment-ship"), `${tag}-sales-barang-dikirim`);
        await R.tunggu(() => segar().shipped_to_store_at, "tonggak barang dikirim tidak tercatat");
        await r.idle(600);
        await r.shot(`${tag}-sales-pengembalian-tercatat`);
      });

    await R.langkah(r, `${tag}5`, "Gudang", `warehouse@ buka retur → tab [[Logistik & perjalanan]] → *Tahap* Terima di gudang, *Gudang* ${R.GUDANG_JKT}, ketik nomor roll → [[Catat scan]]`,
      "Lokasi roll: diterima di Jakarta · Gudang Sukacita; panel QC: 'Roll diterima gudang 1/1'", async (ulang) => {
        const ret = segar();
        const rid = ret.items[0].roll_ids[0];
        const rollNo = (ret.items[0].roll_nos || {})[rid] || mongo(`return db.inventory_rolls.findOne({id:"${rid}"},{_id:0,roll_no:1}).roll_no`);
        if ((LANJUT || ulang) && ((ret.roll_locations || {})[rid] || {}).stage) return `lewati (${ret.roll_locations[rid].stage})`;
        await r.login("warehouse");
        await R.bukaRetur(r, "returns");
        await R.bukaDetailRetur(r, ret);
        await R.klikPotret(r, r.tid("return-tab-logistik"), `${tag}-gudang-tab-logistik`);
        await r.tid("journey-scan-form").waitFor();
        await R.pilih(r, "journey-scan-warehouse", R.GUDANG_JKT);
        await r.tid("journey-scan-codes").fill(rollNo);
        await R.klikPotret(r, r.tid("journey-scan-submit"), `${tag}-gudang-catat-scan`);
        await R.tunggu(() => ((segar().roll_locations || {})[rid] || {}).stage === "received", "scan terima tidak tercatat");
        await r.idle(800);
        await R.sorot(r.tid(`timeline-roll-location-${rid}`));
        await r.shot(`${tag}-gudang-roll-diterima`);
        return `roll ${rollNo} diterima`;
      });

    await R.langkah(r, `${tag}6`, "Kepala Gudang", "wh.admin@ buka retur → panel 'QC retur · SPK inspeksi per roll' → pilih petugas QC (Mulyadi) → [[Tugaskan]]",
      "Petugas SPK: Mulyadi; status SPK Ditugaskan", async (ulang) => {
        const ret = segar();
        const s = R.spk(ret.inspection_id);
        if ((LANJUT || ulang) && s && s.assigned_to) return `lewati (sudah ditugaskan, ${s.status})`;
        await r.login("wh.admin");
        await R.bukaRetur(r, "returns");
        await R.bukaDetailRetur(r, ret);
        await r.tid("return-spk-assign").waitFor({ timeout: 15000 });
        await R.pilihRe(r, "return-spk-officer", /Mulyadi/);
        await R.klikPotret(r, r.tid("return-spk-assign-btn"), `${tag}-kagud-tugaskan`);
        await R.tunggu(() => (R.spk(ret.inspection_id) || {}).assigned_to, "SPK tidak tertugaskan");
        await r.idle(600);
        await r.shot(`${tag}-kagud-spk-ditugaskan`);
      });

    await R.langkah(r, `${tag}7`, "QC", "qc@ buka retur → [[Buka SPK]] → [[Mulai periksa]] → baris roll [[QC 4-point]]: *Kondisi* Baik, *Qty aktual* = qty klaim, *Grade* A → [[Simpan hasil]] → *Keputusan akhir* Diterima → [[Tutup SPK]]",
      "SPK selesai; retur berstatus 'Siap diselesaikan' (hasil per roll: grade A, kondisi Baik)", async (ulang) => {
        const ret = segar();
        if ((LANJUT || ulang) && lewat(ret, "inspected")) return `lewati (${ret.status})`;
        await r.login("qc");
        await R.bukaRetur(r, "returns");
        await R.bukaDetailRetur(r, ret);
        await R.klikPotret(r, r.tid("return-spk-open"), `${tag}-qc-buka-spk`);
        await r.tid("ins-detail-panel").waitFor({ timeout: 20000 });
        await r.idle(600);
        const s0 = R.spk(ret.inspection_id);
        if (["draft", "assigned"].includes(s0.status)) {
          await R.klikPotret(r, r.tid("ins-start-button"), `${tag}-qc-mulai`);
          await R.tunggu(() => R.spk(ret.inspection_id).status === "in_progress", "SPK tidak mulai");
          await r.idle(800);
        }
        const ln = R.spk(ret.inspection_id).lines[0];
        const tombol = (await r.tid(`ins-line-qc-${ln.id}`).count()) ? r.tid(`ins-line-qc-${ln.id}`) : r.tid(`ins-line-inspect-${ln.id}`);
        await R.klikPotret(r, tombol, `${tag}-qc-isi-baris`);
        await r.tid("ins-line-modal").waitFor();
        if (await r.tid("ins-return-condition").count()) await R.pilih(r, "ins-return-condition", "Baik");
        if (await r.tid("ins-return-actual").count()) {
          const v = await r.tid("ins-return-actual").inputValue();
          if (!v) await r.tid("ins-return-actual").fill(String(ln.quantity));
        }
        await R.pilihRe(r, "ins-grade-input", /^A\b/);
        await r.shot(`${tag}-qc-form-hasil`, { full: true });
        await R.klikPotret(r, r.tid("ins-line-submit"), `${tag}-qc-simpan-hasil`);
        await r.tid("ins-line-modal").waitFor({ state: "detached", timeout: 20000 });
        await r.idle(800);
        await R.pilihRe(r, "ins-decision-select", /Diterima/);
        await R.klikPotret(r, r.tid("ins-finish-button"), `${tag}-qc-tutup-spk`);
        await R.tunggu(() => segar().status === "inspected", "retur tidak menjadi 'Siap diselesaikan'");
        await r.idle(800);
        await r.shot(`${tag}-qc-spk-selesai`);
        const rr = (segar().items[0].inspection || {}).roll_results || {};
        return `hasil: ${JSON.stringify(Object.values(rr).map((x) => ({ grade: x.grade, kondisi: x.condition, qty: x.actual_qty })))}`;
      });
    return segar();
  }

  // ── Penyelesaian per roll oleh Manajer + cek buku ────────────────────────────────────────────────────────────────
  // `hasil` = { outcome: label opsi di layar, akun: kode akun kredit tujuan, kas: true bila refund tunai }
  async function selesaikan(tag, so, opsi) {
    let ret = R.returById(ctx.ret[tag].id);
    const rid = ret.items[0].roll_ids[0];
    const rollNo = (ret.items[0].roll_nos || {})[rid] || mongo(`return db.inventory_rolls.findOne({id:"${rid}"},{_id:0,roll_no:1}).roll_no`);
    const sisaAwal = R.sisaSo(so.so_id);
    const saldoAwal = R.saldoKredit(cust.id);
    let pv = null, dilewati = false;   // dilewati = penyelesaian sudah ada dari jalan sebelumnya (KN_LANJUT)
    await R.langkah(r, `${tag}8`, "Manajer", `manager@ buka retur → [[Selesaikan (Pilih Outcome)]] → roll ${rollNo}: *Outcome* ${opsi.label}${opsi.kas ? " · *Rekening pengembalian dana* BCA Operasional KSC" : ""} → buka 'Lihat jurnal yang akan terbentuk' → isi *Bukti keputusan* → [[Simpan penyelesaian (1 roll)]]`,
      opsi.hasil, async (ulang) => {
        if (ulang || LANJUT) ret = R.returById(ret.id);
        if ((LANJUT || ulang) && lewat(ret, opsi.status)) {
          pv = ((ret.settlements || []).slice(-1)[0] || {}).plan || null;   // angka penyelesaian yang sudah tersimpan
          dilewati = !ulang;
          return `lewati (${ret.status})`;
        }
        await r.login("manager");
        await R.bukaRetur(r, "returns");
        await R.bukaDetailRetur(r, ret);
        await R.klikPotret(r, r.tid("open-settle-btn"), `${tag}-manajer-selesaikan`);
        await r.tid("roll-settle-modal").waitFor();
        await r.tid(`roll-settle-outcome-${rollNo}`).waitFor({ timeout: 15000 });
        await R.pilih(r, `roll-settle-outcome-${rollNo}`, opsi.label);
        await r.tid("settle-preview").waitFor({ timeout: 20000 });
        await r.idle(700);
        pv = await (await api("manager")).post(`/sales-returns/${ret.id}/roll-settlement/preview`,
          { rolls: [{ roll_id: rid, outcome: opsi.value }], payout: "", refund_account_code: "" }, R.KSC);
        await r.tid("settle-preview-journal").locator("summary").click();
        await r.tid("roll-settle-decision-note").fill(opsi.bukti);
        await R.sorot(r.tid("settle-preview"));
        await r.shot(`${tag}-manajer-nilai-jurnal`);
        await R.lepas(r.tid("settle-preview"));
        await r.shot(`${tag}-manajer-modal-penuh`, { full: true });
        const teks = (await r.tid("settle-preview-split").innerText()).replace(/\s+/g, " ");
        await R.klikPotret(r, r.tid("roll-settle-confirm"), `${tag}-manajer-simpan`);
        await r.tid("roll-settle-modal").waitFor({ state: "detached", timeout: 30000 });
        ret = await R.tunggu(() => { const x = R.returById(ret.id); return x.status === opsi.status ? x : null; },
          `status retur tidak menjadi ${opsi.status}`);
        await r.idle(900);
        await R.sorot(r.tid("return-credit-note-section"));
        await r.shot(`${tag}-manajer-nota-kredit`, { full: true });
        return `pratinjau: ${teks} · ${ret.credit_note_number}`;
      });

    let cn = null, je = null;
    await R.langkah(r, `${tag}9`, "Sistem", "Cek buku: Nota Kredit, jurnal retur (pembalikan penjualan, PPN keluaran, persediaan kembali), tagihan & saldo",
      opsi.buku, async (ulang) => {
        cn = R.notaKredit(ret.id)[0];
        assert(cn, "Nota Kredit tidak terbit");
        assert(pv && Math.abs(pv.gross_amount - cn.gross_amount) < 0.01, `pratinjau ${pv && pv.gross_amount} ≠ Nota Kredit ${cn.gross_amount}`);
        const sid = cn.settlement_id;
        je = R.jurnalDari([`${ret.id}:${sid}`]).find((j) => j.source_type === "sales_return") || R.jurnalDari([`${ret.id}:${sid}`])[0];
        const bill = R.r2(pv.bill_total), kas = R.r2(pv.cash_total), saldo = R.r2(pv.saldo_total);
        assert(Math.abs(bill + kas + saldo - cn.gross_amount) < 0.02, `pembagian ${bill}+${kas}+${saldo} ≠ ${cn.gross_amount}`);
        const harap = [["4-1000", "D", cn.net_amount], ["2-1200", "D", cn.ppn_amount],
          ["1-1300", "D", cn.cogs_amount], ["5-1000", "K", cn.cogs_amount]];
        if (bill) harap.push(["1-1200", "K", bill]);
        if (kas) harap.push(["1-1100", "K", kas]);
        if (saldo) harap.push(["2-1450", "K", saldo]);
        const t = R.cekJurnal(je, harap);
        assert(cn.cogs_amount > 0, "persediaan tidak kembali (nilai HPP dibalik 0)");
        const sisaAkhir = R.sisaSo(so.so_id), saldoAkhir = R.saldoKredit(cust.id);
        if (!dilewati) assert(Math.abs((sisaAwal - sisaAkhir) - bill) < 0.02, `sisa tagihan ${so.so}: ${sisaAwal} → ${sisaAkhir}, harus turun ${bill}`);
        if (!dilewati) assert(Math.abs((saldoAkhir - saldoAwal) - saldo) < 0.02, `saldo pelanggan ${saldoAwal} → ${saldoAkhir}, harus naik ${saldo}`);
        ctx[`cn${tag}`] = cn; ctx[`je${tag}`] = je; ctx[`pv${tag}`] = pv;
        if (kas) {
          const kt = mongo(`return db.cash_transactions.findOne({ref_type:"sales_return",ref_id:"${ret.id}:${sid}",status:{$ne:"void"}},{_id:0})`);
          assert(kt && Math.abs(kt.amount - kas) < 0.01 && /out|keluar/i.test(kt.type || kt.direction || ""), `transaksi kas refund: ${JSON.stringify(kt).slice(0, 200)}`);
          ctx[`kas${tag}`] = kt;
        }
        return `${cn.number} DPP ${rp(cn.net_amount)} + PPN ${rp(cn.ppn_amount)} = ${R.rpBuku(cn.gross_amount)} · HPP dibalik ${R.rpBuku(cn.cogs_amount)} · potong tagihan ${R.rpBuku(bill)} · refund ${R.rpBuku(kas)} · saldo ${R.rpBuku(saldo)} · ${t}`;
      });
    return ret;
  }

  return { depan, selesaikan };
}

module.exports = { alurRetur, lewat, URUT };
