package id.kainnusantara.handheld.core;

import org.json.JSONObject;

import java.util.List;

/** Tes host alur perangkat dengan radio TIRUAN: pemicu & kepemilikan radio, tulis EPC + baca ulang, uji meja. */
public final class FlowTest {
    static int passed;

    static void check(boolean ok, String label) {
        if (!ok) throw new AssertionError("GAGAL: " + label);
        passed++;
        System.out.println("PASS " + label);
    }

    static final WriteFlow.Sleeper NO_SLEEP = ms -> { };

    public static void main(String[] a) throws Exception {
        trigger(); write(); bench();
        System.out.println("FlowTest: " + passed + " PASS");
    }

    static void trigger() throws Exception {
        SimulatedHardware hw = new SimulatedHardware(false);
        hw.add("E2000000000000000000BB01", -50);
        hw.add("E2000000000000000000BB02", -60);
        Profile p = Profile.defaults();
        hw.initialize(p);
        ScanController sc = new ScanController(hw, new ReadAggregator(100), p);
        check(sc.onKeyDown(293, 0) && sc.mode() == ScanController.Mode.SCANNING && sc.aggregator().unique() == 2, "pemicu tahan: tekan = mulai pindai (2 tag)");
        check(sc.onKeyDown(293, 1) && sc.onKeyDown(293, 0) && sc.sessionsStarted() == 1, "pemicu ganda/auto-repeat: TIDAK membuka sesi radio kedua");
        check(sc.onKeyUp(293) && sc.mode() == ScanController.Mode.IDLE && !hw.inventorying(), "pemicu tahan: lepas = berhenti");
        check(!sc.onKeyDown(4, 0), "tombol non-pemicu tidak dikonsumsi");
        check(sc.acquire(ScanController.Mode.WRITING) && !sc.start(), "radio dipegang tulis → pindai ditolak");
        sc.release(ScanController.Mode.WRITING);
        Profile toggle = new Profile(Json.obj("trigger", Json.obj("mode", "toggle")));
        sc.profile(toggle);
        sc.onKeyDown(293, 0);
        sc.onKeyUp(293);
        check(sc.mode() == ScanController.Mode.SCANNING, "pemicu toggle: lepas tidak menghentikan");
        sc.onKeyDown(293, 0);
        check(sc.mode() == ScanController.Mode.IDLE, "pemicu toggle: tekan lagi = berhenti");
        sc.resetWindow();
        check(sc.aggregator().unique() == 0 && sc.firstWall() == 0, "jendela pindai baru dikosongkan");
        SimulatedHardware dead = new SimulatedHardware(false);
        ScanController sd = new ScanController(dead, new ReadAggregator(10), p);
        check(!sd.start(), "radio belum init → tidak mulai");
    }

    static void write() throws Exception {
        Profile p = new Profile(Json.obj("write", Json.obj("verify_reads", 2, "max_attempts", 3, "min_rssi_gap_db", 6.0)));
        String NEW = "E2ABCDEF0000000000000001";
        SimulatedHardware hw = new SimulatedHardware(false);
        hw.initialize(p);
        WriteFlow.Result none = new WriteFlow(hw, p, NO_SLEEP).write(NEW, null);
        check(none.code == WriteFlow.Code.NO_TAG, "tulis: tanpa tag → NO_TAG");
        SimulatedHardware.SimTag near = hw.add("E2000000000000000000CC01", -40);
        SimulatedHardware.SimTag far = hw.add("E2000000000000000000CC02", -43);
        check(new WriteFlow(hw, p, NO_SLEEP).write(NEW, null).code == WriteFlow.Code.AMBIGUOUS, "tulis: dua tag sinyal mirip → AMBIGUOUS (tidak menebak)");
        far.rssi = -70;
        WriteFlow.Result ok = new WriteFlow(hw, p, NO_SLEEP).write(NEW, null);
        check(ok.ok() && NEW.equals(near.epc) && NEW.equals(ok.verifiedEpc) && "E2000000000000000000CC01".equals(ok.oldEpc) && "E2000000000000000000CC02".equals(far.epc),
                "tulis: tag TERDEKAT ditulis, tag jauh tidak berubah, baca ulang mengonfirmasi");
        check(hw.getPower() == 20 && ok.powerDbm == 10, "tulis: daya diturunkan saat tulis lalu dikembalikan");
        check(new WriteFlow(hw, p, NO_SLEEP).write(NEW, null).ok(), "tulis ulang EPC yang sama (setelah gangguan) → langsung verifikasi");
        String N2 = "E2ABCDEF0000000000000002";
        hw.failWrites = 1;
        WriteFlow.Result retry = new WriteFlow(hw, p, NO_SLEEP).write(N2, null);
        check(retry.ok() && retry.attempts == 2, "tulis: gagal sekali lalu berhasil (percobaan ke-2)");
        String N3 = "E2ABCDEF0000000000000003";
        hw.silentWrites = 5;
        WriteFlow.Result silent = new WriteFlow(hw, p, NO_SLEEP).write(N3, null);
        check(!silent.ok() && silent.code == WriteFlow.Code.VERIFY_FAILED && N2.equals(near.epc), "tulis: SDK lapor sukses tapi chip tidak berubah → VERIFY_FAILED");
        hw.silentWrites = 0;
        hw.failWrites = 10;
        check(new WriteFlow(hw, p, NO_SLEEP).write(N3, null).code == WriteFlow.Code.WRITE_FAILED, "tulis: selalu gagal → WRITE_FAILED");
        hw.failWrites = 0;
        check(new WriteFlow(hw, p, NO_SLEEP).write("BUKAN-EPC", null).code == WriteFlow.Code.INVALID_EPC, "tulis: EPC sasaran tidak valid ditolak");
    }

    static void bench() throws Exception {
        SimulatedHardware hw = new SimulatedHardware(false);
        hw.add("E2000000000000000000DD01", -45);
        hw.add("E2000000000000000000DD02", -75);
        hw.barcodes.add("RL-0001");
        Profile p = Profile.defaults();
        BenchRunner r = new BenchRunner(hw, p, NO_SLEEP);
        List<BenchRunner.Step> steps = r.runAll(true, true, true);
        JSONObject rep = BenchRunner.report(steps, Json.obj("model", "SIM"), "0.1.0-lab", p);
        int fail = rep.getJSONObject("summary").getInt("fail");
        for (BenchRunner.Step s : steps) System.out.println("   " + s.line());
        check(fail == 0 && rep.getJSONObject("summary").getInt("pass") == 10, "uji meja simulasi: 10 langkah PASS");
        check("E2000000000000000000DD01".equals(hw.field.get(0).epc), "uji meja: EPC asal tag uji dikembalikan setelah uji tulis");
        JSONObject inv = steps.get(4).data;
        check(inv.getInt("unique") == 2 && inv.getJSONArray("raw_rssi_samples").getString(0).contains(","), "uji meja: data mentah RSSI (koma locale) ikut diekspor");
        hw.initOk = false;
        check("FAIL".equals(new BenchRunner(hw, p, NO_SLEEP).init().status), "uji meja: init SDK gagal dilaporkan FAIL (bukan diam)");
    }
}
