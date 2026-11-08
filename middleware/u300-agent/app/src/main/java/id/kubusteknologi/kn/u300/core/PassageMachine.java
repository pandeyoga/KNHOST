package id.kubusteknologi.kn.u300.core;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Batas lintasan gate (AUD-MW-02, keputusan K-RFID-01 "photo-eye utama + cadangan RF", audit §8.3).
 * Murni (tanpa Android); waktu = milidetik monotonik yang diberikan pemanggil.
 *
 * <pre>
 * Gate satu arah — A = mulut masuk, B = mulut keluar:
 * IDLE ──A↓──▶ ENTERING (window_start = t(A↓) − pre_buffer, tidak sebelum lintasan sebelumnya tutup)
 * ENTERING ──B↓──▶ IN_PORTAL;   ENTERING ──entry_timeout tanpa B↓──▶ ABORTED (batal, boundary cancelled)
 * ENTERING ──A↑ tanpa B↓──▶ BETWEEN (muatan pendek di antara sinar) ──B↓──▶ IN_PORTAL
 *                                   BETWEEN ──between_timeout / entry_timeout──▶ ABORTED (mundur sebelum masuk)
 * IN_PORTAL ──semua bebas, terakhir B──▶ EXITING ──tail_ms──▶ EXITED (boundary sensor)
 * IN_PORTAL ──semua bebas, terakhir A──▶ REVERSED (mundur, boundary cancelled)
 * IN_PORTAL ──A↓ lagi saat B masih terhalang── / EXITING ──A↓── : muatan beriringan → DIGABUNG (merged)
 * semua state ──max_passage──▶ TIMEOUT (boundary max_duration)
 * sinar macet > sensor_stuck_ms, B↓ sebelum A↓, GPI tak terbaca ──▶ SENSOR_FAULT → mode CADANGAN RF
 *   (rombongan ≥ group_size EPC kuat non-latar dalam rf_window; tutup bila tak ada bacaan kuat stable_interval);
 *   pulih otomatis setelah recovery_sequences urutan A↓→B↓→bebas(B terakhir) yang sah.
 * Tanpa sensor (RF_ONLY): selalu logika RF, sensor_health "absent".
 * Gate dua arah lama (LEGACY_BIDIRECTIONAL): buka oleh tepi/bacaan kuat, tutup karena sepi (idle), arah dari urutan A/B.
 * </pre>
 * Bacaan latar/lemah tidak pernah memperpanjang lintasan. Semua parameter = titik awal kalibrasi.
 */
public final class PassageMachine {
    public enum Mode { ONE_WAY_BEAM, RF_ONLY, LEGACY_BIDIRECTIONAL }
    public enum State { IDLE, ENTERING, BETWEEN, IN_PORTAL, EXITING, RF_OPEN, LEGACY_OPEN, BLOCKED_WAIT }

    public static final String OK = "ok", FAULT = "fault", ABSENT = "absent", DEGRADED = "degraded";

    public static final class Params {
        public long preBufferMs = 3000, tailMs = 1500, entryTimeoutMs = 10000, maxPassageMs = 30000;
        public long betweenTimeoutMs = 5000;
        public long stableIntervalMs = 3000, rfWindowMs = 1500;
        public int rfGroupSize = 3;
        public long sensorStuckMs = 45000;
        public int recoverySequences = 2, bBeforeALimit = 1;
        public long legacyIdleMs = 3000, legacySequenceWindowMs = 5000;
    }

    public static final class Opening {
        public final String openReason;
        public final long tOpenMono, windowStartMono;
        Opening(String openReason, long tOpenMono, long windowStartMono) {
            this.openReason = openReason;
            this.tOpenMono = tOpenMono;
            this.windowStartMono = windowStartMono;
        }
    }

    /** Ringkasan batas lintasan saat ditutup (bahan PassageClose 2.1). Nilai waktu = monotonik. */
    public static final class Closing {
        public String openReason, closeReason, boundaryReason, sensorHealth, direction = "unknown";
        public long tOpenMono, windowStartMono, tCloseMono, preBufferMs, tailMs;
        public Long aBlocked, bBlocked, aCleared, bCleared;
        public boolean merged;
        public final List<BeamDebouncer.Edge> legacySequence = new ArrayList<>();
        public boolean cancelled() { return "REVERSED".equals(closeReason) || "ABORTED".equals(closeReason); }
    }

    public interface Listener {
        void opened(Opening o);
        void closed(Closing c);
        void health(String health, String detail, long tMono);
    }

