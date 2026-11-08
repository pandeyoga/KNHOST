package id.kubusteknologi.kn.u300;
import org.json.*;
import java.util.*;
import id.kubusteknologi.kn.u300.core.BackgroundLearner;
import id.kubusteknologi.kn.u300.core.GatePipeline;
import id.kubusteknologi.kn.u300.core.PassageMachine;

/**
 * DeviceConfig kontrak 2.1 + ekstensi profil {@code kn-u300-v1} (hardware_profile.parameters). Semua nilai
 * bawaan di sini = TITIK AWAL KALIBRASI (K-RFID-03/05/08 masih terbuka), sama dengan bawaan server
 * {@code rfid_v2_params.DEFAULTS}. Profil tidak valid → agent tidak mulai (fail-closed).
 */
final class Config {
    static final List<String> POSITIONS=Arrays.asList("atas","kiri","kanan","lainnya");
    final JSONObject raw,gate,policy,parameters,passageParameters,tuning,radio,sensors,indicators;
    final String version,gateId,direction,basis,sensorMode,pinA,pinB;
    final Set<String> antennas=new LinkedHashSet<>();
    final Map<String,String> positions=new LinkedHashMap<>();
    final int maxEvents,maxBody,idleMs,maxMs,activeState,gpiPollMs,antennaBase,readQueue;
    final int greenOut,yellowOut,redOut,buzzerOut;
    final long maxQueue,minBlockMs,minClearMs,checkpointMs,uploadBudgetMs,yellowHoldMs,buzzerMs;
    final boolean indicatorsEnabled;
    final int[] builtinPorts;final String builtinAction;
    final GatePipeline.Settings pipeline=new GatePipeline.Settings();

    static String fingerprint(JSONObject source){JSONObject copy=Json.parse(source.toString());copy.remove("server_time");return Json.canonical(copy);}

    private static int range(JSONObject o,String key,int def,int lo,int hi,String label) throws Exception{
        if(!o.has(key)||o.isNull(key))return def;Object v=o.get(key);
        if(!(v instanceof Integer||v instanceof Long)||((Number)v).longValue()<lo||((Number)v).longValue()>hi)throw new Exception(label+" '"+key+"' wajib bilangan bulat "+lo+"–"+hi+".");
        return ((Number)v).intValue();
    }
    private static double dbm(Object v,String label) throws Exception{
        if(!(v instanceof Number)||((Number)v).doubleValue()<-120||((Number)v).doubleValue()>0)throw new Exception(label+" wajib angka −120 s.d. 0 dBm.");
        return ((Number)v).doubleValue();
    }

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
        if(!Arrays.asList("per_epc_only","manifest_subset","manifest_full","document_session").contains(basis))throw new Exception("Completion basis tidak didukung");
        if(version.isEmpty()||o.getString("device_id").isEmpty())throw new Exception("Identitas atau versi kosong");
        if(!gate.getString("site_id").equals(o.getString("site_id"))||!gate.getString("warehouse_id").equals(o.getString("warehouse_id")))throw new Exception("Lokasi gate tidak sesuai identitas device");
        if(policy.getInt("gate_decision_validity_seconds")<1||policy.getInt("gate_decision_validity_seconds")>60)throw new Exception("Masa berlaku keputusan di luar batas 1..60 detik");
        JSONArray ants=gate.getJSONArray("antenna_ids");for(int i=0;i<ants.length();i++)antennas.add(ants.getString(i));
        if(antennas.isEmpty())throw new Exception("Pemetaan antena kosong.");
        for(String ant:antennas)if(!ant.matches("[1-9]|1[0-6]"))throw new Exception("ID antena wajib 1..16 (port SDK ANT1..ANT16).");

        // ---- peta port → posisi antena (K-RFID-05: atas/kiri/kanan)
        JSONObject pos=parameters.optJSONObject("antenna_positions");
        if(pos!=null)for(Iterator<String> it=pos.keys();it.hasNext();){String k=it.next();String v=pos.getString(k);if(!antennas.contains(k))throw new Exception("Posisi antena untuk port "+k+" yang tidak dipakai gate.");if(!POSITIONS.contains(v))throw new Exception("Posisi antena wajib atas/kiri/kanan/lainnya.");positions.put(k,v);}
        if(!sim&&!positions.keySet().containsAll(antennas))throw new Exception("Peta port → posisi antena (atas/kiri/kanan) wajib untuk setiap antena.");

