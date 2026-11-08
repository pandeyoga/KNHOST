package id.kubusteknologi.kn.u300;
import android.app.*;
import android.content.*;
import android.os.*;
import android.text.InputType;
import android.graphics.Color;
import android.widget.*;
import java.io.*;

public final class MainActivity extends Activity {
    private static volatile boolean exporting,benchRunning;
    private LinearLayout page;private TextView status;private Provision provision;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Runnable refresh=new Runnable(){public void run(){if(status!=null)status.setText(AgentService.screen);handler.postDelayed(this,1000);}};
    private void title(String value){TextView t=new TextView(this);t.setText(value);t.setTextSize(21);t.setTextColor(Color.rgb(22,48,73));t.setPadding(0,18,0,12);page.addView(t);}
    private void text(String value){TextView t=new TextView(this);t.setText(value);t.setTextSize(14);t.setPadding(0,8,0,8);page.addView(t);}
    private void button(String label,Runnable action){Button b=new Button(this);b.setText(label);page.addView(b);b.setOnClickListener(v->action.run());}
    private EditText field(LinearLayout parent,String hint,String value,boolean password){EditText e=new EditText(this);e.setHint(hint);e.setText(value);e.setSingleLine(true);if(password)e.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);parent.addView(e);return e;}
    private Spinner spinner(String[] values){Spinner s=new Spinner(this);s.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,values));page.addView(s);return s;}
    @Override public void onCreate(Bundle b){super.onCreate(b);provision=new Provision(this);dashboard();
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},1);
    }
    private void dashboard(){
        ScrollView scroll=new ScrollView(this);page=new LinearLayout(this);page.setOrientation(LinearLayout.VERTICAL);page.setPadding(24,16,24,24);scroll.addView(page);setContentView(scroll);
        title("ERP Kain Nussantara • U300");text("PT Kubus Teknologi Indonesia\nMiddleware reader "+BuildConfig.VERSION_NAME+" • LAB: validasi perangkat & lokasi belum dilakukan.");
        status=new TextView(this);status.setTextSize(16);status.setPadding(16,16,16,16);status.setBackgroundColor(Color.rgb(235,242,249));page.addView(status);
        button("Mulai layanan",()->authorize(()->{if(exporting||benchRunning){message("Tunggu ekspor/uji meja selesai sebelum memulai layanan.");return;}if(AgentService.active==null)startForegroundService(new Intent(this,AgentService.class));}));
        button("Jeda capture • sinkronisasi tetap berjalan",()->authorize(()->{if(AgentService.active!=null)AgentService.active.pauseCapture();}));
        button("Lanjutkan capture",()->authorize(()->{if(AgentService.active!=null)AgentService.active.resumeCapture();}));
        button("Tutup lintasan secara manual",()->authorize(()->{if(AgentService.active!=null)AgentService.active.finish();}));
        button("Hentikan layanan",()->authorize(()->stopService(new Intent(this,AgentService.class))));
        button("Konfigurasi & provisioning",()->authorize(this::settings));
        button("Pemulihan koneksi / kontrak",()->authorize(()->new AlertDialog.Builder(this).setTitle("Coba ulang setelah perbaikan")
            .setMessage("Periksa dan perbaiki penyebab di ERP terlebih dahulu. Tindakan ini mengambil ulang konfigurasi dan mengirim ulang request dengan ID asli. Tidak menghapus bukti, tidak mengubah keputusan ERP, dan tidak memberi izin keluar. Jika masalah belum diperbaiki, blok akan muncul kembali.")
            .setPositiveButton("Periksa & coba ulang",(d,w)->{if(AgentService.active!=null)AgentService.active.retryAfterRepair();else message("Mulai layanan terlebih dahulu.");}).setNegativeButton("Batal",null).show()));
        button("Ubah PIN pemeliharaan",()->authorize(()->{EditText pin=new EditText(this);pin.setInputType(18);pin.setHint("PIN baru 6–12 angka");new AlertDialog.Builder(this).setTitle("Ubah PIN").setView(pin).setPositiveButton("Simpan",(d,w)->{try{provision.setPin(pin.getText().toString());message("PIN diperbarui.");}catch(Exception e){message(e.getMessage());}}).setNegativeButton("Batal",null).show();}));
        button("Histori lintasan & diagnosis",()->authorize(this::history));
        button("Ekspor diagnosis JSON",()->authorize(()->{Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/json").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"KN-U300-diagnostic.json");startActivityForResult(i,10);}));
        button("Ekspor seluruh antrean & histori",()->authorize(()->{if(AgentService.active!=null){message("Hentikan layanan sebelum membuat snapshot lengkap. Tidak ada data yang dihapus.");return;}Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/octet-stream").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"KN-U300-snapshot.jsonl");startActivityForResult(i,11);}));
        button("Uji meja K-RFID-03 (mode diagnostik)",()->authorize(this::bench));
        if(provision.simulation()){
            title("Laboratorium simulasi");text("Tidak memakai radio/GPIO atau mengirim data ke ERP. Mulai layanan sebelum skenario. Photo-eye A = mulut masuk, B = mulut keluar.");
            EditText epc=field(page,"EPC dasar 24 karakter hex","E20034120123456789AB0000",false);
            Spinner gate=spinner(new String[]{"lewat","lewat_kecil","mundur","batal_masuk","kosong","beriringan","b_sebelum_a","sinar_macet","sinar_pulih","latar"});
            button("Jalankan skenario gate (photo-eye + tag)",()->{if(AgentService.active!=null)AgentService.active.simulationGate(gate.getSelectedItem().toString(),epc.getText().toString());});
            button("Simulasikan satu pembacaan tag",()->{if(AgentService.active!=null)AgentService.active.simulationTag(epc.getText().toString());});
            button("Simulasikan EPC tidak valid",()->{if(AgentService.active!=null)AgentService.active.simulationTag("INVALID-TAG");});
            CheckBox offline=new CheckBox(this);offline.setText(R.string.simulate_offline);page.addView(offline);offline.setOnCheckedChangeListener((v,on)->{if(AgentService.active!=null)AgentService.active.simulationOffline(on);});
            Spinner verdict=spinner(new String[]{"GREEN","REVIEW","RED","UNKNOWN"});
            button("Pakai keputusan simulasi",()->{if(AgentService.active!=null)AgentService.active.simulationVerdict(verdict.getSelectedItem().toString());});
            Spinner pending=spinner(new String[]{"0","2","5"});
            button("Sisa roll dokumen (trip parsial, document_session)",()->{if(AgentService.active!=null)AgentService.active.simulationPending(Integer.parseInt(pending.getSelectedItem().toString()));});
            button("Simulasikan supervisor melepas kunci gate",()->{if(AgentService.active!=null)AgentService.active.simulationAck();});
            Spinner scenario=spinner(new String[]{"normal","partial","retry","not-durable","overflow","http-413","http-429","http-500","admin-disabled","config-required","auth-invalid","evidence-pending","passage-frozen","event-id-conflict","http-400","http-403","http-409"});
            button("Skenario jaringan untuk request berikutnya",()->{if(AgentService.active!=null){AgentService.active.simulationScenario(scenario.getSelectedItem().toString());message("Skenario dipasang untuk satu request berikutnya.");}});
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
    // ------------------------------------------------------------ uji meja K-RFID-03
    private void bench(){
        if(AgentService.active!=null){message("Hentikan layanan agent dulu: uji meja memakai modul UHF secara eksklusif.");return;}
        if(benchRunning){message("Uji meja sedang berjalan.");return;}
        String run=java.time.Instant.now().toString();
        String[] items=new String[Bench.TITLES.length+2];System.arraycopy(Bench.TITLES,0,items,0,Bench.TITLES.length);
        items[Bench.TITLES.length]="Catat pengamatan operator untuk satu butir";items[Bench.TITLES.length+1]="Ekspor seluruh hasil uji meja (JSON)";
        new AlertDialog.Builder(this).setTitle("Uji meja K-RFID-03"+(provision.simulation()?" • SIMULASI":"")).setItems(items,(d,w)->{
            if(w<Bench.TITLES.length)benchItem(w+1,run);
            else if(w==Bench.TITLES.length)benchNote(run);
            else{Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/json").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"KN-U300-uji-meja.json");startActivityForResult(i,12);}
        }).setNegativeButton("Tutup",null).show();
    }
    private void benchItem(int item,String run){
        LinearLayout form=new LinearLayout(this);form.setOrientation(LinearLayout.VERTICAL);form.setPadding(24,8,24,8);
        TextView info=new TextView(this);info.setText(Bench.INSTRUCTIONS[item-1]);form.addView(info);
        org.json.JSONObject options=new org.json.JSONObject();
        CheckBox opt=null;
        if(item==4){opt=new CheckBox(this);opt.setText(R.string.bench_apply_profile);}
        if(item==5){opt=new CheckBox(this);opt.setText(R.string.bench_allow_region);}
        if(item==8){opt=new CheckBox(this);opt.setText(R.string.bench_cycle_gpo);}
        if(opt!=null)form.addView(opt);
        final CheckBox option=opt;
        new AlertDialog.Builder(this).setTitle(Bench.TITLES[item-1]).setView(form).setPositiveButton("Jalankan",(d,w)->{
            try{if(option!=null&&option.isChecked())options.put(item==4?"apply_profile":item==5?"allow_region":"cycle_gpo",true);}catch(org.json.JSONException e){throw new IllegalStateException(e);}
            if(AgentService.active!=null||benchRunning){message("Layanan agent aktif atau uji lain berjalan.");return;}
            benchRunning=true;ProgressDialogLite progress=new ProgressDialogLite(this,Bench.TITLES[item-1]);
            boolean sim=provision.simulation();
            new Thread(()->{org.json.JSONObject row;
                try(Journal j=new Journal(getApplicationContext(),sim)){row=new Bench(getApplicationContext(),j,sim,run).runItem(item,options,t->runOnUiThread(()->progress.set(t)));}
                benchRunning=false;final String text=row.toString();
                runOnUiThread(()->{progress.dismiss();if(!isDestroyed()){TextView v=new TextView(this);v.setPadding(24,24,24,24);v.setTextIsSelectable(true);v.setText(pretty(text));ScrollView s=new ScrollView(this);s.addView(v);new AlertDialog.Builder(this).setTitle("Hasil butir "+item+" (tersimpan)").setView(s).setPositiveButton("Tutup",null).show();}});
            },"kn-bench").start();
        }).setNegativeButton("Batal",null).show();
    }
    private static String pretty(String json){try{return new org.json.JSONObject(json).toString(2);}catch(org.json.JSONException e){return json;}}
    private void benchNote(String run){
        LinearLayout form=new LinearLayout(this);form.setOrientation(LinearLayout.VERTICAL);form.setPadding(24,8,24,8);
        Spinner item=new Spinner(this);item.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,Bench.TITLES));form.addView(item);
        Spinner verdict=new Spinner(this);verdict.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"sesuai harapan","tidak sesuai","perlu diulang","catatan saja"}));form.addView(verdict);
        EditText note=field(form,"Pengamatan (lampu, terminal, angka, nama penguji)","",false);note.setSingleLine(false);note.setMinLines(3);
        new AlertDialog.Builder(this).setTitle("Pengamatan operator").setView(form).setPositiveButton("Simpan",(d,w)->{
            try(Journal j=new Journal(this,provision.simulation())){new Bench(this,j,provision.simulation(),run).note(item.getSelectedItemPosition()+1,verdict.getSelectedItem().toString(),note.getText().toString());message("Pengamatan tersimpan.");}
        }).setNegativeButton("Batal",null).show();
    }
    /** Dialog progres ringan (ProgressDialog sudah deprecated). */
    private static final class ProgressDialogLite{private final AlertDialog dialog;private final TextView text;
        ProgressDialogLite(Activity a,String title){text=new TextView(a);text.setPadding(32,32,32,32);text.setText(R.string.bench_running);dialog=new AlertDialog.Builder(a).setTitle(title).setView(text).setCancelable(false).show();}
        void set(String t){text.setText(t);}void dismiss(){dialog.dismiss();}}
    private String diagnostics(){AgentService s=AgentService.active;if(s!=null)return s.diagnostic();try(Journal j=new Journal(this,provision.simulation())){return j.diagnostic();}}
    private void history(){
        org.json.JSONArray rows=Json.parse(diagnostics()).optJSONArray("passages");
        if(rows==null||rows.length()==0){message("Belum ada lintasan. Mulai layanan dan lakukan pembacaan.");return;}
        String[] labels=new String[rows.length()];
        for(int i=0;i<rows.length();i++){org.json.JSONObject p=rows.optJSONObject(i),m=Json.parse(p.optString("body"));labels[i]=p.optString("status")+" • "+p.optString("mode")+" • "+m.optString("open_reason","-")+"\n"+m.optString("opened_at")+"\n"+p.optString("id");}
        new AlertDialog.Builder(this).setTitle("100 lintasan terakhir • pilih detail").setItems(labels,(d,w)->{
            org.json.JSONObject p=rows.optJSONObject(w),m=Json.parse(p.optString("body"));org.json.JSONObject close=p.isNull("close_body")?Json.obj():Json.parse(p.optString("close_body"));org.json.JSONObject decision=p.isNull("decision")?Json.obj():Json.parse(p.optString("decision"));
            String details="ID: "+p.optString("id")+"\nStatus: "+p.optString("status")+"\nGate: "+m.optString("logical_gate_id")+"\nKonfigurasi: "+m.optString("config_version")+"\nMode: "+p.optString("mode")+"\nSensor: "+m.optString("sensor_mode","-")+"\nCapture lengkap: "+("1".equals(p.optString("complete"))?"Ya":"Tidak")
                +"\nDibuka oleh: "+close.optString("open_reason",m.optString("open_reason","-"))+"\nDitutup karena: "+close.optString("close_reason",close.optString("boundary_reason","Belum ditutup"))
                +"\nRingkasan EPC×antena: "+close.optInt("observed_summary_count",0)+" | Tepi sinar: "+close.optInt("observed_edge_count",0)+" | Event 0.4: "+close.optInt("observed_event_count",0)
                +"\nKesehatan photo-eye: "+close.optString("sensor_health","-")
                +"\nKeputusan ERP: "+decision.optString("verdict","Belum ada")+" ("+decision.optString("indicator","-")+")\nAlasan: "+(decision.has("reason_codes")?decision.optJSONArray("reason_codes").toString():decision.optString("reason_code","—"))+"\nBasis keputusan: "+decision.optString("completion_basis","—")
                +(decision.optJSONObject("counts")==null?"":"\nSisa roll dokumen: "+decision.optJSONObject("counts").optInt("pending",0));
            TextView v=new TextView(this);v.setPadding(24,24,24,24);v.setText(details);v.setTextIsSelectable(true);ScrollView scroll=new ScrollView(this);scroll.addView(v);new AlertDialog.Builder(this).setTitle("Detail lintasan").setView(scroll).setPositiveButton("Tutup",null).show();
        }).setNegativeButton("Tutup",null).show();
    }
    private void message(String text){new AlertDialog.Builder(this).setMessage(text).setPositiveButton("OK",null).show();}
    @Override protected void onActivityResult(int req,int result,Intent data){super.onActivityResult(req,result,data);
        if((req==10||req==11||req==12)&&result==RESULT_OK&&data!=null&&data.getData()!=null){
            if(exporting){message("Ekspor lain sedang berjalan.");return;}exporting=true;
            android.net.Uri uri=data.getData();boolean sim=provision.simulation();
            new Thread(()->{String notice;
                try(OutputStream out=getContentResolver().openOutputStream(uri)){
                    if(out==null)throw new IOException();
                    if(req==11){if(AgentService.active!=null)throw new IOException("Layanan masih aktif");try(Journal j=new Journal(getApplicationContext(),sim)){j.exportSnapshot(out);}}
                    else if(req==12){try(Journal j=new Journal(getApplicationContext(),sim)){out.write(Bench.export(j).toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8));}}
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
