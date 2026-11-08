package id.kainnusantara.handheld;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import id.kainnusantara.handheld.core.Json;
import id.kainnusantara.handheld.core.OutboxItem;
import id.kainnusantara.handheld.core.Store;

/**
 * Penyimpanan SQLite tahan-mati (pola Journal agent U300 0.5: persist-before-send, WAL, ID stabil, indeks status).
 * Skema 1: kv · snapshots · outbox · doc_codes · epc_pool · reg_lines · audit · bench. Migrasi berikutnya WAJIB
 * menyalin, tidak menghapus antrean (spesifikasi Kubus 02 §2.11).
 */
final class SqliteStore extends SQLiteOpenHelper implements Store {
    static final int VERSION = 1;

    SqliteStore(Context c) {
        super(c, "kn-c72-v1.db", null, VERSION);
        setWriteAheadLoggingEnabled(true);
    }

    @Override
    public void onCreate(SQLiteDatabase d) {
        d.execSQL("CREATE TABLE kv(k TEXT PRIMARY KEY, v TEXT NOT NULL)");
        d.execSQL("CREATE TABLE snapshots(kind TEXT NOT NULL, doc_id TEXT NOT NULL, json TEXT NOT NULL, saved_at INTEGER NOT NULL, PRIMARY KEY(kind, doc_id))");
        d.execSQL("CREATE TABLE outbox(id TEXT PRIMARY KEY, type TEXT NOT NULL, method TEXT NOT NULL, path TEXT NOT NULL, body TEXT, kind TEXT, doc_id TEXT,"
                + " user_id TEXT, op_session TEXT, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_due INTEGER NOT NULL DEFAULT 0,"
                + " last_error TEXT, response TEXT, label TEXT, created INTEGER NOT NULL, updated INTEGER NOT NULL)");
        d.execSQL("CREATE INDEX outbox_due ON outbox(status, user_id, next_due, created)");
        d.execSQL("CREATE INDEX outbox_doc ON outbox(kind, doc_id, status)");
        d.execSQL("CREATE TABLE doc_codes(kind TEXT NOT NULL, doc_id TEXT NOT NULL, code TEXT NOT NULL, state TEXT NOT NULL, message TEXT, PRIMARY KEY(kind, doc_id, code))");
        d.execSQL("CREATE TABLE epc_pool(epc TEXT PRIMARY KEY, session_id TEXT NOT NULL, status TEXT NOT NULL, line_id TEXT, created INTEGER NOT NULL)");
        d.execSQL("CREATE TABLE reg_lines(client_line_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, epc TEXT, json TEXT NOT NULL, state TEXT NOT NULL,"
                + " line_id TEXT, message TEXT, created INTEGER NOT NULL)");
        d.execSQL("CREATE TABLE audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, message TEXT NOT NULL)");
        d.execSQL("CREATE TABLE bench(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, json TEXT NOT NULL)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase d, int a, int b) { throw new IllegalStateException("Migrasi skema " + a + "→" + b + " belum ditulis"); }

    // ── kv ──
    @Override public synchronized String kv(String key, String def) {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT v FROM kv WHERE k=?", new String[]{key})) { return c.moveToFirst() ? c.getString(0) : def; }
    }
    @Override public synchronized void set(String key, String value) {
        if (value == null) { getWritableDatabase().delete("kv", "k=?", new String[]{key}); return; }
        ContentValues v = new ContentValues(); v.put("k", key); v.put("v", value);
        getWritableDatabase().insertWithOnConflict("kv", null, v, SQLiteDatabase.CONFLICT_REPLACE);
    }

    // ── snapshot ──
    @Override public synchronized void putSnapshot(String kind, String docId, String json, long savedAtMs) {
        ContentValues v = new ContentValues(); v.put("kind", kind); v.put("doc_id", docId); v.put("json", json); v.put("saved_at", savedAtMs);
        getWritableDatabase().insertWithOnConflict("snapshots", null, v, SQLiteDatabase.CONFLICT_REPLACE);
    }
    @Override public synchronized String snapshot(String kind, String docId) {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT json FROM snapshots WHERE kind=? AND doc_id=?", new String[]{kind, docId})) { return c.moveToFirst() ? c.getString(0) : null; }
    }
    @Override public synchronized long snapshotSavedAt(String kind, String docId) {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT saved_at FROM snapshots WHERE kind=? AND doc_id=?", new String[]{kind, docId})) { return c.moveToFirst() ? c.getLong(0) : 0; }
    }

    // ── outbox ──
    private static ContentValues values(OutboxItem i) {
        ContentValues v = new ContentValues();
        v.put("id", i.id); v.put("type", i.type); v.put("method", i.method); v.put("path", i.path); v.put("body", i.body);
        v.put("kind", i.kind); v.put("doc_id", i.docId); v.put("user_id", i.userId); v.put("op_session", i.opSessionId);
        v.put("status", i.status); v.put("attempts", i.attempts); v.put("next_due", i.nextDueMs); v.put("last_error", i.lastError);
        v.put("response", i.response); v.put("label", i.label); v.put("created", i.createdMs); v.put("updated", System.currentTimeMillis());
        return v;
    }

    private static OutboxItem item(Cursor c) {
        OutboxItem i = new OutboxItem(c.getString(0), c.getString(1), c.getString(2), c.getString(3), c.getString(4), c.getString(5),
                c.getString(6), c.getString(7), c.getString(8), c.getLong(15));
        i.status = c.getString(9); i.attempts = c.getInt(10); i.nextDueMs = c.getLong(11); i.lastError = nz(c.getString(12));
        i.response = nz(c.getString(13)); i.label = nz(c.getString(14)); i.updatedMs = c.getLong(16);
        return i;
    }

    private static String nz(String s) { return s == null ? "" : s; }
    private static final String COLS = "id,type,method,path,body,kind,doc_id,user_id,op_session,status,attempts,next_due,last_error,response,label,created,updated";

    @Override public synchronized void enqueue(OutboxItem i) { getWritableDatabase().insertOrThrow("outbox", null, values(i)); }
    @Override public synchronized void update(OutboxItem i) {
        ContentValues v = values(i);
        v.remove("body");   // isi kiriman tidak pernah diubah setelah disimpan
        getWritableDatabase().update("outbox", v, "id=?", new String[]{i.id});
    }
    @Override public synchronized OutboxItem get(String id) {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT " + COLS + " FROM outbox WHERE id=?", new String[]{id})) { return c.moveToFirst() ? item(c) : null; }
    }
    @Override public synchronized List<OutboxItem> due(long nowMs, String userId, int limit) {
        List<OutboxItem> out = new ArrayList<>();
        String sql = "SELECT " + COLS + " FROM outbox WHERE status='pending' AND next_due<=?" + (userId == null ? "" : " AND user_id=?") + " ORDER BY created LIMIT " + limit;
        String[] args = userId == null ? new String[]{String.valueOf(nowMs)} : new String[]{String.valueOf(nowMs), userId};
        try (Cursor c = getReadableDatabase().rawQuery(sql, args)) { while (c.moveToNext()) out.add(item(c)); }
        return out;
    }
    @Override public synchronized List<OutboxItem> recent(int limit) {
        List<OutboxItem> out = new ArrayList<>();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT " + COLS + " FROM outbox ORDER BY created DESC LIMIT " + limit, null)) { while (c.moveToNext()) out.add(item(c)); }
        return out;
    }
    @Override public synchronized int count(String status) {
        try (Cursor c = status == null ? getReadableDatabase().rawQuery("SELECT COUNT(*) FROM outbox", null)
                : getReadableDatabase().rawQuery("SELECT COUNT(*) FROM outbox WHERE status=?", new String[]{status})) { c.moveToFirst(); return c.getInt(0); }
    }
    @Override public synchronized int countForDoc(String kind, String docId, String status) {
        try (Cursor c = status == null ? getReadableDatabase().rawQuery("SELECT COUNT(*) FROM outbox WHERE kind=? AND doc_id=?", new String[]{kind, docId})
                : getReadableDatabase().rawQuery("SELECT COUNT(*) FROM outbox WHERE kind=? AND doc_id=? AND status=?", new String[]{kind, docId, status})) { c.moveToFirst(); return c.getInt(0); }
    }
    @Override public synchronized Map<String, Integer> pendingByUser() {
        Map<String, Integer> m = new HashMap<>();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT user_id, COUNT(*) FROM outbox WHERE status IN ('pending','blocked') GROUP BY user_id", null)) {
            while (c.moveToNext()) m.put(nz(c.getString(0)), c.getInt(1));
        }
        return m;
    }

    // ── kode per dokumen ──
    @Override public synchronized void docCode(String kind, String docId, String code, String state, String message) {
        if (code == null || code.isEmpty()) return;
        ContentValues v = new ContentValues(); v.put("kind", kind); v.put("doc_id", docId); v.put("code", code); v.put("state", state); v.put("message", message);
        getWritableDatabase().insertWithOnConflict("doc_codes", null, v, SQLiteDatabase.CONFLICT_REPLACE);
    }
    @Override public synchronized List<String[]> docCodes(String kind, String docId) {
        List<String[]> out = new ArrayList<>();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT code, state, message FROM doc_codes WHERE kind=? AND doc_id=?", new String[]{kind, docId})) {
            while (c.moveToNext()) out.add(new String[]{c.getString(0), c.getString(1), nz(c.getString(2))});
        }
        return out;
    }

