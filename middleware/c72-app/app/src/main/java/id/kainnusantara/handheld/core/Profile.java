package id.kainnusantara.handheld.core;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.LinkedHashSet;
import java.util.Set;

/**
 * Profil perangkat dari ERP ({@code GET /api/handheld/device/config → profile}) dengan nilai bawaan aman. Nilai = TITIK
 * AWAL uji meja (belum terbukti di C72); {@code commissioned=false} ditampilkan sebagai peringatan di layar.
 * Penimpaan lokal (mode diagnostik ber-PIN) disimpan terpisah dan selalu dibatasi rentang aman.
 */
public final class Profile {
    public final boolean commissioned;
    public final int powerDbm, writePowerDbm, locatePowerDbm, session, minPower, maxPower;
    public final Integer regionCode;
    public final Set<Integer> triggerKeys;
    public final boolean triggerHold;
    public final int maxReads, flushMs, maxLabels;
    public final boolean offlineAllowed;
    public final int snapshotMaxAgeHours;
    public final int writeVerifyReads, writeMaxAttempts, writeScanMs;
    public final double minRssiGapDb;
    public final boolean locateEnabled, useSdkLocate;
    public final long syncIntervalMs, backoffMaxMs;
    public final String profileId;
    public final JSONObject raw;

    public Profile(JSONObject p) {
        raw = p == null ? new JSONObject() : p;
        JSONObject rf = sub("rfid"), tr = sub("trigger"), bt = sub("batch"), off = sub("offline"), wr = sub("write"),
                lo = sub("locate"), sy = sub("sync");
        profileId = raw.optString("profile_id", "c72-bawaan");
        commissioned = raw.optBoolean("commissioned", false);
        minPower = clamp(rf.optInt("min_power_dbm", 5), 0, 33);
        maxPower = clamp(rf.optInt("max_power_dbm", 30), minPower, 33);
        powerDbm = clamp(rf.optInt("power_dbm", 20), minPower, maxPower);
        writePowerDbm = clamp(rf.optInt("write_power_dbm", 10), minPower, maxPower);
        locatePowerDbm = clamp(rf.optInt("locate_power_dbm", 26), minPower, maxPower);
        session = clamp(rf.optInt("session", 0), 0, 3);
        regionCode = rf.has("region_code") && !rf.isNull("region_code") ? rf.optInt("region_code") : null;
        Set<Integer> keys = new LinkedHashSet<>();
        JSONArray k = tr.optJSONArray("keycodes");
        for (int i = 0; k != null && i < k.length(); i++) keys.add(k.optInt(i));
        if (keys.isEmpty()) for (int c : new int[]{139, 280, 291, 293, 294, 311, 312, 313, 315}) keys.add(c);
        triggerKeys = keys;
        triggerHold = !"toggle".equals(tr.optString("mode", "hold"));
        maxReads = clamp(bt.optInt("max_reads", 2000), 1, 2000);
        flushMs = clamp(bt.optInt("flush_ms", 4000), 500, 60000);
        maxLabels = clamp(bt.optInt("max_labels", 500), 1, 500);
        offlineAllowed = off.optBoolean("allowed", true);
        snapshotMaxAgeHours = clamp(off.optInt("snapshot_max_age_hours", 12), 1, 168);
        writeVerifyReads = clamp(wr.optInt("verify_reads", 2), 1, 10);
        writeMaxAttempts = clamp(wr.optInt("max_attempts", 3), 1, 10);
        writeScanMs = clamp(wr.optInt("scan_ms", 1500), 300, 10000);
        minRssiGapDb = Math.max(0, wr.optDouble("min_rssi_gap_db", 6.0));
        locateEnabled = lo.optBoolean("enabled", true);
        useSdkLocate = lo.optBoolean("use_sdk_locate", true);
        syncIntervalMs = Math.max(3000, sy.optLong("interval_ms", 15000));
        backoffMaxMs = Math.max(5000, sy.optLong("backoff_max_ms", 300000));
    }

    private JSONObject sub(String k) {
        JSONObject o = raw.optJSONObject(k);
        return o == null ? new JSONObject() : o;
    }

    public static int clamp(int v, int lo, int hi) { return Math.max(lo, Math.min(hi, v)); }

    public static Profile defaults() { return new Profile(new JSONObject()); }

    public boolean isTrigger(int keyCode) { return triggerKeys.contains(keyCode); }
}
