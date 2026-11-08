package id.kubusteknologi.kn.u300;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.os.Build;
import android.os.SystemClock;
import com.rscja.deviceapi.RFIDWithUHFA4;
import com.rscja.deviceapi.entity.AntennaState;
import com.rscja.deviceapi.entity.FastInventoryEntity;
import com.rscja.deviceapi.entity.GPIStateEntity;
import com.rscja.deviceapi.entity.InventoryParameter;
import com.rscja.deviceapi.entity.UHFTAGInfo;
import org.json.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import id.kubusteknologi.kn.u300.core.*;

/**
 * Mode diagnostik UJI MEJA K-RFID-03 (audit §7, 9 butir). Dijalankan operator ber-PIN saat layanan agent
 * BERHENTI (modul UHF dipakai eksklusif). Setiap butir mencatat data mentah + ringkasan otomatis ke tabel
 * {@code bench}; pengamatan operator (lampu mana yang menyala, sinar mana yang dipotong, dsb.) dicatat terpisah.
 * Tidak ada butir yang menyatakan "lulus" sendiri — kesimpulan = keputusan tim (K-RFID-03 tetap terbuka).
 * Mode simulasi menghasilkan data tiruan bertanda SIMULASI hanya untuk menguji alur layar & ekspor.
 */
final class Bench {
    interface Progress {void update(String text);}
    static final String[] TITLES={
        "1. Format nomor antena getAnt()",
        "2. Format RSSI getRssi() pada locale perangkat",
        "3. Arti getCount(), phase & frequency point, cap waktu SDK",
        "4. Nilai bawaan Gen2 (session/target/Q), TagFocus, FastID; persistensi",
        "5. Region 0x3F (Indonesia 920–923 MHz) & versi firmware UHF",
        "6. Rentang & langkah daya per antena + baca-balik",
        "7. Laju callback nyata (3 antena, session 0, 50–100 tag)",
        "8. GPI/GPO: pemetaan terminal, level idle, latensi polling, tepi sinar",
        "9. Layanan UHF bawaan U300 (auto-start, merebut modul)"};
    static final String[] INSTRUCTIONS={
        "Taruh 5–10 tag di depan SETIAP antena terpasang. Uji membaca 5 s dengan semua port aktif lalu mencatat string mentah getAnt() dan hasil parse agent.",
        "Pakai locale perangkat yang akan dipakai operasional (Pengaturan › Bahasa). Uji membaca 5 s dan mencatat string RSSI mentah, jumlah \"N/A\", desimal koma, dan hasil parse.",
        "Taruh 5–10 tag. Uji membaca 5 s (bawaan) lalu 5 s dengan InventoryParameter phase+frequency. Dicatat sebaran getCount(), porsi phase/frequency ≠ 0, dan selisih getTimestamp() vs jam callback.",
        "Jalankan SEBELUM dan SESUDAH aplikasi demo vendor dipakai. Uji membaca getGen2/getTagFocus/getFastId/getRFLink, lalu free()+init() dan membaca ulang. Centang 'terapkan profil' untuk menguji set+baca-balik setelan radio profil tersimpan.",
        "Mencatat getVersion/getHardwareVersion/getFrequencyMode. Bila 'izinkan set region' dicentang: set kode region profil (kandidat 63 = 0x3F), baca-balik, lalu KEMBALIKAN nilai asal.",
        "Tanpa inventory (tidak memancar): set daya 5/10/15/16/20/25/26/30/33 dBm per port, baca-balik, lalu kembalikan nilai asal.",
        "Taruh 50–100 tag, 3 antena terpasang. Tiga putaran 10 s: (a) callback kosong, (b) callback menulis SQLite per bacaan (pola 0.4), (c) callback → antrean RAM agent 0.5. Dicatat bacaan/s, tag unik, bacaan terbuang.",
        "Sambungkan photo-eye/relay sesuai wiring. Uji: level idle GPI1–4, lama panggilan inputStatus() (inventory mati & menyala), lalu 15 s merekam tepi — potong sinar A lalu B. Centang 'uji GPO' untuk menyalakan output 1–4 bergantian (1,5 s) dan catat lampu mana yang menyala.",
        "Jalankan sesaat setelah reboot SEBELUM layanan agent mulai. Dicatat sys.uhf.service.enable (readTcpServiceState), paket cn.cw.uhf.tcpserver, port 9160/9260/8080 sebelum & sesudah init(), dan lama init()."};
    private final Context ctx;private final Journal db;private final boolean sim;final String run;
    Bench(Context ctx,Journal db,boolean sim,String run){this.ctx=ctx;this.db=db;this.sim=sim;this.run=run;}

