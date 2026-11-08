package id.kainnusantara.handheld.core;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Implementasi {@link Store} di memori — untuk tes host & mode tanpa SQLite (perilaku sama dengan SqliteStore). */
public final class MemoryStore implements Store {
    private final Map<String, String> kv = new HashMap<>();
    private final Map<String, String[]> snaps = new HashMap<>();
    private final Map<String, OutboxItem> out = new LinkedHashMap<>();
    private final Map<String, Map<String, String[]>> codes = new HashMap<>();
    private final Map<String, String[]> pool = new LinkedHashMap<>();   // epc → {session, status, line}
    public final List<String> auditLog = new ArrayList<>();

    public synchronized String kv(String key, String def) { String v = kv.get(key); return v == null ? def : v; }
    public synchronized void set(String key, String value) { if (value == null) kv.remove(key); else kv.put(key, value); }

    public synchronized void putSnapshot(String kind, String docId, String json, long savedAtMs) {
        snaps.put(kind + "|" + docId, new String[]{json, String.valueOf(savedAtMs)});
    }
    public synchronized String snapshot(String kind, String docId) { String[] s = snaps.get(kind + "|" + docId); return s == null ? null : s[0]; }
    public synchronized long snapshotSavedAt(String kind, String docId) { String[] s = snaps.get(kind + "|" + docId); return s == null ? 0 : Long.parseLong(s[1]); }

    public synchronized void enqueue(OutboxItem item) {
        if (out.containsKey(item.id)) throw new IllegalStateException("ID antrean ganda: " + item.id);
        out.put(item.id, item);
    }
    public synchronized void update(OutboxItem item) { item.updatedMs = System.currentTimeMillis(); out.put(item.id, item); }
    public synchronized OutboxItem get(String id) { return out.get(id); }

    public synchronized List<OutboxItem> due(long nowMs, String userId, int limit) {
        List<OutboxItem> r = new ArrayList<>();
        for (OutboxItem i : out.values()) {
            if (OutboxItem.PENDING.equals(i.status) && i.nextDueMs <= nowMs && (userId == null || userId.equals(i.userId))) r.add(i);
        }
        r.sort(Comparator.comparingLong(i -> i.createdMs));
        return r.size() > limit ? new ArrayList<>(r.subList(0, limit)) : r;
    }

    public synchronized List<OutboxItem> recent(int limit) {
        List<OutboxItem> r = new ArrayList<>(out.values());
        Collections.reverse(r);
        return r.size() > limit ? new ArrayList<>(r.subList(0, limit)) : r;
    }

    public synchronized int count(String status) {
        int n = 0;
        for (OutboxItem i : out.values()) if (status == null || status.equals(i.status)) n++;
        return n;
    }

    public synchronized int countForDoc(String kind, String docId, String status) {
        int n = 0;
        for (OutboxItem i : out.values()) if (kind.equals(i.kind) && docId.equals(i.docId) && (status == null || status.equals(i.status))) n++;
        return n;
    }

    public synchronized Map<String, Integer> pendingByUser() {
        Map<String, Integer> m = new HashMap<>();
        for (OutboxItem i : out.values()) if (!i.finished()) m.merge(i.userId == null ? "" : i.userId, 1, Integer::sum);
        return m;
    }

    public synchronized void docCode(String kind, String docId, String code, String state, String message) {
        codes.computeIfAbsent(kind + "|" + docId, k -> new LinkedHashMap<>()).put(code, new String[]{code, state, message == null ? "" : message});
    }

    public synchronized List<String[]> docCodes(String kind, String docId) {
        Map<String, String[]> m = codes.get(kind + "|" + docId);
        return m == null ? new ArrayList<>() : new ArrayList<>(m.values());
    }

    public synchronized void poolAdd(String sessionId, List<String> epcs) {
        for (String e : epcs) if (!pool.containsKey(e)) pool.put(e, new String[]{sessionId, "free", ""});
    }

    public synchronized String poolTake(String sessionId) {
        for (Map.Entry<String, String[]> e : pool.entrySet()) {
            if (e.getValue()[0].equals(sessionId) && "free".equals(e.getValue()[1])) { e.getValue()[1] = "taken"; return e.getKey(); }
        }
        return null;
    }

    public synchronized void poolUsed(String epc, String clientLineId) {
        String[] p = pool.get(epc);
        if (p != null) { p[1] = "used"; p[2] = clientLineId; }
    }

    public synchronized int poolFree(String sessionId) {
        int n = 0;
        for (String[] p : pool.values()) if (p[0].equals(sessionId) && "free".equals(p[1])) n++;
        return n;
    }

    public synchronized void audit(String message) { auditLog.add(Json.now() + " " + message); }
}
