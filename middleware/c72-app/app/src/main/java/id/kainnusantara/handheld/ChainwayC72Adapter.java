package id.kainnusantara.handheld;

import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.Build;
import android.os.SystemClock;

import com.rscja.barcode.BarcodeDecoder;
import com.rscja.barcode.BarcodeFactory;
import com.rscja.deviceapi.RFIDWithUHFUART;
import com.rscja.deviceapi.entity.BarcodeEntity;
import com.rscja.deviceapi.entity.Gen2Entity;
import com.rscja.deviceapi.entity.UHFTAGInfo;
import com.rscja.deviceapi.interfaces.IUHF;
import com.rscja.utility.BatteryUtils;

import org.json.JSONObject;

import id.kainnusantara.handheld.core.C72HardwareAdapter;
import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.Profile;

/**
 * Adaptor SDK Chainway (AAR DeviceAPI_ver20251103) untuk C72. Signature diperiksa dengan {@code javap} terhadap
 * classes.jar AAR; PERILAKU di unit C72 = BELUM TERBUKTI sampai uji meja (lihat docs/03_COMMISSIONING_UJI_MEJA.md):
 * <pre>
 * initialize      → RFIDWithUHFUART.getInstance() · init(Context) · setPower/getPower · getGen2/setGen2(querySession)
 * beginInventory  → setInventoryCallback(IUHFInventoryCallback) · startInventoryTag()
 * stopInventory   → stopInventory()
 * writeEpc        → writeDataToEpc(pwd, IUHF.Bank_EPC, 32, 96, epcLama, epcBaru)  [filter bit 32 = sesudah CRC+PC]
 * readSingle      → inventorySingleTag() → UHFTAGInfo.getEPC/getTid/getRssi
 * startLocate     → startLocation(ctx, epc, IUHF.Bank_EPC, 32, IUHFLocationCallback) · stopLocation()
 * barcode         → BarcodeFactory.getInstance().getBarcodeDecoder() · open · setDecodeCallback · startScan/stopScan · close
 * battery         → BatteryManager (sticky ACTION_BATTERY_CHANGED) + com.rscja.utility.BatteryUtils (bila didukung)
 * release         → free()
 * </pre>
 * Callback inventori hanya menyalin string + cap waktu (tanpa I/O). Semua metode dipanggil dari utas radio App.
 */
final class ChainwayC72Adapter implements C72HardwareAdapter {
    private final Context context;
    private RFIDWithUHFUART uhf;
    private BarcodeDecoder barcode;
    private volatile boolean ready, inventorying;
    private final JSONObject setup = new JSONObject();
    private final Capabilities caps = new Capabilities();

    ChainwayC72Adapter(Context c) { context = c.getApplicationContext(); }

    @Override public String name() { return "Chainway C72 (SDK " + caps.sdkVersion + ")"; }

    @Override
    public synchronized void initialize(Profile p) throws HardwareException {
        try {
            uhf = RFIDWithUHFUART.getInstance();
        } catch (Throwable e) {
            throw new HardwareException("SDK UHF tidak tersedia di perangkat ini (" + e.getClass().getSimpleName() + ")", e);
        }
        if (!uhf.init(context)) throw new HardwareException("init() modul UHF gagal (errCode " + safeErr() + ") — modul dipakai aplikasi lain?");
        ready = true;
        caps.rfid = true; caps.write = true; caps.locate = true; caps.battery = true;
        caps.model = Build.MANUFACTURER + " " + Build.MODEL;
        caps.firmware = Build.DISPLAY;
        try { caps.sdkVersion = String.valueOf(uhf.getVersion()); } catch (Throwable ignored) { caps.sdkVersion = "?"; }
        try { caps.hardwareVersion = String.valueOf(uhf.getHardwareVersion()); } catch (Throwable ignored) { caps.hardwareVersion = "?"; }
        boolean pw = uhf.setPower(p.powerDbm);
        Json.put(setup, "power_dbm", Json.obj("set", p.powerDbm, "set_ok", pw, "readback", uhf.getPower()));
        boolean ss = setSession(p.session);
        Json.put(setup, "session", Json.obj("set", p.session, "set_ok", ss, "readback", getSession()));
        try { Json.put(setup, "frequency_mode_readback", uhf.getFrequencyMode()); } catch (Throwable ignored) { }
        if (p.regionCode != null) {   // hanya bila profil commissioning menetapkan region
            boolean rg = uhf.setFrequencyMode(p.regionCode);
            Json.put(setup, "region", Json.obj("set", p.regionCode, "set_ok", rg, "readback", uhf.getFrequencyMode()));
        }
        try {
            barcode = BarcodeFactory.getInstance().getBarcodeDecoder();
            caps.barcode = barcode != null;
        } catch (Throwable e) {
            caps.barcode = false;
            Json.put(setup, "barcode_error", e.getClass().getSimpleName());
        }
    }

