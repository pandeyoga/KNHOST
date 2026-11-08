package id.kubusteknologi.kn.u300;
import android.content.*;
import android.security.keystore.*;
import android.util.Base64;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import java.security.*;
import java.net.URI;
final class Provision implements Api.Settings {
    private final SharedPreferences p;
    private final Context context;
    Provision(Context c) {context=c;p=c.getSharedPreferences("provision",0);}
    boolean hasPin(){return p.contains("pin_hash");}
    private byte[] derive(String pin,byte[] salt) throws Exception {
        return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(new javax.crypto.spec.PBEKeySpec(pin.toCharArray(),salt,120000,256)).getEncoded();
    }
    boolean checkPin(String pin) throws Exception {
        if(System.currentTimeMillis()<p.getLong("locked_until",0))return false;
        boolean ok=hasPin()&&MessageDigest.isEqual(derive(pin,Base64.decode(p.getString("pin_salt",""),0)),Base64.decode(p.getString("pin_hash",""),0));
        int fails=ok?0:p.getInt("pin_fails",0)+1;
        boolean persisted=p.edit().putInt("pin_fails",fails).putLong("locked_until",fails>=5?System.currentTimeMillis()+60000:0).commit();return ok&&persisted;
    }
    void setPin(String pin) throws Exception {
        if(!pin.matches("[0-9]{6,12}"))throw new IllegalArgumentException("PIN wajib 6–12 angka.");
        byte[] salt=new byte[16];new SecureRandom().nextBytes(salt);
        if(!p.edit().putString("pin_salt",Base64.encodeToString(salt,2)).putString("pin_hash",Base64.encodeToString(derive(pin,salt),2)).putInt("pin_fails",0).putLong("locked_until",0).commit())throw new IllegalStateException("PIN gagal disimpan.");
    }
    public boolean simulation(){return p.getBoolean("simulation",true);}
    public String simulatorState(){return p.getString("simulator_state","");}
    public void simulatorState(String value) throws Exception{if(!p.edit().putString("simulator_state",value).commit())throw new java.io.IOException("Simulator state gagal disimpan");}
    boolean boot(){return p.getBoolean("boot",false);}
    public String url(){return p.getString("url","");}
    String gate(){return p.getString("gate","");}
    private SecretKey key() throws Exception {
        KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
        if(!ks.containsAlias("kn-device")) {
            KeyGenerator gen=KeyGenerator.getInstance("AES","AndroidKeyStore");
            gen.init(new KeyGenParameterSpec.Builder("kn-device",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());gen.generateKey();
        } return (SecretKey)ks.getKey("kn-device",null);
    }
    public String token() throws Exception {
        String stored=p.getString("secret",""); if(stored.isEmpty())return "";
        String[] parts=stored.split(":"); Cipher c=Cipher.getInstance("AES/GCM/NoPadding");
        c.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(parts[0],0)));
        return new String(c.doFinal(Base64.decode(parts[1],0)),java.nio.charset.StandardCharsets.UTF_8);
    }
    void save(boolean sim,boolean boot,String url,String gate,String token) throws Exception {
        url=url.trim().replaceAll("/+$",""); gate=gate.trim();
        if(!this.url().isEmpty()&&(!this.url().equals(url)||!this.gate().equals(gate))){
            try(Journal d=new Journal(context,false)){if(!d.rows("SELECT id FROM passages LIMIT 1").isEmpty())throw new IllegalArgumentException("Identitas ERP/gate sudah terikat pada histori. Gunakan prosedur migrasi; antrean tidak boleh diarahkan ulang.");}
        }
        if(!sim) {
            URI u=new URI(url);
            if(!"https".equals(u.getScheme())||u.getHost()==null||u.getUserInfo()!=null||u.getQuery()!=null||u.getFragment()!=null||!u.getPath().isEmpty())
                throw new IllegalArgumentException("Alamat harus origin HTTPS, contoh https://erp.example.com");
            if(gate.isEmpty()||token.isEmpty())throw new IllegalArgumentException("Gate dan device key wajib diisi.");
        }
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,key());
        String secret=Base64.encodeToString(c.getIV(),Base64.NO_WRAP)+":"+Base64.encodeToString(c.doFinal(token.getBytes(java.nio.charset.StandardCharsets.UTF_8)),Base64.NO_WRAP);
        if(!p.edit().putBoolean("simulation",sim).putBoolean("boot",boot).putString("url",url).putString("gate",gate).putString("secret",secret).commit())
            throw new IllegalStateException("Gagal menyimpan konfigurasi.");
    }
}
