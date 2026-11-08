package id.kainnusantara.handheld.core;

import java.util.List;
import java.util.Map;

/**
 * Penyimpanan lokal tahan-mati (Android: SQLite {@code SqliteStore}; tes host: {@link MemoryStore}). Antrean tidak
 * dihapus saat logout/ganti operator/update; snapshot hanya cache baca.
 */
public interface Store {
    String kv(String key, String def);
    /** Simpan nilai; null = hapus kunci. */
    void set(String key, String value);

    void putSnapshot(String kind, String docId, String json, long savedAtMs);
    String snapshot(String kind, String docId);
    long snapshotSavedAt(String kind, String docId);

    void enqueue(OutboxItem item);
    void update(OutboxItem item);
    OutboxItem get(String id);
    /** Item PENDING milik operator {@code userId} (null = semua) yang jatuh tempo, urut waktu buat. */
    List<OutboxItem> due(long nowMs, String userId, int limit);
    List<OutboxItem> recent(int limit);
    int count(String status);
    int countForDoc(String kind, String docId, String status);
    Map<String, Integer> pendingByUser();

    /** Status lokal kode per dokumen: queued | acked | conflict (+ pesan). */
    void docCode(String kind, String docId, String code, String state, String message);
    List<String[]> docCodes(String kind, String docId);

    void poolAdd(String sessionId, List<String> epcs);
    /** Ambil EPC cadangan berikutnya (ditandai "taken" — tidak diberikan dua kali walau aplikasi mati). */
    String poolTake(String sessionId);
    void poolUsed(String epc, String clientLineId);
    int poolFree(String sessionId);

    void audit(String message);
}
