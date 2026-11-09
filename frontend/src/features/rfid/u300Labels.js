/**
 * PREP-D1 — istilah Indonesia untuk panel gate U300 V2 (kode mentah server tidak ditampilkan apa adanya).
 * K-RFID-09: Merah = pelanggaran (gate terkunci) · Kuning = perlu diperiksa, barang jalan, gate tidak terkunci ·
 * Batal = lintasan kosong/mundur tanpa alarm.
 */
export const VERDICT = {
  GREEN: { label: "Hijau — sesuai dokumen", short: "Hijau", color: "green" },
  REVIEW: { label: "Kuning — perlu diperiksa", short: "Kuning", color: "orange" },
  RED: { label: "Merah — pelanggaran, gate terkunci", short: "Merah", color: "red" },
  CANCELLED: { label: "Batal — lintasan kosong/mundur", short: "Batal", color: "gray" },
  UNKNOWN: { label: "Belum diketahui", short: "?", color: "gray" },
};

export function verdictInfo(decision, state) {
  if (!decision) return { label: state === "CLOSING" ? "Sedang dinilai" : "Merekam", short: "Merekam", color: "info" };
  return VERDICT[decision.verdict] || VERDICT.UNKNOWN;
}

export const REASON = {
  MANIFEST_MATCH: "Semua roll kuat milik dokumen aktif",
  NOT_IN_DOCUMENT: "Roll tidak tercantum di dokumen yang dipilih",
  NO_DOCUMENT: "Roll tanpa dokumen keluar/masuk",
  NOT_IN_MANIFEST: "Roll tidak ada di surat jalan",
  UNKNOWN_EPC: "Tag asing bersinyal kuat",
  UNKNOWN_EPC_UNSCORED: "Tag tidak dikenal (tanpa skor sinyal)",
  QUARANTINE: "Roll karantina QC",
  ALREADY_OUT: "Roll sudah keluar/habis",
  REPLAY_EXIT: "Roll sudah pernah lewat untuk dokumen ini",
  REPLAY_CROSSING: "Roll sudah lewat di lintasan lain",
  PREVIOUS_PASSAGE: "Terbaca dari muatan sebelumnya (tidak dinilai ulang)",
  PREVIOUS_PASSAGE_RECENT: "Baru saja lewat gate ini — kemungkinan bacaan muatan lain",
  DOC_CANCELLED: "Dokumen dibatalkan",
  SO_CANCELLED: "Pesanan dibatalkan",
  WRONG_WAREHOUSE: "Dokumen dari gudang lain",
  WRONG_DESTINATION: "Tujuan gudang salah",
  SOURCE_CONTEXT_MISMATCH: "Roll milik dokumen aktif lain",
  NOT_RELEASED: "Dokumen belum dikirim di sistem",
  MOVEMENT_NOT_ACTIVE: "Dokumen belum aktif / roll bukan anggota",
  DOC_MISSING: "Dokumen roll tidak ditemukan",
  SALES_TRANSIT_NOT_INBOUND: "Barang kiriman pelanggan (bukan masuk internal)",
  LOCAL_ROLL: "Roll milik gudang ini terbaca di gate masuk",
  NO_MANIFEST: "Belum ada dokumen terikat/auto-cocok",
  SOURCE_NOT_ACTIVE: "Dokumen terpilih tidak aktif lagi",
  SOURCE_UNSUPPORTED: "Jenis dokumen belum didukung gate",
  MANIFEST_CHANGED: "Isi dokumen berubah sejak dipilih",
  MANIFEST_BOUND_AFTER_CAPTURE: "Dokumen dipilih setelah bacaan dimulai",
  CAPTURE_INCOMPLETE: "Bukti bacaan tidak lengkap",
  CAPTURE_OVERFLOW: "Bukti melewati kapasitas lintasan",
  QUARANTINED_EVIDENCE: "Ada bacaan tidak valid (dikarantina)",
  SUMMARY_COUNT_MISSING: "Jumlah ringkasan tidak dilaporkan",
  TIME_UNVERIFIED: "Waktu reader tidak tervalidasi",
  HISTORICAL_EVIDENCE: "Bukti historis (reader sempat offline)",
  HISTORICAL_CONFIG: "Memakai versi profil lama",
  DEVICE_CONFIG_CHANGED: "Profil/status perangkat berubah",
  DIRECTION_UNVERIFIED: "Arah lintasan tidak tervalidasi",
  COMPLETION_BASIS_UNSUPPORTED: "Basis penilaian gate tidak didukung",
  PASSAGE_TIMEOUT: "Lintasan terlalu lama (barang berhenti di gate?)",
  SENSOR_FAULT: "Photo-eye rusak — logika cadangan RF",
  RF_FALLBACK: "Lintasan dibuka logika cadangan RF",
  REVERSED_WITH_ROLLS: "Muatan berisi roll mundur di gate",
  ABORTED_WITH_ROLLS: "Muatan berisi roll batal di gate",
  PASSAGE_CANCELLED: "Mundur/batal tanpa roll dokumen",
  EMPTY_PASSAGE: "Lintasan kosong (orang/forklift kosong)",
  NO_DOCUMENT_ROLLS: "Tidak ada roll dokumen terbaca kuat",
  ROLLS_MISSING: "Ada roll dokumen yang belum lewat",
  ALL_ROLLS_PASSED: "Semua roll dokumen sudah lewat",
  // PREP-D2 — gate → transaksi gudang
  AREA_FROZEN: "Area sedang dibekukan pendaftaran awal — tidak ada transaksi",
  HANDHELD_MODE: "Gedung bermode handheld — gate hanya mencatat bukti",
  GATE_NOT_PAIRED: "Reader belum tertaut sebagai gate gedung — hanya bukti",
  QUANTITY_MODE: "Gedung mode kuantitas — gate tidak berlaku",
  SIMULATED_EVIDENCE: "Lintasan simulasi — hanya bukti (Mode simulasi RFID mati)",
  TXN_CHECK_FAILED: "Mode gedung belum bisa diperiksa — transaksi dicoba ulang",
  TXN_FAILED: "Transaksi gudang gagal — ulangi dari antrean",
  ARRIVAL_EXCEPTION: "Roll tidak bisa dicatat tiba (tujuan tidak lagi sah)",
  RULE_BLOCKED: "Aturan gudang tujuan menolak roll",
  NOT_IN_TRANSIT: "Roll bukan dalam perjalanan dokumen ini",
  NOT_RECORDED: "Roll cocok tetapi belum dicatat",
  RECORDED: "Sudah dicatat dari lintasan",
};