    private final Mode mode;
    private final Params p;
    private final Listener listener;
    private State state = State.IDLE;
    private String health, faultDetail = "";
    private boolean aBlk, bBlk, aKnown, bKnown, inhibited;
    private long aSince, bSince;
    private Closing cur;
    private boolean aClearedInPortal;
    private long exitStart, enterMono, betweenMono, lastStrongMono, legacyActivity;
    private long prevCloseMono = Long.MIN_VALUE;
    private final LinkedHashMap<String, Long> group = new LinkedHashMap<>();
    private int recoveryStage, validSequences, bBeforeA;
    private long recoveryT;
    private Safety.Direction legacyDirection;
    private long anomalies;

    public PassageMachine(Mode mode, Params params, Listener listener) {
        this.mode = mode;
        this.p = params;
        this.listener = listener;
        this.health = mode == Mode.RF_ONLY ? ABSENT : OK;
    }

    public Mode mode() { return mode; }
    public State state() { return state; }
    public String health() { return health; }
    public String faultDetail() { return faultDetail; }
    public boolean open() { return cur != null; }
    public long anomalies() { return anomalies; }
    public boolean rfLogicActive() { return mode == Mode.RF_ONLY || (mode == Mode.ONE_WAY_BEAM && FAULT.equals(health)); }

    /** Lintasan baru tidak dibuka (mis. offline + capture offline tidak diizinkan). Lintasan aktif dibiarkan. */
    public void setInhibited(boolean value) { inhibited = value; }

    // ------------------------------------------------------------------ input

    public void edge(BeamDebouncer.Edge e) {
        tick(e.tMono);
        if ("A".equals(e.sensor)) { aBlk = e.blocked; aSince = e.tMono; aKnown = true; }
        else { bBlk = e.blocked; bSince = e.tMono; bKnown = true; }
        if (mode == Mode.RF_ONLY) return;
        if (mode == Mode.LEGACY_BIDIRECTIONAL) { legacyEdge(e); return; }
        if (FAULT.equals(health)) { recoveryEdge(e); return; }
        if (inhibited && cur == null) { state = aBlk || bBlk ? State.BLOCKED_WAIT : State.IDLE; return; }
        beamEdge(e);
        if (state == State.BLOCKED_WAIT && !aBlk && !bBlk) state = State.IDLE;
    }

    /** Bacaan valid (EPC kanonik, antena terpetakan). strong = RSSI ≥ ambang (atau tanpa RSSI). */
    public void rf(Sample s, boolean strong, boolean background) {
        tick(s.tMono);
        if (s.epc == null || !s.antennaKnown || !strong || background) return;
        long t = s.tMono;
        if (mode == Mode.LEGACY_BIDIRECTIONAL) {
            legacyActivity = t;
            if (cur == null && !inhibited) {
                if (opening("RF_FALLBACK", t, t)) { legacyDirection = new Safety.Direction(); state = State.LEGACY_OPEN; }
            }
            return;
        }
        if (!rfLogicActive()) return;               // photo-eye sehat: bacaan tidak membuka/memperpanjang lintasan
        group.remove(s.epc);
        group.put(s.epc, t);
        for (Iterator<Map.Entry<String, Long>> it = group.entrySet().iterator(); it.hasNext(); ) {
            if (t - it.next().getValue() > p.rfWindowMs) it.remove(); else break;
        }
        if (cur != null && state == State.RF_OPEN) { lastStrongMono = t; return; }
        if (cur == null && state == State.IDLE && !inhibited && group.size() >= Math.max(1, p.rfGroupSize)) {
            long first = group.values().iterator().next();
            if (opening("RF_FALLBACK", t, first)) { state = State.RF_OPEN; lastStrongMono = t; }
            group.clear();
        }
    }

    /** GPI tidak bisa dibaca → sensor dianggap rusak, jatuh ke cadangan RF (bukan berhenti). */
    public void sensorUnavailable(long tMono, String why) {
        if (mode != Mode.ONE_WAY_BEAM) return;
        aKnown = bKnown = false;
        fault("GPI_UNAVAILABLE " + why, tMono);
    }

    public void manualClose(long tMono) {
        tick(tMono);
        if (cur != null) {
            finish("MANUAL", "authorized_manual", tMono);
            state = beamMode() && (aBlk || bBlk) ? State.BLOCKED_WAIT : State.IDLE;
        }
    }

