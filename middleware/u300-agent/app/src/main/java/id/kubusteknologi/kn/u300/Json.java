package id.kubusteknologi.kn.u300;
import org.json.*;
import java.time.Instant;
final class Json {
    static JSONObject obj(Object... pairs) {
        JSONObject o=new JSONObject();
        try { for(int i=0;i<pairs.length;i+=2) o.put((String)pairs[i],pairs[i+1]==null?JSONObject.NULL:pairs[i+1]); }
        catch(JSONException e) { throw new IllegalArgumentException(e); } return o;
    }
    static JSONObject parse(String s) { try {return new JSONObject(s);} catch(JSONException e){throw new IllegalArgumentException("JSON tidak valid",e);} }
    static String now() { return Instant.now().toString(); }
    static long time(String s) { try {return Instant.parse(s).toEpochMilli();} catch(Exception e){return 0;} }
    static String canonical(Object value){
        if(value instanceof JSONObject){JSONObject o=(JSONObject)value;java.util.TreeSet<String> keys=new java.util.TreeSet<>();java.util.Iterator<String> it=o.keys();while(it.hasNext())keys.add(it.next());StringBuilder b=new StringBuilder("{");for(String k:keys){if(b.length()>1)b.append(',');b.append(JSONObject.quote(k)).append(':').append(canonical(o.opt(k)));}return b.append('}').toString();}
        if(value instanceof JSONArray){JSONArray a=(JSONArray)value;StringBuilder b=new StringBuilder("[");for(int i=0;i<a.length();i++){if(i>0)b.append(',');b.append(canonical(a.opt(i)));}return b.append(']').toString();}
        if(value instanceof String)return JSONObject.quote((String)value);
        return String.valueOf(value);
    }
}
