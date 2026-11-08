package id.kubusteknologi.kn.u300.core;

import java.net.InetSocketAddress;
import java.net.Socket;
import java.util.ArrayList;
import java.util.List;

/**
 * Pemeriksaan port lokal untuk layanan UHF bawaan U300 (audit §7 [S]: TCP 9160 raw, 9260 JSON, web 8080).
 * Hanya socket Java standar — bukan API SDK. Port terbuka = indikasi layanan bawaan masih memegang modul.
 */
public final class PortProbe {
    private PortProbe() {}

    public static List<Integer> open(String host, int[] ports, int timeoutMs) {
        List<Integer> out = new ArrayList<>();
        if (ports == null) return out;
        for (int port : ports) {
            if (port < 1 || port > 65535) continue;
            try (Socket s = new Socket()) {
                s.connect(new InetSocketAddress(host, port), Math.max(50, timeoutMs));
                out.add(port);
            } catch (Exception ignored) {
                // tertutup / tidak menjawab
            }
        }
        return out;
    }
}
