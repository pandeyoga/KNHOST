package id.kubusteknologi.kn.u300;
import org.json.*;
public final class DecisionPolicyTest {
    static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("Decision check "+checks);}
    static final long NOW=1800000000000L;
    static JSONObject decision(){return Json.obj("decision_id","d1","local_passage_id","p1","logical_gate_id","g1","config_version","v1","mode","live","final",true,"allow_live_signal",true,"latched",false,"verdict","GREEN","completion_basis","manifest_full","created_at",java.time.Instant.ofEpochMilli(NOW-1000).toString(),"expires_at",java.time.Instant.ofEpochMilli(NOW+3000).toString(),"counts",Json.obj("observed_unique",2,"matched",2,"missing",0,"extra",0,"unknown",0,"pending",0));}
    static JSONObject state(){return Json.obj("logical_gate_id","g1","latched",false);}
    static JSONObject meta(){return Json.obj("logical_gate_id","g1","config_version","v1","completion_basis","manifest_full");}
    static boolean valid(JSONObject d){return DecisionPolicy.validGreen(state(),d,meta(),"p1","live",NOW,5000);}
    public static void main(String[] args)throws Exception{
        check(valid(decision()));
        for(String f:new String[]{"decision_id","local_passage_id","logical_gate_id","config_version","mode","final","allow_live_signal","latched","verdict","completion_basis","created_at","expires_at","counts"}){JSONObject d=decision();d.remove(f);check(!valid(d));}
        for(String f:new String[]{"final","allow_live_signal","latched"}){JSONObject d=decision();d.put(f,"true");check(!valid(d));}
        for(String f:new String[]{"missing","extra","unknown","pending"}){JSONObject d=decision();d.getJSONObject("counts").put(f,1);check(!valid(d));d.getJSONObject("counts").remove(f);check(!valid(d));}
        JSONObject d=decision();d.getJSONObject("counts").put("matched",1);check(!valid(d));
        d=decision();d.getJSONObject("counts").put("observed_unique",2.5);d.getJSONObject("counts").put("matched",2.5);check(!valid(d));
        for(long age:new long[]{-100,6000}){d=decision();d.put("created_at",java.time.Instant.ofEpochMilli(NOW-age).toString());check(!valid(d));}
        d=decision();d.put("expires_at",java.time.Instant.ofEpochMilli(NOW).toString());check(!valid(d));
        check(!DecisionPolicy.validGreen(state(),decision(),meta(),"p1","backfill",NOW,5000));
        check(!DecisionPolicy.validGreen(state(),decision(),meta(),"other","live",NOW,5000));
        JSONObject s=state();s.put("latched",true);check(!DecisionPolicy.validGreen(s,decision(),meta(),"p1","live",NOW,5000));
        JSONObject c=Config.simulation(),other=Json.parse(c.toString());other.put("server_time","different");check(Config.fingerprint(c).equals(Config.fingerprint(other)));other.getJSONObject("limits").put("max_events",1);check(!Config.fingerprint(c).equals(Config.fingerprint(other)));
        check(DecisionPolicy.sameIdentity(c,Config.simulation()));other=Config.simulation();other.put("warehouse_id","OTHER");check(!DecisionPolicy.sameIdentity(c,other));
        Api api=new Api(new Api.Settings(){public boolean simulation(){return true;}public String url(){return "";}public String token(){return "";}});
        JSONArray events=new JSONArray().put(Json.obj("event_id","e1","epc","E20034120123456789ABCDEF")).put(Json.obj("event_id","e2","epc","E20034120123456789ABCDE0"));JSONObject req=Json.obj("batch_id","b1","events",events);
        api.scenario="partial";check(api.call("POST","/events",req,null).getJSONArray("event_acks").length()==1);
        JSONArray a=api.call("POST","/events",req,null).getJSONArray("event_acks");check(a.getJSONObject(0).getString("status").equals("duplicate"));check(a.getJSONObject(1).getString("status").equals("accepted"));
        api.scenario="not-durable";check(!api.call("POST","/events",req,null).getJSONArray("event_acks").getJSONObject(0).getBoolean("durable"));
        api.scenario="retry";check(api.call("POST","/events",req,null).getJSONArray("event_acks").getJSONObject(0).getString("status").equals("retry"));
        for(int code:new int[]{400,401,403,409,413,429,500}){api.scenario="http-"+code;boolean failed=false;try{api.call("POST","/events",req,null);}catch(Api.Failure f){failed=f.status==code;}check(failed);check(api.call("POST","/events",req,null).has("event_acks"));}
        api.simulationRevision=2;check(api.call("GET","/device/config",null,null).getString("config_version").equals("sim-v2"));
        final String[] persisted={""};Api.Settings memory=new Api.Settings(){public boolean simulation(){return true;}public String url(){return "";}public String token(){return "";}public String simulatorState(){return persisted[0];}public void simulatorState(String v){persisted[0]=v;}};
        Api first=new Api(memory);first.simulationRevision=3;first.call("GET","/device/config",null,null);first.call("POST","/events",req,null);first.verdict="RED";
        JSONObject close=Json.obj("mode","live","config_version","sim-v3","capture_complete",true,"observed_event_count",2);
        JSONObject red=first.call("POST","/passages/persisted/close",close,"key");
        Api restarted=new Api(memory);check(restarted.simulationRevision==3);check(restarted.call("GET","/device/gate-state",null,null).getBoolean("latched"));
        check(restarted.call("POST","/events",req,null).getJSONArray("event_acks").getJSONObject(0).getString("status").equals("duplicate"));
        check(restarted.call("POST","/passages/persisted/close",close,"key").getString("decision_id").equals(red.getString("decision_id")));
        restarted.resetSimulationLatch();check(!new Api(memory).call("GET","/device/gate-state",null,null).getBoolean("latched"));
        JSONObject changed=Json.parse(close.toString());changed.put("observed_event_count",3);boolean conflict=false;try{restarted.call("POST","/passages/persisted/close",changed,"key");}catch(Api.Failure f){conflict=f.status==409;}check(conflict);
        System.out.println("PASS: "+checks+" decision/configuration/fault assertions");
    }
}
