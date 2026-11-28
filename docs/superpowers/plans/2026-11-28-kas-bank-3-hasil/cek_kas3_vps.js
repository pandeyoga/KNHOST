// Hanya-baca. Dijalankan SEBELUM memakai fitur Kas & Bank bagian 3 di VPS (kas kasir, dana tetap, opname kas).
// Pembaruan sendiri tidak mengubah rekening, saldo, atau jurnal; ini hanya untuk tahu sebelumnya apa yang perlu diatur.
const KODE = ["1-1105", "1-1290", "6-9200"];
const KUNCI = ["kas_bank.kas_kasir", "kas_bank.selisih_kas", "kas_bank.piutang_kurang_kas"];
print("1) Akun milik PT sendiri yang sudah berkode 1-1105 / 1-1290 / 6-9200 (ada = atur Pemetaan Akun PT itu dulu):");
db.gl_accounts.find({code: {$in: KODE}, entity_id: {$nin: [null, ""]}}, {_id: 0, code: 1, entity_id: 1, name: 1})
  .forEach((a) => print("   " + JSON.stringify(a)));
print("   Akun templat (entity_id kosong) yang sudah ada — kosong sebelum pembaruan itu wajar:");
db.gl_accounts.find({code: {$in: KODE}, entity_id: {$in: [null, ""]}}, {_id: 0, code: 1, name: 1})
  .forEach((a) => print("   " + JSON.stringify(a)));
print("2) Pemetaan akun tersimpan untuk kunci baru (kosong = memakai bawaan):");
db.gl_account_mappings.find({key: {$in: KUNCI}}, {_id: 0, key: 1, entity_id: 1, account_code: 1})
  .forEach((m) => print("   " + JSON.stringify(m)));
print("3) Rekening tunai per PT dan jenisnya (rekening lama tidak diubah pembaruan):");
db.bank_accounts.aggregate([{$match: {account_type: "cash"}},
  {$group: {_id: {pt: "$entity_id", jenis: "$cash_type", aktif: "$is_active"}, jumlah: {$sum: 1}}},
  {$sort: {"_id.pt": 1}}]).forEach((r) => print("   " + JSON.stringify(r)));
// Pengaturan Pusat Pengaturan disimpan di `config_values` (satu baris per perubahan; yang berlaku: effective_to kosong).
const BERLAKU = {$in: ["", null]};
print("4) Isian tersimpan kontrol.admin_tetap_dua_orang (ada tanpa \"selisih_kas\" = bawaan baru tidak berlaku di lapisan itu):");
db.config_values.find({key: "kontrol.admin_tetap_dua_orang", effective_to: BERLAKU},
  {_id: 0, scope_type: 1, scope_id: 1, value: 1, changed_at: 1}).forEach((s) => print("   " + JSON.stringify(s)));
print("5) Isian tersimpan kas.opname_* / kontrol.selisih_kas.* (kosong = bawaan 1/7/7 hari, 2 orang):");
db.config_values.find({key: {$in: ["kas.opname_kasir_hari", "kas.opname_kas_kecil_hari", "kas.opname_kas_besar_hari",
  "kontrol.selisih_kas.min_orang", "kontrol.selisih_kas.batas_nominal"]}, effective_to: BERLAKU},
  {_id: 0, key: 1, scope_type: 1, scope_id: 1, value: 1}).forEach((s) => print("   " + JSON.stringify(s)));
// Temuan tangkapan A (ketetapan R7) — kas lama tanpa rekening ikut saldo rekening TUNGGAL jenis kasnya; begitu ada
// rekening kedua sejenis, kas itu tidak ikut rekening mana pun. Sesudah pembaruan, kas itu ditetapkan ke rekening tunggal
// saat rekening kedua lahir; keadaan yang SUDAH ambigu (≥ 2 rekening) menahan opname & isi ulang dana tetap jenis itu.
// Jenis kas rekening = `bank_service.account_cash_type` (cash_type tersimpan bila sah, selain itu tunai = kas kecil,
// bank = kas besar); aktif = is_active bukan false dan status bukan "inactive".
print("6) Kas lama tanpa rekening (tidak batal) per PT & jenis kas, dan jumlah rekening aktif jenis itu:");
const JENIS = ["kas_kecil", "kas_kasir", "kas_besar"];
const jenisRek = (a) => (JENIS.includes(a.cash_type) ? a.cash_type : (a.account_type === "cash" ? "kas_kecil" : "kas_besar"));
const rekAktif = {};
db.bank_accounts.find({is_active: {$ne: false}, status: {$ne: "inactive"}},
  {_id: 0, entity_id: 1, cash_type: 1, account_type: 1, name: 1}).forEach((a) => {
  const k = (a.entity_id || "") + "|" + jenisRek(a);
  (rekAktif[k] = rekAktif[k] || []).push(a.name || "");
});
// PT yang sudah memakai akun buku besar per rekening (penanda `cash_account_mode`): kas lama yang tercatat sebelum
// penanda TIDAK ditetapkan otomatis (pembaliknya akan dialihkan ke sub-akun) — sesudah rekening kedua lahir jadi ambigu.
const perRekening = {};
db.system_settings.find({scope: "__kas_per_rekening__"}, {_id: 0}).forEach((d) => Object.keys(d).forEach((k) => {
  if (d[k] && d[k].sejak && (!perRekening[k] || d[k].sejak < perRekening[k])) perRekening[k] = d[k].sejak;
}));
let adaAmbigu = false;
db.cash_transactions.aggregate([
  {$match: {status: {$ne: "void"}, $or: [{account_id: {$exists: false}}, {account_id: {$in: [null, ""]}}]}},
  {$group: {_id: {pt: "$entity_id", jenis: "$cash_type"}, jumlah: {$sum: 1},
    bersih: {$sum: {$cond: [{$eq: ["$direction", "in"]}, "$amount", {$multiply: ["$amount", -1]}]}}}},
  {$sort: {"_id.pt": 1, "_id.jenis": 1}}]).forEach((r) => {
  const rek = rekAktif[(r._id.pt || "") + "|" + (r._id.jenis || "")] || [];
  const tanda = !JENIS.includes(r._id.jenis) ? "JENIS TIDAK DIKENAL (tidak ikut rekening mana pun)"
    : rek.length >= 2 ? "AMBIGU — opname & isi ulang jenis ini akan ditahan; tetapkan rekeningnya (pemilik memutuskan)"
    : rek.length === 1 ? "ikut rekening tunggal " + rek[0] + (perRekening[r._id.pt]
      ? " (PT akun per rekening sejak " + perRekening[r._id.pt] + ": kas sebelum itu TIDAK ditetapkan otomatis)"
      : " (ditetapkan otomatis saat rekening kedua lahir)")
    : "belum ada rekening aktif jenis ini";
  if (rek.length >= 2 && JENIS.includes(r._id.jenis)) adaAmbigu = true;
  print("   " + JSON.stringify({pt: r._id.pt, jenis: r._id.jenis, jumlah: r.jumlah, bersih: r.bersih,
    rekening_aktif: rek.length}) + " → " + tanda);
});
print("   " + (adaAmbigu ? "ADA baris AMBIGU di atas." : "Tidak ada baris ambigu."));
