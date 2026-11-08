import id.kubusteknologi.kn.u300.core.BeamDebouncer;
import id.kubusteknologi.kn.u300.core.BeamDebouncer.Edge;
import id.kubusteknologi.kn.u300.core.PassageMachine;
import id.kubusteknologi.kn.u300.core.PassageMachine.Closing;
import id.kubusteknologi.kn.u300.core.PassageMachine.Mode;
import id.kubusteknologi.kn.u300.core.Sample;

import java.util.ArrayList;
import java.util.List;

/** State machine lintasan gate (audit §8.3) — semua skenario tanpa perangkat. Waktu = ms monotonik. */
public class PassageMachineTest {
    static int checks;
    static void check(boolean v, String label) { checks++; if (!v) throw new AssertionError("check " + checks + ": " + label); }

    static final class Rec implements PassageMachine.Listener {
        final List<PassageMachine.Opening> opened = new ArrayList<>();
        final List<Closing> closed = new ArrayList<>();
        final List<String> health = new ArrayList<>();
        public void opened(PassageMachine.Opening o) { opened.add(o); }
        public void closed(Closing c) { closed.add(c); }
        public void health(String h, String d, long t) { health.add(h + ":" + d); }
        Closing last() { return closed.get(closed.size() - 1); }
    }

    static Edge a(boolean blocked, long t) { return new Edge("A", blocked, t); }
    static Edge b(boolean blocked, long t) { return new Edge("B", blocked, t); }
    static Sample tag(String epc, long t, double rssi) {
        return new Sample(epc, epc, "1", true, rssi, String.valueOf(rssi), t, t + 1_800_000_000_000L, true);
    }
    static String epc(int i) { return String.format("E2000000000000000000%04X", i); }

    static PassageMachine m(Mode mode, Rec r) { return new PassageMachine(mode, new PassageMachine.Params(), r); }

