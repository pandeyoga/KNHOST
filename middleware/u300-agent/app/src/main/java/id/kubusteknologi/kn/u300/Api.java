package id.kubusteknologi.kn.u300;
import org.json.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import id.kubusteknologi.kn.u300.core.ClockSync;
final class Api {
    interface Settings {boolean simulation();String url();String token() throws Exception;default String simulatorState(){return "";}default void simulatorState(String value) throws Exception{}}
    /** Mono clock (ms). Android: SystemClock.elapsedRealtime; host test: System.nanoTime. */
    interface Mono {long now();}
    static final class Failure extends Exception {
        final int status;final long retry;final String code;final Boolean retryable;final long pollAfter;
        Failure(int s,long r){this(s,r,"",null,null,0);}
        Failure(int s,long r,String detail){this(s,r,detail,null,null,0);}
        Failure(int s,long r,String detail,String code,Boolean retryable,long pollAfter){super("ERP HTTP "+s+(detail==null||detail.isEmpty()?"":" · "+detail));status=s;retry=r;this.code=code==null?"":code;this.retryable=retryable;this.pollAfter=pollAfter;}
    }
    private final Settings p;
    volatile ClockSync clock;
    volatile Mono mono=()->System.nanoTime()/1_000_000L;
    volatile boolean offline;
    volatile String verdict="GREEN";
    volatile String scenario="normal";
    volatile int simulationRevision=1;
    volatile int simulationPending=0;
    private final Set<String> acceptedEvents=new HashSet<>();
    private final Map<String,String> closePayloads=new HashMap<>();
    private boolean mockLatch;
    private JSONObject mockDecision;
    private final Map<String,JSONObject> decisions=new HashMap<>();
    private String simulatorError;
    private long lastSeq=-1;private String lastBoot="";
    Api(Settings p){this.p=p;
        if(p.simulation())try{
            String saved=p.simulatorState();if(!saved.isEmpty()){
                JSONObject o=Json.parse(saved);simulationRevision=o.getInt("revision");mockLatch=o.getBoolean("latched");
                JSONArray ids=o.getJSONArray("accepted_events");for(int i=0;i<ids.length();i++)acceptedEvents.add(ids.getString(i));
                JSONObject ds=o.getJSONObject("decisions"),cs=o.getJSONObject("close_payloads");Iterator<String> keys=ds.keys();while(keys.hasNext()){String k=keys.next();decisions.put(k,ds.getJSONObject(k));}
                keys=cs.keys();while(keys.hasNext()){String k=keys.next();closePayloads.put(k,cs.getString(k));}
            }
        }catch(Exception e){simulatorError="State simulator tidak dapat dibaca; ekspor diagnosis sebelum pemulihan.";}
    }
    private void persistSimulator() throws Exception{p.simulatorState(Json.obj("revision",simulationRevision,"latched",mockLatch,"accepted_events",new JSONArray(acceptedEvents),"decisions",new JSONObject(decisions),"close_payloads",new JSONObject(closePayloads)).toString());}
    JSONObject call(String method,String path,JSONObject body,String key) throws Exception {
        long start=mono.now();
        JSONObject out=p.simulation()?simulated(path,body):http(method,path,body,key);
        ClockSync c=clock;long remote=Json.time(out.optString("server_time"));
        if(c!=null&&remote>0)c.offer(remote,start,mono.now());   // AUD-MW-12: setiap respons ber-server_time
        return out;
    }
    private JSONObject http(String method,String path,JSONObject body,String key) throws Exception {
        HttpURLConnection c=(HttpURLConnection)new URL(p.url()+"/api/rfid/v2"+path).openConnection();
        try {
            c.setConnectTimeout(5000);c.setReadTimeout(10000);c.setInstanceFollowRedirects(false);c.setRequestMethod(method);
            c.setRequestProperty("X-Device-Key",p.token());c.setRequestProperty("Accept","application/json");
            if(key!=null)c.setRequestProperty("Idempotency-Key",key);
            if(body!=null){byte[] b=body.toString().getBytes(StandardCharsets.UTF_8);c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setFixedLengthStreamingMode(b.length);try(OutputStream out=c.getOutputStream()){out.write(b);}}
            int status=c.getResponseCode();
            if(status<200||status>=300){long retry=0;String h=c.getHeaderField("Retry-After");try{retry=Long.parseLong(h)*1000;}catch(Exception e){try{retry=java.time.ZonedDateTime.parse(h,java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME).toInstant().toEpochMilli()-System.currentTimeMillis();}catch(Exception ignored){}}throw failure(status,Math.max(0,Math.min(86400000,retry)),readError(c));}
            try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                long start=System.nanoTime();byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(Thread.currentThread().isInterrupted()||System.nanoTime()-start>15000000000L)throw new IOException("Batas waktu membaca respons");if(out.size()+n>2097152)throw new IOException("Respons ERP terlalu besar");out.write(b,0,n);}return out.size()==0?Json.obj():Json.parse(out.toString("UTF-8"));
            }
        } finally {c.disconnect();}
    }
    private static JSONObject readError(HttpURLConnection c){
        try(InputStream in=c.getErrorStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
            if(in==null)return null;
            long start=System.nanoTime();byte[] b=new byte[1024];int n;
            while(out.size()<8192&&(n=in.read(b,0,Math.min(b.length,8192-out.size())))!=-1){
                if(System.nanoTime()-start>5000000000L)return null;out.write(b,0,n);
            }
            return Json.parse(out.toString("UTF-8"));
        }catch(Exception ignored){return null;}
    }
    /** Galat terstruktur {@code {"detail":{"code","message","retryable","details"}}} (AUD-MW-06) atau teks lama. */
    static Failure failure(int status,long retry,JSONObject error){
        Object detail=error==null?null:error.opt("detail");
        if(detail instanceof JSONObject){JSONObject d=(JSONObject)detail;String text=d.optString("code")+": "+d.optString("message");
            Boolean retryable=d.opt("retryable") instanceof Boolean?d.optBoolean("retryable"):null;
            JSONObject details=d.optJSONObject("details");long poll=details==null?0:Math.max(0,Math.min(3600,details.optLong("poll_after_seconds",0)))*1000L;
            return new Failure(status,retry,text.substring(0,Math.min(500,text.length())),d.optString("code"),retryable,poll);}
        if(detail instanceof String){String s=(String)detail;return new Failure(status,retry,s.substring(0,Math.min(500,s.length())));}
        return new Failure(status,retry,"");
    }
    private static Failure simFailure(int status,String code,boolean retryable,long poll){
        JSONObject d=Json.obj("code",code,"message","SIMULASI "+code,"retryable",retryable);
        if(poll>0)try{d.put("details",Json.obj("poll_after_seconds",poll));}catch(JSONException e){throw new IllegalStateException(e);}
        return failure(status,status==429?2000:0,Json.obj("detail",d));
    }
    private void simulatedFault(String fault) throws Failure{
        switch(fault){
            case "admin-disabled":throw simFailure(403,"ADMIN_DISABLED",true,60);
            case "config-required":throw simFailure(409,"CONFIG_REQUIRED",true,60);
            case "auth-invalid":throw simFailure(401,"AUTH_INVALID",false,0);
            case "evidence-pending":throw simFailure(503,"EVIDENCE_PENDING",true,0);
            case "event-id-conflict":throw simFailure(409,"EVENT_ID_CONFLICT",false,0);
            default:if(fault.matches("http-[0-9]{3}"))throw new Failure(Integer.parseInt(fault.substring(5)),fault.equals("http-429")?2000:0);
        }
    }
    private JSONArray simulatedAcks(JSONArray items,String idKey,String ackKey,String fault,String passage){
        JSONArray a=new JSONArray();
        if(items==null)return a;
        for(int i=0;i<items.length();i++){
            if("partial".equals(fault)&&i%2==1)continue;
            JSONObject item=items.optJSONObject(i);String id=item.optString(idKey);boolean ok=!item.has("epc")||!item.isNull("epc"),durable=!"not-durable".equals(fault)&&!"retry".equals(fault);
            String status=!ok?"quarantined":("retry".equals(fault)?"retry":("overflow".equals(fault)?"quarantined":(acceptedEvents.contains(passage+"|"+id)?"duplicate":"accepted")));
            if(durable&&!"retry".equals(fault))acceptedEvents.add(passage+"|"+id);
            JSONObject error=null;
            if("quarantined".equals(status))error=Json.obj("code",ok?"CAPTURE_OVERFLOW":"INVALID_EPC","message","SIMULASI karantina","retryable",false);
            a.put(Json.obj(ackKey,id,"status",status,"durable",durable,"processing_status","quarantined".equals(status)?"not_applicable":"completed","error",error));
        }
        return a;
    }
    private synchronized JSONObject simulated(String path,JSONObject body) throws Exception {
        if(simulatorError!=null)throw new IOException(simulatorError);
        if(offline)throw new IOException("Simulasi jaringan offline");
        if(path.equals("/device/config")){
            if(scenario.equals("config-required")||scenario.equals("admin-disabled")||scenario.equals("auth-invalid")){String f=scenario;scenario="normal";simulatedFault(f);}
            persistSimulator();JSONObject c=Config.simulation();c.put("config_version","sim-v"+simulationRevision);return c;}
        if(path.equals("/events")){
            String fault=scenario;scenario="normal";
            if(fault.equals("passage-frozen"))throw simFailure(409,"PASSAGE_FROZEN",false,0);
            if(fault.equals("http-413"))throw simFailure(413,"BATCH_TOO_LARGE",false,0);
            simulatedFault(fault);
            JSONObject ctx=body.optJSONObject("context");String passage=ctx==null?"":ctx.optString("local_passage_id");
            JSONObject out=Json.obj("request_id",UUID.randomUUID().toString(),"batch_id",body.getString("batch_id"),"server_time",Json.now(),
                "event_acks",simulatedAcks(body.optJSONArray("events"),"event_id","event_id",fault,passage));
            if(body.has("tag_summaries"))out.put("summary_acks",simulatedAcks(body.getJSONArray("tag_summaries"),"summary_id","item_id",fault,passage));
            if(body.has("gpi_edges"))out.put("edge_acks",simulatedAcks(body.getJSONArray("gpi_edges"),"edge_id","item_id","overflow".equals(fault)?"normal":fault,passage));
            if(body.has("boot_id")){String boot=body.getString("boot_id");long seq=body.getLong("seq");boolean gap=boot.equals(lastBoot)&&seq>lastSeq+1;if(!boot.equals(lastBoot)){lastBoot=boot;lastSeq=seq;}else lastSeq=Math.max(lastSeq,seq);out.put("last_seq",lastSeq).put("seq_gap",gap);}
            persistSimulator();return out;
        }
        if(path.endsWith("/close")){
            String fault=scenario;if(fault.equals("evidence-pending")){scenario="normal";simulatedFault(fault);}
            String id=path.split("/")[2];if(decisions.containsKey(id)){if(!body.toString().equals(closePayloads.get(id)))throw simFailure(409,"CLOSE_CONFLICT",false,0);return decisions.get(id);}
            String close=body.optString("close_reason"),boundary=body.optString("boundary_reason");
            int observed=body.optInt("observed_summary_count",0)+body.optInt("observed_event_count",0);
            boolean cancelled="REVERSED".equals(close)||"ABORTED".equals(close)||"cancelled".equals(boundary);
            String v;
            if(observed==0||cancelled&&!"RED".equals(verdict))v="CANCELLED";
            else if(!body.optBoolean("capture_complete"))v="RED".equals(verdict)?"RED":"REVIEW";
            else if("SENSOR_FAULT".equals(close)||"RF_FALLBACK".equals(body.optString("open_reason")))v="RED".equals(verdict)?"RED":"REVIEW";
            else v=verdict;
            boolean red="RED".equals(v);if(red)mockLatch=true;
            JSONObject counts=Json.obj("observed_unique",observed,"matched","GREEN".equals(v)?observed:0,"missing",0,"extra",0,"unknown",0,"pending","GREEN".equals(v)?simulationPending:0);
            mockDecision=Json.obj("decision_id",UUID.randomUUID().toString(),"local_passage_id",id,"logical_gate_id","SIM-GATE","mode",body.getString("mode"),"final",true,"verdict",v,"completion_basis","document_session","config_version",body.getString("config_version"),"created_at",Json.now(),"expires_at",java.time.Instant.now().plusSeconds(5).toString(),"allow_live_signal","GREEN".equals(v)&&"live".equals(body.getString("mode")),"latched",red,"reason_code","SIMULATION_ONLY","action","simulation","counts",counts,"source_ref",null,
                "reason_codes",new JSONArray().put("SIMULATION_ONLY"),"indicator","GREEN".equals(v)?"GREEN":"REVIEW".equals(v)?"YELLOW":red?"RED":"OFF","open_reason",body.opt("open_reason"),"close_reason",body.opt("close_reason"),"binding_mode","none","latch_id",red?"SIM-LATCH":null,"simulated",true);
            closePayloads.put(id,body.toString());decisions.put(id,mockDecision);persistSimulator();return mockDecision;
        }
        if(path.startsWith("/device/gate-state")){
            String marker="&local_passage_id=";int at=path.indexOf(marker);
            JSONObject s=state();if(at>=0)s.put("decision",decisions.containsKey(path.substring(at+marker.length()))?decisions.get(path.substring(at+marker.length())):JSONObject.NULL);return s;
        }
        return Json.obj("request_id",UUID.randomUUID().toString(),"server_time",Json.now());
    }
    synchronized void resetSimulationLatch(){mockLatch=false;mockDecision=null;try{persistSimulator();}catch(Exception e){simulatorError="Gagal menyimpan acknowledge simulasi.";}}
    private JSONObject state(){return Json.obj("request_id",UUID.randomUUID().toString(),"logical_gate_id","SIM-GATE","config_version","sim-v"+simulationRevision,"latched",mockLatch,"latch_id",mockLatch?"SIM-LATCH":null,"decision",mockDecision,"server_time",Json.now(),"latch_since",mockLatch?Json.now():null,"latch_reason_codes",new JSONArray(),"latch_passage_count",mockLatch?1:0);}
}