    static JSONObject device(){return Json.obj("model",Build.MODEL,"manufacturer",Build.MANUFACTURER,"android",Build.VERSION.RELEASE,"sdk_int",Build.VERSION.SDK_INT,"locale",Locale.getDefault().toLanguageTag(),"app_build",BuildConfig.VERSION_NAME);}

    JSONObject runItem(int item,JSONObject options,Progress progress){
        JSONObject row=Json.obj("kind","hasil_otomatis","run",run,"item",item,"title",TITLES[item-1],"instructions",INSTRUCTIONS[item-1],"started_at",Json.now(),"device",device(),"source",sim?"SIMULASI — bukan hasil perangkat":"PERANGKAT");
        try{
            JSONObject data=sim?simulated(item):real(item,options,progress);
            row.put("data",data).put("status",data.optBoolean("needs_operator",true)?"butuh_pengamatan_operator":"selesai_otomatis");
        }catch(Throwable e){
            try{row.put("status","gagal").put("error",e.getClass().getSimpleName()+": "+e.getMessage());}catch(JSONException ignored){/* tidak mungkin */}
        }
        try{row.put("finished_at",Json.now());}catch(JSONException ignored){/* tidak mungkin */}
        db.addBench(run,item,row);
        return row;
    }
    void note(int item,String verdict,String note){
        db.addBench(run,item,Json.obj("kind","catatan_operator","run",run,"item",item,"title",TITLES[item-1],"at",Json.now(),"verdict",verdict,"note",Parse.clip(note,2000)));
    }
    static JSONObject export(Journal db){
        JSONArray rows=new JSONArray();for(JSONObject r:db.rows("SELECT body FROM bench ORDER BY id"))rows.put(Json.parse(r.optString("body")));
        return Json.obj("kind","kn_u300_uji_meja","schema_version",1,"decision","K-RFID-03 (terbuka — hasil ini bahan keputusan tim, bukan kelulusan otomatis)","generated_at",Json.now(),"device",device(),"rows",rows);
    }

