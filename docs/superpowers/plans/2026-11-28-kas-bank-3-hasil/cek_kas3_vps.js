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
