package id.kubusteknologi.kn.u300.core;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.Collection;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Setelan radio dari profil commissioning (AUD-MW-04): region, daya per port, Gen2 (session/target/Q),
 * TagFocus, FastID, RF link, filter. Mode {@code apply=true}: set lalu baca ulang; {@code apply=false}: hanya
 * verifikasi (perilaku 0.4). Satu butir gagal → {@link Failure} → agent TIDAK mulai inventory (fail-closed).
 * Arti nilai baca-balik TagFocus/FastID (int) belum dibuktikan di unit → uji meja K-RFID-03 butir 4.
 */
public final class RadioSetup {
    private RadioSetup() {}

    /** Nama kunci Gen2 profil → field {@code Gen2Entity} SDK (dipetakan di Reader). */
    public static final String[] GEN2_KEYS = {"query_session", "query_target", "q", "start_q", "min_q", "max_q",
            "query_sel", "query_dr", "query_m", "query_trext", "link_frequency", "select_target", "select_action",
            "select_truncate"};

    public interface Port {
        int getRegion() throws Exception;
        boolean setRegion(int code) throws Exception;
        int getPower(String antenna) throws Exception;
        boolean setPower(String antenna, int dbm) throws Exception;
        Map<String, Integer> getGen2() throws Exception;
        boolean setGen2(Map<String, Integer> all) throws Exception;
        int getTagFocus() throws Exception;
        boolean setTagFocus(boolean on) throws Exception;
        int getFastId() throws Exception;
        boolean setFastId(boolean on) throws Exception;
        int getRfLink() throws Exception;
        boolean setRfLink(int value) throws Exception;
        boolean setFilter(int bank, int ptr, int len, String data) throws Exception;
    }

    public static final class Failure extends Exception {
        public final JSONArray report;
        Failure(String message, JSONArray report) { super(message); this.report = report; }
    }