    public void tick(long now) {
        if (mode == Mode.LEGACY_BIDIRECTIONAL) { legacyTick(now); return; }
        if (mode == Mode.ONE_WAY_BEAM) {
            boolean stuckA = aKnown && aBlk && now - aSince > p.sensorStuckMs;
            boolean stuckB = bKnown && bBlk && now - bSince > p.sensorStuckMs;
            if (stuckA || stuckB) {
                if (OK.equals(health)) fault("BEAM_STUCK " + (stuckA ? "A" : "B"), now);
                else { recoveryStage = 0; validSequences = 0; }
            }
        }
        switch (state) {
            case ENTERING:
                if (cur != null && now - enterMono >= p.entryTimeoutMs) {
                    finish("ABORTED", "cancelled", now);
                    state = aBlk || bBlk ? State.BLOCKED_WAIT : State.IDLE;
                }
                break;
            case BETWEEN:
                if (cur != null && (now - betweenMono >= p.betweenTimeoutMs || now - enterMono >= p.entryTimeoutMs)) {
                    finish("ABORTED", "cancelled", now);
                    state = aBlk || bBlk ? State.BLOCKED_WAIT : State.IDLE;
                }
                break;
            case EXITING:
                if (cur != null && now - exitStart >= p.tailMs) { finish("EXITED", "sensor", now); state = State.IDLE; }
                break;
            case RF_OPEN:
                if (cur != null && now - lastStrongMono >= p.stableIntervalMs) {
                    finish(FAULT.equals(health) ? "SENSOR_FAULT" : "EXITED", "idle_timeout", now);
                    state = State.IDLE;
                }
                break;
            default:
                break;
        }
        if (cur != null && now - cur.tOpenMono >= p.maxPassageMs) {
            finish("TIMEOUT", "max_duration", now);
            state = beamMode() && (aBlk || bBlk) ? State.BLOCKED_WAIT : State.IDLE;
        }
        if (state == State.BLOCKED_WAIT && !aBlk && !bBlk) state = State.IDLE;
        if (FAULT.equals(health) && validSequences >= Math.max(1, p.recoverySequences) && cur == null && !aBlk && !bBlk
                && aKnown && bKnown) {
            health = OK;
            faultDetail = "";
            bBeforeA = 0;
            validSequences = 0;
            state = State.IDLE;
            group.clear();
            listener.health(OK, "Photo-eye pulih: " + p.recoverySequences + " urutan A→B sah.", now);
        }
    }

    // ------------------------------------------------------------------ beam (sehat)

    private boolean beamMode() { return mode == Mode.ONE_WAY_BEAM && OK.equals(health); }

    private void beamEdge(BeamDebouncer.Edge e) {
        long t = e.tMono;
        boolean a = "A".equals(e.sensor);
        switch (state) {
            case IDLE:
                if (a && e.blocked) {
                    if (opening("BEAM_A", t, t)) { cur.aBlocked = t; aClearedInPortal = false; enterMono = t; state = State.ENTERING; }
                } else if (!a && e.blocked) {
                    anomalies++;
                    if (++bBeforeA >= Math.max(1, p.bBeforeALimit)) fault("B_BEFORE_A", t);
                    else listener.health(DEGRADED, "Sinar B terpotong sebelum A (urutan mustahil).", t);
                    if (OK.equals(health)) state = State.BLOCKED_WAIT;
                }
                break;
            case ENTERING:
                if (!a && e.blocked) { if (cur.bBlocked == null) cur.bBlocked = t; state = State.IN_PORTAL; }
                else if (a && !e.blocked) { cur.aCleared = t; betweenMono = t; state = State.BETWEEN; }
                break;
            case BETWEEN:
                if (!a && e.blocked) {
                    if (cur.bBlocked == null) cur.bBlocked = t;
                    aClearedInPortal = true;
                    state = State.IN_PORTAL;
                } else if (a && e.blocked) {
                    state = State.ENTERING;                  // kembali memotong A (goyang/mundur lalu maju)
                }
                break;
            case IN_PORTAL:
                if (a && e.blocked) {
                    if (aClearedInPortal && bBlk) cur.merged = true;     // muatan berikut menyusul / muatan mundur
                    aClearedInPortal = false;
                } else if (a) {
                    cur.aCleared = t;
                    aClearedInPortal = true;
                    if (!bBlk) { finish("REVERSED", "cancelled", t); state = State.IDLE; }
                } else if (e.blocked) {
                    if (cur.bBlocked == null) cur.bBlocked = t;
                } else {
                    cur.bCleared = t;
                    if (!aBlk) { exitStart = t; state = State.EXITING; }
                }
                break;
            case EXITING:
                if (a && e.blocked) {                      // muatan berikut masuk sebelum ekor selesai → digabung
                    cur.merged = true;
                    aClearedInPortal = false;
                    enterMono = t;
                    state = State.ENTERING;
                } else if (!a && e.blocked) {              // muatan kembali ke sinar B
                    state = State.IN_PORTAL;
                }
                break;
            default:
                break;
        }
    }

