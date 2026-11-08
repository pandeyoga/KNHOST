package id.kubusteknologi.kn.u300;
import org.json.*;
import id.kubusteknologi.kn.u300.core.Safety;
/** Strict validation of the clearance-bearing fields. Unknown/malformed fields fail closed. */
final class DecisionPolicy {
    private static boolean bool(JSONObject o,String key,boolean expected){return o.opt(key) instanceof Boolean&&o.optBoolean(key)==expected;}
    private static boolean zero(JSONObject o,String key){Object v=o.opt(key);return v instanceof Number&&((Number)v).doubleValue()==0;}
    private static boolean whole(JSONObject o,String key){Object v=o.opt(key);return v instanceof Number&&((Number)v).doubleValue()>=0&&((Number)v).doubleValue()==Math.floor(((Number)v).doubleValue());}
    /** Konteks & kesegaran yang sama untuk hijau dan kuning. */
    private static boolean context(JSONObject state,JSONObject d,JSONObject meta,String passage,String mode,long now,long validity){
        if(state==null||d==null||meta==null||validity<1||validity>60000)return false;
        if(!bool(d,"final",true))return false;
        if(!"live".equals(mode)||!"live".equals(d.optString("mode"))||passage==null||!passage.equals(d.optString("local_passage_id")))return false;
        if(!meta.optString("logical_gate_id").equals(d.optString("logical_gate_id"))||!meta.optString("logical_gate_id").equals(state.optString("logical_gate_id"))||!meta.optString("config_version").equals(d.optString("config_version")))return false;
        if(!meta.optString("completion_basis").equals(d.optString("completion_basis")))return false;
        if(d.optString("decision_id").isEmpty())return false;
        long made=Json.time(d.optString("created_at")),expires=Json.time(d.optString("expires_at"));
        return made>0&&made<=now&&now-made<=validity&&expires>now&&expires>=made;
    }
    static boolean validGreen(JSONObject state,JSONObject d,JSONObject meta,String passage,String mode,long now,long validity){
        if(!context(state,d,meta,passage,mode,now,validity))return false;
        if(!bool(state,"latched",false)||!bool(d,"latched",false)||!bool(d,"allow_live_signal",true))return false;
        String basis=d.optString("completion_basis");
        if(!"GREEN".equals(d.optString("verdict"))||!Safety.clearanceBasis(basis))return false;
        JSONObject counts=d.optJSONObject("counts");if(counts==null)return false;
        if(!zero(counts,"missing")||!zero(counts,"extra")||!zero(counts,"unknown"))return false;
        // manifest_full: seluruh dokumen harus lewat di lintasan ini. document_session (K-RFID-10): sisa (pending) boleh > 0.
        if("manifest_full".equals(basis)?!zero(counts,"pending"):!whole(counts,"pending"))return false;
        Object observed=counts.opt("observed_unique"),matched=counts.opt("matched");
        if(!(observed instanceof Number)||!(matched instanceof Number))return false;
        double n=((Number)observed).doubleValue(),m=((Number)matched).doubleValue();
        return n>0&&n==Math.floor(n)&&n==m;
    }
    /** Kuning (REVIEW, K-RFID-09): barang boleh jalan + antrean periksa; tidak pernah saat gate terkunci. */
    static boolean validYellow(JSONObject state,JSONObject d,JSONObject meta,String passage,String mode,long now,long validity){
        if(!context(state,d,meta,passage,mode,now,validity))return false;
        if(!bool(state,"latched",false)||!bool(d,"latched",false))return false;
        return "REVIEW".equals(d.optString("verdict"));
    }
    static boolean sameIdentity(JSONObject a,JSONObject b){
        for(String key:new String[]{"device_id","site_id","warehouse_id","device_type"})
            if(a.optString(key).isEmpty()||!a.optString(key).equals(b.optString(key)))return false;
        return true;
    }
}