export const reasonText = (code) => REASON[code] || "Alasan lain — lihat bukti lintasan";

export const LEVEL_COLOR = { RED: "red", REVIEW: "orange", INFO: "gray" };

export const SOURCE_KINDS = [
  { value: "shipment", label: "Surat jalan penjualan" },
  { value: "wh_transfer", label: "Transfer fisik antar gudang" },
  { value: "putaway", label: "Putaway" },
  { value: "makloon_order", label: "Order Makloon (kirim ke mitra)" },
  { value: "repair_order", label: "Perbaikan" },
];

export const SCENARIOS = [
  { value: "full_load", label: "Muatan penuh lewat (harus hijau)" },
  { value: "partial_trip", label: "Dua trip satu dokumen — sesi bertahap (hijau, hijau)" },
  { value: "reversed", label: "Mundur sebelum roll terbaca (batal)" },
  { value: "reversed_with_rolls", label: "Mundur membawa roll dokumen (kuning)" },
  { value: "empty", label: "Orang/forklift kosong (batal tanpa alarm)" },
  { value: "foreign_roll", label: "Roll di luar dokumen (merah)" },
  { value: "quarantine_roll", label: "Roll karantina (merah)" },
  { value: "background_tag", label: "Tag rak latar (diabaikan, hijau)" },
  { value: "overflow", label: "Bukti meluap (kuning)" },
  { value: "sensor_fault", label: "Photo-eye rusak — cadangan RF (kuning)" },
];

export const HEALTH = {
  READER_STOPPED: "Reader berhenti membaca",
  TELEMETRY_STALE: "Laporan reader terlambat",
  QUEUE_RISING: "Antrean reader menumpuk",
};