    private static JSONObject step(JSONArray report, String item, Object wanted, Object before, Object after, boolean ok, String note) {
        try {
            JSONObject o = new JSONObject().put("item", item).put("wanted", wanted == null ? JSONObject.NULL : wanted)
                    .put("before", before == null ? JSONObject.NULL : before).put("after", after == null ? JSONObject.NULL : after)
                    .put("ok", ok);
            if (note != null) o.put("note", note);
            report.put(o);
            return o;
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
    }

    private static void require(boolean ok, String item, JSONArray report) throws Failure {
        if (!ok) throw new Failure("Setelan radio gagal: " + item, report);
    }

    /** @return laporan per butir (disimpan di audit & telemetry). */
    public static JSONArray apply(Port port, JSONObject radio, Collection<String> antennas) throws Failure {
        JSONArray report = new JSONArray();
        boolean apply = radio.optBoolean("apply", false);
        try {
            if (radio.has("region_code") && !radio.isNull("region_code")) {
                int want = radio.getInt("region_code"), before = port.getRegion();
                boolean set = !apply || before == want || port.setRegion(want);
                int after = apply && before != want ? port.getRegion() : before;
                boolean ok = set && after == want;
                step(report, "region", want, before, after, ok, apply ? null : "verifikasi saja");
                require(ok, "region " + want + " (terbaca " + after + ")", report);
            }
            JSONObject power = radio.optJSONObject("antenna_power_dbm");
            if (power != null) {
                for (String ant : antennas) {
                    if (!power.has(ant)) { step(report, "power:" + ant, null, null, null, false, "daya port tidak ada di profil"); require(false, "daya port " + ant, report); }
                    int want = power.getInt(ant), before = port.getPower(ant);
                    boolean set = !apply || before == want || port.setPower(ant, want);
                    int after = apply && before != want ? port.getPower(ant) : before;
                    boolean ok = set && after == want;
                    step(report, "power:" + ant, want, before, after, ok, null);
                    require(ok, "daya port " + ant + " " + want + " dBm (terbaca " + after + ")", report);
                }
            }
            JSONObject gen2 = radio.optJSONObject("gen2");
            if (gen2 != null && gen2.length() > 0) {
                Map<String, Integer> before = port.getGen2();
                if (before == null) { step(report, "gen2", gen2, null, null, false, "getGen2 null"); require(false, "baca Gen2", report); }
                Map<String, Integer> wanted = new LinkedHashMap<>(before);
                boolean differs = false;
                for (Iterator<String> it = gen2.keys(); it.hasNext(); ) {
                    String k = it.next();
                    if (!before.containsKey(k)) { step(report, "gen2:" + k, gen2.opt(k), null, null, false, "kunci Gen2 tidak dikenal"); require(false, "Gen2 " + k, report); }
                    int v = gen2.getInt(k);
                    differs |= before.get(k) != v;
                    wanted.put(k, v);
                }
                boolean set = !apply || !differs || port.setGen2(wanted);
                Map<String, Integer> after = apply && differs ? port.getGen2() : before;
                boolean ok = set && after != null;
                for (Iterator<String> it = gen2.keys(); ok && it.hasNext(); ) {
                    String k = it.next();
                    ok = after.get(k) != null && after.get(k) == gen2.getInt(k);
                }
                step(report, "gen2", gen2, new JSONObject(before), after == null ? null : new JSONObject(after), ok, null);
                require(ok, "Gen2 " + gen2, report);
            }
            if (radio.has("tag_focus") && !radio.isNull("tag_focus")) flag(report, "tag_focus", radio.getBoolean("tag_focus"), apply,
                    port::getTagFocus, port::setTagFocus);
            if (radio.has("fast_id") && !radio.isNull("fast_id")) flag(report, "fast_id", radio.getBoolean("fast_id"), apply,
                    port::getFastId, port::setFastId);
            if (radio.has("rf_link") && !radio.isNull("rf_link")) {
                int want = radio.getInt("rf_link"), before = port.getRfLink();
                boolean set = !apply || before == want || port.setRfLink(want);
                int after = apply && before != want ? port.getRfLink() : before;
                boolean ok = set && after == want;
                step(report, "rf_link", want, before, after, ok, null);
                require(ok, "RF link " + want, report);
            }
            JSONObject filter = radio.optJSONObject("filter");
            if (filter != null) {
                if (!apply) { step(report, "filter", filter, null, null, false, "filter hanya bisa diterapkan (apply=true); AAR tidak punya getFilter"); require(false, "filter tanpa apply", report); }
                boolean ok = port.setFilter(filter.getInt("bank"), filter.getInt("ptr"), filter.getInt("len"), filter.getString("data"));
                step(report, "filter", filter, null, null, ok, "tanpa baca-balik (AAR tidak punya getFilter)");
                require(ok, "filter", report);
            }
        } catch (Failure f) {
            throw f;
        } catch (Exception e) {
            step(report, "exception", null, null, null, false, e.getClass().getSimpleName() + ": " + e.getMessage());
            throw new Failure("Setelan radio gagal: " + e.getMessage(), report);
        }
        return report;
    }

    interface IntGetter { int get() throws Exception; }
    interface BoolSetter { boolean set(boolean v) throws Exception; }

    private static void flag(JSONArray report, String item, boolean want, boolean apply, IntGetter get, BoolSetter set) throws Exception {
        int before = get.get();
        boolean beforeOn = before == 1;
        boolean valid = before == 0 || before == 1;
        boolean wrote = !apply || (valid && beforeOn == want) || set.set(want);
        int after = apply && !(valid && beforeOn == want) ? get.get() : before;
        boolean ok = wrote && (after == 0 || after == 1) && (after == 1) == want;
        step(report, item, want, before, after, ok, "baca-balik int: 1 = aktif, 0 = mati (konfirmasi uji meja butir 4)");
        require(ok, item + " " + want + " (terbaca " + after + ")", report);
    }
}
