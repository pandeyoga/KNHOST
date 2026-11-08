package id.kainnusantara.handheld.core;

import org.json.JSONObject;

/**
 * Batas antara logika aplikasi dan SDK vendor (spesifikasi Kubus 02 §2.2: initialize/beginInventory/stopInventory/
 * readCapabilities/release + barcode/search bila terbukti). Nama metode BUKAN metode SDK resmi — pemetaannya ke
 * {@code com.rscja.deviceapi.RFIDWithUHFUART} / {@code com.rscja.barcode.BarcodeDecoder} ada di
 * {@code ChainwayC72Adapter} dan dokumen commissioning (status "belum terbukti" sampai uji meja).
 * Implementasi wajib: callback SDK hanya menyalin nilai (tanpa I/O); satu pemilik radio (diserialisasi pemanggil).
 */
public interface C72HardwareAdapter {
    interface TagListener { void onTag(String epc, String tid, String rssiRaw, long monoMs, long wallMs); }
    interface BarcodeListener { void onBarcode(String data, String symbology); void onBarcodeError(String reason); }
    interface LocateListener { void onLocate(int value, boolean valid); }

    final class HardwareException extends Exception {
        public HardwareException(String m) { super(m); }
        public HardwareException(String m, Throwable t) { super(m, t); }
    }

    final class Capabilities {
        public boolean rfid, barcode, write, locate, battery, simulated;
        public String model = "", sdkVersion = "", hardwareVersion = "", firmware = "";
        public int minPowerDbm = 5, maxPowerDbm = 30;
        public JSONObject toJson() {
            return Json.obj("rfid", rfid, "barcode", barcode, "write", write, "locate", locate, "battery", battery, "simulated", simulated,
                    "model", model, "sdk_version", sdkVersion, "hardware_version", hardwareVersion, "firmware", firmware,
                    "min_power_dbm", minPowerDbm, "max_power_dbm", maxPowerDbm);
        }
    }

    final class WriteOutcome {
        public final boolean ok;
        public final int errCode;
        public final String message;
        public WriteOutcome(boolean ok, int errCode, String message) { this.ok = ok; this.errCode = errCode; this.message = message == null ? "" : message; }
    }

    String name();
    /** Init SDK + terapkan daya & session profil (set lalu BACA ULANG; laporan di {@link #setupReport()}). */
    void initialize(Profile profile) throws HardwareException;
    Capabilities capabilities();
    JSONObject setupReport();
    boolean ready();

    boolean beginInventory(TagListener listener);
    boolean stopInventory();
    boolean inventorying();

    int getPower();
    boolean setPower(int dbm);
    int getSession();
    boolean setSession(int session);

    /** Tulis EPC baru ke tag ber-EPC {@code currentEpc} (filter bank EPC). Akses sandi 8 hex ("00000000" bawaan). */
    WriteOutcome writeEpc(String currentEpc, String newEpc, String accessPassword);
    /** Satu kali baca tag terdekat (verifikasi). null bila tidak ada. */
    String[] readSingle();

    boolean startLocate(String epc, LocateListener listener);
    boolean stopLocate();

    boolean openBarcode(BarcodeListener listener);
    boolean startBarcode();
    void stopBarcode();
    void closeBarcode();

    JSONObject battery();
    void release();
}
