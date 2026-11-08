package id.kubusteknologi.kn.u300;
import org.json.*;
import java.nio.file.*;
public class HostTest {
    static int checks;
    static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
    interface Action {void run() throws Exception;}
    static void rejects(Action action)throws Exception{boolean rejected=false;try{action.run();}catch(Exception e){rejected=true;}check(rejected);}
    static JSONObject cloneConfig(){return Json.parse(Config.simulation().toString());}
    public static void main(String[] args)throws Exception{
        JSONObject cfg=cloneConfig();Config c=new Config(cfg,"SIM-GATE",true);check(c.antennas.size()==2);
        rejects(()->new Config(cloneConfig(),"WRONG-GATE",true));
        rejects(()->new Config(cloneConfig(),"SIM-GATE",false));
        cfg=cloneConfig();cfg.put("enabled",false);final JSONObject disabled=cfg;rejects(()->new Config(disabled,"SIM-GATE",true));
        cfg=cloneConfig();cfg.getJSONArray("logical_gates").getJSONObject(0).put("direction","bidirectional");final JSONObject noSensor=cfg;rejects(()->new Config(noSensor,"SIM-GATE",true));
        cfg=cloneConfig();cfg.getJSONObject("limits").put("max_body_bytes",20);final JSONObject tiny=cfg;rejects(()->new Config(tiny,"SIM-GATE",true));
        cfg=cloneConfig();cfg.getJSONArray("logical_gates").getJSONObject(0).put("completion_basis","anything");final JSONObject badBasis=cfg;rejects(()->new Config(badBasis,"SIM-GATE",true));
        cfg=cloneConfig();cfg.getJSONArray("logical_gates").getJSONObject(0).put("warehouse_id","OTHER");final JSONObject otherSite=cfg;rejects(()->new Config(otherSite,"SIM-GATE",true));
        cfg=cloneConfig();cfg.getJSONArray("logical_gates").getJSONObject(0).put("indicators",Json.obj("enabled",true,"red_output",1,"green_output",1,"active_high",true));final JSONObject samePin=cfg;rejects(()->new Config(samePin,"SIM-GATE",true));
        Api a=new Api(new Api.Settings(){public boolean simulation(){return true;}public String url(){return "";}public String token(){return "";}});
        check(a.call("GET","/device/config",null,null).getInt("schema_version")==2);
        JSONObject event=Json.obj("event_id","ev-1","raw_epc","E20034120123456789ABCDEF","epc","E20034120123456789ABCDEF","captured_at",Json.now(),"time_quality","synced","antenna","1","rssi_dbm",-45);
        JSONObject evidence=Json.obj("source","fixed_profile","profile_binding_id","sim-u300","sensor_sequence",new JSONArray());
        JSONObject req=Json.obj("schema_version",2,"batch_id","batch-1","mode","live","config_version","sim-v1","context",Json.obj("kind","gate","logical_gate_id","SIM-GATE","local_passage_id","pass-1","direction","out","direction_evidence",evidence),"events",new JSONArray().put(event));
        JSONObject ack=a.call("POST","/events",req,null);check(ack.getJSONArray("event_acks").getJSONObject(0).getBoolean("durable"));
        JSONObject bad=Json.parse(req.toString());bad.getJSONArray("events").getJSONObject(0).put("epc",JSONObject.NULL);
        check(a.call("POST","/events",bad,null).getJSONArray("event_acks").getJSONObject(0).getString("status").equals("quarantined"));
        JSONObject close=Json.obj("logical_gate_id","SIM-GATE","config_version","sim-v1","mode","live","closing_captured_at",Json.now(),"boundary_reason","idle_timeout","last_event_id","ev-1","observed_event_count",1,"capture_complete",true,"direction","out","direction_evidence",evidence);
        JSONObject d=a.call("POST","/passages/pass-1/close",close,"key-1");check(d.getString("verdict").equals("GREEN"));
        check(a.call("POST","/passages/pass-1/close",close,"key-1").getString("decision_id").equals(d.getString("decision_id")));
        a.verdict="RED";a.call("POST","/passages/pass-2/close",close,"key-2");
        JSONObject state=a.call("GET","/device/gate-state?logical_gate_id=SIM-GATE&local_passage_id=pass-1",null,null);
        check(state.getBoolean("latched"));check(state.getJSONObject("decision").getString("local_passage_id").equals("pass-1"));
        a.resetSimulationLatch();check(!a.call("GET","/device/gate-state",null,null).getBoolean("latched"));
        a.offline=true;rejects(()->a.call("POST","/events",req,null));a.offline=false;
        close.put("capture_complete",false);check(a.call("POST","/passages/pass-3/close",close,"key-3").getString("verdict").equals("UNKNOWN"));
        JSONObject fixtures=Json.obj("DeviceConfig",Config.simulation(),"EventsRequest",req,"EventsResponse",ack,"PassageClose",close,"GateDecision",d,"GateState",state);
        Files.write(Paths.get(args[0]),fixtures.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8));
        System.out.println("PASS: "+checks+" configuration/simulation assertions; schema fixtures exported.");
    }
}
