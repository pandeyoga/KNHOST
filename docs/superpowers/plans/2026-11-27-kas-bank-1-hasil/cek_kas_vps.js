// Hanya-baca. Dijalankan SEBELUM pembaruan Kas & Bank bagian 1 di VPS untuk melihat PT mana yang angka posisi kasnya akan
// berubah tampilan (pembaca posisi kas kini membaca semua akun kas PT: pemetaan kas_bank.* + akun bertanda kas), dan
// apakah daftar "Admin tetap dua orang" disimpan sendiri (bawaan baru `pindah_saldo_kas` tidak berlaku bila disimpan).
// Tidak ada jurnal atau data yang diubah oleh pembaruan; ini hanya untuk tahu sebelumnya.
const KUNCI = ["kas_bank.kas_besar", "kas_bank.kas_kecil"];
print("1) Pemetaan akun kas per PT (selain bawaan 1-1100 / 1-1110):");
db.gl_account_mappings.find({key: {$in: KUNCI}}, {_id: 0, key: 1, entity_id: 1, account_code: 1})
  .forEach((m) => print("   " + JSON.stringify(m)));
print("2) Riwayat pemetaan akun kas:");
db.gl_account_mapping_history.find({key: {$in: KUNCI}}, {_id: 0, key: 1, entity_id: 1, from_code: 1, to_code: 1})
  .forEach((h) => print("   " + JSON.stringify(h)));
print("3) Akun bertanda kas / setara kas di bagan akun:");
db.gl_accounts.find({$or: [{is_cash: true}, {cash_equivalent: true}]}, {_id: 0, code: 1, entity_id: 1, name: 1})
  .forEach((a) => print("   " + JSON.stringify(a)));
print("4) Isian tersimpan kontrol.admin_tetap_dua_orang (kosong = memakai bawaan baru):");
// Pengaturan Pusat Pengaturan disimpan di `config_values` (yang berlaku: effective_to kosong) — diperbaiki 28 Nov
// (versi pertama butir ini membaca `system_settings`, yang tidak memuat kunci kontrol.*).
db.config_values.find({key: "kontrol.admin_tetap_dua_orang", effective_to: {$in: ["", null]}},
  {_id: 0, scope_type: 1, scope_id: 1, value: 1, changed_at: 1}).forEach((s) => print("   " + JSON.stringify(s)));
print("5) Kas yang posting jurnalnya gagal/tertunda per PT (pindah saldo PT itu akan ditolak sampai nol):");
db.cash_transactions.aggregate([{$match: {gl_status: {$in: ["failed", "pending"]}}},
  {$group: {_id: {pt: "$entity_id", status: "$gl_status"}, jumlah: {$sum: 1}}}]).forEach((r) => print("   " + JSON.stringify(r)));