        // ---- setelan radio (AUD-MW-04): radio{} 0.5; cadangan dari field 0.4 (verifikasi saja)
        JSONObject r=parameters.optJSONObject("radio");
        if(r==null){
            r=new JSONObject();r.put("apply",false);
            if(parameters.has("expected_region_code"))r.put("region_code",parameters.getInt("expected_region_code"));
            if(parameters.has("expected_antenna_power_dbm"))r.put("antenna_power_dbm",parameters.getJSONObject("expected_antenna_power_dbm"));
        }
        radio=r;
        if(!sim){
            if(radio.optInt("region_code",-1)<0)throw new Exception("Region perlu commissioning (kandidat 0x3F = 63 Indonesia 920–923 MHz, wajib dikonfirmasi di unit).");
            JSONObject power=radio.optJSONObject("antenna_power_dbm");if(power==null)throw new Exception("Daya per port perlu commissioning.");
            for(String ant:antennas){if(!power.has(ant)||power.getInt(ant)<0||power.getInt(ant)>33)throw new Exception("Antena/power belum valid (port "+ant+").");}
        }
        JSONObject gen2=radio.optJSONObject("gen2");
        if(gen2!=null)for(Iterator<String> it=gen2.keys();it.hasNext();){String k=it.next();if(!Arrays.asList(id.kubusteknologi.kn.u300.core.RadioSetup.GEN2_KEYS).contains(k))throw new Exception("Kunci Gen2 tidak dikenal: "+k);range(gen2,k,0,0,255,"Gen2");}

        // ---- batas transport
        JSONObject limits=o.getJSONObject("limits");maxEvents=Math.min(500,limits.getInt("max_events"));maxBody=limits.getInt("max_body_bytes");maxQueue=limits.getLong("max_queue_bytes");
        idleMs=policy.getInt("passage_idle_close_milliseconds");
        if(maxEvents<1||maxBody<2048||maxBody>1_000_000||maxQueue<4096||idleMs<500)throw new Exception("Batas konfigurasi tidak aman.");
        if(!"stop_capture_and_alarm".equals(policy.getString("queue_full_action")))throw new Exception("Queue policy tidak didukung");

        // ---- parameter lintasan (GateParameters kontrak 2.1; bawaan = titik awal kalibrasi)
        JSONObject pp=gate.optJSONObject("passage_parameters");passageParameters=pp==null?new JSONObject():pp;
        tuning=parameters.optJSONObject("agent_tuning")==null?new JSONObject():parameters.getJSONObject("agent_tuning");
        PassageMachine.Params m=pipeline.machine;
        m.preBufferMs=range(passageParameters,"pre_buffer_ms",3000,0,10000,"Parameter gate");
        m.tailMs=range(passageParameters,"tail_ms",1500,0,10000,"Parameter gate");
        minBlockMs=range(passageParameters,"min_block_ms",50,1,1000,"Parameter gate");
        m.entryTimeoutMs=range(passageParameters,"entry_timeout_ms",10000,1000,60000,"Parameter gate");
        maxMs=range(passageParameters,"max_passage_ms",parameters.optInt("max_passage_milliseconds",30000),5000,120000,"Parameter gate");m.maxPassageMs=maxMs;
        m.stableIntervalMs=range(passageParameters,"stable_interval_ms",3000,500,10000,"Parameter gate");
        pipeline.bucketMs=range(passageParameters,"bucket_ms",250,50,2000,"Parameter gate");
        m.rfGroupSize=range(passageParameters,"rf_fallback_group_size",3,1,100,"Parameter gate");
        m.rfWindowMs=range(passageParameters,"rf_fallback_window_ms",1500,100,10000,"Parameter gate");
        pipeline.learner.retentionMs=range(passageParameters,"background_retention_s",86400,60,604800,"Parameter gate")*1000L;
        pipeline.defaultStrongDbm=passageParameters.has("rssi_default_strong_dbm")?dbm(passageParameters.get("rssi_default_strong_dbm"),"Ambang RSSI bawaan"):-65;
        JSONObject per=passageParameters.optJSONObject("rssi_strong_dbm");
        if(per!=null)for(Iterator<String> it=per.keys();it.hasNext();){String k=it.next();pipeline.strongDbm.put(k,dbm(per.get(k),"Ambang RSSI antena "+k));}
        if(m.entryTimeoutMs>=maxMs||m.tailMs>=maxMs)throw new Exception("entry_timeout_ms dan tail_ms wajib < max_passage_ms.");
        if((maxMs+m.preBufferMs+m.tailMs)/pipeline.bucketMs>id.kubusteknologi.kn.u300.core.Aggregator.MAX_BUCKETS)throw new Exception("bucket_ms terlalu kecil untuk max_passage_ms (maks 400 bucket per ringkasan).");