    // ── cadangan EPC Daftar Awal ──
    @Override public synchronized void poolAdd(String sessionId, List<String> epcs) {
        SQLiteDatabase d = getWritableDatabase();
        d.beginTransaction();
        try {
            for (String e : epcs) d.execSQL("INSERT OR IGNORE INTO epc_pool(epc, session_id, status, created) VALUES(?,?, 'free', ?)", new Object[]{e, sessionId, System.currentTimeMillis()});
            d.setTransactionSuccessful();
        } finally { d.endTransaction(); }
    }
    @Override public synchronized String poolTake(String sessionId) {
        String epc;
        try (Cursor c = getReadableDatabase().rawQuery("SELECT epc FROM epc_pool WHERE session_id=? AND status='free' ORDER BY created LIMIT 1", new String[]{sessionId})) {
            if (!c.moveToFirst()) return null;
            epc = c.getString(0);
        }
        getWritableDatabase().execSQL("UPDATE epc_pool SET status='taken' WHERE epc=?", new Object[]{epc});
        return epc;
    }
    @Override public synchronized void poolUsed(String epc, String clientLineId) {
        getWritableDatabase().execSQL("UPDATE epc_pool SET status='used', line_id=? WHERE epc=?", new Object[]{clientLineId, epc});
    }
    @Override public synchronized int poolFree(String sessionId) {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT COUNT(*) FROM epc_pool WHERE session_id=? AND status='free'", new String[]{sessionId})) { c.moveToFirst(); return c.getInt(0); }
    }