    // ------------------------------------------------------------------ sensor rusak → cadangan RF

    private void fault(String detail, long t) {
        if (FAULT.equals(health)) return;
        anomalies++;
        health = FAULT;
        faultDetail = detail;
        recoveryStage = 0;
        validSequences = 0;
        group.clear();
        if (cur != null) finish("SENSOR_FAULT", "sensor", t);
        state = State.IDLE;
        listener.health(FAULT, detail, t);
    }

    private void recoveryEdge(BeamDebouncer.Edge e) {
        long t = e.tMono;
        boolean a = "A".equals(e.sensor);
        switch (recoveryStage) {
            case 0:
                if (a && e.blocked && !bBlk) { recoveryStage = 1; recoveryT = t; }
                else if (!a && e.blocked && !aBlk) validSequences = 0;   // urutan mustahil lagi
                break;
            case 1:
                if (!a && e.blocked) recoveryStage = t - recoveryT <= p.entryTimeoutMs ? 2 : 0;
                break;
            default:
                if (!aBlk && !bBlk) {
                    if (!a && !e.blocked) validSequences++;          // bebas terakhir = B → lewat sah
                    recoveryStage = 0;
                }
                break;
        }
    }

    // ------------------------------------------------------------------ dua arah lama

    private void legacyEdge(BeamDebouncer.Edge e) {
        legacyActivity = e.tMono;
        if (!e.blocked) return;
        if (cur == null) {
            if (inhibited || !opening("BEAM_A", e.tMono, e.tMono)) return;
            legacyDirection = new Safety.Direction();
            state = State.LEGACY_OPEN;
        }
        if (cur.legacySequence.size() < 2) cur.legacySequence.add(e);
        cur.direction = legacyDirection.edge(e.sensor, e.tMono, p.legacySequenceWindowMs);
        if ("A".equals(e.sensor) && cur.aBlocked == null) cur.aBlocked = e.tMono;
        if ("B".equals(e.sensor) && cur.bBlocked == null) cur.bBlocked = e.tMono;
    }

    private void legacyTick(long now) {
        if (cur == null) return;
        if (now - cur.tOpenMono >= p.maxPassageMs) finish(null, "max_duration", now);
        else if (now - legacyActivity >= p.legacyIdleMs) finish(null, "idle_timeout", now);
        if (cur == null) state = State.IDLE;
    }

    // ------------------------------------------------------------------ buka/tutup

    private boolean opening(String reason, long tOpen, long earliest) {
        if (inhibited) return false;
        long start = earliest - p.preBufferMs;
        if (prevCloseMono != Long.MIN_VALUE && start <= prevCloseMono) start = prevCloseMono + 1;
        if (start > tOpen) start = tOpen;
        cur = new Closing();
        cur.openReason = mode == Mode.LEGACY_BIDIRECTIONAL ? null : reason;
        cur.tOpenMono = tOpen;
        cur.windowStartMono = start;
        legacyActivity = tOpen;
        listener.opened(new Opening(cur.openReason, tOpen, start));
        return true;
    }

    private void finish(String closeReason, String boundary, long t) {
        Closing c = cur;
        cur = null;
        c.closeReason = closeReason;
        c.boundaryReason = boundary;
        c.tCloseMono = t;
        c.preBufferMs = Math.max(0, c.tOpenMono - c.windowStartMono);
        c.tailMs = "EXITED".equals(closeReason) && c.bCleared != null ? Math.max(0, t - c.bCleared) : 0;
        if (mode == Mode.RF_ONLY) c.sensorHealth = ABSENT;
        else if (FAULT.equals(health) || "SENSOR_FAULT".equals(closeReason)) c.sensorHealth = FAULT;
        else if (c.merged) c.sensorHealth = DEGRADED;
        else c.sensorHealth = OK;
        if (mode != Mode.LEGACY_BIDIRECTIONAL) c.direction = null;   // gate satu arah: arah dari profil
        prevCloseMono = t;
        aClearedInPortal = false;
        listener.closed(c);
    }
}
