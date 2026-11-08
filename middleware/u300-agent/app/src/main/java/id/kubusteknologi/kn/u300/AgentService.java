package id.kubusteknologi.kn.u300;

import android.app.*;
import android.content.*;
import android.os.*;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;
import id.kubusteknologi.kn.u300.core.*;

/**
 * Agent 0.5.0-lab. Capture tahan lama sebelum transport; worker jaringan terpisah.
 * Thread: (1) callback SDK → {@link ReadQueue} (salin saja, AUD-MW-24); (2) kontrol tiap {@code gpi_poll_ms}:
 * polling GPI + debounce, kuras antrean bacaan, {@link GatePipeline} (photo-eye utama + cadangan RF, ringkasan),
 * tulis SQLite (tepi/draf/close), indikator 4 GPO; (3) jaringan: config, multi-batch, close, gate-state, telemetry.
 */
public final class AgentService extends Service implements GatePipeline.Store {
    static volatile AgentService active;
    static volatile String screen="Layanan berhenti.";
    private final ScheduledExecutorService control=Executors.newSingleThreadScheduledExecutor();
    private final ScheduledExecutorService network=Executors.newSingleThreadScheduledExecutor();
    private final Object lock=new Object();
    private Journal db;private Provision provision;private Reader reader;private Api api;private ClockSync clock;
    private volatile Config config,pendingConfig;
    private volatile boolean recoveryRequested,running,online,halted,destroying,configCheckNow,latchedCache,forceIncomplete;
    private volatile String error="",radio="stopped",signal=Indicator.UNKNOWN,transport="offline",sensorHealth="-",bootId;
    private PowerManager.WakeLock wake;
    private ReadQueue<RawRead> queue;private GatePipeline pipeline;private BeamDebouncer debA,debB;
    private String passage,current,lastLatchId="";
    private volatile long greenUntil,yellowUntil,buzzerUntil,lastConfig,lastTelemetry,nextNetwork;
    private int failures;private long lastScreen,lastPoll,maxPollGapMs,lastDropped,seqGaps;
    private volatile long cachedPending,cachedPendingBytes,cachedQuarantined,cachedRejected;
    private volatile int bodyCap=Integer.MAX_VALUE;   // 413 → batas body adaptif (server lebih ketat dari profil)
    private volatile JSONObject pipelineStats=new JSONObject();
    private boolean[] lastOutputs;
    private final List<long[]> simSteps=new ArrayList<>();private final List<Runnable> simActions=new ArrayList<>();