        // ---- tuning agent (hardware_profile.parameters.agent_tuning; titik awal kalibrasi)
        gpiPollMs=range(tuning,"gpi_poll_ms",20,5,100,"Tuning agent");
        minClearMs=range(tuning,"min_clear_ms",200,1,2000,"Tuning agent");
        m.betweenTimeoutMs=range(tuning,"between_timeout_ms",5000,500,60000,"Tuning agent");
        m.sensorStuckMs=range(tuning,"sensor_stuck_ms",45000,5000,600000,"Tuning agent");
        m.recoverySequences=range(tuning,"sensor_recovery_sequences",2,1,20,"Tuning agent");
        m.bBeforeALimit=range(tuning,"b_before_a_limit",1,1,20,"Tuning agent");
        pipeline.ringMs=range(tuning,"ring_buffer_ms",10000,1000,60000,"Tuning agent");
        readQueue=range(tuning,"read_queue_capacity",20000,1000,200000,"Tuning agent");
        pipeline.learner.minReads=range(tuning,"background_min_reads",3,1,1000,"Tuning agent");
        pipeline.learner.minSpanMs=range(tuning,"background_min_span_ms",2000,0,600000,"Tuning agent");
        pipeline.learner.jumpDb=range(tuning,"background_jump_db",10,1,60,"Tuning agent");
        pipeline.learner.warmupMs=range(tuning,"background_warmup_ms",5000,0,600000,"Tuning agent");
        pipeline.checkpointMs=checkpointMs=range(tuning,"checkpoint_ms",1000,200,10000,"Tuning agent");
        uploadBudgetMs=range(tuning,"upload_budget_ms",3000,200,30000,"Tuning agent");
        antennaBase=range(tuning,"antenna_index_base",1,0,1,"Tuning agent");pipeline.antennaBase=antennaBase;
        yellowHoldMs=range(tuning,"yellow_hold_ms",policy.getInt("gate_decision_validity_seconds")*1000,500,60000,"Tuning agent");
        buzzerMs=range(tuning,"buzzer_ms",3000,0,60000,"Tuning agent");
        JSONObject builtin=tuning.optJSONObject("builtin_service");
        JSONArray ports=builtin==null?null:builtin.optJSONArray("ports");
        builtinPorts=new int[ports==null?2:ports.length()];
        if(ports==null){builtinPorts[0]=9160;builtinPorts[1]=9260;}else for(int i=0;i<ports.length();i++)builtinPorts[i]=ports.getInt(i);
        builtinAction=builtin==null?"block":builtin.optString("action","block");
        if(!Arrays.asList("block","warn").contains(builtinAction))throw new Exception("builtin_service.action wajib block/warn.");
        pipeline.antennas.addAll(antennas);
        if(pipeline.ringMs<m.preBufferMs+1000)throw new Exception("ring_buffer_ms wajib ≥ pre_buffer_ms + 1000.");
        if(minBlockMs<gpiPollMs)throw new Exception("min_block_ms wajib ≥ gpi_poll_ms (debounce tidak boleh lebih rapat dari polling GPI).");
        if(m.sensorStuckMs<m.entryTimeoutMs)throw new Exception("sensor_stuck_ms wajib ≥ entry_timeout_ms.");

        // ---- sensor photo-eye (K-RFID-01): satu arah = A mulut masuk, B mulut keluar
        JSONObject sb=gate.optJSONObject("sensor_bindings");sensors=sb==null?new JSONObject():sb;
        String a=sensors.optString("a"),b=sensors.optString("b");pinA=a;pinB=b;
        activeState=sensors.optInt("active_state",1);
        if(activeState!=0&&activeState!=1)throw new Exception("Active state harus 0/1");
        for(String pin:new String[]{a,b})if(!pin.isEmpty()&&!pin.matches("GPI[1-4]"))throw new Exception("Input sensor wajib GPI1..GPI4 sesuai SDK");
        if(!a.isEmpty()&&a.equals(b))throw new Exception("Sensor A dan B wajib input berbeda.");
        if("bidirectional".equals(direction)){
            if(a.isEmpty()||b.isEmpty())throw new Exception("Gate dua arah wajib sensor A/B yang berbeda.");
            sensorMode="legacy_bidirectional";pipeline.mode=PassageMachine.Mode.LEGACY_BIDIRECTIONAL;
            m.legacyIdleMs=idleMs;
            int debounce=sensors.optInt("debounce_ms",100),window=sensors.optInt("sequence_window_ms",5000);
            if(debounce<10||debounce>2000||window<100||window>maxMs)throw new Exception("Timing sensor di luar batas");
            m.legacySequenceWindowMs=window;
        }else if(a.isEmpty()&&b.isEmpty()){
            sensorMode="rf_only";pipeline.mode=PassageMachine.Mode.RF_ONLY;
        }else{
            if(a.isEmpty()||b.isEmpty())throw new Exception("Gate satu arah ber-photo-eye wajib sensor A (mulut masuk) dan B (mulut keluar).");
            String mode=sensors.optString("mode","through_beam");if(!"through_beam".equals(mode))throw new Exception("Mode sensor yang didukung: through_beam.");
            sensorMode="one_way_beam";pipeline.mode=PassageMachine.Mode.ONE_WAY_BEAM;
        }

