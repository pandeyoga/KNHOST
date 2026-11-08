package id.kubusteknologi.kn.u300;

import android.app.*;
import android.content.*;
import android.os.*;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;
import id.kubusteknologi.kn.u300.core.Safety;

/** Capture is durable before transport. A separate worker handles all network requests. */
public final class AgentService extends Service {
    static volatile AgentService active;
    static volatile String screen="Layanan berhenti.";
    private final ScheduledExecutorService control=Executors.newSingleThreadScheduledExecutor();
    private final ScheduledExecutorService network=Executors.newSingleThreadScheduledExecutor();
    private final Object lock=new Object();
    private Journal db;private Provision provision;private Reader reader;private Api api;private volatile Config config,pendingConfig;
    private volatile boolean recoveryRequested;
    private PowerManager.WakeLock wake;
    private volatile boolean running,online,halted,destroying;
    private volatile String error="",radio="stopped",signal="UNKNOWN";
    private String passage,current,lastEvent,direction;
    private volatile long greenUntil,timeSyncAt,lastConfig,lastTelemetry,nextNetwork;
    private long opened,lastRead,serverBase,monoBase;
    private int failures;
    private JSONArray sensorEvidence=new JSONArray();private Safety.Direction directionDetector;
    private final Map<String,Integer> inputStates=new HashMap<>();private final Map<String,Long> inputEdges=new HashMap<>();
    private String lastSignal="";
    @Override public void onCreate(){
        super.onCreate();active=this;provision=new Provision(this);db=new Journal(this,provision.simulation());db.recover();halted="true".equals(db.state("paused","false"));
        reader=new Reader(provision.simulation());api=new Api(provision);
        NotificationManager nm=getSystemService(NotificationManager.class);nm.createNotificationChannel(new NotificationChannel("gate","KN U300 Agent",NotificationManager.IMPORTANCE_LOW));
        PendingIntent pi=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
        startForeground(1,new Notification.Builder(this,"gate").setSmallIcon(android.R.drawable.stat_notify_sync).setContentTitle("KN U300 Agent").setContentText("Reader aktif • buka untuk status").setContentIntent(pi).build());
        wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"KN:Reader");wake.acquire(10*60*1000L);
        control.scheduleWithFixedDelay(this::tick,0,100,TimeUnit.MILLISECONDS);
        network.scheduleWithFixedDelay(this::sync,0,1000,TimeUnit.MILLISECONDS);
    }
    @Override public int onStartCommand(Intent i,int flags,int id){return START_STICKY;}
    @Override public IBinder onBind(Intent i){return null;}
    private long serverNow(){return timeSyncAt==0?System.currentTimeMillis():serverBase+SystemClock.elapsedRealtime()-monoBase;}
    private String timestamp(){return java.time.Instant.ofEpochMilli(serverNow()).toString();}
    private boolean timeGood(){return timeSyncAt>0&&SystemClock.elapsedRealtime()-timeSyncAt<120000;}
    private void clock(JSONObject o,long start){long remote=Json.time(o.optString("server_time"));long elapsed=SystemClock.elapsedRealtime()-start;
        if(remote>0&&elapsed<2000){serverBase=remote;monoBase=SystemClock.elapsedRealtime();timeSyncAt=monoBase;}}
    private void fault(String message){halted=true;error=message;greenUntil=0;signal="UNKNOWN";
        try{synchronized(lock){if(passage!=null)db.markGap(passage);if(current!=null)db.setState("ineligible:"+current,"true");}db.audit(message);}
        catch(Exception storageFailure){error=message+" Penyimpanan diagnosis juga gagal.";}
    }
    private void startReader(){
        if(running||halted||config==null||pendingConfig!=null)return;
        try {running=true;reader.start(this,config,this::capture);radio="ready";lastSignal="";db.audit("Inventory dimulai");}
        catch(Exception e){running=false;try{reader.stop();}catch(Exception ignored){}fault("Reader gagal diinisialisasi; periksa SDK/firmware.");radio="error";}
    }
    void simulationTag(String epc){if(provision.simulation())capture(epc,"SIM-TID","1","-45");}
    void simulationOffline(boolean value){if(provision.simulation()){api.offline=value;if(value)invalidateLive();}}
    void simulationVerdict(String value){if(provision.simulation())api.verdict=value;}
    void simulationScenario(String value){if(provision.simulation())api.scenario=value;}
    void simulationConfig(){if(provision.simulation()){api.simulationRevision++;retryAfterRepair();}}
    void simulationAck(){if(provision.simulation()){api.resetSimulationLatch();db.audit("SIMULASI supervisor acknowledge.");}}
    void finish(){control.execute(()->{synchronized(lock){close("authorized_manual");}});}
    void pauseCapture(){control.execute(()->{synchronized(lock){halted=true;greenUntil=0;if(current!=null)db.setState("ineligible:"+current,"true");close("authorized_manual");}db.setState("paused","true");error="Capture dijeda operator; sinkronisasi tetap berjalan.";});}
    void resumeCapture(){control.execute(()->{if(!db.state("auth_block","false").equals("true")&&!db.state("contract_block","false").equals("true")){db.setState("paused","false");halted=false;error="";}});}
    void retryAfterRepair(){
        if("true".equals(db.state("auth_block","false"))){error="Key ditolak: hentikan layanan dan perbarui provisioning terlebih dahulu.";return;}
        synchronized(lock){halted=true;greenUntil=0;if(current!=null)db.setState("ineligible:"+current,"true");close("max_duration");}
        db.audit("Operator meminta retry setelah pemeriksaan; ID/body antrean tetap.");
        recoveryRequested=true;nextNetwork=0;lastConfig=0;
    }
    private void invalidateLive(){online=false;synchronized(lock){greenUntil=0;if(current!=null)db.setState("ineligible:"+current,"true");}}
    private void capture(String epc,String tid,String ant,String rssi){
        synchronized(lock){
            if(halted||pendingConfig!=null||config==null||destroying||!running)return;
            Config c=config;
            if(!online&&!c.policy.optBoolean("capture_offline_allowed")){fault("Koneksi offline: capture dihentikan sesuai policy.");return;}
            if(!c.antennas.contains(ant)){fault("Antena tidak terpetakan; capture dihentikan.");return;}
            try {
                if(db.pendingBytes()+4096>c.maxQueue||db.diskBytes()>256L*1024*1024||new StatFs(getFilesDir().getAbsolutePath()).getAvailableBytes()<64L*1024*1024){fault("Penyimpanan mencapai batas; capture dihentikan. Antrean dipertahankan.");return;}
                long now=SystemClock.elapsedRealtime();if(passage==null)open(now);lastRead=now;
                String id=UUID.randomUUID().toString();Double strength=null;try{strength=Double.valueOf(rssi);if(!Double.isFinite(strength))strength=null;}catch(Exception ignored){}
                String raw=epc==null?"":epc;if(raw.length()>1024){fault("Raw EPC melebihi batas kontrak; capture tidak lengkap.");return;}
                JSONObject e=Json.obj("event_id",id,"raw_epc",raw,"epc",Safety.canonicalEpc(raw),"captured_at",timestamp(),"time_quality",timeGood()?"synced":"unsynced","antenna",ant,"rssi_dbm",strength,"raw_rssi",rssi,"sdk_metadata",Json.obj("tid",tid));
                db.add(id,passage,e);lastEvent=id;
            }catch(Exception e){fault("Gagal menyimpan observasi; lintasan tidak lengkap.");}
        }
    }
    private void open(long now){
        passage=UUID.randomUUID().toString();current=passage;opened=lastRead=now;lastEvent=null;greenUntil=0;
        direction="bidirectional".equals(config.direction)?"unknown":config.direction;
        directionDetector=new Safety.Direction();sensorEvidence=new JSONArray();String mode=online&&timeGood()?"live":"backfill";
        db.open(passage,Json.obj("config_version",config.version,"logical_gate_id",config.gateId,"completion_basis",config.basis,"direction",direction,"profile_id",config.raw.optString("hardware_profile_id"),"opened_at",timestamp()),mode);
        if(!"live".equals(mode))db.setState("ineligible:"+passage,"true");
    }
    private JSONObject evidence(){return Json.obj("source","bidirectional".equals(config.direction)?"sensor_sequence":"fixed_profile","profile_binding_id",config.raw.optString("hardware_profile_id"),"sensor_sequence",sensorEvidence);}
    private void close(String reason){
        if(passage==null)return;JSONObject p=db.rows("SELECT * FROM passages WHERE id=?",passage).get(0);
        boolean complete="1".equals(p.optString("complete"))&&!"unknown".equals(direction)&&!"max_duration".equals(reason);
        if(!complete)db.markGap(passage);
        JSONObject body=Json.obj("logical_gate_id",config.gateId,"config_version",config.version,"mode",p.optString("mode"),"closing_captured_at",timestamp(),"boundary_reason",reason,"last_event_id",lastEvent,"observed_event_count",db.count("passage=?",passage),"capture_complete",complete,"direction",direction,"direction_evidence",evidence());
        db.closePassage(passage,body);db.audit("Capture ditutup: "+passage+" ("+reason+")");passage=null;
    }
    private void sensors(){
        JSONObject b=config.gate.optJSONObject("sensor_bindings");if(b==null||b.optString("a").isEmpty())return;
        Map<String,Integer> values=reader.inputs();long now=SystemClock.elapsedRealtime();
        synchronized(lock){
        int simultaneous=0;for(String label:new String[]{"a","b"}){String pin=b.optString(label);Integer v=values.get(pin),old=inputStates.get(pin);if(v!=null&&old!=null&&!v.equals(old)&&v==b.optInt("active_state",1))simultaneous++;}
        if(simultaneous>1){if(passage==null)open(now);directionDetector.invalidate();direction="unknown";db.markGap(passage);}
        for(String label:new String[]{"a","b"}){
            String pin=b.optString(label);if(pin.isEmpty())continue;Integer state=values.get(pin);
            if(state==null){if(!provision.simulation())throw new IllegalStateException("Sensor tidak ada");continue;}
            Integer old=inputStates.put(pin,state);if(old==null||old.equals(state))continue;
            if(now-inputEdges.getOrDefault(pin,0L)<b.optLong("debounce_ms",100))continue;inputEdges.put(pin,now);
            if(state!=b.optInt("active_state",1))continue;if(passage==null)open(now);
            sensorEvidence.put(Json.obj("sensor_id",pin,"captured_at",timestamp(),"state",String.valueOf(state)));
            if("bidirectional".equals(config.direction))direction=directionDetector.edge(label.toUpperCase(java.util.Locale.ROOT),now,b.optLong("sequence_window_ms",5000));
            lastRead=now;
        }}
    }
    private void output(){
        String wanted="true".equals(db.state("latched","true"))?"RED":(!halted&&SystemClock.elapsedRealtime()<greenUntil?"GREEN":"UNKNOWN");signal=wanted;
        if(wanted.equals(lastSignal))return;JSONObject ind=config.gate.optJSONObject("indicators");
        if(ind!=null&&ind.optBoolean("enabled")&&!provision.simulation()){
            int red=ind.optInt("red_output"),green=ind.optInt("green_output");reader.output(green,false);reader.output(red,"RED".equals(wanted));if("GREEN".equals(wanted))reader.output(green,true);
        }lastSignal=wanted;
    }
    private void tick(){
        if(destroying)return;
        try {
            if(!wake.isHeld())wake.acquire(10*60*1000L);
            if(config!=null){
                    if((halted||pendingConfig!=null)&&running){synchronized(lock){close("max_duration");greenUntil=0;running=false;}output();reader.stop();radio="stopped";}
                    synchronized(lock){if(pendingConfig!=null&&!running&&db.settled()&&!"true".equals(db.state("contract_block","false"))){
                        config=pendingConfig;pendingConfig=null;current=null;greenUntil=0;inputStates.clear();inputEdges.clear();lastSignal="";
                        db.setState("config",config.raw.toString());db.setState("pending_config","");db.audit("Konfigurasi diterapkan setelah antrean selesai: "+config.version);
                        halted="true".equals(db.state("paused","false"));error="";
                    }}
                    if(!halted){startReader();if(running)sensors();}
                    synchronized(lock){
                    long now=SystemClock.elapsedRealtime();if(passage!=null){if(now-opened>=config.maxMs)close("max_duration");else if(now-lastRead>=config.idleMs)close("idle_timeout");}
                    }
                    if(running||provision.simulation())output();
            }
            screen=(provision.simulation()?"SIMULASI — GPIO tidak diaktifkan":"PERANGKAT — U300")+"\nRadio: "+radio+" | ERP: "+(online?"online":"offline")+"\nSinyal: "+signal+"\nGate: "+(config==null?"menunggu konfigurasi":config.gateId)+"\nLintasan: "+(passage==null?"tidak sedang capture":passage)+"\nMenunggu kirim: "+db.count("status='pending'")+" | Karantina: "+db.count("status='quarantined'")+"\nAntrean: "+db.pendingBytes()+" byte\n"+error;
        }catch(Exception e){fault("Kontrol perangkat gagal; periksa diagnosis.");radio="error";screen=error;}
    }
    private void sync(){
        if(destroying||SystemClock.elapsedRealtime()<nextNetwork||"true".equals(db.state("auth_block","false"))||(!recoveryRequested&&"true".equals(db.state("contract_block","false"))))return;
        long start=SystemClock.elapsedRealtime();
        try{
            if(config==null||recoveryRequested||start-lastConfig>60000){
                JSONObject o=api.call("GET","/device/config",null,null);Config candidate;
                try{candidate=new Config(o,provision.simulation()?"SIM-GATE":provision.gate(),provision.simulation());}
                catch(Exception invalid){recoveryRequested=false;db.setState("contract_block","true");fault("Konfigurasi ERP tidak aktif/tidak didukung: "+invalid.getMessage());return;}
                synchronized(lock){clock(o,start);
                    if(config==null){
                        String previous=db.state("config","");
                        if(!previous.isEmpty()){
                            JSONObject old=Json.parse(previous);
                            if(!DecisionPolicy.sameIdentity(old,o)){db.setState("contract_block","true");recoveryRequested=false;fault("Device/site/warehouse berbeda dari histori. Migrasi diperlukan.");return;}
                            if(old.optString("config_version").equals(candidate.version)&&!Config.fingerprint(old).equals(Config.fingerprint(o))){recoveryRequested=false;db.setState("contract_block","true");fault("Isi konfigurasi berubah tanpa perubahan versi.");return;}
                            if(!old.optString("config_version").equals(candidate.version)&&!db.settled()){
                                config=new Config(old,candidate.gateId,provision.simulation());pendingConfig=candidate;halted=true;db.setState("pending_config",o.toString());
                            }
                        }
                        if(config==null){config=candidate;db.setState("config",o.toString());}
                    }
                    else if(!DecisionPolicy.sameIdentity(config.raw,o)){db.setState("contract_block","true");recoveryRequested=false;fault("Identitas konfigurasi berubah; perlu migrasi.");return;}
                    else if(config.version.equals(candidate.version)&&!Config.fingerprint(config.raw).equals(Config.fingerprint(o))){recoveryRequested=false;db.setState("contract_block","true");fault("Isi konfigurasi berubah tanpa perubahan versi.");return;}
                    else if(!config.version.equals(candidate.version)){
                        if(passage!=null)db.markGap(passage);close("max_duration");greenUntil=0;halted=true;pendingConfig=candidate;db.setState("pending_config",o.toString());error="Konfigurasi baru menunggu antrean lama selesai.";
                    }
                    if(recoveryRequested){db.setState("contract_block","false");recoveryRequested=false;db.audit("Konfigurasi diperiksa; retry kontrak dengan ID asli.");error="Retry berjalan; capture tetap dijeda sampai operator melanjutkan.";}
                }lastConfig=start;
            }
            if(destroying)return;
            online=true;recoverInterrupted();transmitBatch();if(destroying)return;closeReady();if(destroying)return;pollGate();
            if(start-lastTelemetry>Math.max(10,config.policy.optInt("telemetry_interval_seconds",30))*1000L){telemetry();lastTelemetry=start;}
            failures=0;nextNetwork=0;if(!halted&&pendingConfig==null)error="";
        }catch(Exception e){
            invalidateLive();long delay=Safety.retryMillis(failures++,config==null?2000:config.policy.optLong("retry_initial_seconds",2)*1000,config==null?60000:config.policy.optLong("retry_max_seconds",60)*1000);
            if(e instanceof Api.Failure){Api.Failure f=(Api.Failure)e;delay=Math.max(delay,f.retry);
                if(f.status==401||f.status==403){db.setState("auth_block","true");fault("Device key ditolak; provisioning ulang diperlukan.");}
                else if(f.status==400||f.status==409){db.setState("contract_block","true");fault("Kontrak/konteks ERP ditolak; antrean dipertahankan untuk rekonsiliasi.");}
            }
            if(!halted)error=e instanceof Api.Failure?e.getMessage():"ERP belum tersambung atau respons tidak valid. Antrean tetap tersimpan.";
            nextNetwork=SystemClock.elapsedRealtime()+delay;
        }
    }
    private void recoverInterrupted(){
        for(JSONObject p:db.rows("SELECT * FROM passages WHERE status='INTERRUPTED'")){
            JSONObject meta=Json.parse(p.optString("body"));String id=p.optString("id");List<JSONObject> last=db.rows("SELECT id FROM events WHERE passage=? ORDER BY rowid DESC LIMIT 1",id);
            db.closePassage(id,Json.obj("logical_gate_id",meta.optString("logical_gate_id"),"config_version",meta.optString("config_version"),"mode",p.optString("mode"),"closing_captured_at",timestamp(),"boundary_reason","max_duration","last_event_id",last.isEmpty()?null:last.get(0).optString("id"),"observed_event_count",db.count("passage=?",id),"capture_complete",false,"direction","unknown","direction_evidence",Json.obj("source","unknown","profile_binding_id",null,"sensor_sequence",new JSONArray())));
            db.setState("ineligible:"+id,"true");
        }
    }
    private void transmitBatch() throws Exception{
        long wall=System.currentTimeMillis();
        List<JSONObject> batches=db.rows("SELECT * FROM batches WHERE due<=? OR due>? ORDER BY due,rowid LIMIT 1",String.valueOf(wall),String.valueOf(wall+86400000L));
        if(batches.isEmpty()){
            List<JSONObject> pending=db.rows("SELECT e.passage,p.body AS meta,p.mode FROM events e JOIN passages p ON p.id=e.passage WHERE e.status='pending' AND e.batch IS NULL ORDER BY e.rowid LIMIT 1");if(pending.isEmpty())return;
            JSONObject p=pending.get(0),meta=Json.parse(p.optString("meta"));String id=p.optString("passage"),batch=UUID.randomUUID().toString();JSONArray events=new JSONArray();List<String> ids=new ArrayList<>();
            JSONObject request=Json.obj("schema_version",2,"batch_id",batch,"mode",p.optString("mode"),"config_version",meta.optString("config_version"),"context",Json.obj("kind","gate","logical_gate_id",meta.optString("logical_gate_id"),"local_passage_id",id,"direction",meta.optString("direction"),"direction_evidence",Json.obj("source","unknown".equals(meta.optString("direction"))?"unknown":"fixed_profile","profile_binding_id",meta.optString("profile_id"),"sensor_sequence",new JSONArray())),"events",events);
            for(JSONObject event:db.rows("SELECT id,body FROM events WHERE passage=? AND status='pending' AND batch IS NULL ORDER BY rowid LIMIT "+config.maxEvents,id)){
                events.put(Json.parse(event.optString("body")));if(request.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length>config.maxBody){events.remove(events.length()-1);break;}ids.add(event.optString("id"));
            }
            if(ids.isEmpty()){db.setState("contract_block","true");fault("Satu event melebihi max_body_bytes; perlu perbaikan konfigurasi.");return;}
            db.createBatch(batch,id,request,ids);batches=db.rows("SELECT * FROM batches WHERE id=?",batch);
        }
        JSONObject batch=batches.get(0);String id=batch.optString("id");
        try{
            JSONObject response=api.call("POST","/events",Json.parse(batch.optString("body")),null);
            if(!id.equals(response.optString("batch_id")))throw new Exception("Batch ACK tidak sesuai");
            long before=db.count("batch=? AND status='pending'",id);db.acknowledgements(id,response.getJSONArray("event_acks"));
            long after=db.count("batch=? AND status='pending'",id);
            if(after>0){int attempts=after<before?0:batch.optInt("attempt",0)+1;long wait=Safety.retryMillis(attempts,config.policy.optLong("retry_initial_seconds",2)*1000,config.policy.optLong("retry_max_seconds",60)*1000);db.execute("UPDATE batches SET attempt=?,due=? WHERE id=?",attempts,System.currentTimeMillis()+wait,id);}
        }catch(Api.Failure e){
            if(e.status==413){
                JSONObject b=Json.parse(batch.optString("body"));JSONArray a=b.getJSONArray("events");
                if(a.length()<=1){db.setState("contract_block","true");fault("Satu event ditolak 413; perlu rekonsiliasi.");throw e;}
                // 413 contract guarantees envelope unprocessed. Event IDs remain stable.
                int half=a.length()/2;JSONArray subset=new JSONArray();List<String> ids=new ArrayList<>();for(int i=0;i<half;i++){JSONObject event=a.getJSONObject(i);subset.put(event);ids.add(event.getString("event_id"));}
                String next=UUID.randomUUID().toString();b.put("batch_id",next);b.put("events",subset);db.splitBatch(id,batch.optString("passage"),b,ids);return;
            }throw e;
        }
    }
    private void closeReady() throws Exception{
        for(JSONObject p:db.rows("SELECT * FROM passages WHERE status='CLOSING' ORDER BY rowid LIMIT 10")){
            if(destroying)return;
            String id=p.optString("id");if(db.count("passage=? AND status='pending'",id)>0)continue;JSONObject body=Json.parse(p.optString("close_body"));
            if(db.count("passage=? AND status='quarantined'",id)>0)body.put("capture_complete",false);
            db.execute("UPDATE passages SET close_body=? WHERE id=?",body.toString(),id);
            JSONObject response=api.call("POST","/passages/"+id+"/close",body,p.optString("close_key"));
            if(!id.equals(response.optString("local_passage_id")))throw new Exception("Close response tidak sesuai passage");
            db.execute("UPDATE passages SET status='DECISION_PENDING',decision=? WHERE id=?",response.toString(),id);
            // /close returns GateDecision. Only /gate-state supplies authoritative latch state.
        }
    }
    private void pollGate() throws Exception{
        String id;synchronized(lock){id=current;}
        String base="/device/gate-state?logical_gate_id="+java.net.URLEncoder.encode(config.gateId,"UTF-8");
        acceptState(api.call("GET",base+(id==null?"":"&local_passage_id="+id),null,null));
        for(JSONObject p:db.rows("SELECT id FROM passages WHERE status='DECISION_PENDING' ORDER BY rowid LIMIT 3")){
            if(destroying)return;
            if(!p.optString("id").equals(id))acceptState(api.call("GET",base+"&local_passage_id="+p.optString("id"),null,null));
        }
    }
    private void acceptState(JSONObject state) throws Exception{
        if(!config.gateId.equals(state.optString("logical_gate_id"))||!(state.opt("latched") instanceof Boolean))throw new Exception("Gate-state tidak sesuai kontrak");
        if(!config.version.equals(state.optString("config_version"))&&(pendingConfig==null||!pendingConfig.version.equals(state.optString("config_version"))))throw new Exception("Versi gate-state tidak dikenal");
        synchronized(lock){
            db.setState("latched",String.valueOf(state.getBoolean("latched")));if(state.getBoolean("latched"))greenUntil=0;
            JSONObject d=state.optJSONObject("decision");if(d==null)return;
            String id=d.optString("local_passage_id");List<JSONObject> rows=db.rows("SELECT * FROM passages WHERE id=?",id);if(rows.isEmpty())return;JSONObject p=rows.get(0);
            JSONObject meta=Json.parse(p.optString("body"));
            boolean matching=config.gateId.equals(d.optString("logical_gate_id"))&&meta.optString("config_version").equals(d.optString("config_version"))&&meta.optString("completion_basis").equals(d.optString("completion_basis"));if(!matching)return;
            if(!"DECISION_PENDING".equals(p.optString("status"))&&!"FINAL".equals(p.optString("status")))return;
            if(db.count("passage=? AND status='pending'",id)>0)return;
            if(d.opt("final") instanceof Boolean&&d.optBoolean("final"))db.execute("UPDATE passages SET status='FINAL',decision=? WHERE id=?",d.toString(),id);
            long now=serverNow(),expires=Json.time(d.optString("expires_at")),created=Json.time(d.optString("created_at"));
            boolean fresh=timeGood()&&created<=now&&created>0&&now-created<=config.policy.optInt("gate_decision_validity_seconds",5)*1000L&&expires>now;
            boolean eligible=!"true".equals(db.state("ineligible:"+id,"false"));
            JSONObject counts=d.optJSONObject("counts");
            boolean reconciled=DecisionPolicy.validGreen(state,d,meta,id,p.optString("mode"),now,config.policy.optInt("gate_decision_validity_seconds",5)*1000L);
            boolean green=Safety.greenAllowed(pendingConfig==null&&!halted&&online&&eligible&&"live".equals(d.optString("mode"))&&"live".equals(p.optString("mode")),id.equals(current)&&passage==null,"1".equals(p.optString("complete"))&&reconciled,db.count("passage=? AND status!='acked'",id)==0,d.optBoolean("final"),d.optBoolean("allow_live_signal"),state.getBoolean("latched")||d.optBoolean("latched"),fresh,matching,d.optString("verdict"),d.optString("completion_basis"));
            String decisionId=d.optString("decision_id");
            if(green&&!decisionId.isEmpty()&&!decisionId.equals(db.state("signaled_decision",""))){greenUntil=SystemClock.elapsedRealtime()+Math.min(expires-now,config.policy.optInt("gate_decision_validity_seconds",5)*1000L);db.setState("signaled_decision",decisionId);db.audit("Keputusan ERP untuk "+id);}
            if("RED".equals(d.optString("verdict")))greenUntil=0;
        }
    }
    private void telemetry() throws Exception{
        List<JSONObject> pending=db.rows("SELECT body FROM events WHERE status='pending' ORDER BY rowid LIMIT 1");
        JSONObject t=Json.obj("event_id",UUID.randomUUID().toString(),"captured_at",timestamp(),"config_version",config.version,"app_build",BuildConfig.VERSION_NAME,"sdk_version","20251103","radio_state",radio,"printer_state","not_applicable","erp_transport",online?"online":"offline","pending_event_count",db.count("status='pending'"),"pending_bytes",db.pendingBytes(),"oldest_pending_at",pending.isEmpty()?null:Json.parse(pending.get(0).optString("body")).optString("captured_at"),"free_storage_bytes",new StatFs(getFilesDir().getAbsolutePath()).getAvailableBytes(),"uptime_seconds",SystemClock.elapsedRealtime()/1000,"time_quality",timeGood()?"synced":"unsynced","last_error",null,"platform_health",Json.obj("mode",provision.simulation()?"simulation":"device","signal",signal,"capture_halted",halted,"quarantined",db.count("status='quarantined'"),"firmware_android",Build.VERSION.RELEASE));
        if(!error.isEmpty())t.put("last_error",Json.obj("code","AGENT_STATUS","message",error,"retryable",!halted));
        api.call("POST","/device/telemetry",t,null);
    }
    String diagnostic(){return db.diagnostic();}
    @Override public void onDestroy(){
        destroying=true;active=null;network.shutdownNow();control.shutdown();
        synchronized(lock){try{close("max_duration");greenUntil=0;running=false;}catch(Exception ignored){}}
        try{if(config!=null){JSONObject i=config.gate.optJSONObject("indicators");if(i!=null&&i.optBoolean("enabled")){reader.output(i.optInt("green_output"),false);reader.output(i.optInt("red_output"),true);}}}catch(Exception ignored){}
        try{reader.stop();}catch(Exception ignored){}
        if(wake!=null&&wake.isHeld())wake.release();screen="Layanan berhenti. Antrean tetap tersimpan.";
        new Thread(()->{try{while(!network.awaitTermination(1,TimeUnit.SECONDS)){/* Keep storage open until transport exits. */}while(!control.awaitTermination(1,TimeUnit.SECONDS)){/* Drain control. */}db.close();}catch(InterruptedException e){Thread.currentThread().interrupt();}},"kn-shutdown").start();super.onDestroy();
    }
}
