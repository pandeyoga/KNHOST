package id.kainnusantara.handheld.core;

import java.security.SecureRandom;
import java.security.spec.KeySpec;
import java.util.Base64;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;

/**
 * PIN mode diagnostik/pemeliharaan (6–12 angka). Disimpan sebagai PBKDF2-HMAC-SHA256 bergaram; 5 salah berturut-turut
 * → terkunci 5 menit. PIN tidak pernah dikirim ke ERP dan tidak ditulis di dokumen.
 */
public final class Pin {
    private Pin() {}

    public static final int ITERATIONS = 20000, MAX_FAILS = 5;
    public static final long LOCK_MS = 5 * 60_000L;

    public static String validate(String pin) {
        if (pin == null || !pin.matches("\\d{6,12}")) return "PIN harus 6–12 angka.";
        if (pin.matches("(\\d)\\1+")) return "PIN tidak boleh angka yang sama semua.";
        if ("123456".equals(pin) || "1234567890".startsWith(pin)) return "PIN terlalu mudah ditebak.";
        return null;
    }

    public static String hash(String pin) {
        byte[] salt = new byte[16];
        new SecureRandom().nextBytes(salt);
        return "pbkdf2$" + ITERATIONS + "$" + Base64.getEncoder().encodeToString(salt) + "$" + Base64.getEncoder().encodeToString(derive(pin, salt, ITERATIONS));
    }

    public static boolean verify(String pin, String stored) {
        if (pin == null || stored == null || !stored.startsWith("pbkdf2$")) return false;
        String[] p = stored.split("\\$");
        if (p.length != 4) return false;
        byte[] salt = Base64.getDecoder().decode(p[2]), want = Base64.getDecoder().decode(p[3]);
        byte[] got = derive(pin, salt, Integer.parseInt(p[1]));
        int diff = got.length ^ want.length;
        for (int i = 0; i < Math.min(got.length, want.length); i++) diff |= got[i] ^ want[i];
        return diff == 0;
    }

    static byte[] derive(String pin, byte[] salt, int iterations) {
        try {
            KeySpec spec = new PBEKeySpec(pin.toCharArray(), salt, iterations, 256);
            return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).getEncoded();
        } catch (Exception e) {
            throw new IllegalStateException("PBKDF2 tidak tersedia", e);
        }
    }

    /** Penjaga percobaan: {fails, lockedUntilMs} disimpan di Store. */
    public static String check(Store store, String pin, long nowMs) {
        long until = Long.parseLong(store.kv("pin.locked_until", "0"));
        if (nowMs < until) return "PIN terkunci " + ((until - nowMs) / 1000 + 1) + " dtk lagi.";
        String stored = store.kv("pin.hash", null);
        if (stored == null) return "PIN belum dibuat.";
        if (verify(pin, stored)) { store.set("pin.fails", "0"); return null; }
        int fails = Integer.parseInt(store.kv("pin.fails", "0")) + 1;
        store.set("pin.fails", String.valueOf(fails));
        store.audit("PIN diagnostik salah (" + fails + "×)");
        if (fails >= MAX_FAILS) { store.set("pin.locked_until", String.valueOf(nowMs + LOCK_MS)); store.set("pin.fails", "0"); return "PIN salah " + MAX_FAILS + "× — terkunci 5 menit."; }
        return "PIN salah.";
    }
}
