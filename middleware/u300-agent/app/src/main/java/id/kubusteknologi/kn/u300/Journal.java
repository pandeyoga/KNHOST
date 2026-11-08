package id.kubusteknologi.kn.u300;
import android.content.*;
import android.database.*;
import android.database.sqlite.*;
import org.json.*;
import java.util.*;
import id.kubusteknologi.kn.u300.core.Batcher;
import id.kubusteknologi.kn.u300.core.Safety;

/**
 * Outbox SQLite (persist-before-send, ID stabil, ACK per item). Skema 2 (0.5.0):
 * {@code items(kind,id)} menyimpan event 0.4, TagSummary (draf → pending saat lintasan ditutup) dan GpiEdge;
 * {@code batches} menyimpan body persis untuk retry beserta seq/boot_id. Migrasi 1→2 menyalin event 0.4 ke
 * {@code items} dan mengganti nama tabel lama menjadi {@code events_v1_archive} (tidak ada yang dihapus).
 * Antrean dihitung dengan indeks status (AUD-MW-11), bukan scan seluruh histori.
 */
final class Journal extends SQLiteOpenHelper {
    static final int VERSION=2;
    Journal(Context c,boolean sim){this(c,sim?"simulation-v1.db":"production-v1.db");}
    Journal(Context c,String name){super(c,name,null,VERSION);setWriteAheadLoggingEnabled(true);}
    private static void createV2(SQLiteDatabase d){
        d.execSQL("CREATE TABLE items(kind TEXT NOT NULL,id TEXT NOT NULL,passage TEXT NOT NULL,body TEXT NOT NULL,status TEXT NOT NULL,batch TEXT,bytes INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(kind,id))");
        d.execSQL("CREATE INDEX items_status ON items(status,passage)");
        d.execSQL("CREATE INDEX items_batch ON items(batch)");
        d.execSQL("CREATE INDEX items_passage ON items(passage,kind)");
        d.execSQL("CREATE TABLE bench(id INTEGER PRIMARY KEY AUTOINCREMENT,run TEXT NOT NULL,item INTEGER NOT NULL,at TEXT NOT NULL,body TEXT NOT NULL)");
    }
    public void onCreate(SQLiteDatabase d){
        d.execSQL("CREATE TABLE state(k TEXT PRIMARY KEY,v TEXT NOT NULL)");
        d.execSQL("CREATE TABLE passages(id TEXT PRIMARY KEY,body TEXT NOT NULL,status TEXT NOT NULL,mode TEXT NOT NULL,complete INTEGER NOT NULL,close_body TEXT,close_key TEXT NOT NULL,decision TEXT,close_attempts INTEGER NOT NULL DEFAULT 0,close_due INTEGER NOT NULL DEFAULT 0)");
        d.execSQL("CREATE INDEX passages_status ON passages(status)");
        d.execSQL("CREATE TABLE batches(id TEXT PRIMARY KEY,passage TEXT NOT NULL,body TEXT NOT NULL,attempt INTEGER NOT NULL DEFAULT 0,due INTEGER NOT NULL DEFAULT 0,seq INTEGER,boot TEXT)");
        d.execSQL("CREATE TABLE audit(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,message TEXT NOT NULL)");
        createV2(d);
    }
    public void onUpgrade(SQLiteDatabase d,int a,int b){
        if(a!=1||b!=2)throw new IllegalStateException("Migration required");
        createV2(d);
        d.execSQL("INSERT INTO items(kind,id,passage,body,status,batch,bytes) SELECT 'event',id,passage,body,status,batch,LENGTH(body) FROM events");
        d.execSQL("ALTER TABLE events RENAME TO events_v1_archive");
        d.execSQL("ALTER TABLE passages ADD COLUMN close_attempts INTEGER NOT NULL DEFAULT 0");
        d.execSQL("ALTER TABLE passages ADD COLUMN close_due INTEGER NOT NULL DEFAULT 0");
        d.execSQL("CREATE INDEX passages_status ON passages(status)");
        d.execSQL("ALTER TABLE batches ADD COLUMN seq INTEGER");
        d.execSQL("ALTER TABLE batches ADD COLUMN boot TEXT");
        d.execSQL("INSERT INTO audit(at,message) VALUES(?,?)",new Object[]{Json.now(),"Migrasi skema 1 → 2 (agent 0.5.0): event 0.4 disalin ke items; tabel lama disimpan sebagai events_v1_archive."});
    }
    synchronized String state(String k,String def){try(Cursor c=getReadableDatabase().rawQuery("SELECT v FROM state WHERE k=?",new String[]{k})){return c.moveToFirst()?c.getString(0):def;}}
    synchronized void setState(String k,String v){ContentValues c=new ContentValues();c.put("k",k);c.put("v",v);getWritableDatabase().insertWithOnConflict("state",null,c,SQLiteDatabase.CONFLICT_REPLACE);}
    synchronized void audit(String s){getWritableDatabase().execSQL("INSERT INTO audit(at,message) VALUES(?,?)",new Object[]{Json.now(),s});}
    synchronized void open(String id,JSONObject body,String mode){getWritableDatabase().execSQL("INSERT INTO passages(id,body,status,mode,complete,close_body,close_key,decision) VALUES(?,?,'OPEN',?,1,NULL,?,NULL)",new Object[]{id,body.toString(),mode,UUID.randomUUID().toString()});audit("Lintasan dibuka "+id);}
    /** Item final (siap kirim): tepi sinar, atau event 0.4. */
    synchronized void addItem(String kind,String id,String passage,JSONObject body){String b=body.toString();getWritableDatabase().execSQL("INSERT INTO items(kind,id,passage,body,status,batch,bytes) VALUES(?,?,?,?,'pending',NULL,?)",new Object[]{kind,id,passage,b,b.length()});}
    private static void upsertSummary(SQLiteDatabase d,String passage,JSONObject s,String status){
        String b=s.toString();String id=s.optString("summary_id");
        d.execSQL("INSERT INTO items(kind,id,passage,body,status,batch,bytes) VALUES('summary',?,?,?,?,NULL,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body,bytes=excluded.bytes,status=excluded.status WHERE items.status='draft'",new Object[]{id,passage,b,status,b.length()});
    }
    /** Draf ringkasan (pemulihan crash); tidak pernah dikirim sebelum lintasan ditutup. */
    synchronized void checkpoint(String passage,List<JSONObject> drafts){
        SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{for(JSONObject s:drafts)upsertSummary(d,passage,s,"draft");d.setTransactionSuccessful();}finally{d.endTransaction();}
    }
    /** Lintasan ditutup: ringkasan final menjadi pending + body close, satu transaksi. */
    synchronized void finalizePassage(String passage,JSONObject close,List<JSONObject> summaries,boolean complete){
        SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            for(JSONObject s:summaries)upsertSummary(d,passage,s,"pending");
            d.execSQL("UPDATE items SET status='pending' WHERE passage=? AND status='draft'",new Object[]{passage});
            d.execSQL("UPDATE passages SET status='CLOSING',close_body=?,complete=CASE WHEN ? THEN complete ELSE 0 END WHERE id=?",new Object[]{close.toString(),complete?1:0,passage});
            d.setTransactionSuccessful();
        }finally{d.endTransaction();}
    }
    synchronized void markGap(String p){getWritableDatabase().execSQL("UPDATE passages SET complete=0 WHERE id=?",new Object[]{p});}
    synchronized void closePassage(String p,JSONObject body){getWritableDatabase().execSQL("UPDATE passages SET status='CLOSING',close_body=? WHERE id=?",new Object[]{body.toString(),p});}
    /** Restart: OPEN → INTERRUPTED (tidak lengkap); draf ringkasan ikut dikirim untuk rekonsiliasi. */
    synchronized void recover(){
        SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            d.execSQL("UPDATE items SET status='pending' WHERE status='draft' AND passage IN (SELECT id FROM passages WHERE status='OPEN')");
            d.execSQL("UPDATE passages SET status='INTERRUPTED',complete=0 WHERE status='OPEN'");
            d.setTransactionSuccessful();
        }finally{d.endTransaction();}
        audit("Service dimulai; lintasan OPEN sebelumnya menjadi INTERRUPTED.");
    }
    synchronized List<JSONObject> rows(String sql,String... args){List<JSONObject> out=new ArrayList<>();try(Cursor c=getReadableDatabase().rawQuery(sql,args)){while(c.moveToNext()){JSONObject o=new JSONObject();for(int i=0;i<c.getColumnCount();i++){try{o.put(c.getColumnName(i),c.isNull(i)?JSONObject.NULL:c.getString(i));}catch(JSONException e){throw new IllegalStateException(e);}}out.add(o);}}return out;}
    synchronized long count(String where,String...args){try(Cursor c=getReadableDatabase().rawQuery("SELECT COUNT(*) FROM items WHERE "+where,args)){c.moveToFirst();return c.getLong(0);}}
    /** Byte antrean belum terkirim (indeks status). Riwayat ber-ACK/karantina tidak ikut. */
    synchronized long pendingBytes(){try(Cursor c=getReadableDatabase().rawQuery("SELECT COALESCE(SUM(bytes),0) FROM items WHERE status IN ('pending','draft')",null)){c.moveToFirst();return c.getLong(0);}}
    synchronized long diskBytes(){return new java.io.File(getReadableDatabase().getPath()).length()+new java.io.File(getReadableDatabase().getPath()+"-wal").length();}
    synchronized void execute(String sql,Object... args){getWritableDatabase().execSQL(sql,args);}
    synchronized boolean settled(){return rows("SELECT id FROM passages WHERE status!='FINAL' LIMIT 1").isEmpty()&&count("status IN ('pending','draft')")==0;}
    /** seq envelope berikutnya untuk boot_id ini (Sparkplug-style; deteksi celah di server). */
    private long nextSeq(SQLiteDatabase d,String boot){
        String key="seq:"+boot;long next=0;
        try(Cursor c=d.rawQuery("SELECT v FROM state WHERE k=?",new String[]{key})){if(c.moveToFirst())next=Long.parseLong(c.getString(0))+1;}
        ContentValues v=new ContentValues();v.put("k",key);v.put("v",String.valueOf(next));d.insertWithOnConflict("state",null,v,SQLiteDatabase.CONFLICT_REPLACE);
        return next;
    }
    /** Item pending tanpa batch untuk satu lintasan: tepi dulu, lalu ringkasan, lalu event 0.4. */
    synchronized List<Batcher.Item> pendingItems(String passage,int limit){
        List<Batcher.Item> out=new ArrayList<>();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT kind,id,body FROM items WHERE passage=? AND status='pending' AND batch IS NULL ORDER BY CASE kind WHEN 'edge' THEN 0 WHEN 'summary' THEN 1 ELSE 2 END,rowid LIMIT "+limit,new String[]{passage})){
            while(c.moveToNext())out.add(new Batcher.Item(c.getString(0),c.getString(1),Json.parse(c.getString(2))));
        }
        return out;
    }
    /** Simpan batch (body persis untuk retry) + tandai item dalam satu transaksi. base memperoleh seq di sini. */
    synchronized JSONObject createBatch(String batch,String passage,JSONObject base,List<Batcher.Item> items,String boot){
        SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            long seq=nextSeq(d,boot);
            try{base.put("seq",seq).put("boot_id",boot);}catch(JSONException e){throw new IllegalStateException(e);}
            JSONObject body=Batcher.build(base,items);
            d.execSQL("INSERT INTO batches(id,passage,body,seq,boot) VALUES(?,?,?,?,?)",new Object[]{batch,passage,body.toString(),seq,boot});
            for(Batcher.Item it:items)d.execSQL("UPDATE items SET batch=? WHERE kind=? AND id=? AND status='pending'",new Object[]{batch,it.kind,it.id});
            d.setTransactionSuccessful();return body;
        }finally{d.endTransaction();}
    }
    /** 413: batch tidak diproses server → lepaskan item agar dibagi ulang (ID item tetap). */
    synchronized void releaseBatch(String batch){
        SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            d.execSQL("UPDATE items SET batch=NULL WHERE batch=? AND status='pending'",new Object[]{batch});
            d.execSQL("DELETE FROM batches WHERE id=?",new Object[]{batch});d.setTransactionSuccessful();
        }finally{d.endTransaction();}
    }
    /** PASSAGE_FROZEN: server tidak akan menerima item baru lintasan ini → tolak lokal (disimpan, tidak dihitung), lintasan tidak lengkap. */
    synchronized void rejectBatch(String batch){
        SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            d.execSQL("UPDATE passages SET complete=0 WHERE id IN (SELECT passage FROM items WHERE batch=?)",new Object[]{batch});
            d.execSQL("UPDATE items SET status='rejected' WHERE batch=? AND status='pending'",new Object[]{batch});
            d.execSQL("DELETE FROM batches WHERE id=?",new Object[]{batch});d.setTransactionSuccessful();
        }finally{d.endTransaction();}
        audit("Batch "+batch+" ditolak PASSAGE_FROZEN; item disimpan sebagai rejected untuk rekonsiliasi.");
    }
    /** ACK per item dari event_acks / summary_acks / edge_acks; hanya item milik batch ini yang berubah. */
    synchronized void acknowledgements(String batch,JSONObject response){
        SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            for(String kind:new String[]{Batcher.EVENT,Batcher.SUMMARY,Batcher.EDGE}){
                JSONArray a=response.optJSONArray(Batcher.ackArray(kind));if(a==null)continue;
                for(int i=0;i<a.length();i++){
                    JSONObject v=a.optJSONObject(i);if(v==null)continue;
                    String s=v.optString("status"),id=v.optString(Batcher.ackId(kind));
                    if(Safety.durableAck(s,v.optBoolean("durable")))d.execSQL("UPDATE items SET status='acked' WHERE kind=? AND id=? AND batch=? AND status='pending'",new Object[]{kind,id,batch});
                    else if("quarantined".equals(s)&&v.optBoolean("durable"))d.execSQL("UPDATE items SET status='quarantined' WHERE kind=? AND id=? AND batch=? AND status='pending'",new Object[]{kind,id,batch});
                    else if("rejected".equals(s)){d.execSQL("UPDATE items SET status='rejected' WHERE kind=? AND id=? AND batch=? AND status='pending'",new Object[]{kind,id,batch});d.execSQL("UPDATE passages SET complete=0 WHERE id IN (SELECT passage FROM items WHERE kind=? AND id=?)",new Object[]{kind,id});}
                }
            }
            try(Cursor c=d.rawQuery("SELECT COUNT(*) FROM items WHERE batch=? AND status='pending'",new String[]{batch})){
                c.moveToFirst();if(c.getInt(0)==0)d.execSQL("DELETE FROM batches WHERE id=?",new Object[]{batch});
            }d.setTransactionSuccessful();
        }finally{d.endTransaction();}
    }
    /** Jumlah item yang diterima server per jenis (acked + quarantined) untuk observed_*_count close. */
    synchronized Map<String,Long> observed(String passage){
        Map<String,Long> m=new HashMap<>();m.put(Batcher.EVENT,0L);m.put(Batcher.SUMMARY,0L);m.put(Batcher.EDGE,0L);
        try(Cursor c=getReadableDatabase().rawQuery("SELECT kind,COUNT(*) FROM items WHERE passage=? AND status IN ('acked','quarantined') GROUP BY kind",new String[]{passage})){while(c.moveToNext())m.put(c.getString(0),c.getLong(1));}
        return m;
    }
    synchronized long unsent(String passage){return count("passage=? AND status IN ('pending','draft')",passage);}
    synchronized String lastEventId(String passage){List<JSONObject> r=rows("SELECT id FROM items WHERE passage=? AND kind='event' AND status IN ('acked','quarantined') ORDER BY rowid DESC LIMIT 1",passage);return r.isEmpty()?null:r.get(0).optString("id");}
    synchronized void addBench(String run,int item,JSONObject body){getWritableDatabase().execSQL("INSERT INTO bench(run,item,at,body) VALUES(?,?,?,?)",new Object[]{run,item,Json.now(),body.toString()});}
    synchronized String diagnostic(){return Json.obj("generated_at",Json.now(),"passages",new JSONArray(rows("SELECT * FROM passages ORDER BY rowid DESC LIMIT 100")),"audit",new JSONArray(rows("SELECT * FROM audit ORDER BY id DESC LIMIT 300")),"pending_items",count("status='pending'"),"draft_items",count("status='draft'"),"quarantined",count("status='quarantined'"),"rejected",count("status='rejected'"),"database_bytes",diskBytes()).toString();}
    synchronized void exportSnapshot(java.io.OutputStream stream) throws Exception{
        SQLiteDatabase d=getWritableDatabase();d.beginTransactionNonExclusive();
        try{
            java.io.BufferedWriter writer=new java.io.BufferedWriter(new java.io.OutputStreamWriter(stream,java.nio.charset.StandardCharsets.UTF_8));
            writer.write(Json.obj("kind","snapshot_header","schema_version",2,"generated_at",Json.now(),"app_build",BuildConfig.VERSION_NAME).toString());writer.newLine();long records=0;
            List<String> tables=new ArrayList<>(Arrays.asList("state","passages","items","batches","audit","bench"));
            try(Cursor t=d.rawQuery("SELECT name FROM sqlite_master WHERE type='table' AND name='events_v1_archive'",null)){if(t.moveToFirst())tables.add("events_v1_archive");}
            for(String table:tables){
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
