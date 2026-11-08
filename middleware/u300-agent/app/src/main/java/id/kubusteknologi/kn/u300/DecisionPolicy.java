package id.kubusteknologi.kn.u300;
import org.json.*;
/** Strict validation of the clearance-bearing fields. Unknown/malformed fields fail closed. */
final class DecisionPolicy {
    private static boolean bool(JSONObject o,String key,boolean expected){return o.opt(key) instanceof Boolean&&o.optBoolean(key)==expected;}
    private static boolean zero(JSONObject o,String key){Object v=o.opt(key);return v instanceof Number&&((Number)v).doubleValue()==0;}
    static boolean validGreen(JSONObject state,JSONObject d,JSONObject meta,String passage,String mode,long now,long validity){
        if(state==null||d==null||meta==null||validity<1||validity>60000)return false;
        if(!bool(state,"latched",false)||!bool(d,"latched",false)||!bool(d,"final",true)||!bool(d,"allow_live_signal",true))return false;
        if(!"GREEN".equals(d.optString("verdict"))||!"manifest_full".equals(d.optString("completion_basis"))||!"manifest_full".equals(meta.optString("completion_basis")))return false;
        if(!"live".equals(mode)||!"live".equals(d.optString("mode"))||passage==null||!passage.equals(d.optString("local_passage_id")))return false;
        if(!meta.optString("logical_gate_id").equals(d.optString("logical_gate_id"))||!meta.optString("logical_gate_id").equals(state.optString("logical_gate_id"))||!meta.optString("config_version").equals(d.optString("config_version")))return false;
        if(d.optString("decision_id").isEmpty())return false;
        long made=Json.time(d.optString("created_at")),expires=Json.time(d.optString("expires_at"));
        if(made<=0||made>now||now-made>validity||expires<=now||expires<made)return false;
        JSONObject counts=d.optJSONObject("counts");if(counts==null)return false;
        if(!zero(counts,"missing")||!zero(counts,"extra")||!zero(counts,"unknown")||!zero(counts,"pending"))return false;
        Object observed=counts.opt("observed_unique"),matched=counts.opt("matched");
        if(!(observed instanceof Number)||!(matched instanceof Number))return false;
        double n=((Number)observed).doubleValue(),m=((Number)matched).doubleValue();
        return n>0&&n==Math.floor(n)&&n==m;
    }
    static boolean sameIdentity(JSONObject a,JSONObject b){
        for(String key:new String[]{"device_id","site_id","warehouse_id","device_type"})
            if(a.optString(key).isEmpty()||!a.optString(key).equals(b.optString(key)))return false;
        return true;
    }
}
