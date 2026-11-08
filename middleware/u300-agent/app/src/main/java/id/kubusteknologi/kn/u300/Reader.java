package id.kubusteknologi.kn.u300;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.SystemClock;
import com.rscja.deviceapi.RFIDWithUHFA4;
import com.rscja.deviceapi.entity.AntennaState;
import com.rscja.deviceapi.entity.Gen2Entity;
import com.rscja.deviceapi.entity.GPIStateEntity;
import com.rscja.deviceapi.enums.AntennaEnum;
import org.json.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import id.kubusteknologi.kn.u300.core.PortProbe;
import id.kubusteknologi.kn.u300.core.RadioSetup;
import id.kubusteknologi.kn.u300.core.RawRead;
import id.kubusteknologi.kn.u300.core.ReadQueue;

/**
 * Batas integrasi SDK Chainway (RFIDWithUHFA4, AAR 20251103). Callback inventory HANYA menyalin string &
 * cap waktu ke {@link ReadQueue} (AUD-MW-24). Setelan radio = set + baca ulang (AUD-MW-04). Signature diperiksa
 * dengan javap terhadap AAR; perilaku firmware U300 dibuktikan lewat uji meja K-RFID-03 (bukan di sini).
 */
final class Reader implements RadioSetup.Port {
    /** Paket layanan UHF bawaan yang dimatikan SDK saat init bila {@code sys.uhf.service.enable=1} [AAR]. */
    static final String BUILTIN_PACKAGE="cn.cw.uhf.tcpserver";
    private RFIDWithUHFA4 sdk;
    private final boolean simulation;
    final Map<String,Integer> simLevels=new ConcurrentHashMap<>();
    private long gpiCalls,gpiNanos,gpiMaxNanos,gpiFailures;
    private JSONArray setupReport=new JSONArray();
    private JSONObject builtin=new JSONObject();
    Reader(boolean sim){simulation=sim;}

    /** Pemeriksaan layanan UHF bawaan (audit §7, uji meja butir 9) — hanya API yang ada di AAR + socket standar. */
    JSONObject builtinCheck(Context context,int[] ports){
        JSONObject o=new JSONObject();
        try{
            o.put("checked_at",Json.now());
            if(simulation){o.put("mode","simulation");return o;}
            String prop="";
            try{prop=RFIDWithUHFA4.getInstance().readTcpServiceState();}catch(Throwable e){prop="error:"+e.getClass().getSimpleName();}
            o.put("sys_uhf_service_enable",prop);
            boolean installed;
            try{context.getPackageManager().getPackageInfo(BUILTIN_PACKAGE,0);installed=true;}catch(PackageManager.NameNotFoundException e){installed=false;}
            o.put("builtin_package_installed",installed).put("open_ports",new JSONArray(PortProbe.open("127.0.0.1",ports,200)));
        }catch(JSONException e){throw new IllegalStateException(e);}
        builtin=o;return o;
    }
    JSONObject builtin(){return builtin;}
    /** Uji meja: pakai instance SDK milik Bench untuk adapter RadioSetup.Port (tanpa start inventory agent). */
    synchronized void attach(RFIDWithUHFA4 instance){sdk=instance;}
    JSONArray setupReport(){return setupReport;}

    synchronized void start(Context context,Config config,ReadQueue<RawRead> queue) throws Exception{
        if(simulation){setupReport=RadioSetup.apply(new SimRadio(),config.radio,config.antennas);return;}
        sdk=RFIDWithUHFA4.getInstance();
        if(!sdk.init(context))throw new Exception("SDK init gagal. Kemungkinan modul UHF dipegang layanan bawaan ("+BUILTIN_PACKAGE+", sys.uhf.service.enable="+builtin.optString("sys_uhf_service_enable","?")+", port terbuka "+builtin.optJSONArray("open_ports")+"). Lihat dokumen 03 §Layanan UHF bawaan.");
        if(config.indicatorsEnabled){output(config.greenOut,false);if(config.yellowOut>0)output(config.yellowOut,false);if(config.buzzerOut>0)output(config.buzzerOut,false);output(config.redOut,true);}
        List<AntennaState> ants=sdk.getANT();if(ants==null||ants.isEmpty())throw new Exception("Daftar antena tidak tersedia");
        Set<String> found=new HashSet<>();
        for(AntennaState a:ants){String id=String.valueOf(a.getAntennaName().getValue());boolean enabled=config.antennas.contains(id);a.setEnable(enabled);if(enabled)found.add(id);}
        if(!found.containsAll(config.antennas)||!sdk.setANT(ants))throw new Exception("Konfigurasi antena gagal");
        List<AntennaState> verified=sdk.getANT();if(verified==null)throw new Exception("Readback antena gagal");
        for(AntennaState a:verified){if(a.isEnable()!=config.antennas.contains(String.valueOf(a.getAntennaName().getValue())))throw new Exception("Readback antena tidak cocok");}
        setupReport=RadioSetup.apply(this,config.radio,config.antennas);
        // AUD-MW-24: callback SDK hanya menyalin. Tanpa lock global, tanpa SQLite, tanpa parse.
        sdk.setInventoryCallback(t->{if(t!=null)queue.offer(new RawRead(t.getEPC(),t.getTid(),t.getAnt(),t.getRssi(),SystemClock.elapsedRealtimeNanos(),System.currentTimeMillis()));});
        if(!sdk.startInventoryTag())throw new Exception("SDK inventory gagal");
    }

