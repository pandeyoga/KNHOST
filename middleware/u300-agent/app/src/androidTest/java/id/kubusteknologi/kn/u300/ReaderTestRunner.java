package id.kubusteknologi.kn.u300;
import android.app.Instrumentation;
import android.os.Bundle;
import org.json.*;
import java.util.*;
import id.kubusteknologi.kn.u300.core.Batcher;
/** Real Android SQLite tests (Journal skema 2). Own randomly named database; never touches operational databases. */
public final class ReaderTestRunner extends Instrumentation {
    private int assertions;
    private void check(boolean condition){assertions++;if(!condition)throw new AssertionError("assertion "+assertions);}
    @Override public void onCreate(Bundle args){super.onCreate(args);start();}
    @Override public void onStart(){Bundle result=new Bundle();String database="uat-"+UUID.randomUUID()+".db";
        try(Journal db=new Journal(getTargetContext(),database)){
            db.open("p1",Json.obj("opened_at",Json.now(),"logical_gate_id","g","config_version","v"),"live");
            db.addItem(Batcher.EDGE,"p1:g:0","p1",Json.obj("edge_id","p1:g:0"));
            db.checkpoint("p1",Arrays.asList(Json.obj("summary_id","p1:E1:1","count",1),Json.obj("summary_id","p1:E2:1","count",1)));
            check(db.count("status='draft'")==2);check(db.pendingItems("p1",100).size()==1);
            db.checkpoint("p1",Collections.singletonList(Json.obj("summary_id","p1:E1:1","count",5)));
            check(db.rows("SELECT body FROM items WHERE id='p1:E1:1'").get(0).getString("body").contains("5"));
            boolean duplicate=false;try{db.addItem(Batcher.EDGE,"p1:g:0","p1",Json.obj());}catch(android.database.sqlite.SQLiteConstraintException expected){duplicate=true;}check(duplicate);
            db.finalizePassage("p1",Json.obj("capture_complete",true),Collections.singletonList(Json.obj("summary_id","p1:E1:1","count",6)),true);
            check(db.count("status='draft'")==0&&db.count("status='pending'")==3);check(db.pendingBytes()>0);
            List<Batcher.Item> items=db.pendingItems("p1",100);check(items.size()==3&&Batcher.EDGE.equals(items.get(0).kind));
            JSONObject b1=db.createBatch("b1","p1",Json.obj("batch_id","b1","events",new JSONArray()),items,"boot-1");
            check(b1.getLong("seq")==0&&"boot-1".equals(b1.getString("boot_id"))&&b1.getJSONArray("tag_summaries").length()==2);
            check(db.createBatch("b2","p1",Json.obj("batch_id","b2","events",new JSONArray()),new ArrayList<>(),"boot-1").getLong("seq")==1);
            db.acknowledgements("b1",Json.obj("summary_acks",new JSONArray().put(Json.obj("item_id","p1:E1:1","status","accepted","durable",false))));check(db.count("status='pending'")==3);
            db.acknowledgements("b1",Json.obj("summary_acks",new JSONArray().put(Json.obj("item_id","foreign","status","accepted","durable",true))));check(db.count("status='pending'")==3);
            db.acknowledgements("b1",Json.obj("summary_acks",new JSONArray().put(Json.obj("item_id","p1:E1:1","status","accepted","durable",true)).put(Json.obj("item_id","p1:E2:1","status","quarantined","durable",true)),"edge_acks",new JSONArray().put(Json.obj("item_id","p1:g:0","status","duplicate","durable",true))));
            check(db.count("status='pending'")==0&&db.count("status='quarantined'")==1);check(db.rows("SELECT * FROM batches WHERE id='b1'").isEmpty());
            Map<String,Long> obs=db.observed("p1");check(obs.get(Batcher.SUMMARY)==2&&obs.get(Batcher.EDGE)==1&&obs.get(Batcher.EVENT)==0);
            db.open("p2",Json.obj("opened_at",Json.now()),"live");db.checkpoint("p2",Collections.singletonList(Json.obj("summary_id","p2:E1:1")));
            check(!db.settled());db.recover();check(db.rows("SELECT status FROM passages WHERE id='p2'").get(0).getString("status").equals("INTERRUPTED"));
            check(db.count("passage='p2' AND status='pending'")==1);
            db.addItem(Batcher.EDGE,"p2:g:0","p2",Json.obj("edge_id","p2:g:0"));
            db.createBatch("b3","p2",Json.obj("batch_id","b3","events",new JSONArray()),db.pendingItems("p2",10),"boot-2");db.rejectBatch("b3");
            check(db.count("status='rejected'")==2&&db.rows("SELECT complete FROM passages WHERE id='p2'").get(0).getString("complete").equals("0"));
            String key=db.rows("SELECT close_key FROM passages WHERE id='p1'").get(0).getString("close_key");
            db.close();try(Journal reopened=new Journal(getTargetContext(),database)){check(reopened.count("status='quarantined'")==1);check(reopened.rows("SELECT close_key FROM passages WHERE id='p1'").get(0).getString("close_key").equals(key));}
            result.putString("stream","PASS Android SQLite: "+assertions+" assertions. Test database retained: "+database);finish(-1,result);
        }catch(Throwable e){result.putString("stream","FAIL Android SQLite: "+e.toString());finish(0,result);}
    }
}