    // ------------------------------------------------------------------ perangkat
    private RFIDWithUHFA4 open() throws Exception{RFIDWithUHFA4 s=RFIDWithUHFA4.getInstance();if(!s.init(ctx))throw new Exception("init() gagal — lihat butir 9 (layanan bawaan)");return s;}
    private static final class Read{String epc,ant,rssi;int count,phase;float freq;long ts,wall,nanos;}
    private static List<Read> inventory(RFIDWithUHFA4 s,long ms,InventoryParameter param) throws Exception{
        List<Read> out=Collections.synchronizedList(new ArrayList<>());
        s.setInventoryCallback(t->{if(t!=null&&out.size()<20000){Read r=new Read();r.epc=t.getEPC();r.ant=t.getAnt();r.rssi=t.getRssi();r.count=t.getCount();r.phase=t.getPhase();r.freq=t.getFrequencyPoint();r.ts=t.getTimestamp();r.wall=System.currentTimeMillis();r.nanos=SystemClock.elapsedRealtimeNanos();out.add(r);}});
        boolean started=param==null?s.startInventoryTag():s.startInventoryTag(param);if(!started)throw new Exception("startInventoryTag gagal");
        SystemClock.sleep(ms);s.stopInventory();SystemClock.sleep(300);
        synchronized(out){return new ArrayList<>(out);}
    }
    private static void enableAll(RFIDWithUHFA4 s,JSONObject data) throws Exception{
        List<AntennaState> ants=s.getANT();JSONArray before=new JSONArray();if(ants!=null)for(AntennaState a:ants){before.put(a.getAntennaName().name()+":"+a.isEnable());a.setEnable(true);}
        data.put("antennas_before",before).put("set_all_enabled",ants!=null&&s.setANT(ants));
    }
    private JSONObject real(int item,JSONObject o,Progress p) throws Exception{
        JSONObject data=new JSONObject();
        if(item==9)return builtin(data);
        RFIDWithUHFA4 s=open();
        try{
            switch(item){
                case 1:case 2:{
                    enableAll(s,data);p.update("Membaca 5 s…");List<Read> reads=inventory(s,5000,null);data.put("reads",reads.size());
                    Map<String,Integer> raw=new TreeMap<>();for(Read r:reads)raw.merge(item==1?String.valueOf(r.ant):String.valueOf(r.rssi),1,Integer::sum);
                    JSONArray rows=new JSONArray();int n=0;
                    for(Map.Entry<String,Integer> e:raw.entrySet()){if(n++>=40)break;rows.put(Json.obj("raw",e.getKey(),"count",e.getValue(),"parsed",item==1?Parse.antenna(e.getKey()):Parse.rssi(e.getKey())));}
                    data.put("distinct",rows).put("distinct_total",raw.size());
                    if(item==2){int na=0,comma=0,invalid=0;double min=0,max=-200;for(Read r:reads){int k=Parse.rssiKind(r.rssi);if(k==Parse.RSSI_MISSING)na++;else if(k==Parse.RSSI_INVALID)invalid++;else{double v=Parse.rssi(r.rssi);min=Math.min(min,v);max=Math.max(max,v);}if(r.rssi!=null&&r.rssi.contains(","))comma++;}
                        data.put("locale",Locale.getDefault().toLanguageTag()).put("missing_or_na",na).put("comma_decimal",comma).put("invalid",invalid).put("parsed_min",min).put("parsed_max",max);}
                    data.put("needs_operator",true).put("question",item==1?"Apakah port fisik 1..n sesuai string? 1-based?":"Apakah RSSI selalu negatif dBm? Seberapa sering N/A?");
                    break;
                }
                case 3:{
                    p.update("Membaca 5 s (bawaan)…");data.put("default",stats(inventory(s,5000,null)));
                    p.update("Membaca 5 s (phase+frequency)…");
                    InventoryParameter param=new InventoryParameter();param.setResultData(new InventoryParameter.ResultData().setNeedPhase(true).setNeedFrequencyPoint(true));
                    data.put("with_phase_frequency",stats(inventory(s,5000,param))).put("needs_operator",true);
                    break;
                }
                case 4:{
                    data.put("before",radioState(s));
                    if(o.optBoolean("apply_profile")){
                        String cfg=db.state("config","");if(cfg.isEmpty())throw new Exception("Belum ada profil tersimpan (mulai layanan sekali dengan ERP).");
                        JSONObject parameters=Json.parse(cfg).getJSONObject("hardware_profile").getJSONObject("parameters");JSONObject radio=parameters.optJSONObject("radio");
                        if(radio==null)throw new Exception("Profil tersimpan tidak punya setelan radio.");
                        Reader adapter=new Reader(false);adapter.attach(s);
                        List<String> ants=new ArrayList<>();JSONObject power=radio.optJSONObject("antenna_power_dbm");if(power!=null)for(Iterator<String> it=power.keys();it.hasNext();)ants.add(it.next());
                        try{data.put("apply_report",RadioSetup.apply(adapter,radio,ants));}catch(RadioSetup.Failure f){data.put("apply_report",f.report).put("apply_failed",f.getMessage());}
                        data.put("after_apply",radioState(s));
                    }
                    s.free();SystemClock.sleep(500);s=open();data.put("after_free_init",radioState(s)).put("needs_operator",true).put("question","Apakah setGen2/TagFocus persisten setelah free+init? Bandingkan dengan sesudah aplikasi demo vendor.");
                    break;
                }
                case 5:{
                    data.put("version",s.getVersion()).put("hardware_version",s.getHardwareVersion());int before=s.getFrequencyMode();data.put("region_before",before);
                    if(o.optBoolean("allow_region")){int want=o.optInt("region",63);boolean set=s.setFrequencyMode(want);int after=s.getFrequencyMode();boolean restore=s.setFrequencyMode(before);
                        data.put("region_wanted",want).put("set_ok",set).put("region_after",after).put("accepted",set&&after==want).put("restore_ok",restore).put("region_restored",s.getFrequencyMode());}
                    data.put("needs_operator",true).put("question","Kode region 63 (0x3F) = Indonesia 920–923 MHz? Bukan 0x02 China2 920–925.");
                    break;
                }
                case 6:{
                    JSONArray rows=new JSONArray();List<AntennaState> ants=s.getANT();
                    if(ants!=null)for(AntennaState a:ants){int orig=s.getAntennaPower(a.getAntennaName());JSONArray steps=new JSONArray();
                        for(int v:new int[]{5,10,15,16,20,25,26,30,33}){boolean ok=s.setAntennaPower(a.getAntennaName(),v);steps.put(Json.obj("set",v,"ok",ok,"readback",s.getAntennaPower(a.getAntennaName())));}
                        boolean restored=s.setAntennaPower(a.getAntennaName(),orig);rows.put(Json.obj("antenna",a.getAntennaName().name(),"original",orig,"steps",steps,"restore_ok",restored,"restored",s.getAntennaPower(a.getAntennaName())));}
                    data.put("antennas",rows).put("needs_operator",false);
                    break;
                }
                case 7:return rate(s,data,p);
                case 8:return gpio(s,data,o,p);
                default:throw new IllegalArgumentException("Butir 1..9");
            }
        }finally{try{s.free();}catch(Throwable ignored){/* bebaskan modul */}}
        return data;
    }
    private static JSONObject stats(List<Read> reads){
        int phase=0,freq=0;long minC=Long.MAX_VALUE,maxC=0,sumC=0,minDt=Long.MAX_VALUE,maxDt=Long.MIN_VALUE;
        for(Read r:reads){if(r.phase!=0)phase++;if(r.freq!=0)freq++;minC=Math.min(minC,r.count);maxC=Math.max(maxC,r.count);sumC+=r.count;long dt=r.wall-r.ts;minDt=Math.min(minDt,dt);maxDt=Math.max(maxDt,dt);}
        return Json.obj("reads",reads.size(),"count_min",reads.isEmpty()?0:minC,"count_max",maxC,"count_mean",reads.isEmpty()?0:sumC/(double)reads.size(),"phase_nonzero",phase,"frequency_nonzero",freq,"wall_minus_sdk_timestamp_ms_min",reads.isEmpty()?0:minDt,"wall_minus_sdk_timestamp_ms_max",reads.isEmpty()?0:maxDt);
    }
    private static JSONObject radioState(RFIDWithUHFA4 s){
        FastInventoryEntity fi=null;try{fi=s.getFastInventoryMode();}catch(Throwable ignored){/* tidak didukung */}
        Map<String,Integer> g=Reader.gen2Map(s.getGen2());
        return Json.obj("gen2",g==null?null:new JSONObject(g),"tag_focus",s.getTagFocus(),"fast_id",s.getFastId(),"rf_link",s.getRFLink(),"fast_inventory_cr",fi==null?null:fi.getCr(),"region",s.getFrequencyMode());
    }
    private JSONObject rate(RFIDWithUHFA4 s,JSONObject data,Progress p) throws Exception{
        enableAll(s,data);
        // (a) callback kosong
        AtomicLong a=new AtomicLong();Set<String> tags=Collections.synchronizedSet(new HashSet<>());
        s.setInventoryCallback(t->{if(t!=null){a.incrementAndGet();if(tags.size()<5000)tags.add(t.getEPC());}});
        p.update("Putaran (a) callback kosong 10 s…");if(!s.startInventoryTag())throw new Exception("startInventoryTag gagal");SystemClock.sleep(10000);s.stopInventory();SystemClock.sleep(300);
        data.put("a_empty_callback",Json.obj("reads",a.get(),"reads_per_s",a.get()/10.0,"distinct_tags",tags.size()));
        // (b) SQLite per bacaan (pola 0.4) di DB sementara
        String name="bench-callback-"+UUID.randomUUID()+".db";
        SQLiteDatabase d=ctx.openOrCreateDatabase(name,0,null);d.execSQL("CREATE TABLE r(epc TEXT,ant TEXT,rssi TEXT)");
        AtomicLong b=new AtomicLong(),nanos=new AtomicLong(),maxNanos=new AtomicLong();
        s.setInventoryCallback(t->{if(t!=null){long t0=System.nanoTime();synchronized(d){d.execSQL("INSERT INTO r VALUES(?,?,?)",new Object[]{t.getEPC(),t.getAnt(),t.getRssi()});}long dt=System.nanoTime()-t0;b.incrementAndGet();nanos.addAndGet(dt);maxNanos.accumulateAndGet(dt,Math::max);}});
        p.update("Putaran (b) SQLite per bacaan 10 s…");if(!s.startInventoryTag())throw new Exception("startInventoryTag gagal");SystemClock.sleep(10000);s.stopInventory();SystemClock.sleep(300);
        d.close();ctx.deleteDatabase(name);
        data.put("b_sqlite_per_read",Json.obj("reads",b.get(),"reads_per_s",b.get()/10.0,"insert_avg_us",b.get()==0?0:nanos.get()/b.get()/1000,"insert_max_us",maxNanos.get()/1000));
        // (c) antrean RAM agent 0.5
        ReadQueue<RawRead> q=new ReadQueue<>(20000);
        s.setInventoryCallback(t->{if(t!=null)q.offer(new RawRead(t.getEPC(),t.getTid(),t.getAnt(),t.getRssi(),SystemClock.elapsedRealtimeNanos(),System.currentTimeMillis()));});
        p.update("Putaran (c) antrean RAM 0.5 10 s…");if(!s.startInventoryTag())throw new Exception("startInventoryTag gagal");
        long drained=0;long end=SystemClock.elapsedRealtime()+10000;List<RawRead> buf=new ArrayList<>();
        while(SystemClock.elapsedRealtime()<end){buf.clear();drained+=q.drainTo(buf,20000);SystemClock.sleep(20);}
        s.stopInventory();SystemClock.sleep(300);buf.clear();drained+=q.drainTo(buf,20000);
        data.put("c_ram_queue",Json.obj("offered",q.offered(),"drained",drained,"dropped",q.dropped(),"reads_per_s",q.offered()/10.0));
        data.put("gen2",Reader.gen2Map(s.getGen2())==null?null:new JSONObject(Reader.gen2Map(s.getGen2()))).put("needs_operator",true).put("question","Ada selisih laju (a) vs (b)? Bacaan terbuang di (c)?");
        return data;
    }
    private static long pct(List<Long> v,double q){if(v.isEmpty())return 0;List<Long> s=new ArrayList<>(v);Collections.sort(s);return s.get(Math.min(s.size()-1,(int)Math.floor(q*(s.size()-1))));}
    private static JSONObject timing(RFIDWithUHFA4 s,int n){List<Long> us=new ArrayList<>();int nulls=0;for(int i=0;i<n;i++){long t0=System.nanoTime();List<GPIStateEntity> v=s.inputStatus();us.add((System.nanoTime()-t0)/1000);if(v==null)nulls++;SystemClock.sleep(5);}
        return Json.obj("calls",n,"null_results",nulls,"p50_us",pct(us,0.5),"p95_us",pct(us,0.95),"max_us",pct(us,1.0));}
    private JSONObject gpio(RFIDWithUHFA4 s,JSONObject data,JSONObject o,Progress p) throws Exception{
        Map<String,int[]> idle=new TreeMap<>();
        for(int i=0;i<100;i++){List<GPIStateEntity> v=s.inputStatus();if(v!=null)for(GPIStateEntity e:v){int[] c=idle.get(e.getGpiName());if(c==null){c=new int[2];idle.put(e.getGpiName(),c);}c[e.getGpiState()==0?0:1]++;}SystemClock.sleep(20);}
        JSONObject levels=new JSONObject();for(Map.Entry<String,int[]> e:idle.entrySet())levels.put(e.getKey(),Json.obj("level0",e.getValue()[0],"level1",e.getValue()[1]));
        data.put("idle_levels",levels);
        p.update("Mengukur inputStatus() — inventory mati…");data.put("timing_inventory_off",timing(s,200));
        s.setInventoryCallback(t->{});if(s.startInventoryTag()){p.update("Mengukur inputStatus() — inventory menyala…");data.put("timing_inventory_on",timing(s,200));s.stopInventory();SystemClock.sleep(300);}
        p.update("15 s: potong sinar A lalu B…");
        JSONArray edges=new JSONArray();Map<String,Integer> last=new HashMap<>();long end=SystemClock.elapsedRealtime()+15000;
        while(SystemClock.elapsedRealtime()<end){List<GPIStateEntity> v=s.inputStatus();long t=SystemClock.elapsedRealtime();if(v!=null)for(GPIStateEntity e:v){Integer old=last.put(e.getGpiName(),e.getGpiState());if(old!=null&&old!=e.getGpiState()&&edges.length()<500)edges.put(Json.obj("gpi",e.getGpiName(),"from",old,"to",e.getGpiState(),"t_mono",t));}SystemClock.sleep(10);}
        data.put("edges_15s",edges);
        if(o.optBoolean("cycle_gpo")){JSONArray outs=new JSONArray();for(int n=1;n<=4;n++){p.update("GPO "+n+" menyala 1,5 s…");boolean on=out(s,n,true);SystemClock.sleep(1500);boolean off=out(s,n,false);SystemClock.sleep(500);outs.put(Json.obj("output",n,"on_ok",on,"off_ok",off));}data.put("gpo_cycle",outs);}
        data.put("needs_operator",true).put("question","Terminal mana = GPI1..4 / GPO1..4? Level saat sinar terhalang? Latensi p95 cukup untuk polling ≤ 20 ms?");
        return data;
    }
    private static boolean out(RFIDWithUHFA4 s,int n,boolean on){switch(n){case 1:return on?s.output1On():s.output1Off();case 2:return on?s.output2On():s.output2Off();case 3:return on?s.output3On():s.output3Off();default:return on?s.output4On():s.output4Off();}}
    private JSONObject builtin(JSONObject data) throws Exception{
        int[] ports={9160,9260,8080};Reader probe=new Reader(false);
        data.put("before",probe.builtinCheck(ctx,ports));
        RFIDWithUHFA4 s=RFIDWithUHFA4.getInstance();long t0=SystemClock.elapsedRealtime();boolean ok=s.init(ctx);long dt=SystemClock.elapsedRealtime()-t0;
        data.put("init_ok",ok).put("init_ms",dt).put("sys_uhf_service_enable_after",s.readTcpServiceState()).put("open_ports_after_init",new JSONArray(PortProbe.open("127.0.0.1",ports,200)));
        try{s.free();}catch(Throwable ignored){/* bebaskan */}
        data.put("needs_operator",true).put("question","Setelah reboot, apakah layanan bawaan mulai sendiri dan merebut modul sebelum agent? Cara mematikan permanen? Sandi web 8080 diganti?");
        return data;
    }