    public static void main(String[] args) {
        long T = 1_000_000;
        // 1. Lewat normal: A↓ B↓ A↑ B↑ + ekor 1500 ms
        Rec r = new Rec(); PassageMachine pm = m(Mode.ONE_WAY_BEAM, r);
        pm.edge(a(true, T)); check(r.opened.size() == 1 && "BEAM_A".equals(r.opened.get(0).openReason), "lewat: dibuka BEAM_A");
        check(r.opened.get(0).windowStartMono == T - 3000, "lewat: window_start = A↓ − pre_buffer");
        pm.edge(b(true, T + 1100)); pm.edge(a(false, T + 1800)); pm.edge(b(false, T + 2600));
        check(pm.state() == PassageMachine.State.EXITING && r.closed.isEmpty(), "lewat: ekor berjalan");
        pm.tick(T + 2600 + 1499); check(r.closed.isEmpty(), "lewat: ekor belum habis");
        pm.tick(T + 2600 + 1500); Closing c = r.last();
        check("EXITED".equals(c.closeReason) && "sensor".equals(c.boundaryReason), "lewat: EXITED / sensor");
        check(c.tailMs == 1500 && c.preBufferMs == 3000 && "ok".equals(c.sensorHealth) && !c.merged, "lewat: tail/pre/health");
        check(c.aBlocked == T && c.bBlocked == T + 1100 && c.aCleared == T + 1800 && c.bCleared == T + 2600, "lewat: beam_times");
        check(c.direction == null && !c.cancelled(), "lewat: arah dari profil");

        // 2. Lintasan berikut tidak mengambil bacaan lintasan sebelumnya (window ≥ close sebelumnya + 1)
        pm.edge(a(true, T + 4200)); check(r.opened.get(1).windowStartMono == T + 4100 + 1, "berikut: window dijepit setelah close");
        pm.edge(b(true, T + 5000)); pm.edge(b(false, T + 5600)); pm.edge(a(false, T + 6000));
        check("REVERSED".equals(r.last().closeReason) && "cancelled".equals(r.last().boundaryReason) && r.last().cancelled(), "mundur: REVERSED / cancelled");

        // 3. Masuk lalu mundur sebelum B (muatan panjang): BETWEEN → between_timeout → ABORTED
        r = new Rec(); pm = m(Mode.ONE_WAY_BEAM, r);
        pm.edge(a(true, T)); pm.edge(a(false, T + 700)); check(pm.state() == PassageMachine.State.BETWEEN, "batal: BETWEEN");
        pm.tick(T + 700 + 4999); check(r.closed.isEmpty(), "batal: belum timeout");
        pm.tick(T + 700 + 5000); check("ABORTED".equals(r.last().closeReason) && "cancelled".equals(r.last().boundaryReason), "batal: ABORTED");
        // entry_timeout saat sinar A terus terhalang tanpa B
        pm.edge(a(true, T + 10_000)); pm.tick(T + 20_000); check("ABORTED".equals(r.last().closeReason), "entry_timeout: ABORTED");
        check(pm.state() == PassageMachine.State.BLOCKED_WAIT, "entry_timeout: tunggu sinar bebas");
        pm.edge(a(false, T + 21_000)); check(pm.state() == PassageMachine.State.IDLE, "entry_timeout: kembali IDLE");

        // 4. Muatan pendek (1–3 roll dibawa orang): A↓ A↑ B↓ B↑ = lewat sah
        r = new Rec(); pm = m(Mode.ONE_WAY_BEAM, r);
        pm.edge(a(true, T)); pm.edge(a(false, T + 400)); pm.edge(b(true, T + 1300)); pm.edge(b(false, T + 1700));
        pm.tick(T + 1700 + 1500); check("EXITED".equals(r.last().closeReason) && r.closed.size() == 1, "muatan pendek: EXITED");

        // 5. Dua muatan beriringan: A dipotong lagi saat B masih terhalang → digabung (merged, degraded)
        r = new Rec(); pm = m(Mode.ONE_WAY_BEAM, r);
        pm.edge(a(true, T)); pm.edge(b(true, T + 1100)); pm.edge(a(false, T + 1800)); pm.edge(a(true, T + 2300));
        pm.edge(b(false, T + 2600)); pm.edge(b(true, T + 3400)); pm.edge(a(false, T + 4100)); pm.edge(b(false, T + 4900));
        pm.tick(T + 4900 + 1500); c = r.last();
        check(r.closed.size() == 1 && "EXITED".equals(c.closeReason) && c.merged && "degraded".equals(c.sensorHealth), "beriringan: satu lintasan digabung");
        // A↓ saat ekor berjalan → digabung juga
        pm.edge(a(true, T + 10_000)); pm.edge(b(true, T + 11_000)); pm.edge(a(false, T + 11_500)); pm.edge(b(false, T + 12_000));
        pm.edge(a(true, T + 12_800)); check(pm.state() == PassageMachine.State.ENTERING && r.closed.size() == 1, "ekor: A↓ → digabung");
        pm.edge(b(true, T + 13_500)); pm.edge(a(false, T + 14_000)); pm.edge(b(false, T + 14_500)); pm.tick(T + 16_000);
        check(r.closed.size() == 2 && r.last().merged, "ekor: lintasan gabungan ditutup");

        // 6. Timeout: stacker berhenti di gate → TIMEOUT / max_duration
        r = new Rec(); pm = m(Mode.ONE_WAY_BEAM, r);
        pm.edge(a(true, T)); pm.edge(b(true, T + 1000)); pm.tick(T + 30_000);
        check("TIMEOUT".equals(r.last().closeReason) && "max_duration".equals(r.last().boundaryReason), "timeout: TIMEOUT");
        check(pm.state() == PassageMachine.State.BLOCKED_WAIT, "timeout: menunggu sinar bebas");
        // 7. Sinar tetap terhalang > sensor_stuck_ms → SENSOR_FAULT → cadangan RF (bukan berhenti)
        pm.tick(T + 45_001); check("fault".equals(pm.health()) && pm.rfLogicActive(), "macet: fault → cadangan RF");
        check(r.health.size() == 1 && r.health.get(0).startsWith("fault:BEAM_STUCK"), "macet: laporan kesehatan");
        long t = T + 50_000;
        pm.rf(tag(epc(1), t, -50), true, false); pm.rf(tag(epc(2), t + 300, -50), true, false);
        check(r.opened.size() == 1, "RF: rombongan belum cukup");
        pm.rf(tag(epc(3), t + 600, -50), true, false);
        check(r.opened.size() == 2 && "RF_FALLBACK".equals(r.opened.get(1).openReason), "RF: dibuka RF_FALLBACK");
        check(r.opened.get(1).windowStartMono == t - 3000, "RF: window = bacaan kuat pertama − pre_buffer");
        pm.rf(tag(epc(4), t + 2000, -50), true, false); pm.tick(t + 2000 + 2999); check(r.closed.size() == 1, "RF: bacaan kuat memperpanjang");
        pm.rf(tag(epc(9), t + 3500, -80), false, false); pm.rf(tag(epc(8), t + 3600, -50), true, true);
        pm.tick(t + 2000 + 3000); c = r.last();
        check(r.closed.size() == 2 && "SENSOR_FAULT".equals(c.closeReason) && "idle_timeout".equals(c.boundaryReason) && "fault".equals(c.sensorHealth),
                "RF: tutup SENSOR_FAULT; bacaan lemah/latar tidak memperpanjang");
        // 8. Bacaan lemah/latar tidak membuka lintasan cadangan
        for (int i = 0; i < 6; i++) pm.rf(tag(epc(20 + i), t + 10_000 + i * 100, -85), false, false);
        for (int i = 0; i < 6; i++) pm.rf(tag(epc(30 + i), t + 11_000 + i * 100, -40), true, true);
        check(r.opened.size() == 2, "RF: lemah/latar tidak membuka");
        // 9. Pulih: sinar bebas + 2 urutan A→B sah → kembali ke photo-eye
        pm.edge(a(false, t + 12_000)); pm.edge(b(false, t + 12_000));
        for (int k = 0; k < 2; k++) {
            long s0 = t + 13_000 + k * 5000;
            pm.edge(a(true, s0)); pm.edge(b(true, s0 + 1000)); pm.edge(a(false, s0 + 1700)); pm.edge(b(false, s0 + 2500));
        }
        pm.tick(t + 30_000); check("ok".equals(pm.health()) && !pm.rfLogicActive(), "pulih: kembali photo-eye");
        pm.edge(a(true, t + 31_000)); check("BEAM_A".equals(r.opened.get(r.opened.size() - 1).openReason), "pulih: lintasan dibuka sinar");

        // 10. B↓ sebelum A↓ (urutan mustahil) → fault (batas 1 = titik awal)
        r = new Rec(); pm = m(Mode.ONE_WAY_BEAM, r);
        pm.edge(b(true, T)); check("fault".equals(pm.health()) && r.opened.isEmpty(), "B sebelum A: fault");
        PassageMachine.Params lenient = new PassageMachine.Params(); lenient.bBeforeALimit = 3;
        Rec r2 = new Rec(); PassageMachine pm2 = new PassageMachine(Mode.ONE_WAY_BEAM, lenient, r2);
        pm2.edge(b(true, T)); pm2.edge(b(false, T + 300));
        check("ok".equals(pm2.health()) && r2.health.get(0).startsWith("degraded"), "B sebelum A (batas 3): degraded dulu");

        // 11. GPI tidak terbaca di tengah lintasan → tutup SENSOR_FAULT, lanjut cadangan RF
        r = new Rec(); pm = m(Mode.ONE_WAY_BEAM, r);
        pm.edge(a(true, T)); pm.sensorUnavailable(T + 500, "inputStatus null");
        check("SENSOR_FAULT".equals(r.last().closeReason) && "sensor".equals(r.last().boundaryReason) && pm.rfLogicActive(), "GPI hilang: SENSOR_FAULT");

        // 12. Tanpa sensor (RF_ONLY): sensor_health absent, close EXITED
        r = new Rec(); pm = m(Mode.RF_ONLY, r);
        for (int i = 0; i < 3; i++) pm.rf(tag(epc(i), T + i * 200, -50), true, false);
        pm.tick(T + 400 + 3000); c = r.last();
        check("RF_FALLBACK".equals(c.openReason) && "EXITED".equals(c.closeReason) && "absent".equals(c.sensorHealth), "RF saja: absent / EXITED");
        // tag diam (selalu terbaca kuat) memperpanjang sampai max_passage → TIMEOUT
        pm.rf(tag(epc(78), T + 9_800, -50), true, false); pm.rf(tag(epc(79), T + 9_900, -50), true, false);
        for (long k = 0; k <= 31_000; k += 500) pm.rf(tag(epc(77), T + 10_000 + k, -50), true, false);
        check("TIMEOUT".equals(r.last().closeReason), "RF saja: tag diam → TIMEOUT, bukan lintasan tanpa batas");

        // 13. Photo-eye sehat: bacaan kuat saat IDLE tidak membuka lintasan (tag diam tidak membuka/memperpanjang)
        r = new Rec(); pm = m(Mode.ONE_WAY_BEAM, r);
        for (int i = 0; i < 10; i++) pm.rf(tag(epc(i), T + i * 100, -40), true, false);
        check(r.opened.isEmpty(), "photo-eye sehat: bacaan tidak membuka");
        pm.edge(a(true, T + 2000)); pm.edge(b(true, T + 2500)); pm.edge(a(false, T + 3000)); pm.edge(b(false, T + 3500));
        for (int i = 0; i < 10; i++) pm.rf(tag(epc(1), T + 3600 + i * 100, -40), true, false);
        pm.tick(T + 5000); check(r.closed.size() == 1, "photo-eye sehat: bacaan tidak memperpanjang ekor");

        // 14. Inhibit (offline + capture offline dilarang): tidak membuka, tidak salah fault
        r = new Rec(); pm = m(Mode.ONE_WAY_BEAM, r); pm.setInhibited(true);
        pm.edge(a(true, T)); pm.edge(b(true, T + 1000)); pm.edge(a(false, T + 1500)); pm.edge(b(false, T + 2000));
        check(r.opened.isEmpty() && "ok".equals(pm.health()), "inhibit: tidak membuka, sensor tetap ok");
        pm.setInhibited(false); pm.edge(a(true, T + 5000)); check(r.opened.size() == 1, "inhibit dilepas: buka lagi");
        pm.manualClose(T + 5200); check("MANUAL".equals(r.last().closeReason) && "authorized_manual".equals(r.last().boundaryReason), "manual: MANUAL");

        // 15. Gate dua arah lama: arah dari urutan A/B, tutup karena sepi
        r = new Rec(); pm = m(Mode.LEGACY_BIDIRECTIONAL, r);
        pm.edge(b(true, T)); pm.edge(a(true, T + 800)); pm.edge(b(false, T + 1500)); pm.edge(a(false, T + 2000));
        pm.tick(T + 2000 + 3000); c = r.last();
        check("in".equals(c.direction) && "idle_timeout".equals(c.boundaryReason) && c.openReason == null && c.closeReason == null, "dua arah: in / idle");
        check(c.legacySequence.size() == 2 && "B".equals(c.legacySequence.get(0).sensor), "dua arah: urutan bukti 2 tepi");
        pm.rf(tag(epc(5), T + 10_000, -50), true, false); pm.tick(T + 13_000);
        check("unknown".equals(r.last().direction), "dua arah: dibuka bacaan, arah unknown");

        // 16. Debounce: kedip < min_block diabaikan; bebas butuh min_clear; cap waktu = perubahan mentah
        BeamDebouncer d = new BeamDebouncer("A", 50, 200);
        check(d.sample(false, 0) == null, "debounce: baseline");
        check(d.sample(true, 20) == null && d.sample(false, 40) == null && d.sample(false, 100) == null, "debounce: kedip 20 ms diabaikan");
        check(d.sample(true, 120) == null && d.sample(true, 160) == null, "debounce: belum 50 ms");
        Edge e = d.sample(true, 180); check(e != null && e.blocked && e.tMono == 120, "debounce: tepi pada t mentah");
        check(d.sample(false, 300) == null && d.sample(true, 380) == null && d.sample(true, 700) == null, "debounce: celah garpu 80 ms tidak memecah");
        check(d.sample(false, 800) == null && d.sample(false, 990) == null, "debounce: bebas belum 200 ms");
        e = d.sample(false, 1000); check(e != null && !e.blocked && e.tMono == 800, "debounce: bebas setelah 200 ms");

        System.out.println("PASS: " + checks + " passage state machine assertions");
    }
}
