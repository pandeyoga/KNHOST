package id.kubusteknologi.kn.u300;
import android.app.*;
import android.content.*;
import android.os.*;
import android.text.InputType;
import android.graphics.Color;
import android.widget.*;
import java.io.*;

public final class MainActivity extends Activity {
    private static volatile boolean exporting;
    private LinearLayout page;private TextView status;private Provision provision;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Runnable refresh=new Runnable(){public void run(){if(status!=null)status.setText(AgentService.screen);handler.postDelayed(this,1000);}};
    private void title(String value){TextView t=new TextView(this);t.setText(value);t.setTextSize(21);t.setTextColor(Color.rgb(22,48,73));t.setPadding(0,18,0,12);page.addView(t);}
    private void text(String value){TextView t=new TextView(this);t.setText(value);t.setTextSize(14);t.setPadding(0,8,0,8);page.addView(t);}
    private void button(String label,Runnable action){Button b=new Button(this);b.setText(label);page.addView(b);b.setOnClickListener(v->action.run());}
    private EditText field(LinearLayout parent,String hint,String value,boolean password){EditText e=new EditText(this);e.setHint(hint);e.setText(value);e.setSingleLine(true);if(password)e.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);parent.addView(e);return e;}
    @Override public void onCreate(Bundle b){super.onCreate(b);provision=new Provision(this);dashboard();
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},1);
    }
    private void dashboard(){
        ScrollView scroll=new ScrollView(this);page=new LinearLayout(this);page.setOrientation(LinearLayout.VERTICAL);page.setPadding(24,16,24,24);scroll.addView(page);setContentView(scroll);
        title("ERP Kain Nussantara • U300");text("PT Kubus Teknologi Indonesia\nMiddleware reader "+BuildConfig.VERSION_NAME+" • validasi perangkat dan ERP belum dilakukan.");
        status=new TextView(this);status.setTextSize(16);status.setPadding(16,16,16,16);status.setBackgroundColor(Color.rgb(235,242,249));page.addView(status);
        button("Mulai layanan",()->authorize(()->{if(exporting){message("Tunggu ekspor selesai sebelum memulai layanan.");return;}if(AgentService.active==null)startForegroundService(new Intent(this,AgentService.class));}));
        button("Jeda capture • sinkronisasi tetap berjalan",()->authorize(()->{if(AgentService.active!=null)AgentService.active.pauseCapture();}));
        button("Lanjutkan capture",()->authorize(()->{if(AgentService.active!=null)AgentService.active.resumeCapture();}));
        button("Tutup lintasan secara manual",()->authorize(()->{if(AgentService.active!=null)AgentService.active.finish();}));
        button("Hentikan layanan",()->authorize(()->stopService(new Intent(this,AgentService.class))));
        button("Konfigurasi & provisioning",()->authorize(this::settings));
        button("Pemulihan koneksi / kontrak",()->authorize(()->new AlertDialog.Builder(this).setTitle("Coba ulang setelah perbaikan")
            .setMessage("Periksa dan perbaiki penyebab di ERP terlebih dahulu. Tindakan ini mengambil ulang konfigurasi dan mengirim ulang request dengan ID asli. Tidak menghapus event, tidak mengubah keputusan ERP, dan tidak memberi izin keluar. Jika masalah belum diperbaiki, blok akan muncul kembali.")
            .setPositiveButton("Periksa & coba ulang",(d,w)->{if(AgentService.active!=null)AgentService.active.retryAfterRepair();else message("Mulai layanan terlebih dahulu.");}).setNegativeButton("Batal",null).show()));
        button("Ubah PIN pemeliharaan",()->authorize(()->{EditText pin=new EditText(this);pin.setInputType(18);pin.setHint("PIN baru 6–12 angka");new AlertDialog.Builder(this).setTitle("Ubah PIN").setView(pin).setPositiveButton("Simpan",(d,w)->{try{provision.setPin(pin.getText().toString());message("PIN diperbarui.");}catch(Exception e){message(e.getMessage());}}).setNegativeButton("Batal",null).show();}));
        button("Histori lintasan & diagnosis",()->authorize(this::history));
        button("Ekspor diagnosis JSON",()->authorize(()->{Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/json").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"KN-U300-diagnostic.json");startActivityForResult(i,10);}));
        button("Ekspor seluruh antrean & histori",()->authorize(()->{if(AgentService.active!=null){message("Hentikan layanan sebelum membuat snapshot lengkap. Tidak ada data yang dihapus.");return;}Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/octet-stream").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"KN-U300-snapshot.jsonl");startActivityForResult(i,11);}));
        if(provision.simulation()){
            title("Laboratorium simulasi");text("Tidak memakai radio/GPIO atau mengirim data ke ERP. Mulai layanan sebelum mengirim tag.");
            EditText epc=field(page,"EPC 24 karakter hex","E20034120123456789ABCDEF",false);
            button("Simulasikan pembacaan tag",()->{if(AgentService.active!=null)AgentService.active.simulationTag(epc.getText().toString());});
            button("Simulasikan EPC tidak valid",()->{if(AgentService.active!=null)AgentService.active.simulationTag("INVALID-TAG");});
            CheckBox offline=new CheckBox(this);offline.setText(R.string.simulate_offline);page.addView(offline);offline.setOnCheckedChangeListener((v,on)->{if(AgentService.active!=null)AgentService.active.simulationOffline(on);});
            Spinner verdict=new Spinner(this);verdict.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"GREEN","RED","REVIEW","UNKNOWN"}));page.addView(verdict);
            button("Pakai keputusan simulasi",()->{if(AgentService.active!=null)AgentService.active.simulationVerdict(verdict.getSelectedItem().toString());});
            button("Simulasikan supervisor melepas red latch",()->{if(AgentService.active!=null)AgentService.active.simulationAck();});
            Spinner scenario=new Spinner(this);scenario.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"normal","partial","retry","not-durable","http-413","http-429","http-500","http-400","http-409","http-401","http-403"}));page.addView(scenario);
            button("Skenario untuk batch berikutnya",()->{if(AgentService.active!=null){AgentService.active.simulationScenario(scenario.getSelectedItem().toString());message("Skenario dipasang untuk satu request events berikutnya. Kirim beberapa tag untuk menguji ACK parsial/413.");}});
            button("Simulasikan versi konfigurasi baru",()->{if(AgentService.active!=null)AgentService.active.simulationConfig();});
        }
        text("Produksi: persetujuan supervisor dilakukan di ERP. Device key tidak dapat menyetujui atau mengubah stok.");
    }
    private void authorize(Runnable action){
        if(!provision.hasPin()){
            EditText pin=new EditText(this);pin.setHint("PIN pemeliharaan 6–12 angka");pin.setInputType(18);
            new AlertDialog.Builder(this).setTitle("Buat PIN pemeliharaan pertama").setView(pin).setPositiveButton("Simpan",(d,w)->{try{provision.setPin(pin.getText().toString());action.run();}catch(Exception e){message(e.getMessage());}}).setNegativeButton("Batal",null).show();return;
        }
        EditText pin=new EditText(this);pin.setInputType(18);pin.setHint("PIN pemeliharaan");
        new AlertDialog.Builder(this).setTitle("Otorisasi lokal").setView(pin).setPositiveButton("Lanjut",(d,w)->{try{if(provision.checkPin(pin.getText().toString()))action.run();else message("PIN salah atau terkunci sementara setelah 5 percobaan.");}catch(Exception e){message("Tidak dapat memeriksa PIN.");}}).setNegativeButton("Batal",null).show();
    }
    private void settings(){
        if(AgentService.active!=null){message("Hentikan layanan sebelum mengubah provisioning.");return;}
        LinearLayout form=new LinearLayout(this);form.setOrientation(LinearLayout.VERTICAL);form.setPadding(24,8,24,8);
        CheckBox sim=new CheckBox(this);sim.setText(R.string.simulation_mode);sim.setChecked(provision.simulation());form.addView(sim);
        CheckBox boot=new CheckBox(this);boot.setText(R.string.start_on_boot);boot.setChecked(provision.boot());form.addView(boot);
        EditText url=field(form,"Origin ERP HTTPS",provision.url(),false),gate=field(form,"Logical gate ID",provision.gate(),false),key=field(form,"Device key baru • kosong = pertahankan","",true);
        new AlertDialog.Builder(this).setTitle("Provisioning").setView(form).setPositiveButton("Simpan",(d,w)->{
            try{String token=key.getText().toString();if(token.isEmpty())token=provision.token();provision.save(sim.isChecked(),boot.isChecked(),url.getText().toString(),gate.getText().toString(),token);
                try(Journal j=new Journal(this,sim.isChecked())){j.setState("auth_block","false");j.audit("Provisioning disimpan; device key tidak dicatat.");}dashboard();message("Tersimpan. Mulai layanan untuk mengambil konfigurasi ERP.");
            }catch(Exception e){message(e.getMessage());}
        }).setNegativeButton("Batal",null).show();
    }
    private String diagnostics(){AgentService s=AgentService.active;if(s!=null)return s.diagnostic();try(Journal j=new Journal(this,provision.simulation())){return j.diagnostic();}}
    private void history(){
        org.json.JSONArray rows=Json.parse(diagnostics()).optJSONArray("passages");
        if(rows==null||rows.length()==0){message("Belum ada lintasan. Mulai layanan dan lakukan pembacaan.");return;}
        String[] labels=new String[rows.length()];
        for(int i=0;i<rows.length();i++){org.json.JSONObject p=rows.optJSONObject(i),m=Json.parse(p.optString("body"));labels[i]=p.optString("status")+" • "+p.optString("mode")+"\n"+m.optString("opened_at")+"\n"+p.optString("id");}
        new AlertDialog.Builder(this).setTitle("100 lintasan terakhir • pilih detail").setItems(labels,(d,w)->{
            org.json.JSONObject p=rows.optJSONObject(w),m=Json.parse(p.optString("body"));org.json.JSONObject close=p.isNull("close_body")?Json.obj():Json.parse(p.optString("close_body"));org.json.JSONObject decision=p.isNull("decision")?Json.obj():Json.parse(p.optString("decision"));
            String details="ID: "+p.optString("id")+"\nStatus: "+p.optString("status")+"\nGate: "+m.optString("logical_gate_id")+"\nKonfigurasi: "+m.optString("config_version")+"\nMode: "+p.optString("mode")+"\nCapture lengkap: "+("1".equals(p.optString("complete"))?"Ya":"Tidak")+"\nJumlah observasi: "+close.optInt("observed_event_count",0)+"\nAlasan penutupan: "+close.optString("boundary_reason","Belum ditutup")+"\nKeputusan ERP: "+decision.optString("verdict","Belum ada")+"\nAlasan keputusan: "+decision.optString("reason_code","—")+"\nBasis keputusan: "+decision.optString("completion_basis","—");
            TextView v=new TextView(this);v.setPadding(24,24,24,24);v.setText(details);v.setTextIsSelectable(true);ScrollView scroll=new ScrollView(this);scroll.addView(v);new AlertDialog.Builder(this).setTitle("Detail lintasan").setView(scroll).setPositiveButton("Tutup",null).show();
        }).setNegativeButton("Tutup",null).show();
    }
    private void message(String text){new AlertDialog.Builder(this).setMessage(text).setPositiveButton("OK",null).show();}
    @Override protected void onActivityResult(int req,int result,Intent data){super.onActivityResult(req,result,data);
        if((req==10||req==11)&&result==RESULT_OK&&data!=null&&data.getData()!=null){
            if(exporting){message("Ekspor lain sedang berjalan.");return;}exporting=true;
            android.net.Uri uri=data.getData();boolean sim=provision.simulation();
            new Thread(()->{String notice;
                try(OutputStream out=getContentResolver().openOutputStream(uri)){
                    if(out==null)throw new IOException();
                    if(req==11){if(AgentService.active!=null)throw new IOException("Layanan masih aktif");try(Journal j=new Journal(getApplicationContext(),sim)){j.exportSnapshot(out);}}
                    else out.write(diagnostics().getBytes(java.nio.charset.StandardCharsets.UTF_8));
                    notice="Ekspor selesai tanpa menghapus data. File mengandung data operasional; bagikan hanya kepada tim terkait.";
                }catch(Exception e){notice="Ekspor gagal. File mungkin belum lengkap; jangan gunakan untuk rekonsiliasi.";}
                exporting=false;final String report=notice;runOnUiThread(()->{if(!isDestroyed())message(report);});
            },"kn-export").start();
        }
    }
    @Override protected void onResume(){super.onResume();handler.post(refresh);}
    @Override protected void onPause(){handler.removeCallbacks(refresh);super.onPause();}
}