        // ---- indikator 4 GPO (AUD-MW-14): hijau / kuning / merah / buzzer
        JSONObject ind=gate.optJSONObject("indicators");indicators=ind==null?new JSONObject():ind;
        indicatorsEnabled=indicators.optBoolean("enabled");
        redOut=indicators.optInt("red_output");greenOut=indicators.optInt("green_output");yellowOut=indicators.optInt("yellow_output",0);buzzerOut=indicators.optInt("buzzer_output",0);
        if(indicatorsEnabled){
            if(!indicators.optBoolean("active_high"))throw new Exception("Mapping output hanya 1..4 active-high.");
            Set<Integer> used=new HashSet<>();int[] outs={redOut,greenOut,yellowOut,buzzerOut};
            for(int i=0;i<outs.length;i++){boolean optional=i>=2;if(optional&&outs[i]==0)continue;if(outs[i]<1||outs[i]>4||!used.add(outs[i]))throw new Exception("Mapping output hanya 1..4 active-high; harus berbeda (kuning/buzzer 0 = tidak dipasang).");}
        }
    }

    JSONObject summary(){
        return Json.obj("config_version",version,"gate",gateId,"direction",direction,"basis",basis,"sensor_mode",sensorMode,"antennas",new JSONArray(antennas),"positions",new JSONObject(positions),"calibration_status",passageParameters.optString("calibration_status","initial"));
    }

    static JSONObject simulation(){
        JSONObject positions=Json.obj("1","atas","2","kiri","3","kanan");
        JSONObject power=Json.obj("1",15,"2",15,"3",15);
        JSONObject radio=Json.obj("apply",true,"region_code",63,"antenna_power_dbm",power,"gen2",Json.obj("query_session",0,"query_target",0),"tag_focus",false,"fast_id",false);
        return Json.obj("schema_version",2,"device_id","SIM-U300","device_type","fixed_reader","site_id","SIM-SITE","warehouse_id","SIM-WH","enabled",true,"config_version","sim-v1","server_time",Json.now(),"hardware_profile_id","sim-u300",
            "hardware_profile",Json.obj("model_label","SIMULATOR","firmware_version","sim","sdk_name","DeviceAPI","sdk_version","20251103","profile_revision","1","capabilities",new JSONArray(),"parameters",Json.obj("agent_profile","kn-u300-v1","commissioned",false,"antenna_positions",positions,"radio",radio,"agent_tuning",Json.obj("background_warmup_ms",3000))),
            "limits",Json.obj("max_events",100,"max_body_bytes",256000,"max_queue_bytes",10000000),
            "policies",Json.obj("telemetry_interval_seconds",30,"retry_initial_seconds",2,"retry_max_seconds",60,"capture_offline_allowed",true,"gate_decision_validity_seconds",5,"passage_idle_close_milliseconds",3000,"printer_lease_seconds",60,"printer_max_started_items",1,"queue_full_action","stop_capture_and_alarm"),
            "logical_gates",new JSONArray().put(Json.obj("logical_gate_id","SIM-GATE","direction","out","antenna_ids",new JSONArray().put("1").put("2").put("3"),"sensor_bindings",Json.obj("a","GPI1","b","GPI2","active_state",1,"mode","through_beam"),"site_id","SIM-SITE","warehouse_id","SIM-WH","completion_basis","document_session","enabled",true,
                "indicators",Json.obj("enabled",true,"active_high",true,"green_output",1,"yellow_output",2,"red_output",3,"buzzer_output",4),
                "passage_parameters",Json.obj("calibration_status","initial","pre_buffer_ms",3000,"tail_ms",1500,"min_block_ms",50,"entry_timeout_ms",10000,"max_passage_ms",30000,"stable_interval_ms",3000,"bucket_ms",250,"rf_fallback_group_size",3,"rf_fallback_window_ms",1500,"rssi_strong_dbm",new JSONObject(),"rssi_default_strong_dbm",-65,"background_retention_s",86400))));
    }
}
