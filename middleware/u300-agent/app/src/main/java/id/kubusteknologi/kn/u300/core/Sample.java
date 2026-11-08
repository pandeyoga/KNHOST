package id.kubusteknologi.kn.u300.core;

/** Satu bacaan yang sudah di-parse (thread kontrol). Waktu utama = monotonik (ms sejak boot). */
public final class Sample {
    public final String rawEpc;
    /** EPC kanonik 24 hex atau null (EPC rusak tetap dibawa sebagai bukti, tidak dibuang). */
    public final String epc;
    /** Port kanonik "1".."16"; bila format tidak dikenal = "raw:" + nilai mentah (server mengkarantina). */
    public final String antenna;
    public final boolean antennaKnown;
    public final Double rssi;
    public final String rawRssi;
    public final long tMono;
    /** Jam server-tersinkron (perkiraan) saat bacaan; lihat {@link #synced}. */
    public final long tWall;
    public final boolean synced;

    public Sample(String rawEpc, String epc, String antenna, boolean antennaKnown, Double rssi, String rawRssi,
                  long tMono, long tWall, boolean synced) {
        this.rawEpc = rawEpc == null ? "" : rawEpc;
        this.epc = epc;
        this.antenna = antenna;
        this.antennaKnown = antennaKnown;
        this.rssi = rssi;
        this.rawRssi = rawRssi;
        this.tMono = tMono;
        this.tWall = tWall;
        this.synced = synced;
        this.key = (epc != null ? epc : Parse.rawKey(this.rawEpc)) + ":" + antenna;
    }

    private final String key;

    /** Kunci ringkasan lintasan × EPC × antena. */
    public String key() { return key; }

    /** Kunci EPC (kanonik atau hash mentah) tanpa antena. */
    public String epcKey() { return epc != null ? epc : Parse.rawKey(rawEpc); }
}