    private int safeErr() { try { return uhf == null ? -1 : uhf.getErrCode(); } catch (Throwable e) { return -1; } }

    @Override public Capabilities capabilities() { return caps; }
    @Override public JSONObject setupReport() { return setup; }
    @Override public boolean ready() { return ready; }

    @Override
    public synchronized boolean beginInventory(TagListener l) {
        if (!ready || inventorying) return false;
        uhf.setInventoryCallback(t -> {
            if (t != null) l.onTag(t.getEPC(), t.getTid(), t.getRssi(), SystemClock.elapsedRealtime(), System.currentTimeMillis());
        });
        inventorying = uhf.startInventoryTag();
        return inventorying;
    }

    @Override
    public synchronized boolean stopInventory() {
        if (!ready) return false;
        boolean ok = uhf.stopInventory();
        inventorying = false;
        return ok;
    }

    @Override public boolean inventorying() { return inventorying; }
    @Override public synchronized int getPower() { return ready ? uhf.getPower() : -1; }
    @Override public synchronized boolean setPower(int dbm) { return ready && uhf.setPower(dbm); }

    @Override
    public synchronized int getSession() {
        if (!ready) return -1;
        Gen2Entity g = uhf.getGen2();
        return g == null ? -1 : g.getQuerySession();
    }

    @Override
    public synchronized boolean setSession(int session) {
        if (!ready) return false;
        Gen2Entity g = uhf.getGen2();
        if (g == null) return false;
        g.setQuerySession(session);
        return uhf.setGen2(g);
    }

    @Override
    public synchronized WriteOutcome writeEpc(String currentEpc, String newEpc, String pwd) {
        if (!ready) return new WriteOutcome(false, -1, "radio belum siap");
        boolean ok = uhf.writeDataToEpc(pwd, IUHF.Bank_EPC, 32, currentEpc.length() * 4, currentEpc, newEpc);
        return new WriteOutcome(ok, ok ? 0 : safeErr(), ok ? "" : "writeDataToEpc=false");
    }

    @Override
    public synchronized String[] readSingle() {
        if (!ready) return null;
        UHFTAGInfo t = uhf.inventorySingleTag();
        return t == null || t.getEPC() == null ? null : new String[]{t.getEPC(), t.getTid(), t.getRssi()};
    }

    @Override
    public synchronized boolean startLocate(String epc, LocateListener l) {
        if (!ready) return false;
        return uhf.startLocation(context, epc, IUHF.Bank_EPC, 32, l::onLocate);
    }

    @Override public synchronized boolean stopLocate() { return ready && uhf.stopLocation(); }

    @Override
    public synchronized boolean openBarcode(BarcodeListener l) {
        if (barcode == null) return false;
        if (!barcode.isOpen() && !barcode.open(context)) return false;
        barcode.setDecodeCallback((BarcodeEntity e) -> {
            if (e == null) return;
            if (e.getResultCode() == BarcodeDecoder.DECODE_SUCCESS) l.onBarcode(e.getBarcodeData(), e.getBarcodeName());
            else l.onBarcodeError("kode hasil " + e.getResultCode());
        });
        return true;
    }

    @Override public synchronized boolean startBarcode() { return barcode != null && barcode.startScan(); }
    @Override public synchronized void stopBarcode() { if (barcode != null) barcode.stopScan(); }
    @Override public synchronized void closeBarcode() { if (barcode != null && barcode.isOpen()) barcode.close(); }

    @Override
    public JSONObject battery() {
        JSONObject o = new JSONObject();
        Intent b = context.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        if (b != null) {
            int level = b.getIntExtra(BatteryManager.EXTRA_LEVEL, -1), scale = b.getIntExtra(BatteryManager.EXTRA_SCALE, 100);
            Json.put(o, "level_pct", level < 0 ? null : Math.round(level * 100f / Math.max(1, scale)));
            Json.put(o, "temperature_c", b.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) / 10.0);
            Json.put(o, "voltage_mv", b.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0));
            Json.put(o, "health_code", b.getIntExtra(BatteryManager.EXTRA_HEALTH, 0));
            Json.put(o, "plugged", b.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0));
        }
        try {   // baterai pintar Chainway (belum terbukti tersedia di C72)
            Json.put(o, "smart_battery", BatteryUtils.getSmartBattery());
            Json.put(o, "cycle_count", BatteryUtils.getCycleCount());
            Json.put(o, "health_pct", BatteryUtils.getBatteryHealth());
            Json.put(o, "rated_capacity_mah", BatteryUtils.getRatedCapacity());
        } catch (Throwable e) {
            Json.put(o, "smart_battery_error", e.getClass().getSimpleName());
        }
        return o;
    }

    @Override
    public synchronized void release() {
        try { if (inventorying) uhf.stopInventory(); } catch (Throwable ignored) { }
        try { closeBarcode(); } catch (Throwable ignored) { }
        try { if (uhf != null) uhf.free(); } catch (Throwable ignored) { }
        ready = false;
        inventorying = false;
    }
}
