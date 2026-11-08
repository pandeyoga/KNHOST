package id.kubusteknologi.kn.u300;
import org.json.*;
import java.util.*;
final class Config {
    final JSONObject raw,gate,policy,parameters;
    final String version,gateId,direction,basis;
    final Set<String> antennas=new HashSet<>();
    final int maxEvents,maxBody,idleMs,maxMs;
    final long maxQueue;
    static String fingerprint(JSONObject source){JSONObject copy=Json.parse(source.toString());copy.remove("server_time");return Json.canonical(copy);}
    Config(JSONObject o,String selected,boolean sim) throws Exception {
        raw=o;
        if(o.getInt("schema_version")!=2||!o.getBoolean("enabled")||!"fixed_reader".equals(o.getString("device_type")))throw new Exception("Perangkat tidak aktif / schema tidak didukung.");
        version=o.getString("config_version"); policy=o.getJSONObject("policies");
        parameters=o.getJSONObject("hardware_profile").getJSONObject("parameters");
        if(!sim && (!"kn-u300-v1".equals(parameters.optString("agent_profile"))||!parameters.optBoolean("commissioned")))
            throw new Exception("Profil U300 belum dikomisikan: agent_profile kn-u300-v1 dan commissioned wajib.");
        JSONArray gates=o.getJSONArray("logical_gates");JSONObject chosen=null;
        for(int i=0;i<gates.length();i++){JSONObject g=gates.getJSONObject(i);if(g.getString("logical_gate_id").equals(selected)&&g.getBoolean("enabled"))chosen=g;}
        if(chosen==null)throw new Exception("Logical gate tidak tersedia.");gate=chosen;gateId=selected;
        direction=gate.getString("direction");basis=gate.getString("completion_basis");
        if(!Arrays.asList("in","out","bidirectional").contains(direction))throw new Exception("Arah tidak didukung");
        if(!Arrays.asList("per_epc_only","manifest_subset","manifest_full").contains(basis))throw new Exception("Completion basis tidak didukung");
        if(version.isEmpty()||o.getString("device_id").isEmpty())throw new Exception("Identitas atau versi kosong");
        if(!gate.getString("site_id").equals(o.getString("site_id"))||!gate.getString("warehouse_id").equals(o.getString("warehouse_id")))throw new Exception("Lokasi gate tidak sesuai identitas device");
        if(policy.getInt("gate_decision_validity_seconds")<1||policy.getInt("gate_decision_validity_seconds")>60)throw new Exception("Masa berlaku keputusan di luar batas 1..60 detik");
        JSONArray ants=gate.getJSONArray("antenna_ids");for(int i=0;i<ants.length();i++)antennas.add(ants.getString(i));
        if(antennas.isEmpty())throw new Exception("Pemetaan antena kosong.");
        if(!sim){
            if(parameters.getInt("expected_region_code")<0)throw new Exception("Region perlu commissioning");
            JSONObject power=parameters.getJSONObject("expected_antenna_power_dbm");
            for(String ant:antennas){if(!ant.matches("[1-8]")||power.getInt(ant)<0)throw new Exception("Antena/power belum valid");}
        }
        JSONObject limits=o.getJSONObject("limits");maxEvents=Math.min(500,limits.getInt("max_events"));maxBody=limits.getInt("max_body_bytes");maxQueue=limits.getLong("max_queue_bytes");
        idleMs=policy.getInt("passage_idle_close_milliseconds");maxMs=parameters.optInt("max_passage_milliseconds",30000);
        if(maxEvents<1||maxBody<2048||maxQueue<4096||idleMs<500||maxMs<idleMs||maxMs>300000)throw new Exception("Batas konfigurasi tidak aman.");
        if(!"stop_capture_and_alarm".equals(policy.getString("queue_full_action")))throw new Exception("Queue policy tidak didukung");
        JSONObject sensors=gate.optJSONObject("sensor_bindings");
        if("bidirectional".equals(direction)&&(sensors==null||sensors.optString("a").isEmpty()||sensors.optString("b").isEmpty()||sensors.optString("a").equals(sensors.optString("b"))))throw new Exception("Gate dua arah wajib sensor A/B yang berbeda.");
        if(sensors!=null&&!sensors.optString("a").isEmpty()){
            for(String label:new String[]{"a","b"})if(!sensors.optString(label).isEmpty()&&!sensors.optString(label).matches("GPI[1-4]"))throw new Exception("Input sensor wajib GPI1..GPI4 sesuai SDK");
            if(sensors.optInt("active_state",1)!=0&&sensors.optInt("active_state",1)!=1)throw new Exception("Active state harus 0/1");
            if(sensors.optInt("debounce_ms",100)<10||sensors.optInt("debounce_ms",100)>2000||sensors.optInt("sequence_window_ms",5000)<100||sensors.optInt("sequence_window_ms",5000)>maxMs)throw new Exception("Timing sensor di luar batas");
        }
        JSONObject ind=gate.optJSONObject("indicators");if(ind!=null && ind.optBoolean("enabled")){
            int red=ind.optInt("red_output"),green=ind.optInt("green_output");
            if(red<1||red>4||green<1||green>4||red==green||!ind.optBoolean("active_high"))throw new Exception("Mapping output hanya 1..4 active-high; harus berbeda.");
        }
    }
    static JSONObject simulation(){
        return Json.obj("schema_version",2,"device_id","SIM-U300","device_type","fixed_reader","site_id","SIM-SITE","warehouse_id","SIM-WH","enabled",true,"config_version","sim-v1","server_time",Json.now(),"hardware_profile_id","sim-u300",
            "hardware_profile",Json.obj("model_label","SIMULATOR","firmware_version","sim","sdk_name","DeviceAPI","sdk_version","20251103","profile_revision","1","capabilities",new JSONArray(),"parameters",Json.obj("agent_profile","kn-u300-v1","commissioned",false,"max_passage_milliseconds",30000)),
            "limits",Json.obj("max_events",100,"max_body_bytes",128000,"max_queue_bytes",10000000),
            "policies",Json.obj("telemetry_interval_seconds",30,"retry_initial_seconds",2,"retry_max_seconds",60,"capture_offline_allowed",true,"gate_decision_validity_seconds",5,"passage_idle_close_milliseconds",3000,"printer_lease_seconds",60,"printer_max_started_items",1,"queue_full_action","stop_capture_and_alarm"),
            "logical_gates",new JSONArray().put(Json.obj("logical_gate_id","SIM-GATE","direction","out","antenna_ids",new JSONArray().put("1").put("2"),"sensor_bindings",Json.obj(),"site_id","SIM-SITE","warehouse_id","SIM-WH","completion_basis","manifest_full","enabled",true,"indicators",Json.obj("enabled",false))));
    }
}