    // ── baris Daftar Awal lokal (tampilan + koreksi) ──
    synchronized void regLine(String clientLineId, String sessionId, String epc, String json, String state, String lineId, String message) {
        ContentValues v = new ContentValues(); v.put("client_line_id", clientLineId); v.put("session_id", sessionId); v.put("epc", epc); v.put("json", json);
        v.put("state", state); v.put("line_id", lineId); v.put("message", message); v.put("created", System.currentTimeMillis());
        getWritableDatabase().insertWithOnConflict("reg_lines", null, v, SQLiteDatabase.CONFLICT_REPLACE);
    }
    synchronized void regLineResult(String clientLineId, String state, String lineId, String message) {
        getWritableDatabase().execSQL("UPDATE reg_lines SET state=?, line_id=COALESCE(?, line_id), message=? WHERE client_line_id=?", new Object[]{state, lineId, message, clientLineId});
    }
    synchronized String regLineJson(String clientLineId) {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT json FROM reg_lines WHERE client_line_id=?", new String[]{clientLineId})) { return c.moveToFirst() ? c.getString(0) : null; }
    }

    synchronized List<String[]> regLines(String sessionId, int limit) {
        List<String[]> out = new ArrayList<>();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT client_line_id, epc, json, state, line_id, message FROM reg_lines WHERE session_id=? ORDER BY created DESC LIMIT " + limit, new String[]{sessionId})) {
            while (c.moveToNext()) out.add(new String[]{c.getString(0), c.getString(1), c.getString(2), c.getString(3), nz(c.getString(4)), nz(c.getString(5))});
        }
        return out;
    }

    // ── audit & uji meja ──
    @Override public synchronized void audit(String message) {
        getWritableDatabase().execSQL("INSERT INTO audit(at, message) VALUES(?,?)", new Object[]{Json.now(), message});
        getWritableDatabase().execSQL("DELETE FROM audit WHERE id <= (SELECT MAX(id) - 5000 FROM audit)");
    }
    synchronized List<String> auditTail(int limit) {
        List<String> out = new ArrayList<>();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT at, message FROM audit ORDER BY id DESC LIMIT " + limit, null)) { while (c.moveToNext()) out.add(c.getString(0) + " " + c.getString(1)); }
        return out;
    }
    synchronized void bench(String json) { getWritableDatabase().execSQL("INSERT INTO bench(at, json) VALUES(?,?)", new Object[]{Json.now(), json}); }
}