    /** Level GPI1..GPI4. Waktu panggilan dicatat (uji latensi polling, uji meja butir 8). */
    synchronized Map<String,Integer> inputs(){
        Map<String,Integer> m=new HashMap<>();
        if(simulation){m.putAll(simLevels);return m;}
        if(sdk==null)return m;
        long t0=System.nanoTime();List<GPIStateEntity> values;
        try{values=sdk.inputStatus();}finally{long dt=System.nanoTime()-t0;gpiCalls++;gpiNanos+=dt;gpiMaxNanos=Math.max(gpiMaxNanos,dt);}
        if(values==null){gpiFailures++;throw new IllegalStateException("GPI tidak tersedia");}
        for(GPIStateEntity e:values)m.put(e.getGpiName(),e.getGpiState());return m;
    }
    synchronized JSONObject gpiStats(){return Json.obj("calls",gpiCalls,"avg_us",gpiCalls==0?0:gpiNanos/gpiCalls/1000,"max_us",gpiMaxNanos/1000,"failures",gpiFailures);}
    synchronized void output(int n,boolean on){if(simulation||n<1)return;if(sdk==null)throw new IllegalStateException("Radio belum siap");boolean ok;
        switch(n){case 1:ok=on?sdk.output1On():sdk.output1Off();break;case 2:ok=on?sdk.output2On():sdk.output2Off();break;case 3:ok=on?sdk.output3On():sdk.output3Off();break;case 4:ok=on?sdk.output4On():sdk.output4Off();break;default:throw new IllegalArgumentException("Output 1..4");}if(!ok)throw new IllegalStateException("GPO gagal");}
    synchronized void stop(){if(sdk!=null){try{if(!sdk.stopInventory())throw new IllegalStateException("Stop inventory tidak dikonfirmasi");}finally{sdk.free();sdk=null;}}}

    // ------------------------------------------------------------ RadioSetup.Port (SDK)
    private static AntennaEnum ant(String id){return AntennaEnum.getValue(Integer.parseInt(id));}
    public int getRegion(){return sdk.getFrequencyMode();}
    public boolean setRegion(int code){return sdk.setFrequencyMode(code);}
    public int getPower(String antenna){return sdk.getAntennaPower(ant(antenna));}
    public boolean setPower(String antenna,int dbm){return sdk.setAntennaPower(ant(antenna),dbm);}
    static Map<String,Integer> gen2Map(Gen2Entity g){
        Map<String,Integer> m=new LinkedHashMap<>();if(g==null)return null;
        m.put("query_session",g.getQuerySession());m.put("query_target",g.getQueryTarget());m.put("q",g.getQ());m.put("start_q",g.getStartQ());m.put("min_q",g.getMinQ());m.put("max_q",g.getMaxQ());
        m.put("query_sel",g.getQuerySel());m.put("query_dr",g.getQueryDR());m.put("query_m",g.getQueryM());m.put("query_trext",g.getQueryTRext());m.put("link_frequency",g.getLinkFrequency());
        m.put("select_target",g.getSelectTarget());m.put("select_action",g.getSelectAction());m.put("select_truncate",g.getSelectTruncate());
        return m;
    }
    public Map<String,Integer> getGen2(){return gen2Map(sdk.getGen2());}
    public boolean setGen2(Map<String,Integer> v){
        Gen2Entity g=sdk.getGen2();if(g==null)return false;
        g.setQuerySession(v.get("query_session"));g.setQueryTarget(v.get("query_target"));g.setQ(v.get("q"));g.setStartQ(v.get("start_q"));g.setMinQ(v.get("min_q"));g.setMaxQ(v.get("max_q"));
        g.setQuerySel(v.get("query_sel"));g.setQueryDR(v.get("query_dr"));g.setQueryM(v.get("query_m"));g.setQueryTRext(v.get("query_trext"));g.setLinkFrequency(v.get("link_frequency"));
        g.setSelectTarget(v.get("select_target"));g.setSelectAction(v.get("select_action"));g.setSelectTruncate(v.get("select_truncate"));
        return sdk.setGen2(g);
    }
    public int getTagFocus(){return sdk.getTagFocus();}
    public boolean setTagFocus(boolean on){return sdk.setTagFocus(on);}
    public int getFastId(){return sdk.getFastId();}
    public boolean setFastId(boolean on){return sdk.setFastID(on);}
    public int getRfLink(){return sdk.getRFLink();}
    public boolean setRfLink(int value){return sdk.setRFLink(value);}
    public boolean setFilter(int bank,int ptr,int len,String data){return sdk.setFilter(bank,ptr,len,data);}

    /** Radio tiruan untuk mode simulasi (tidak memakai modul). */
    static final class SimRadio implements RadioSetup.Port {
        int region=2,tagFocus=1,fastId=0,rfLink=0;final Map<String,Integer> power=new HashMap<>();final Map<String,Integer> gen2=new LinkedHashMap<>();
        SimRadio(){for(int i=1;i<=16;i++)power.put(String.valueOf(i),30);for(String k:RadioSetup.GEN2_KEYS)gen2.put(k,k.equals("query_session")?1:0);}
        public int getRegion(){return region;}public boolean setRegion(int c){region=c;return true;}
        public int getPower(String a){return power.get(a);}public boolean setPower(String a,int d){power.put(a,d);return true;}
        public Map<String,Integer> getGen2(){return new LinkedHashMap<>(gen2);}public boolean setGen2(Map<String,Integer> all){gen2.putAll(all);return true;}
        public int getTagFocus(){return tagFocus;}public boolean setTagFocus(boolean on){tagFocus=on?1:0;return true;}
        public int getFastId(){return fastId;}public boolean setFastId(boolean on){fastId=on?1:0;return true;}
        public int getRfLink(){return rfLink;}public boolean setRfLink(int v){rfLink=v;return true;}
        public boolean setFilter(int b,int p,int l,String d){return true;}
    }
}
