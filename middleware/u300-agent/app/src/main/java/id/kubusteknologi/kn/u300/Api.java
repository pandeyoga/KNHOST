package id.kubusteknologi.kn.u300;
import org.json.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
final class Api {
    interface Settings {boolean simulation();String url();String token() throws Exception;default String simulatorState(){return "";}default void simulatorState(String value) throws Exception{}}
    static final class Failure extends Exception {
        final int status;final long retry;
        Failure(int s,long r){super("ERP HTTP "+s);status=s;retry=r;}
        Failure(int s,long r,String detail){super("ERP HTTP "+s+(detail.isEmpty()?"":" · "+detail));status=s;retry=r;}
    }
    private final Settings p;
    volatile boolean offline;
    volatile String verdict="GREEN";
    volatile String scenario="normal";
    volatile int simulationRevision=1;
    private final java.util.Set<String> acceptedEvents=new java.util.HashSet<>();
    private final java.util.Map<String,String> closePayloads=new java.util.HashMap<>();
    private boolean mockLatch;
    private JSONObject mockDecision;
    private final java.util.Map<String,JSONObject> decisions=new java.util.HashMap<>();
    private String simulatorError;
    Api(Settings p){this.p=p;
        if(p.simulation())try{
            String saved=p.simulatorState();if(!saved.isEmpty()){
                JSONObject o=Json.parse(saved);simulationRevision=o.getInt("revision");mockLatch=o.getBoolean("latched");
                JSONArray ids=o.getJSONArray("accepted_events");for(int i=0;i<ids.length();i++)acceptedEvents.add(ids.getString(i));
                JSONObject ds=o.getJSONObject("decisions"),cs=o.getJSONObject("close_payloads");java.util.Iterator<String> keys=ds.keys();while(keys.hasNext()){String k=keys.next();decisions.put(k,ds.getJSONObject(k));}
                keys=cs.keys();while(keys.hasNext()){String k=keys.next();closePayloads.put(k,cs.getString(k));}
            }
        }catch(Exception e){simulatorError="State simulator tidak dapat dibaca; ekspor diagnosis sebelum pemulihan.";}
    }
    private void persistSimulator() throws Exception{p.simulatorState(Json.obj("revision",simulationRevision,"latched",mockLatch,"accepted_events",new JSONArray(acceptedEvents),"decisions",new JSONObject(decisions),"close_payloads",new JSONObject(closePayloads)).toString());}
    JSONObject call(String method,String path,JSONObject body,String key) throws Exception {
        if(p.simulation())return simulated(path,body);
        HttpURLConnection c=(HttpURLConnection)new URL(p.url()+"/api/rfid/v2"+path).openConnection();
        try {
            c.setConnectTimeout(5000);c.setReadTimeout(5000);c.setInstanceFollowRedirects(false);c.setRequestMethod(method);
            c.setRequestProperty("X-Device-Key",p.token());c.setRequestProperty("Accept","application/json");
            if(key!=null)c.setRequestProperty("Idempotency-Key",key);
            if(body!=null){byte[] b=body.toString().getBytes(StandardCharsets.UTF_8);c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setFixedLengthStreamingMode(b.length);try(OutputStream out=c.getOutputStream()){out.write(b);}}
            int status=c.getResponseCode();
            if(status<200||status>=300){long retry=0;String h=c.getHeaderField("Retry-After");try{retry=Long.parseLong(h)*1000;}catch(Exception e){try{retry=java.time.ZonedDateTime.parse(h,java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME).toInstant().toEpochMilli()-System.currentTimeMillis();}catch(Exception ignored){}}throw new Failure(status,Math.max(0,Math.min(86400000,retry)),errorDetail(c));}
            try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                long start=System.nanoTime();byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(Thread.currentThread().isInterrupted()||System.nanoTime()-start>15000000000L)throw new IOException("Batas waktu membaca respons");if(out.size()+n>2097152)throw new IOException("Respons ERP terlalu besar");out.write(b,0,n);}return out.size()==0?Json.obj():Json.parse(out.toString("UTF-8"));
            }
        } finally {c.disconnect();}
    }
    private static String errorDetail(HttpURLConnection c){
        try(InputStream in=c.getErrorStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
            if(in==null)return "";
            long start=System.nanoTime();byte[] b=new byte[1024];int n;
            while(out.size()<8192&&(n=in.read(b,0,Math.min(b.length,8192-out.size())))!=-1){
                if(System.nanoTime()-start>5000000000L)return "";out.write(b,0,n);
            }
            JSONObject error=Json.parse(out.toString("UTF-8"));Object detail=error.opt("detail");
            if(detail instanceof JSONObject){JSONObject d=(JSONObject)detail;return (d.optString("code")+": "+d.optString("message")).substring(0,Math.min(500,(d.optString("code")+": "+d.optString("message")).length()));}
            if(detail instanceof String)return ((String)detail).substring(0,Math.min(500,((String)detail).length()));
        }catch(Exception ignored){}return "";
    }
    private synchronized JSONObject simulated(String path,JSONObject body) throws Exception {
        if(simulatorError!=null)throw new IOException(simulatorError);
        if(offline)throw new IOException("Simulasi jaringan offline");
        if(path.equals("/device/config")){persistSimulator();JSONObject c=Config.simulation();c.put("config_version","sim-v"+simulationRevision);return c;}
        if(path.equals("/events")){
            String fault=scenario;scenario="normal";
            if(fault.matches("http-[0-9]{3}"))throw new Failure(Integer.parseInt(fault.substring(5)),fault.equals("http-429")?2000:0);
            JSONArray a=new JSONArray(),events=body.getJSONArray("events");
            for(int i=0;i<events.length();i++){
                if("partial".equals(fault)&&i%2==1)continue;
                JSONObject event=events.getJSONObject(i);String id=event.getString("event_id");boolean ok=!event.isNull("epc"),durable=!"not-durable".equals(fault)&&!"retry".equals(fault);
                String status=!ok?"quarantined":("retry".equals(fault)?"retry":(acceptedEvents.contains(id)?"duplicate":"accepted"));
                if(ok&&durable)acceptedEvents.add(id);
                a.put(Json.obj("event_id",id,"status",status,"durable",durable,"processing_status",ok?"completed":"not_applicable","error",null));
            }
            persistSimulator();return Json.obj("request_id",java.util.UUID.randomUUID().toString(),"batch_id",body.getString("batch_id"),"server_time",Json.now(),"event_acks",a);
        }
        if(path.endsWith("/close")){
            String id=path.split("/")[2];if(decisions.containsKey(id)){if(!body.toString().equals(closePayloads.get(id)))throw new Failure(409,0);return decisions.get(id);}
            String v=body.optBoolean("capture_complete")?verdict:"UNKNOWN";
            if("RED".equals(v))mockLatch=true;
            mockDecision=Json.obj("decision_id",java.util.UUID.randomUUID().toString(),"local_passage_id",id,"logical_gate_id","SIM-GATE","mode",body.getString("mode"),"final",true,"verdict",v,"completion_basis","manifest_full","config_version","sim-v1","created_at",Json.now(),"expires_at",java.time.Instant.now().plusSeconds(5).toString(),"allow_live_signal",!mockLatch,"latched",mockLatch,"reason_code","SIMULATION_ONLY","action","simulation","counts",Json.obj("observed_unique",body.optInt("observed_event_count"),"matched",body.optInt("observed_event_count"),"missing",0,"extra",0,"unknown",0,"pending",0),"source_ref",null);
            mockDecision.put("config_version",body.getString("config_version"));closePayloads.put(id,body.toString());decisions.put(id,mockDecision);persistSimulator();return mockDecision;
        }
        if(path.startsWith("/device/gate-state")){
            String marker="&local_passage_id=";int at=path.indexOf(marker);
            JSONObject s=state();if(at>=0)s.put("decision",decisions.containsKey(path.substring(at+marker.length()))?decisions.get(path.substring(at+marker.length())):JSONObject.NULL);return s;
        }
        return Json.obj("request_id",java.util.UUID.randomUUID().toString(),"server_time",Json.now());
    }
    synchronized void resetSimulationLatch(){mockLatch=false;mockDecision=null;try{persistSimulator();}catch(Exception e){simulatorError="Gagal menyimpan acknowledge simulasi.";}}
    private JSONObject state(){return Json.obj("request_id",java.util.UUID.randomUUID().toString(),"logical_gate_id","SIM-GATE","config_version","sim-v"+simulationRevision,"latched",mockLatch,"latch_id",mockLatch?"SIM-LATCH":null,"decision",mockDecision,"server_time",Json.now());}
}
