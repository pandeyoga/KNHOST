package id.kainnusantara.handheld.core;

import org.json.JSONObject;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Locale;
import java.util.Random;

/**
 * Radio & pemindai TIRUAN (tes host, emulator, demo UAT tanpa perangkat). Bukti dari mode ini dikirim berlabel
 * {@code simulated} dan server tidak menjadikannya hasil operasional; mutasi stok (tiba/terima/daftar) ditolak.
 * RSSI dibentuk dengan koma desimal (meniru SDK di locale id-ID) supaya jalur parse ikut teruji.
 */
public final class SimulatedHardware implements C72HardwareAdapter {
    public static final class SimTag {
        public String epc;
        public double rssi;
        public boolean present = true;
        public final String tid;
        public SimTag(String epc, double rssi, String tid) { this.epc = epc; this.rssi = rssi; this.tid = tid; }
    }

    public final List<SimTag> field = new ArrayList<>();
    public final Deque<String> barcodes = new ArrayDeque<>();
    public int failWrites, silentWrites, power = 20, session = 0;
    public boolean initOk = true, threaded;
    private volatile boolean inventorying, ready;
    private volatile TagListener listener;
    private Thread worker;
    private BarcodeListener barcodeListener;
    private final Random random = new Random(7);
    private final JSONObject setup = new JSONObject();

    public SimulatedHardware(boolean threaded) { this.threaded = threaded; }

    public SimTag add(String epc, double rssi) { SimTag t = new SimTag(epc, rssi, "SIMTID" + field.size()); field.add(t); return t; }

    @Override public String name() { return "Simulasi (tanpa radio)"; }

    @Override
    public void initialize(Profile p) throws HardwareException {
        if (!initOk) throw new HardwareException("SDK simulasi: init gagal (skenario uji)");
        power = p.powerDbm; session = p.session; ready = true;
        Json.put(setup, "power_dbm", Json.obj("set", p.powerDbm, "readback", power));
        Json.put(setup, "session", Json.obj("set", p.session, "readback", session));
    }

    @Override public Capabilities capabilities() {
        Capabilities c = new Capabilities();
        c.rfid = c.barcode = c.write = c.locate = c.battery = c.simulated = true;
        c.model = "SIMULASI"; c.sdkVersion = "sim"; c.hardwareVersion = "sim";
        return c;
    }

    @Override public JSONObject setupReport() { return setup; }
    @Override public boolean ready() { return ready; }

    static String rssiText(double v) { return String.format(new Locale("in", "ID"), "%.2f", v); }

    /** Satu putaran baca: setiap tag yang ada di medan terbaca sekali (dengan derau). */
    public void emitOnce() {
        TagListener l = listener;
        if (l == null) return;
        long now = System.currentTimeMillis();
        for (SimTag t : new ArrayList<>(field)) {
            if (!t.present) continue;
            double noise = (random.nextDouble() - 0.5) * 2;
            double att = (20 - power) * 0.8;   // daya lebih kecil → sinyal lebih lemah
            l.onTag(t.epc, t.tid, rssiText(t.rssi - att + noise), System.nanoTime() / 1_000_000L, now);
        }
    }

    @Override
    public synchronized boolean beginInventory(TagListener l) {
        if (inventorying || !ready) return false;
        listener = l;
        inventorying = true;
        emitOnce();
        if (threaded) {
            worker = new Thread(() -> {
                while (inventorying) {
                    try { Thread.sleep(80); } catch (InterruptedException e) { return; }
                    if (inventorying) emitOnce();
                }
            }, "sim-inventory");
            worker.setDaemon(true);
            worker.start();
        }
        return true;
    }

    @Override
    public synchronized boolean stopInventory() {
        inventorying = false;
        if (worker != null) { worker.interrupt(); worker = null; }
        listener = null;
        return true;
    }

    @Override public boolean inventorying() { return inventorying; }
    @Override public int getPower() { return power; }
    @Override public boolean setPower(int dbm) { if (dbm < 5 || dbm > 30) return false; power = dbm; return true; }
    @Override public int getSession() { return session; }
    @Override public boolean setSession(int s) { if (s < 0 || s > 3) return false; session = s; return true; }

    @Override
    public WriteOutcome writeEpc(String currentEpc, String newEpc, String pwd) {
        if (failWrites > 0) { failWrites--; return new WriteOutcome(false, 9, "simulasi: tulis gagal"); }
        for (SimTag t : field) {
            if (t.present && t.epc.equals(currentEpc)) {
                if (silentWrites > 0) { silentWrites--; return new WriteOutcome(true, 0, "simulasi: SDK lapor sukses tapi chip tidak berubah"); }
                t.epc = newEpc;
                return new WriteOutcome(true, 0, "");
            }
        }
        return new WriteOutcome(false, 1, "simulasi: tag sasaran tidak ditemukan");
    }

    @Override
    public String[] readSingle() {
        SimTag best = null;
        for (SimTag t : field) if (t.present && (best == null || t.rssi > best.rssi)) best = t;
        return best == null ? null : new String[]{best.epc, best.tid, rssiText(best.rssi)};
    }

    @Override
    public boolean startLocate(String epc, LocateListener l) {
        for (SimTag t : field) {
            if (t.present && t.epc.equals(epc)) {
                l.onLocate((int) Math.max(0, Math.min(100, (t.rssi + 80) * 2)), true);
                return true;
            }
        }
        l.onLocate(0, false);
        return true;
    }

    @Override public boolean stopLocate() { return true; }
    @Override public boolean openBarcode(BarcodeListener l) { barcodeListener = l; return true; }

    @Override
    public boolean startBarcode() {
        BarcodeListener l = barcodeListener;
        if (l == null) return false;
        String next = barcodes.poll();
        if (next == null) l.onBarcodeError("simulasi: tidak ada barcode di depan pemindai");
        else l.onBarcode(next, "QR");
        return true;
    }

    @Override public void stopBarcode() { }
    @Override public void closeBarcode() { barcodeListener = null; }
    @Override public JSONObject battery() { return Json.obj("level_pct", 87, "health", "simulasi", "temperature_c", 31.5); }
    @Override public void release() { stopInventory(); ready = false; }
}