export const PROTOCOL = { v2: "Protokol U300 V2", legacy: "Jalur lama" };

export const PARAM_LABEL = {
  pre_buffer_ms: "Bacaan sebelum sinar A (ms)",
  tail_ms: "Ekor setelah sinar B (ms)",
  min_block_ms: "Debounce sinar (ms)",
  entry_timeout_ms: "Batas masuk tanpa sinar B (ms)",
  max_passage_ms: "Batas lama lintasan (ms)",
  stable_interval_ms: "Cadangan RF: jeda tutup (ms)",
  rf_fallback_group_size: "Cadangan RF: ukuran rombongan",
  rssi_default_strong_dbm: "Ambang sinyal kuat (dBm)",
  background_retention_s: "Masa simpan daftar latar (detik)",
  auto_match: "Auto-cocok dokumen",
  manual_binding_ttl_s: "Binding manual berlaku (detik)",
};

export function errorText(e) {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  return d?.message || e?.message || "Gagal memuat data reader";
}

/** PREP-D2 — antrean periksa admin gudang (istilah Indonesia; kode server tidak ditampilkan). */
export const ROLL_STATE = {
  open: { label: "Perlu tindakan", color: "orange" },
  rescan: { label: "Menunggu pindai ulang handheld", color: "purple" },
  accepting: { label: "Sedang diproses", color: "info" },
  accepted: { label: "Diterima admin", color: "green" },
  rejected: { label: "Ditolak", color: "red" },
  ignored: { label: "Diabaikan", color: "gray" },
  done_elsewhere: { label: "Dilengkapi jalur lain", color: "green" },
  recorded: { label: "Sudah dicatat gate", color: "green" },
};

export const CASE_KIND = {
  passage: "Lintasan gate",
  rolls_missing: "Roll kurang saat dokumen ditutup",
};

export const CASE_STATUS = [
  { value: "open", label: "Terbuka" },
  { value: "resolved", label: "Selesai" },
  { value: "all", label: "Semua" },
];

export const CASE_VERDICT = [
  { value: "", label: "Semua hasil" },
  { value: "REVIEW", label: "Kuning — perlu diperiksa" },
  { value: "RED", label: "Merah — pelanggaran" },
];

export const DIRECTION = { in: "Masuk", out: "Keluar" };

export const TXN_MODE = {
  gate: "Gate utama — terima/tolak mencatat transaksi gudang",
  evidence: "Gedung handheld — gate hanya bukti; transaksi lewat handheld",
  unknown: "Mode gedung belum diketahui",
};

// PREP-H — status transaksi gudang lintasan (pekerja latar): lampu gate tidak menunggu transaksi.
export const TXN_STATE = {
  pending: { label: "Transaksi gudang menunggu", color: "gray" },
  processing: { label: "Transaksi gudang diproses", color: "blue" },
  done: { label: "Transaksi gudang selesai", color: "green" },
  error: { label: "Transaksi gudang gagal — diulang otomatis", color: "orange" },
  gave_up: { label: "Transaksi gudang gagal — perlu Ulangi transaksi", color: "red" },
};
export function txnStateInfo(p) {
  if (!p || !p.gate_txn_state) return null;
  const key = p.gate_txn_state === "error" && p.gate_txn_gave_up ? "gave_up" : p.gate_txn_state;
  return TXN_STATE[key] || null;
}

export const ACTION_LABEL = {
  accept: "Diterima", reject: "Ditolak", ignore: "Diabaikan", rescan: "Minta pindai ulang", dismiss: "Kasus ditutup",
  acknowledge_latch: "Kunci gate diakui", retry: "Transaksi diulang", done_elsewhere: "Dilengkapi jalur lain",
};

/** Kode → kalimat; daftar kode dirangkum tanpa menampilkan kode mentah. */
export const codesText = (codes) => (codes || []).map(reasonText).filter((t, i, a) => a.indexOf(t) === i).join(" · ");

export function fmtRssi(v) {
  return v === null || v === undefined ? "—" : `${Number(v).toFixed(1)} dBm`;
}
