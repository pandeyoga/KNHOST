package id.kainnusantara.handheld.core;

/**
 * Satu-satunya pemilik radio (spesifikasi Kubus 02 §2.2/§2.5): mulai/berhenti diserialisasi; pemicu ganda TIDAK membuka
 * sesi radio kedua; tulis tag & cari tag memegang radio secara eksklusif. Tombol pemicu fisik: mode "tahan" (tekan =
 * mulai, lepas = berhenti) atau "toggle"; auto-repeat tombol diabaikan. Callback SDK hanya masuk ke
 * {@link ReadAggregator} (tanpa I/O); UI menarik ringkasan dengan laju terbatas.
 */
public final class ScanController {
    public enum Mode { IDLE, SCANNING, WRITING, LOCATING, DIAGNOSTIC }

    public interface Listener { void onState(Mode mode, String message); void onNewTag(String epc); }

    private final C72HardwareAdapter hw;
    private final ReadAggregator agg;
    private volatile Profile profile;
    private volatile Listener listener;
    private Mode mode = Mode.IDLE;
    private final Object times = new Object();   // kunci terpisah: callback SDK tidak pernah menunggu kunci kontrol
    private long firstWall, lastWall;
    private int sessions;

    private final C72HardwareAdapter.TagListener sink;

    public ScanController(C72HardwareAdapter hw, ReadAggregator agg, Profile profile) {
        this.hw = hw; this.agg = agg; this.profile = profile;
        this.sink = this::onTag;
    }

    public void profile(Profile p) { profile = p; }
    public void listener(Listener l) { listener = l; }
    public ReadAggregator aggregator() { return agg; }
    public synchronized Mode mode() { return mode; }
    public synchronized int sessionsStarted() { return sessions; }
    public long firstWall() { synchronized (times) { return firstWall; } }
    public long lastWall() { synchronized (times) { return lastWall; } }

    /** Callback SDK (utas vendor): hanya menyalin ke agregator — tanpa I/O, tanpa kunci kontrol (cegah deadlock stop). */
    private void onTag(String epc, String tid, String rssi, long mono, long wall) {
        boolean fresh = agg.offer(epc, tid, rssi, mono, wall);
        synchronized (times) {
            if (firstWall == 0) firstWall = wall;
            lastWall = wall;
        }
        Listener l = listener;
        if (fresh && l != null) l.onNewTag(Epc.normalizeRead(epc));
    }

    /** @return false bila radio sedang dipakai (tulis/cari) atau belum siap — tidak ada sesi kedua. */
    public synchronized boolean start() {
        if (mode == Mode.SCANNING) return true;
        if (mode != Mode.IDLE) { notify("Radio sedang dipakai (" + mode + ") — tunggu selesai."); return false; }
        if (!hw.ready()) { notify("Radio belum siap — buka Diagnostik untuk init SDK."); return false; }
        if (agg.full()) { notify("Batas " + profile.maxReads + " tag per pindai tercapai — kirim dulu."); return false; }
        if (!hw.beginInventory(sink)) { notify("SDK menolak mulai inventori."); return false; }
        mode = Mode.SCANNING;
        sessions++;
        notifyState("Memindai…");
        return true;
    }

    public synchronized boolean stop() {
        if (mode != Mode.SCANNING) return false;
        boolean ok = hw.stopInventory();
        mode = Mode.IDLE;
        notifyState(ok ? "Berhenti." : "Berhenti (SDK tidak mengonfirmasi stop).");
        return ok;
    }

    public synchronized boolean toggle() { return mode == Mode.SCANNING ? stop() : start(); }

    /** @return true bila tombol adalah pemicu (event dikonsumsi). */
    public boolean onKeyDown(int keyCode, int repeatCount) {
        Profile p = profile;
        if (!p.isTrigger(keyCode)) return false;
        if (repeatCount > 0) return true;
        if (p.triggerHold) start(); else toggle();
        return true;
    }

    public boolean onKeyUp(int keyCode) {
        Profile p = profile;
        if (!p.isTrigger(keyCode)) return false;
        if (p.triggerHold) stop();
        return true;
    }

    /** Pegang radio eksklusif untuk tulis/cari/diagnostik. Pindai berjalan dihentikan dulu. */
    public synchronized boolean acquire(Mode m) {
        if (mode == Mode.SCANNING) stop();
        if (mode != Mode.IDLE) return false;
        mode = m;
        notifyState(m.name());
        return true;
    }

    public synchronized void release(Mode m) {
        if (mode == m) { mode = Mode.IDLE; notifyState("Siap."); }
    }

    /** Jendela pindai baru (setelah kirim): bacaan & cap waktu dikosongkan. */
    public synchronized void resetWindow() {
        if (mode == Mode.SCANNING) stop();
        agg.clear();
        synchronized (times) { firstWall = lastWall = 0; }
    }

    private void notifyState(String msg) { Listener l = listener; if (l != null) l.onState(mode, msg); }
    private void notify(String msg) { Listener l = listener; if (l != null) l.onState(mode, msg); }
}
