package id.kubusteknologi.kn.u300;
import org.json.*;
import java.nio.file.*;
public class HostTest {
    static int checks;
    static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
    interface Action {void run() throws Exception;}
    static void rejects(Action action)throws Exception{boolean rejected=false;try{action.run();}catch(Exception e){rejected=true;}check(rejected);}
    static JSONObject cloneConfig(){return Json.parse(Config.simulation().toString());}
    static JSONObject gate(JSONObject cfg)throws Exception{return cfg.getJSONArray("logical_gates").getJSONObject(0);}
    static JSONObject params(JSONObject cfg)throws Exception{return cfg.getJSONObject("hardware_profile").getJSONObject("parameters");}
    public static void main(String[] args)throws Exception{
        JSONObject cfg=cloneConfig();Config c=new Config(cfg,"SIM-GATE",true);check(c.antennas.size()==3);check("one_way_beam".equals(c.sensorMode));check("document_session".equals(c.basis));
        rejects(()->new Config(cloneConfig(),"WRONG-GATE",true));
        rejects(()->new Config(cloneConfig(),"SIM-GATE",false));
        cfg=cloneConfig();cfg.put("enabled",false);final JSONObject disabled=cfg;rejects(()->new Config(disabled,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).put("direction","bidirectional");gate(cfg).put("sensor_bindings",new JSONObject());final JSONObject noSensor=cfg;rejects(()->new Config(noSensor,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).put("direction","bidirectional");check("legacy_bidirectional".equals(new Config(cfg,"SIM-GATE",true).sensorMode));
        cfg=cloneConfig();gate(cfg).put("sensor_bindings",new JSONObject());check("rf_only".equals(new Config(cfg,"SIM-GATE",true).sensorMode));
        cfg=cloneConfig();gate(cfg).put("sensor_bindings",Json.obj("a","GPI1"));final JSONObject onlyA=cfg;rejects(()->new Config(onlyA,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).put("sensor_bindings",Json.obj("a","GPI1","b","GPI1"));final JSONObject sameAB=cfg;rejects(()->new Config(sameAB,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).put("sensor_bindings",Json.obj("a","IN1","b","GPI2"));final JSONObject badPin=cfg;rejects(()->new Config(badPin,"SIM-GATE",true));
        cfg=cloneConfig();cfg.getJSONObject("limits").put("max_body_bytes",20);final JSONObject tiny=cfg;rejects(()->new Config(tiny,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).put("completion_basis","anything");final JSONObject badBasis=cfg;rejects(()->new Config(badBasis,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).put("warehouse_id","OTHER");final JSONObject otherSite=cfg;rejects(()->new Config(otherSite,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).put("indicators",Json.obj("enabled",true,"red_output",1,"green_output",1,"active_high",true));final JSONObject samePin=cfg;rejects(()->new Config(samePin,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).getJSONObject("indicators").put("yellow_output",3);final JSONObject yellowRed=cfg;rejects(()->new Config(yellowRed,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).getJSONObject("indicators").put("yellow_output",0).put("buzzer_output",0);check(new Config(cfg,"SIM-GATE",true).yellowOut==0);
        // Parameter lintasan (GateParameters 2.1): batas & konsistensi, fail-closed
        cfg=cloneConfig();gate(cfg).getJSONObject("passage_parameters").put("pre_buffer_ms",20000);final JSONObject pre=cfg;rejects(()->new Config(pre,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).getJSONObject("passage_parameters").put("bucket_ms",50).put("max_passage_ms",120000);final JSONObject buckets=cfg;rejects(()->new Config(buckets,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).getJSONObject("passage_parameters").put("rssi_default_strong_dbm",5);final JSONObject rssi=cfg;rejects(()->new Config(rssi,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).getJSONObject("passage_parameters").put("rssi_strong_dbm",Json.obj("1",-60));check(new Config(cfg,"SIM-GATE",true).pipeline.strongDbm.get("1")==-60.0);
        cfg=cloneConfig();gate(cfg).getJSONObject("passage_parameters").put("min_block_ms",10);final JSONObject debounce=cfg;rejects(()->new Config(debounce,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).getJSONObject("passage_parameters").put("entry_timeout_ms",40000);final JSONObject entry=cfg;rejects(()->new Config(entry,"SIM-GATE",true));
        cfg=cloneConfig();gate(cfg).remove("passage_parameters");Config dflt=new Config(cfg,"SIM-GATE",true);check(dflt.pipeline.machine.preBufferMs==3000&&dflt.pipeline.defaultStrongDbm==-65&&dflt.maxMs==30000);
        // Tuning agent & setelan radio
        cfg=cloneConfig();params(cfg).put("agent_tuning",Json.obj("ring_buffer_ms",2000));final JSONObject ring=cfg;rejects(()->new Config(ring,"SIM-GATE",true));
        cfg=cloneConfig();params(cfg).put("agent_tuning",Json.obj("builtin_service",Json.obj("action","ignore")));final JSONObject builtin=cfg;rejects(()->new Config(builtin,"SIM-GATE",true));
        cfg=cloneConfig();params(cfg).getJSONObject("radio").put("gen2",Json.obj("session",0));final JSONObject gen2=cfg;rejects(()->new Config(gen2,"SIM-GATE",true));
        cfg=cloneConfig();params(cfg).getJSONObject("antenna_positions").put("1","depan");final JSONObject pos=cfg;rejects(()->new Config(pos,"SIM-GATE",true));
        // Profil perangkat (non-simulasi): commissioning wajib region, daya per port, peta posisi
        JSONObject prod=cloneConfig();params(prod).put("commissioned",true);check(new Config(prod,"SIM-GATE",false).radio.getInt("region_code")==63);
        cfg=Json.parse(prod.toString());params(cfg).getJSONObject("radio").put("region_code",-1);final JSONObject region=cfg;rejects(()->new Config(region,"SIM-GATE",false));
        cfg=Json.parse(prod.toString());params(cfg).getJSONObject("radio").getJSONObject("antenna_power_dbm").remove("3");final JSONObject power=cfg;rejects(()->new Config(power,"SIM-GATE",false));
        cfg=Json.parse(prod.toString());params(cfg).getJSONObject("antenna_positions").remove("2");final JSONObject nopos=cfg;rejects(()->new Config(nopos,"SIM-GATE",false));
        cfg=Json.parse(prod.toString());params(cfg).remove("radio");params(cfg).put("expected_region_code",63).put("expected_antenna_power_dbm",Json.obj("1",15,"2",15,"3",15));
        Config legacy=new Config(cfg,"SIM-GATE",false);check(!legacy.radio.getBoolean("apply")&&legacy.radio.getInt("region_code")==63);
        // Simulator ERP (0.4 & 2.1)
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
        a.verdict="GREEN";
        // 2.1 / K-RFID-09: capture tidak lengkap = kuning (REVIEW) tanpa kunci, bukan merah/UNKNOWN
        close.put("capture_complete",false);JSONObject review=a.call("POST","/passages/pass-3/close",close,"key-3");check(review.getString("verdict").equals("REVIEW")&&!review.getBoolean("latched"));
        JSONObject fixtures=Json.obj("DeviceConfig",Config.simulation(),"EventsRequest",req,"EventsResponse",ack,"PassageClose",close,"GateDecision",d,"GateState",state);
        Files.write(Paths.get(args[0]),fixtures.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8));
        System.out.println("PASS: "+checks+" configuration/simulation assertions; schema fixtures exported.");
    }
}
