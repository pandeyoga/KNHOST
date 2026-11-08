package id.kainnusantara.handheld.core;

/**
 * Jenis tugas handheld (keputusan pemilik: dibedakan jelas). Kode = kontrak server {@code handheld_core.KINDS}.
 * Lapisan tugas hanya mengenal kode & sifat ini; isi dokumen datang dari server (snapshot) — bila model tugas ERP
 * berubah, cukup kontrak snapshot yang disesuaikan.
 */
public enum TaskKind {
    PUTAWAY_IN("putaway_in", "Masuk · Putaway", "Tiba Putaway Order per trip", "↓", Flow.BULK, false, true),
    OUTBOUND_SO("outbound_so", "Keluar · SO", "Final Loading Check", "↑", Flow.BULK, true, false),
    OUTBOUND_SAMPLE("outbound_sample", "Keluar · Sampel", "Cek muat pesanan sampel", "↑", Flow.BULK, true, false),
    TRANSFER_IN("transfer_in", "Transfer masuk", "Terima roll transfer", "⇄", Flow.BULK, false, true),
    CUTTING("cutting", "Potong sampel", "Pindai roll induk lalu potong", "✂", Flow.IDENTIFY, false, false),
    CYCLE_COUNT("cycle_count", "Stock Opname RFID", "Sapu RFID per gudang", "≡", Flow.BULK, true, false),
    PRINT_VERIFY("print_verify", "Verifikasi cetak", "Cocokkan EPC label tercetak", "✓", Flow.BULK, true, false),
    REGISTRATION("registration", "Daftar Awal", "Daftar ulang roll + tulis tag", "+", Flow.REGISTER, false, false);

    public enum Flow { BULK, IDENTIFY, REGISTER }

    public final String code, label, hint, glyph;
    public final Flow flow;
    /** Dokumen butuh "Selesaikan" eksplisit (sesi verifikasi/cek muat/opname). */
    public final boolean needsComplete;
    /** Setiap kiriman langsung memindah status roll di ERP (tiba/terima) — tombolnya "Konfirmasi". */
    public final boolean mutatesOnSend;

    TaskKind(String code, String label, String hint, String glyph, Flow flow, boolean needsComplete, boolean mutatesOnSend) {
        this.code = code; this.label = label; this.hint = hint; this.glyph = glyph; this.flow = flow;
        this.needsComplete = needsComplete; this.mutatesOnSend = mutatesOnSend;
    }

    public static TaskKind of(String code) {
        for (TaskKind k : values()) if (k.code.equals(code)) return k;
        return null;
    }

    /** Simulasi radio hanya boleh untuk sesi bukti (server mencatatnya "simulated"); tidak untuk mutasi stok. */
    public boolean simulationAllowed() { return needsComplete; }

    public String sendLabel() {
        if (this == PUTAWAY_IN) return "KONFIRMASI TIBA";
        if (this == TRANSFER_IN) return "KONFIRMASI TERIMA";
        return "KIRIM HASIL PINDAI";
    }
}
