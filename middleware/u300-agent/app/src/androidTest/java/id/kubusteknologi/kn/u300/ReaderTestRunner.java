package id.kubusteknologi.kn.u300;
import android.app.Instrumentation;
import android.os.Bundle;
import org.json.*;
import java.util.*;
/** Real Android SQLite tests. Own randomly named database; never touches operational databases. */
public final class ReaderTestRunner extends Instrumentation {
    private int assertions;
    private void check(boolean condition){assertions++;if(!condition)throw new AssertionError("assertion "+assertions);}
    @Override public void onCreate(Bundle args){super.onCreate(args);start();}
    @Override public void onStart(){Bundle result=new Bundle();String database="uat-"+UUID.randomUUID()+".db";
        try(Journal db=new Journal(getTargetContext(),database)){
            db.open("p1",Json.obj("opened_at",Json.now()),"live");
            db.add("e1","p1",Json.obj("event_id","e1"));db.add("e2","p1",Json.obj("event_id","e2"));
            boolean duplicate=false;try{db.add("e1","p1",Json.obj());}catch(android.database.sqlite.SQLiteConstraintException expected){duplicate=true;}check(duplicate);
            JSONObject b=Json.obj("batch_id","b1");db.createBatch("b1","p1",b,Arrays.asList("e1","e2"));
            db.acknowledgements("b1",new JSONArray().put(Json.obj("event_id","e1","status","accepted","durable",false)));check(db.count("status='pending'")==2);
            db.acknowledgements("b1",new JSONArray().put(Json.obj("event_id","foreign","status","accepted","durable",true)));check(db.count("status='pending'")==2);
            db.acknowledgements("b1",new JSONArray().put(Json.obj("event_id","e1","status","accepted","durable",true)));check(db.count("status='pending'")==1);check(db.rows("SELECT * FROM batches").size()==1);
            db.splitBatch("b1","p1",Json.obj("batch_id","b2"),Collections.singletonList("e2"));check(db.rows("SELECT * FROM batches WHERE id='b1'").isEmpty());check(db.rows("SELECT * FROM events WHERE id='e2'").get(0).getString("batch").equals("b2"));
            db.acknowledgements("b2",new JSONArray().put(Json.obj("event_id","e2","status","quarantined","durable",true)));check(db.count("status='quarantined'")==1);check(db.rows("SELECT complete FROM passages WHERE id='p1'").get(0).getString("complete").equals("0"));
            db.acknowledgements("b2",new JSONArray().put(Json.obj("event_id","e2","status","accepted","durable",true)));check(db.count("status='quarantined'")==1);
            check(!db.settled());db.recover();check(db.rows("SELECT status FROM passages WHERE id='p1'").get(0).getString("status").equals("INTERRUPTED"));
            db.closePassage("p1",Json.obj("capture_complete",false));String key=db.rows("SELECT close_key FROM passages WHERE id='p1'").get(0).getString("close_key");
            db.close();try(Journal reopened=new Journal(getTargetContext(),database)){check(reopened.count("status='quarantined'")==1);check(reopened.rows("SELECT close_key FROM passages WHERE id='p1'").get(0).getString("close_key").equals(key));}
            result.putString("stream","PASS Android SQLite: "+assertions+" assertions. Test database retained: "+database);finish(-1,result);
        }catch(Throwable e){result.putString("stream","FAIL Android SQLite: "+e.toString());finish(0,result);}
    }
}
