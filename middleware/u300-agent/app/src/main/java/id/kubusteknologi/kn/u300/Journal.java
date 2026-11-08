package id.kubusteknologi.kn.u300;
import android.content.*;
import android.database.*;
import android.database.sqlite.*;
import org.json.*;
import java.util.*;
final class Journal extends SQLiteOpenHelper {
    Journal(Context c,boolean sim){this(c,sim?"simulation-v1.db":"production-v1.db");}
    Journal(Context c,String name){super(c,name,null,1);setWriteAheadLoggingEnabled(true);}
    public void onCreate(SQLiteDatabase d){
        d.execSQL("CREATE TABLE state(k TEXT PRIMARY KEY,v TEXT NOT NULL)");
        d.execSQL("CREATE TABLE passages(id TEXT PRIMARY KEY,body TEXT NOT NULL,status TEXT NOT NULL,mode TEXT NOT NULL,complete INTEGER NOT NULL,close_body TEXT,close_key TEXT NOT NULL,decision TEXT)");
        d.execSQL("CREATE TABLE events(id TEXT PRIMARY KEY,passage TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL,batch TEXT)");
        d.execSQL("CREATE INDEX event_pending ON events(status,passage)");
        d.execSQL("CREATE TABLE batches(id TEXT PRIMARY KEY,passage TEXT NOT NULL,body TEXT NOT NULL,attempt INTEGER NOT NULL DEFAULT 0,due INTEGER NOT NULL DEFAULT 0)");
        d.execSQL("CREATE TABLE audit(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,message TEXT NOT NULL)");
    }
    public void onUpgrade(SQLiteDatabase d,int a,int b){throw new IllegalStateException("Migration required");}
    synchronized String state(String k,String def){try(Cursor c=getReadableDatabase().rawQuery("SELECT v FROM state WHERE k=?",new String[]{k})){return c.moveToFirst()?c.getString(0):def;}}
    synchronized void setState(String k,String v){ContentValues c=new ContentValues();c.put("k",k);c.put("v",v);getWritableDatabase().insertWithOnConflict("state",null,c,SQLiteDatabase.CONFLICT_REPLACE);}
    synchronized void audit(String s){getWritableDatabase().execSQL("INSERT INTO audit(at,message) VALUES(?,?)",new Object[]{Json.now(),s});}
    synchronized void open(String id,JSONObject body,String mode){getWritableDatabase().execSQL("INSERT INTO passages VALUES(?,?,'OPEN',?,1,NULL,?,NULL)",new Object[]{id,body.toString(),mode,UUID.randomUUID().toString()});audit("Passage dibuka "+id);}
    synchronized void add(String id,String passage,JSONObject body){getWritableDatabase().execSQL("INSERT INTO events VALUES(?,?,?,'pending',NULL)",new Object[]{id,passage,body.toString()});}
    synchronized void markGap(String p){getWritableDatabase().execSQL("UPDATE passages SET complete=0 WHERE id=?",new Object[]{p});}
    synchronized void closePassage(String p,JSONObject body){getWritableDatabase().execSQL("UPDATE passages SET status='CLOSING',close_body=? WHERE id=?",new Object[]{body.toString(),p});}
    synchronized void recover(){getWritableDatabase().execSQL("UPDATE passages SET status='INTERRUPTED',complete=0 WHERE status='OPEN'");audit("Service dimulai; lintasan OPEN sebelumnya menjadi INTERRUPTED.");}
    synchronized List<JSONObject> rows(String sql,String... args){List<JSONObject> out=new ArrayList<>();try(Cursor c=getReadableDatabase().rawQuery(sql,args)){while(c.moveToNext()){JSONObject o=new JSONObject();for(int i=0;i<c.getColumnCount();i++){try{o.put(c.getColumnName(i),c.isNull(i)?JSONObject.NULL:c.getString(i));}catch(JSONException e){throw new IllegalStateException(e);}}out.add(o);}}return out;}
    synchronized long count(String where,String...args){try(Cursor c=getReadableDatabase().rawQuery("SELECT COUNT(*) FROM events WHERE "+where,args)){c.moveToFirst();return c.getLong(0);}}
    synchronized long pendingBytes(){try(Cursor c=getReadableDatabase().rawQuery("SELECT COALESCE(SUM(LENGTH(body)),0) FROM events WHERE status!='acked'",null)){c.moveToFirst();return c.getLong(0);}}
    synchronized long diskBytes(){return new java.io.File(getReadableDatabase().getPath()).length()+new java.io.File(getReadableDatabase().getPath()+"-wal").length();}
    synchronized void execute(String sql,Object... args){getWritableDatabase().execSQL(sql,args);}
    synchronized boolean settled(){return rows("SELECT id FROM passages WHERE status!='FINAL' LIMIT 1").isEmpty()&&count("status='pending'")==0;}
    synchronized void splitBatch(String batch,String passage,JSONObject body,List<String> ids){
        SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            d.execSQL("UPDATE events SET batch=NULL WHERE batch=? AND status='pending'",new Object[]{batch});
            d.execSQL("DELETE FROM batches WHERE id=?",new Object[]{batch});
            createBatch(body.optString("batch_id"),passage,body,ids);d.setTransactionSuccessful();
        }finally{d.endTransaction();}
    }
    synchronized void createBatch(String batch,String passage,JSONObject body,List<String> ids){
        SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            d.execSQL("INSERT INTO batches(id,passage,body) VALUES(?,?,?)",new Object[]{batch,passage,body.toString()});
            for(String id:ids)d.execSQL("UPDATE events SET batch=? WHERE id=? AND status='pending'",new Object[]{batch,id});d.setTransactionSuccessful();
        }finally{d.endTransaction();}
    }
    synchronized void acknowledgements(String batch,JSONArray a){
        SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            for(int i=0;i<a.length();i++){
                JSONObject v=a.optJSONObject(i);if(v==null)continue;
                String s=v.optString("status");
                if(id.kubusteknologi.kn.u300.core.Safety.durableAck(s,v.optBoolean("durable")))
                    d.execSQL("UPDATE events SET status='acked' WHERE id=? AND batch=? AND status='pending'",new Object[]{v.optString("event_id"),batch});
                else if("rejected".equals(s)||"quarantined".equals(s)){
                    d.execSQL("UPDATE events SET status='quarantined' WHERE id=? AND batch=? AND status='pending'",new Object[]{v.optString("event_id"),batch});
                    d.execSQL("UPDATE passages SET complete=0 WHERE id IN (SELECT passage FROM events WHERE batch=? AND status='quarantined')",new Object[]{batch});
                }
            }
            try(Cursor c=d.rawQuery("SELECT COUNT(*) FROM events WHERE batch=? AND status='pending'",new String[]{batch})){
                c.moveToFirst();if(c.getInt(0)==0)d.execSQL("DELETE FROM batches WHERE id=?",new Object[]{batch});
            }d.setTransactionSuccessful();
        }finally{d.endTransaction();}
    }
    synchronized String diagnostic(){return Json.obj("generated_at",Json.now(),"passages",new JSONArray(rows("SELECT * FROM passages ORDER BY rowid DESC LIMIT 100")),"audit",new JSONArray(rows("SELECT * FROM audit ORDER BY id DESC LIMIT 300")),"pending_events",count("status='pending'"),"quarantined",count("status='quarantined'"),"database_bytes",diskBytes()).toString();}
    synchronized void exportSnapshot(java.io.OutputStream stream) throws Exception{
        SQLiteDatabase d=getWritableDatabase();d.beginTransactionNonExclusive();
        try{
            java.io.BufferedWriter writer=new java.io.BufferedWriter(new java.io.OutputStreamWriter(stream,java.nio.charset.StandardCharsets.UTF_8));
            writer.write(Json.obj("kind","snapshot_header","schema_version",1,"generated_at",Json.now(),"app_build",BuildConfig.VERSION_NAME).toString());writer.newLine();long records=0;
            for(String table:new String[]{"state","passages","events","batches","audit"}){
                try(Cursor cursor=d.rawQuery("SELECT * FROM "+table,null)){
                    while(cursor.moveToNext()){
                        JSONObject row=new JSONObject();for(int i=0;i<cursor.getColumnCount();i++)row.put(cursor.getColumnName(i),cursor.isNull(i)?JSONObject.NULL:cursor.getString(i));
                        writer.write(Json.obj("table",table,"record",row).toString());writer.newLine();records++;
                    }
                }
            }
            writer.write(Json.obj("kind","snapshot_end","complete",true,"record_count",records).toString());writer.newLine();writer.flush();d.setTransactionSuccessful();
        }finally{d.endTransaction();}
    }
}
