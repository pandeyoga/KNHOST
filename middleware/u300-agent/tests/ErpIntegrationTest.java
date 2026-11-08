package id.kubusteknologi.kn.u300;

import java.io.FileInputStream;
import java.security.KeyStore;
import java.security.cert.CertificateFactory;
import javax.net.ssl.*;
import org.json.*;

/** Runs the real transport and clearance policy against the local ERP router.
 * Trusts only the generated local test certificate. Never packaged into the APK.
 */
public final class ErpIntegrationTest {
    private static int passed;
    private static void check(boolean ok,String label){if(!ok)throw new AssertionError(label);passed++;System.out.println("PASS "+label);}
    public static void main(String[] args) throws Exception {
        KeyStore store=KeyStore.getInstance(KeyStore.getDefaultType());store.load(null,null);
        try(FileInputStream in=new FileInputStream(args[1])){store.setCertificateEntry("erp-local",CertificateFactory.getInstance("X.509").generateCertificate(in));}
        TrustManagerFactory tm=TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());tm.init(store);
        SSLContext ssl=SSLContext.getInstance("TLS");ssl.init(null,tm.getTrustManagers(),null);
        SSLSocketFactory previous=HttpsURLConnection.getDefaultSSLSocketFactory();
        try {
            HttpsURLConnection.setDefaultSSLSocketFactory(ssl.getSocketFactory());
            Api api=new Api(new Api.Settings(){public boolean simulation(){return false;}public String url(){return args[0];}public String token(){return System.getenv("KN_TEST_DEVICE_KEY");}});
            JSONObject cfg=api.call("GET","/device/config",null,null);
            Config config=new Config(cfg,"gate",true); // LAB profile: no physical radio is initialized.
            check(config.version.equals("v1"),"real ERP config parsed by reader");
            String passage=java.util.UUID.randomUUID().toString(),event=java.util.UUID.randomUUID().toString();
            JSONObject body=Json.obj("schema_version",2,"batch_id",java.util.UUID.randomUUID().toString(),"mode","live","config_version",config.version,
                "context",Json.obj("kind","gate","logical_gate_id","gate","local_passage_id",passage),
                "events",new JSONArray().put(Json.obj("event_id",event,"raw_epc",args[2],"epc",args[2],"captured_at",Json.now(),"time_quality","synced","antenna","1","rssi_dbm",-45)));
            JSONObject ack=api.call("POST","/events",body,null);
            check(ack.getJSONArray("event_acks").getJSONObject(0).getBoolean("durable"),"real ERP durable ACK reaches Java");
            JSONObject duplicate=api.call("POST","/events",body,null);
            check(duplicate.getJSONArray("event_acks").getJSONObject(0).getString("status").equals("duplicate"),"Java network retry remains idempotent");
            JSONObject close=Json.obj("logical_gate_id","gate","config_version",config.version,"mode","live","closing_captured_at",Json.now(),"boundary_reason","idle_timeout","last_event_id",event,"observed_event_count",1,"capture_complete",true,"direction","out",
                "direction_evidence",Json.obj("source","fixed_profile","profile_binding_id",cfg.getString("hardware_profile_id"),"sensor_sequence",new JSONArray()));
            JSONObject d=api.call("POST","/passages/"+passage+"/close",close,"java-close");
            check(d.getString("verdict").equals("GREEN"),"ERP authorizes complete real document manifest");
            JSONObject state=api.call("GET","/device/gate-state?logical_gate_id=gate&local_passage_id="+passage,null,null);
            JSONObject meta=Json.obj("logical_gate_id","gate","config_version",config.version,"completion_basis","manifest_full");
            check(DecisionPolicy.validGreen(state,d,meta,passage,"live",Json.time(state.getString("server_time")),5000),"reader accepts fresh ERP clearance");
            check(!DecisionPolicy.validGreen(state,d,meta,passage,"backfill",Json.time(state.getString("server_time")),5000),"reader refuses historical clearance");
            check(api.call("POST","/passages/"+passage+"/close",close,"java-close").getString("decision_id").equals(d.getString("decision_id")),"close retry keeps decision identity");
            close.put("capture_complete",false);
            try {api.call("POST","/passages/"+passage+"/close",close,"java-close");throw new AssertionError("expected conflict");}
            catch(Api.Failure e){check(e.status==409,"ERP conflict reaches reader recovery policy");check(e.getMessage().contains("CLOSE_CONFLICT"),"ERP reason shown in reader diagnostics");}
            System.out.println("ERP_JAVA_HTTPS_ASSERTIONS="+passed);
        } finally {HttpsURLConnection.setDefaultSSLSocketFactory(previous);}
    }
}
