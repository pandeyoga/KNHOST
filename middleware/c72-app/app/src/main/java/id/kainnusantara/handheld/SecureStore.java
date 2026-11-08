package id.kainnusantara.handheld;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Kredensial (device key, token sesi operator) terenkripsi AES-GCM dengan kunci Android Keystore yang tidak bisa
 * diekspor. Sandi operator TIDAK pernah disimpan. Backup aplikasi dimatikan di manifest.
 */
final class SecureStore {
    private static final String ALIAS = "kn-c72-secrets";
    private final SharedPreferences prefs;

    SecureStore(Context c) { prefs = c.getSharedPreferences("kn_secure", Context.MODE_PRIVATE); }

    private SecretKey key() throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (ks.containsAlias(ALIAS)) return ((KeyStore.SecretKeyEntry) ks.getEntry(ALIAS, null)).getSecretKey();
        KeyGenerator g = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        g.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build());
        return g.generateKey();
    }

    synchronized void put(String name, String value) {
        if (value == null) { prefs.edit().remove(name).apply(); return; }
        try {
            Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
            c.init(Cipher.ENCRYPT_MODE, key());
            byte[] enc = c.doFinal(value.getBytes(StandardCharsets.UTF_8));
            prefs.edit().putString(name, Base64.encodeToString(c.getIV(), Base64.NO_WRAP) + ":" + Base64.encodeToString(enc, Base64.NO_WRAP)).apply();
        } catch (Exception e) {
            throw new IllegalStateException("Gagal menyimpan kredensial aman: " + e.getMessage(), e);
        }
    }

    synchronized String get(String name) {
        String v = prefs.getString(name, null);
        if (v == null) return null;
        try {
            String[] p = v.split(":", 2);
            Cipher c = Cipher.getInstance("AES/GCM/NoPadding");
            c.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, Base64.decode(p[0], Base64.NO_WRAP)));
            return new String(c.doFinal(Base64.decode(p[1], Base64.NO_WRAP)), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return null;
        }
    }

    synchronized void remove(String name) { prefs.edit().remove(name).apply(); }
}