    // ------------------------------------------------------------------ simulasi (alur layar & ekspor saja)
    private static JSONObject simulated(int item){
        JSONObject d=Json.obj("simulated",true,"needs_operator",item!=6);
        try{
            switch(item){
                case 1:d.put("distinct",new JSONArray().put(Json.obj("raw","1","count",120,"parsed","1")).put(Json.obj("raw","ANT2","count",98,"parsed","2")).put(Json.obj("raw","03","count",77,"parsed","3")));break;
                case 2:d.put("locale",Locale.getDefault().toLanguageTag()).put("distinct",new JSONArray().put(Json.obj("raw","-58,30","count",40,"parsed",-58.3)).put(Json.obj("raw","N/A","count",2,"parsed",JSONObject.NULL))).put("comma_decimal",40).put("missing_or_na",2);break;
                case 7:d.put("a_empty_callback",Json.obj("reads_per_s",900)).put("c_ram_queue",Json.obj("dropped",0));break;
                case 8:d.put("timing_inventory_off",Json.obj("p95_us",800)).put("edges_15s",new JSONArray().put(Json.obj("gpi","GPI1","from",0,"to",1,"t_mono",1000)));break;
                default:d.put("note","data tiruan");break;
            }
        }catch(JSONException e){throw new IllegalStateException(e);}
        return d;
    }
}
