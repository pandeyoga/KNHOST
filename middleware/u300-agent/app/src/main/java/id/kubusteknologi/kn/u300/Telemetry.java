package id.kubusteknologi.kn.u300;
import org.json.*;
/**
 * Payload {@code Telemetry} kontrak 2.1 (murni, teruji di host). {@code platform_health} memuat penghitung 0.5:
 * dropped_reads (AUD-MW-24), bacaan tanpa RSSI/RSSI rusak/antena tak dikenal (AUD-MW-23), kesehatan photo-eye
 * & cadangan RF (AUD-MW-02), daftar latar, polling GPI (AUD-MW-14), sinkron jam (AUD-MW-12), status transport
 * (AUD-MW-06), setelan radio (AUD-MW-04) dan layanan UHF bawaan.
 */
final class Telemetry {
    private Telemetry(){}
    static final class Values {
        String eventId,capturedAt,configVersion,appBuild,radioState="stopped",transport="offline",timeQuality="unsynced",oldestPendingAt,lastErrorMessage="";
        boolean lastErrorRetryable=true;
        long pendingCount,pendingBytes,freeStorage,uptimeSeconds;
        JSONObject health=new JSONObject();
    }
    static JSONObject body(Values v){
        JSONObject t=Json.obj("event_id",v.eventId,"captured_at",v.capturedAt,"config_version",v.configVersion,"app_build",v.appBuild,"sdk_version","20251103",
            "radio_state",v.radioState,"printer_state","not_applicable","erp_transport",v.transport,"pending_event_count",Math.max(0,v.pendingCount),
            "pending_bytes",Math.max(0,v.pendingBytes),"oldest_pending_at",v.oldestPendingAt,"free_storage_bytes",Math.max(0,v.freeStorage),
            "uptime_seconds",Math.max(0,v.uptimeSeconds),"time_quality",v.timeQuality,"last_error",null,"platform_health",v.health);
        if(v.lastErrorMessage!=null&&!v.lastErrorMessage.isEmpty())try{t.put("last_error",Json.obj("code","AGENT_STATUS","message",v.lastErrorMessage.substring(0,Math.min(500,v.lastErrorMessage.length())),"retryable",v.lastErrorRetryable));}catch(JSONException e){throw new IllegalStateException(e);}
        return t;
    }
}