    @Override public void onCreate(){
        super.onCreate();active=this;provision=new Provision(this);db=new Journal(this,provision.simulation());db.recover();halted="true".equals(db.state("paused","false"));
        latchedCache="true".equals(db.state("latched","true"));bootId=UUID.randomUUID().toString();
        db.audit("Agent "+BuildConfig.VERSION_NAME+" mulai; boot_id "+bootId);
        reader=new Reader(provision.simulation());api=new Api(provision);
        clock=new ClockSync(new ClockSync.Source(){public long mono(){return SystemClock.elapsedRealtime();}public long deviceWall(){return System.currentTimeMillis();}},2000,120000);
        api.clock=clock;api.mono=SystemClock::elapsedRealtime;
        NotificationManager nm=getSystemService(NotificationManager.class);nm.createNotificationChannel(new NotificationChannel("gate","KN U300 Agent",NotificationManager.IMPORTANCE_LOW));
        PendingIntent pi=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        startForeground(1,new Notification.Builder(this,"gate").setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("KN U300 Agent").setContentText("Reader aktif • buka untuk status").setContentIntent(pi).build());
        wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"KN:Reader");wake.acquire(10*60*1000L);
        control.execute(this::loop);
        network.scheduleWithFixedDelay(this::sync,0,1000,TimeUnit.MILLISECONDS);
    }
    @Override public int onStartCommand(Intent i,int flags,int id){return START_STICKY;}
    @Override public IBinder onBind(Intent i){return null;}
    private static long mono(){return SystemClock.elapsedRealtime();}
    private String timestamp(){return Envelope.iso(clock.now());}
    private boolean timeGood(){return clock.good(mono());}
    private void fault(String message){halted=true;error=message;greenUntil=0;yellowUntil=0;signal=Indicator.UNKNOWN;
        try{synchronized(lock){if(passage!=null)db.markGap(passage);if(current!=null)db.setState("ineligible:"+current,"true");}db.audit(message);}
        catch(Exception storageFailure){error=message+" Penyimpanan diagnosis juga gagal.";}
    }

    // =============================================================== loop kontrol
    private void loop(){
        long start=mono();
        try{tick();}finally{
            if(!destroying){Config c=config;long period=c==null?100:c.gpiPollMs;long delay=Math.max(1,period-(mono()-start));
                try{control.schedule(this::loop,delay,TimeUnit.MILLISECONDS);}catch(RejectedExecutionException ignored){/* layanan berhenti */}}
        }
    }
    private void tick(){
        if(destroying)return;
        try{
            if(!wake.isHeld())wake.acquire(10*60*1000L);
            long now=mono();Config c=config;
            if(c!=null){
                if((halted||pendingConfig!=null)&&running)stopCapture(now);
                synchronized(lock){if(pendingConfig!=null&&!running&&db.settled()&&!"true".equals(db.state("contract_block","false"))){
                    config=pendingConfig;pendingConfig=null;current=null;greenUntil=0;yellowUntil=0;lastOutputs=null;
                    db.setState("config",config.raw.toString());db.setState("pending_config","");db.audit("Konfigurasi diterapkan setelah antrean selesai: "+config.version);
                    halted="true".equals(db.state("paused","false"));error="";c=config;
                }}
                if(!halted)startReader();
                if(running){
                    runSimulation(now);
                    List<Object> events=new ArrayList<>();
                    pollSensors(c,now,events);drainReads(events);
                    Collections.sort(events,(x,y)->Long.compare(at(x),at(y)));
                    for(Object e:events){if(e instanceof Sample)pipeline.onSample((Sample)e);else pipeline.onEdge((BeamDebouncer.Edge)e);}
                    long dropped=queue.dropped();if(dropped>lastDropped){pipeline.markIncomplete();lastDropped=dropped;}
                    pipeline.machine().setInhibited(!online&&!c.policy.optBoolean("capture_offline_allowed"));
                    pipeline.tick(now);
                }
                outputs(c,now);
            }
            if(now-lastScreen>=1000){lastScreen=now;refreshCounts();if(running&&c!=null)storageGuard(c);if(pipeline!=null)pipelineStats=pipeline.stats(now);screen();}
        }catch(Exception e){fault("Kontrol perangkat gagal ("+e.getClass().getSimpleName()+"); periksa diagnosis.");radio="error";screen=error;}
    }
    private static long at(Object o){return o instanceof Sample?((Sample)o).tMono:((BeamDebouncer.Edge)o).tMono;}
    private void pollSensors(Config c,long now,List<Object> out){
        if("rf_only".equals(c.sensorMode))return;
        if(lastPoll>0)maxPollGapMs=Math.max(maxPollGapMs,now-lastPoll);lastPoll=now;
        Map<String,Integer> v;
        try{v=reader.inputs();}catch(Exception e){pipeline.sensorUnavailable(now,"inputStatus gagal");debA.reset();debB.reset();return;}
        Integer a=v.get(c.pinA),b=v.get(c.pinB);
        if(a==null||b==null){pipeline.sensorUnavailable(now,"pin "+c.pinA+"/"+c.pinB+" tidak terbaca");debA.reset();debB.reset();return;}
        BeamDebouncer.Edge ea=debA.sample(a==c.activeState,now),eb=debB.sample(b==c.activeState,now);
        if(ea!=null)out.add(ea);if(eb!=null)out.add(eb);
    }
    private void drainReads(List<Object> out){
        List<RawRead> raw=new ArrayList<>();queue.drainTo(raw,20000);
        for(RawRead r:raw)out.add(pipeline.parse(r));
    }
    private void startReader(){
        if(running||halted||config==null||pendingConfig!=null)return;
        Config c=config;boolean sim=provision.simulation();
        try{
            JSONObject builtin=reader.builtinCheck(this,c.builtinPorts);
            JSONArray open=builtin.optJSONArray("open_ports");
            if(!sim&&open!=null&&open.length()>0&&"block".equals(c.builtinAction)){radio="error";fault("Layanan UHF bawaan U300 tampak aktif (port "+open+" terbuka, sys.uhf.service.enable="+builtin.optString("sys_uhf_service_enable")+"). Hentikan layanan bawaan (dokumen 03 §Layanan UHF bawaan), lalu Lanjutkan capture.");return;}
            queue=new ReadQueue<>(c.readQueue);lastDropped=0;
            pipeline=new GatePipeline(c.pipeline,this,clock::wallAt,clock::good);
            debA=new BeamDebouncer("A",c.minBlockMs,c.minClearMs);debB=new BeamDebouncer("B",c.minBlockMs,c.minClearMs);
            sensorHealth=pipeline.machine().health();
            if(sim){int clear=1-c.activeState;if(!c.pinA.isEmpty())reader.simLevels.put(c.pinA,clear);if(!c.pinB.isEmpty())reader.simLevels.put(c.pinB,clear);}
            running=true;
            reader.start(this,c,queue);
            if(!sim){List<Integer> still=PortProbe.open("127.0.0.1",c.builtinPorts,200);
                if(!still.isEmpty()){if("block".equals(c.builtinAction)){running=false;reader.stop();radio="error";fault("Layanan UHF bawaan masih aktif setelah init (port "+still+"); capture tidak dimulai.");return;}db.audit("PERINGATAN: port layanan bawaan "+still+" masih terbuka setelah init (action=warn).");}}
            radio="ready";lastOutputs=null;db.audit("Inventory dimulai ("+c.sensorMode+"); setelan radio: "+reader.setupReport());
        }catch(RadioSetup.Failure f){running=false;try{reader.stop();}catch(Exception ignored){}db.audit("Laporan setelan radio: "+f.report);fault(f.getMessage()+" — capture tidak dimulai (fail-closed).");radio="error";}
        catch(Exception e){running=false;try{reader.stop();}catch(Exception ignored){}fault(e.getMessage()!=null&&e.getMessage().startsWith("SDK init")?e.getMessage():"Reader gagal diinisialisasi; periksa SDK/firmware ("+e.getMessage()+").");radio="error";}
    }
    /** Hentikan capture: lintasan aktif ditutup sebagai tidak lengkap (bukti terpotong). */
    private void stopCapture(long now){
        synchronized(lock){if(pipeline!=null&&pipeline.currentPassage()!=null){forceIncomplete=true;pipeline.markIncomplete();pipeline.manualClose(now);}greenUntil=0;yellowUntil=0;}
        try{outputs(config,now);}catch(Exception ignored){/* GPO gagal: dicatat lewat fault berikutnya */}
        synchronized(lock){running=false;}
        reader.stop();radio="stopped";pipeline=null;
    }
    private void storageGuard(Config c){
        if(cachedPendingBytes+4096>c.maxQueue||db.diskBytes()>256L*1024*1024||new StatFs(getFilesDir().getAbsolutePath()).getAvailableBytes()<64L*1024*1024)
            fault("Penyimpanan mencapai batas; capture dihentikan. Antrean dipertahankan.");
    }
    private void refreshCounts(){cachedPending=db.count("status='pending'");cachedPendingBytes=db.pendingBytes();cachedQuarantined=db.count("status='quarantined'");cachedRejected=db.count("status='rejected'");}
    private void outputs(Config c,long now){
        if(c==null)return;
        String wanted=Indicator.signal(latchedCache,halted,now,greenUntil,yellowUntil);signal=wanted;
        boolean[] outs=Indicator.outputs(wanted,now<buzzerUntil);
        if(Arrays.equals(outs,lastOutputs))return;
        if(c.indicatorsEnabled&&!provision.simulation()&&running){
            int[] pins={c.greenOut,c.yellowOut,c.redOut,c.buzzerOut};
            for(int i=0;i<4;i++)if(!outs[i]&&pins[i]>0)reader.output(pins[i],false);   // padamkan dulu, lalu nyalakan
            for(int i=0;i<4;i++)if(outs[i]&&pins[i]>0)reader.output(pins[i],true);
        }
        lastOutputs=outs;
    }
    private void screen(){
        Config c=config;JSONObject ps=pipelineStats;
        screen=(provision.simulation()?"SIMULASI — GPIO tidak diaktifkan":"PERANGKAT — U300")+" • "+BuildConfig.VERSION_NAME
            +"\nRadio: "+radio+" | ERP: "+(online?"online":transport)
            +"\nIndikator: "+Indicator.label(signal)
            +"\nGate: "+(c==null?"menunggu konfigurasi":c.gateId+" ("+c.sensorMode+")")
            +"\nPhoto-eye: "+ps.optString("sensor_health",sensorHealth)+(ps.optString("sensor_fault_detail").isEmpty()?"":" — "+ps.optString("sensor_fault_detail"))+(pipeline!=null&&pipeline.machine().rfLogicActive()?" • CADANGAN RF":"")
            +"\nState: "+ps.optString("machine_state","-")+" | Lintasan: "+(passage==null?"tidak sedang capture":passage)
            +"\nLatar: "+ps.optInt("background_size")+" EPC"+(ps.optBoolean("background_warm")?"":" (belum hangat)")+" | Dibuang: "+(queue==null?0:queue.dropped())+" | Tanpa RSSI: "+ps.optLong("rssi_missing")
            +"\nAntrean: "+cachedPending+" item, "+cachedPendingBytes+" byte | Karantina: "+cachedQuarantined+(cachedRejected>0?" | Ditolak: "+cachedRejected:"")
            +"\n"+error;
    }

    // =============================================================== GatePipeline.Store (thread kontrol)
    @Override public String newPassageId(){return UUID.randomUUID().toString();}
    @Override public void opened(String id,PassageMachine.Opening o){
        Config c=config;boolean live=online&&timeGood();String mode=live?"live":"backfill";
        JSONObject meta=Json.obj("config_version",c.version,"logical_gate_id",c.gateId,"completion_basis",c.basis,"direction","bidirectional".equals(c.direction)?"unknown":c.direction,
            "profile_id",c.raw.optString("hardware_profile_id"),"opened_at",Envelope.iso(clock.wallAt(o.tOpenMono)),"window_start",Envelope.iso(clock.wallAt(o.windowStartMono)),
            "open_reason",o.openReason,"sensor_mode",c.sensorMode,"boot_id",bootId,"agent",BuildConfig.VERSION_NAME);
        db.open(id,meta,mode);if(!live)db.setState("ineligible:"+id,"true");
        synchronized(lock){passage=id;current=id;greenUntil=0;yellowUntil=0;}
    }
    @Override public void edge(String id,JSONObject e){db.addItem(Batcher.EDGE,e.optString("edge_id"),id,e);}
    @Override public void checkpoint(String id,List<JSONObject> drafts){db.checkpoint(id,drafts);}
    @Override public void closed(String id,PassageMachine.Closing c,List<JSONObject> summaries,boolean complete){
        Config cfg=config;JSONObject p=db.rows("SELECT body,mode,complete FROM passages WHERE id=?",id).get(0);JSONObject meta=Json.parse(p.optString("body"));
        boolean ok=complete&&"1".equals(p.optString("complete"))&&!forceIncomplete;
        if("legacy_bidirectional".equals(cfg.sensorMode)&&("unknown".equals(c.direction)||"max_duration".equals(c.boundaryReason)))ok=false;
        JSONObject body=Envelope.close(meta,c,clock::wallAt,ok,p.optString("mode"),bootId,Json.obj("a",cfg.pinA,"b",cfg.pinB),cfg.activeState);
        db.finalizePassage(id,body,summaries,ok);
        db.audit("Lintasan ditutup "+id+" ("+(c.closeReason!=null?c.closeReason:c.boundaryReason)+", "+summaries.size()+" ringkasan, lengkap="+ok+")");
        synchronized(lock){passage=null;}forceIncomplete=false;
        nextNetwork=0;try{network.execute(this::sync);}catch(RejectedExecutionException ignored){/* berhenti */}
    }
    @Override public void health(String h,String detail,long t){sensorHealth=h;db.audit("Photo-eye "+h+": "+detail);}

    // =============================================================== simulasi (tanpa radio/GPIO)
    private void simAt(long at,Runnable r){synchronized(simSteps){simSteps.add(new long[]{at});simActions.add(r);}}
    private void runSimulation(long now){
        List<Runnable> due=new ArrayList<>();
        synchronized(simSteps){for(int i=0;i<simSteps.size();){if(simSteps.get(i)[0]<=now){due.add(simActions.remove(i));simSteps.remove(i);}else i++;}}
        for(Runnable r:due)r.run();
    }
    private void simBeam(long at,String sensor,boolean blocked){Config c=config;String pin="A".equals(sensor)?c.pinA:c.pinB;if(pin.isEmpty())return;int level=blocked?c.activeState:1-c.activeState;simAt(at,()->reader.simLevels.put(pin,level));}
    private void simRead(long at,String epc,String ant,double rssi){
        // RSSI berformat locale Indonesia (koma) untuk menguji parse tahan-locale (AUD-MW-23).
        String raw=String.format(new Locale("in","ID"),"%.2f",rssi);
        simAt(at,()->{if(queue!=null)queue.offer(new RawRead(epc,"SIM-TID",ant,raw,SystemClock.elapsedRealtimeNanos(),System.currentTimeMillis()));});
    }
    private void simLoad(long t0,String base,int rolls,long peakAt){
        for(int i=0;i<rolls;i++){String epc=simEpc(base,i);
            for(long k=-1500;k<=2500;k+=150){long t=peakAt+k;double r=-46-Math.abs(k)/120.0;simRead(t,epc,i%2==0?"1":"2",r);if(i%3==0&&k%450==0)simRead(t,epc,"3",r-6);}}
    }
    private static String simEpc(String base,int i){String b=(base==null?"":base.replaceAll("[^0-9A-Fa-f]","").toUpperCase(Locale.ROOT));if(b.length()<24)b=(b+"E20034120123456789ABCDEF").substring(0,24);return b.substring(0,20)+String.format(Locale.ROOT,"%04X",(Integer.parseInt(b.substring(20),16)+i)&0xFFFF);}
    void simulationGate(String name,String base){
        if(!provision.simulation())return;
        control.execute(()->{
            if(config==null||!running){error="Mulai layanan dan tunggu radio ready sebelum skenario.";return;}
            long t=mono()+300;
            switch(name){
                case "lewat":simLoad(t,base,6,t+1400);simBeam(t,"A",true);simBeam(t+1100,"B",true);simBeam(t+1800,"A",false);simBeam(t+2600,"B",false);break;
                case "lewat_kecil":simLoad(t,base,2,t+900);simBeam(t,"A",true);simBeam(t+400,"A",false);simBeam(t+1300,"B",true);simBeam(t+1700,"B",false);break;
                case "mundur":simLoad(t,base,4,t+1200);simBeam(t,"A",true);simBeam(t+1100,"B",true);simBeam(t+1700,"B",false);simBeam(t+2300,"A",false);break;
                case "batal_masuk":simBeam(t,"A",true);simBeam(t+600,"A",false);break;
                case "kosong":simBeam(t,"A",true);simBeam(t+1000,"B",true);simBeam(t+1500,"A",false);simBeam(t+2100,"B",false);break;
                case "beriringan":simLoad(t,base,4,t+1300);simLoad(t,simEpc(base,100),4,t+3200);
                    simBeam(t,"A",true);simBeam(t+1100,"B",true);simBeam(t+1800,"A",false);simBeam(t+2300,"A",true);simBeam(t+2600,"B",false);simBeam(t+3400,"B",true);simBeam(t+4100,"A",false);simBeam(t+4900,"B",false);break;
                case "b_sebelum_a":simBeam(t,"B",true);simBeam(t+500,"B",false);simLoad(t,base,4,t+2500);break;
                case "sinar_macet":simBeam(t,"A",true);break;
                case "sinar_pulih":simBeam(t,"A",false);simBeam(t,"B",false);for(int k=0;k<2;k++){long s=t+1000+k*4000;simBeam(s,"A",true);simBeam(s+1000,"B",true);simBeam(s+1700,"A",false);simBeam(s+2500,"B",false);}break;
                case "latar":for(long k=0;k<=8000;k+=300)simRead(t+k,simEpc(base,0xFFF),"3",-70);break;
                default:error="Skenario simulasi tidak dikenal.";
            }
            db.audit("SIMULASI skenario gate: "+name);
        });
    }
    void simulationTag(String epc){if(provision.simulation())control.execute(()->{if(queue!=null)queue.offer(new RawRead(epc,"SIM-TID","1","-45,00",SystemClock.elapsedRealtimeNanos(),System.currentTimeMillis()));});}
    void simulationOffline(boolean value){if(provision.simulation()){api.offline=value;if(value)invalidateLive();}}
    void simulationVerdict(String value){if(provision.simulation())api.verdict=value;}
    void simulationPending(int value){if(provision.simulation())api.simulationPending=value;}
    void simulationScenario(String value){if(provision.simulation())api.scenario=value;}
    void simulationConfig(){if(provision.simulation()){api.simulationRevision++;retryAfterRepair();}}
    void simulationAck(){if(provision.simulation()){api.resetSimulationLatch();db.audit("SIMULASI supervisor acknowledge.");}}

    // =============================================================== kontrol operator
    void finish(){control.execute(()->{if(pipeline!=null)pipeline.manualClose(mono());});}
    void pauseCapture(){control.execute(()->{synchronized(lock){halted=true;greenUntil=0;yellowUntil=0;if(current!=null)db.setState("ineligible:"+current,"true");}if(running)stopCapture(mono());db.setState("paused","true");error="Capture dijeda operator; sinkronisasi tetap berjalan.";});}
    void resumeCapture(){control.execute(()->{if(!db.state("auth_block","false").equals("true")&&!db.state("contract_block","false").equals("true")){db.setState("paused","false");halted=false;error="";}});}
    void retryAfterRepair(){
        if("true".equals(db.state("auth_block","false"))){error="Key ditolak: hentikan layanan dan perbarui provisioning terlebih dahulu.";return;}
        control.execute(()->{synchronized(lock){halted=true;greenUntil=0;yellowUntil=0;if(current!=null)db.setState("ineligible:"+current,"true");}if(running)stopCapture(mono());});
        db.audit("Operator meminta retry setelah pemeriksaan; ID/body antrean tetap.");
        recoveryRequested=true;nextNetwork=0;lastConfig=0;
    }
    private void invalidateLive(){online=false;synchronized(lock){greenUntil=0;yellowUntil=0;if(current!=null)db.setState("ineligible:"+current,"true");}}

    // =============================================================== jaringan
    private void sync(){
        if(destroying||mono()<nextNetwork||"true".equals(db.state("auth_block","false"))||(!recoveryRequested&&"true".equals(db.state("contract_block","false"))))return;
        long start=mono();
        try{
            if(config==null||recoveryRequested||configCheckNow||start-lastConfig>60000){
                configCheckNow=false;
                if(!fetchConfig())return;
                lastConfig=start;
            }
            if(destroying)return;
            online=true;transport="online";recoverInterrupted();transmitAll(start);if(destroying)return;closeReady();if(destroying)return;pollGate();
            if(start-lastTelemetry>Math.max(10,config.policy.optInt("telemetry_interval_seconds",30))*1000L){telemetry();lastTelemetry=start;}
            failures=0;nextNetwork=0;if(!halted&&pendingConfig==null)error="";
        }catch(Exception e){handleFailure(e);}
    }
    private void handleFailure(Exception e){
        invalidateLive();long backoff=Safety.retryMillis(failures++,config==null?2000:config.policy.optLong("retry_initial_seconds",2)*1000,config==null?60000:config.policy.optLong("retry_max_seconds",60)*1000);
        long delay=backoff;String label="ERP belum tersambung atau respons tidak valid. Antrean tetap tersimpan.";
        if(e instanceof Api.Failure){Api.Failure f=(Api.Failure)e;ErrorPolicy.Action a=ErrorPolicy.classify(f.status,f.code,f.retryable);
            String code=f.code.isEmpty()?"HTTP "+f.status:f.code;
            switch(a){
                case AUTH_BLOCK:db.setState("auth_block","true");transport="auth_block";fault("Device key ditolak ("+code+"); provisioning ulang diperlukan.");break;
                case CONTRACT_BLOCK:db.setState("contract_block","true");transport="contract_block";fault("Kontrak/konteks ERP ditolak ("+code+"); antrean dipertahankan untuk rekonsiliasi.");break;
                case ADMIN_DISABLED:transport="admin_disabled";break;
                case CONFIG_REQUIRED:transport="config_required";break;
                case FORBIDDEN_UNKNOWN:transport="forbidden";break;
                default:transport="offline";
            }
            delay=ErrorPolicy.delayMs(a,f.pollAfter,f.retry,backoff);label=ErrorPolicy.label(a)+" · "+e.getMessage();
        }else transport="offline";
        if(!halted)error=label;
        nextNetwork=mono()+delay;
    }
    private boolean fetchConfig() throws Exception{
        JSONObject o=api.call("GET","/device/config",null,null);Config candidate;
        try{candidate=new Config(o,provision.simulation()?"SIM-GATE":provision.gate(),provision.simulation());}
        catch(Exception invalid){recoveryRequested=false;db.setState("contract_block","true");fault("Konfigurasi ERP tidak aktif/tidak didukung: "+invalid.getMessage());return false;}
        synchronized(lock){
            if(config==null){
                String previous=db.state("config","");
                if(!previous.isEmpty()){
                    JSONObject old=Json.parse(previous);
                    if(!DecisionPolicy.sameIdentity(old,o)){db.setState("contract_block","true");recoveryRequested=false;fault("Device/site/warehouse berbeda dari histori. Migrasi diperlukan.");return false;}
                    if(old.optString("config_version").equals(candidate.version)&&!Config.fingerprint(old).equals(Config.fingerprint(o))){recoveryRequested=false;db.setState("contract_block","true");fault("Isi konfigurasi berubah tanpa perubahan versi.");return false;}
                    if(!old.optString("config_version").equals(candidate.version)&&!db.settled()){
                        try{config=new Config(old,candidate.gateId,provision.simulation());}catch(Exception legacy){config=candidate;}
                        pendingConfig=candidate;halted=true;db.setState("pending_config",o.toString());
                    }
                }
                if(config==null){config=candidate;db.setState("config",o.toString());}
            }
            else if(!DecisionPolicy.sameIdentity(config.raw,o)){db.setState("contract_block","true");recoveryRequested=false;fault("Identitas konfigurasi berubah; perlu migrasi.");return false;}
            else if(config.version.equals(candidate.version)&&!Config.fingerprint(config.raw).equals(Config.fingerprint(o))){recoveryRequested=false;db.setState("contract_block","true");fault("Isi konfigurasi berubah tanpa perubahan versi.");return false;}
            else if(!config.version.equals(candidate.version)&&(pendingConfig==null||!pendingConfig.version.equals(candidate.version))){
                greenUntil=0;yellowUntil=0;halted=true;pendingConfig=candidate;db.setState("pending_config",o.toString());error="Konfigurasi baru menunggu antrean lama selesai.";
            }
            if(recoveryRequested){db.setState("contract_block","false");recoveryRequested=false;db.audit("Konfigurasi diperiksa; retry kontrak dengan ID asli.");error="Retry berjalan; capture tetap dijeda sampai operator melanjutkan.";}
        }
        return true;
    }
    private void recoverInterrupted(){
        for(JSONObject p:db.rows("SELECT * FROM passages WHERE status='INTERRUPTED'")){
            JSONObject meta=Json.parse(p.optString("body"));String id=p.optString("id");JSONObject body;
            if(meta.has("sensor_mode")){   // lintasan 0.5: batal karena proses mati (tanpa klaim lewat), bukti tetap dikirim
                PassageMachine.Closing c=new PassageMachine.Closing();c.openReason=meta.optString("open_reason",null);c.closeReason="ABORTED";c.boundaryReason="cancelled";c.sensorHealth="degraded";
                long now=mono();c.tCloseMono=now;c.windowStartMono=now-Math.max(0,clock.now()-Json.time(meta.optString("window_start")));c.tOpenMono=c.windowStartMono;
                body=Envelope.close(meta,c,clock::wallAt,false,p.optString("mode"),bootId,null,1);
                try{body.put("window_start",meta.optString("window_start"));body.put("closing_captured_at",timestamp());}catch(JSONException e){throw new IllegalStateException(e);}
            }else{
                body=Json.obj("logical_gate_id",meta.optString("logical_gate_id"),"config_version",meta.optString("config_version"),"mode",p.optString("mode"),"closing_captured_at",timestamp(),"boundary_reason","max_duration","last_event_id",null,"observed_event_count",0,"capture_complete",false,"direction","unknown","direction_evidence",Json.obj("source","unknown","profile_binding_id",null,"sensor_sequence",new JSONArray()));
            }
            db.closePassage(id,body);db.setState("ineligible:"+id,"true");db.audit("Lintasan terputus restart dikirim sebagai tidak lengkap: "+id);
        }
    }
    private void transmitAll(long start) throws Exception{
        long deadline=start+config.uploadBudgetMs;
        while(!destroying&&mono()<deadline){if(!transmitBatch())break;}
    }
    /** @return true bila satu batch dikirim (mungkin masih ada sisa). Multi-batch per siklus (AUD-MW-01b). */
    private boolean transmitBatch() throws Exception{
        long wall=System.currentTimeMillis();
        List<JSONObject> batches=db.rows("SELECT * FROM batches WHERE due<=? OR due>? ORDER BY due,rowid LIMIT 1",String.valueOf(wall),String.valueOf(wall+86400000L));
        JSONObject batch;
        if(batches.isEmpty()){
            List<JSONObject> pend=db.rows("SELECT i.passage,p.body AS meta,p.mode FROM items i JOIN passages p ON p.id=i.passage WHERE i.status='pending' AND i.batch IS NULL ORDER BY i.rowid LIMIT 1");
            if(pend.isEmpty())return false;
            JSONObject p=pend.get(0);String pid=p.optString("passage"),batchId=UUID.randomUUID().toString();
            JSONObject base=Envelope.eventsBase(batchId,pid,Json.parse(p.optString("meta")),p.optString("mode"),0,bootId,timestamp());
            List<Batcher.Item> fit=Batcher.fit(db.pendingItems(pid,1500),base,config.maxEvents,Math.min(config.maxBody,bodyCap));
            if(fit.isEmpty()){db.setState("contract_block","true");fault("Satu item bukti melebihi max_body_bytes; perlu perbaikan konfigurasi.");return false;}
            JSONObject body=db.createBatch(batchId,pid,base,fit,bootId);
            batch=Json.obj("id",batchId,"passage",pid,"body",body.toString(),"attempt","0");
        }else batch=batches.get(0);
        String id=batch.optString("id");
        try{
            JSONObject response=api.call("POST","/events",Json.parse(batch.optString("body")),null);
            if(!id.equals(response.optString("batch_id")))throw new Exception("Batch ACK tidak sesuai");
            if(response.optBoolean("seq_gap"))seqGaps++;
            long before=db.count("batch=? AND status='pending'",id);db.acknowledgements(id,response);
            long after=db.count("batch=? AND status='pending'",id);
            if(after>0){int attempts=after<before?0:batch.optInt("attempt",0)+1;long wait=Safety.retryMillis(attempts,config.policy.optLong("retry_initial_seconds",2)*1000,config.policy.optLong("retry_max_seconds",60)*1000);db.execute("UPDATE batches SET attempt=?,due=? WHERE id=?",attempts,System.currentTimeMillis()+wait,id);}
            return true;
        }catch(Api.Failure e){
            ErrorPolicy.Action a=ErrorPolicy.classify(e.status,e.code,e.retryable);
            if(a==ErrorPolicy.Action.SPLIT_BATCH){
                if(db.count("batch=? AND status='pending'",id)<=1){db.setState("contract_block","true");fault("Satu item ditolak 413; perlu rekonsiliasi.");throw e;}
                // 413 = envelope tidak diproses. ID item tetap; item dilepas dan dirakit ulang dengan batas body separuh.
                bodyCap=Math.max(2048,Batcher.size(Json.parse(batch.optString("body")))/2);db.releaseBatch(id);db.audit("413: batch "+id+" dipecah; batas body sementara "+bodyCap+" byte.");
                return true;
            }
            if(a==ErrorPolicy.Action.PASSAGE_FROZEN){db.rejectBatch(id);return true;}
            throw e;
        }
    }
    private void closeReady() throws Exception{
        for(JSONObject p:db.rows("SELECT * FROM passages WHERE status='CLOSING' AND close_due<=? ORDER BY rowid LIMIT 10",String.valueOf(System.currentTimeMillis()))){
            if(destroying)return;
            String id=p.optString("id");if(db.unsent(id)>0)continue;JSONObject body=Json.parse(p.optString("close_body"));
            Map<String,Long> obs=db.observed(id);
            body.put("observed_event_count",obs.get(Batcher.EVENT));
            if(body.has("observed_summary_count")||obs.get(Batcher.SUMMARY)>0)body.put("observed_summary_count",obs.get(Batcher.SUMMARY));
            if(body.has("observed_edge_count")||obs.get(Batcher.EDGE)>0)body.put("observed_edge_count",obs.get(Batcher.EDGE));
            if(obs.get(Batcher.EVENT)>0)body.put("last_event_id",db.lastEventId(id));
            if(!"1".equals(p.optString("complete")))body.put("capture_complete",false);
            db.execute("UPDATE passages SET close_body=? WHERE id=?",body.toString(),id);
            try{
                JSONObject response=api.call("POST","/passages/"+id+"/close",body,p.optString("close_key"));
                if(!id.equals(response.optString("local_passage_id")))throw new Exception("Close response tidak sesuai passage");
                db.execute("UPDATE passages SET status='DECISION_PENDING',decision=? WHERE id=?",response.toString(),id);
            }catch(Api.Failure f){
                if(ErrorPolicy.classify(f.status,f.code,f.retryable)!=ErrorPolicy.Action.EVIDENCE_PENDING)throw f;
                int attempts=p.optInt("close_attempts",0)+1;db.execute("UPDATE passages SET close_attempts=?,close_due=? WHERE id=?",attempts,System.currentTimeMillis()+Safety.retryMillis(attempts,1000,60000),id);
                if(attempts==20)db.audit("Close "+id+" tertahan EVIDENCE_PENDING 20×; periksa jumlah bukti.");
            }
        }
    }
    private void pollGate() throws Exception{
        String id;synchronized(lock){id=current;}
        String base="/device/gate-state?logical_gate_id="+java.net.URLEncoder.encode(config.gateId,"UTF-8");
        acceptState(api.call("GET",base+(id==null?"":"&local_passage_id="+java.net.URLEncoder.encode(id,"UTF-8")),null,null));
        for(JSONObject p:db.rows("SELECT id FROM passages WHERE status='DECISION_PENDING' ORDER BY rowid LIMIT 3")){
            if(destroying)return;
            if(!p.optString("id").equals(id))acceptState(api.call("GET",base+"&local_passage_id="+java.net.URLEncoder.encode(p.optString("id"),"UTF-8"),null,null));
        }
    }
    private void acceptState(JSONObject state) throws Exception{
        if(!config.gateId.equals(state.optString("logical_gate_id"))||!(state.opt("latched") instanceof Boolean))throw new Exception("Gate-state tidak sesuai kontrak");
        boolean latched=state.getBoolean("latched");long nowMono=mono();
        synchronized(lock){
            if(latched!=latchedCache){latchedCache=latched;db.setState("latched",String.valueOf(latched));}
            if(latched){greenUntil=0;yellowUntil=0;String lid=state.optString("latch_id","?");if(!lid.equals(lastLatchId)){lastLatchId=lid;buzzerUntil=nowMono+config.buzzerMs;db.audit("Gate terkunci "+lid+" "+state.optJSONArray("latch_reason_codes"));}}
            else lastLatchId="";
        }
        boolean known=config.version.equals(state.optString("config_version"))||(pendingConfig!=null&&pendingConfig.version.equals(state.optString("config_version")));
        if(!known){configCheckNow=true;lastConfig=0;return;}   // AUD-MW-13: versi baru di ERP → ambil config segera, bukan offline
        synchronized(lock){
            JSONObject d=state.optJSONObject("decision");if(d==null)return;
            String id=d.optString("local_passage_id");List<JSONObject> rows=db.rows("SELECT * FROM passages WHERE id=?",id);if(rows.isEmpty())return;JSONObject p=rows.get(0);
            JSONObject meta=Json.parse(p.optString("body"));
            boolean matching=config.gateId.equals(d.optString("logical_gate_id"))&&meta.optString("config_version").equals(d.optString("config_version"))&&meta.optString("completion_basis").equals(d.optString("completion_basis"));if(!matching)return;
            if(!"DECISION_PENDING".equals(p.optString("status"))&&!"FINAL".equals(p.optString("status")))return;
            if(db.unsent(id)>0)return;
            if(d.opt("final") instanceof Boolean&&d.optBoolean("final"))db.execute("UPDATE passages SET status='FINAL',decision=? WHERE id=?",d.toString(),id);
            long now=clock.now(),expires=Json.time(d.optString("expires_at")),created=Json.time(d.optString("created_at"));
            long validity=config.policy.optInt("gate_decision_validity_seconds",5)*1000L;
            boolean fresh=timeGood()&&created<=now&&created>0&&now-created<=validity&&expires>now;
            boolean eligible=!"true".equals(db.state("ineligible:"+id,"false"));
            boolean base=pendingConfig==null&&!halted&&online&&eligible&&"live".equals(d.optString("mode"))&&"live".equals(p.optString("mode"));
            boolean currentPassage=id.equals(current)&&passage==null;
            boolean reconciled=DecisionPolicy.validGreen(state,d,meta,id,p.optString("mode"),now,validity);
            boolean green=Safety.greenAllowed(base,currentPassage,"1".equals(p.optString("complete"))&&reconciled,db.count("passage=? AND status!='acked'",id)==0,d.optBoolean("final"),d.optBoolean("allow_live_signal"),latched||d.optBoolean("latched"),fresh,matching,d.optString("verdict"),d.optString("completion_basis"));
            boolean yellow=!green&&base&&currentPassage&&fresh&&DecisionPolicy.validYellow(state,d,meta,id,p.optString("mode"),now,validity);
            String decisionId=d.optString("decision_id");
            if((green||yellow)&&!decisionId.isEmpty()&&!decisionId.equals(db.state("signaled_decision",""))){
                if(green)greenUntil=nowMono+Math.min(expires-now,validity);else yellowUntil=nowMono+Math.min(60000,config.yellowHoldMs);
                db.setState("signaled_decision",decisionId);db.audit("Keputusan ERP "+d.optString("verdict")+" untuk "+id+" → "+(green?"HIJAU":"KUNING"));
            }
            if("RED".equals(d.optString("verdict"))){greenUntil=0;yellowUntil=0;}
        }
    }
    private void telemetry() throws Exception{
        Telemetry.Values v=new Telemetry.Values();long now=mono();
        List<JSONObject> oldest=db.rows("SELECT kind,body FROM items WHERE status='pending' ORDER BY rowid LIMIT 1");
        if(!oldest.isEmpty()){JSONObject b=Json.parse(oldest.get(0).optString("body"));v.oldestPendingAt=b.optString("captured_at",b.optString("first_seen",b.optString("t_wall",null)));}
        v.eventId=UUID.randomUUID().toString();v.capturedAt=timestamp();v.configVersion=config.version;v.appBuild=BuildConfig.VERSION_NAME;v.radioState=radio;v.transport=online?"online":"offline";
        v.pendingCount=cachedPending;v.pendingBytes=cachedPendingBytes;v.freeStorage=new StatFs(getFilesDir().getAbsolutePath()).getAvailableBytes();v.uptimeSeconds=now/1000;v.timeQuality=timeGood()?"synced":"unsynced";
        v.lastErrorMessage=error;v.lastErrorRetryable=!halted;
        v.health=Json.obj("mode",provision.simulation()?"simulation":"device","signal",signal,"capture_halted",halted,"quarantined",cachedQuarantined,"rejected",cachedRejected,"firmware_android",Build.VERSION.RELEASE,
            "boot_id",bootId,"transport_state",transport,"dropped_reads",queue==null?0:queue.dropped(),"reads_offered",queue==null?0:queue.offered(),"read_queue_size",queue==null?0:queue.size(),
            "pipeline",pipelineStats,"gpi",reader.gpiStats(),"gpi_poll_max_gap_ms",maxPollGapMs,"seq_gaps",seqGaps,
            "clock",Json.obj("age_ms",clock.ageMs(now),"rtt_ms",clock.lastRttMs(),"samples",clock.samples(),"rejected",clock.rejected()),
            "radio_setup",reader.setupReport(),"builtin_service",reader.builtin(),"config",config.summary(),"locale",Locale.getDefault().toLanguageTag());
        api.call("POST","/device/telemetry",Telemetry.body(v),null);
    }
    String diagnostic(){JSONObject d=Json.parse(db.diagnostic());try{d.put("pipeline",pipelineStats).put("radio_setup",reader.setupReport()).put("builtin_service",reader.builtin()).put("boot_id",bootId);}catch(JSONException e){throw new IllegalStateException(e);}return d.toString();}
    @Override public void onDestroy(){
        destroying=true;active=null;network.shutdownNow();control.shutdown();
        synchronized(lock){try{if(pipeline!=null&&pipeline.currentPassage()!=null){forceIncomplete=true;pipeline.markIncomplete();pipeline.manualClose(mono());}greenUntil=0;yellowUntil=0;running=false;}catch(Exception ignored){}}
        try{Config c=config;if(c!=null&&c.indicatorsEnabled&&!provision.simulation()){reader.output(c.greenOut,false);if(c.yellowOut>0)reader.output(c.yellowOut,false);if(c.buzzerOut>0)reader.output(c.buzzerOut,false);reader.output(c.redOut,true);}}catch(Exception ignored){}
        try{reader.stop();}catch(Exception ignored){}
        if(wake!=null&&wake.isHeld())wake.release();screen="Layanan berhenti. Antrean tetap tersimpan.";
        new Thread(()->{try{while(!network.awaitTermination(1,TimeUnit.SECONDS)){/* Keep storage open until transport exits. */}while(!control.awaitTermination(1,TimeUnit.SECONDS)){/* Drain control. */}db.close();}catch(InterruptedException e){Thread.currentThread().interrupt();}},"kn-shutdown").start();super.onDestroy();
    }
}
