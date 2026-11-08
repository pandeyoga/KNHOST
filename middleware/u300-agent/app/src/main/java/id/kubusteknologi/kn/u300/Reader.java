package id.kubusteknologi.kn.u300;
import android.content.Context;
import com.rscja.deviceapi.RFIDWithUHFA4;
import com.rscja.deviceapi.entity.GPIStateEntity;
import com.rscja.deviceapi.entity.AntennaState;
import java.util.*;
final class Reader {
    interface Sink{void tag(String epc,String tid,String ant,String rssi);}
    private RFIDWithUHFA4 sdk;
    private final boolean simulation;
    Reader(boolean sim){simulation=sim;}
    synchronized void start(Context context,Config config,Sink sink) throws Exception{
        if(simulation)return;
        sdk=RFIDWithUHFA4.getInstance();if(!sdk.init(context))throw new Exception("SDK init gagal");
        org.json.JSONObject indicators=config.gate.optJSONObject("indicators");
        if(indicators!=null&&indicators.optBoolean("enabled")){output(indicators.getInt("green_output"),false);output(indicators.getInt("red_output"),true);}
        // Region codes are vendor/firmware specific. Verify the commissioned value; never guess one.
        if(sdk.getFrequencyMode()!=config.parameters.getInt("expected_region_code"))throw new Exception("Region reader berbeda dari profil");
        List<AntennaState> ants=sdk.getANT();if(ants==null||ants.isEmpty())throw new Exception("Daftar antena tidak tersedia");
        Set<String> found=new HashSet<>();
        for(AntennaState a:ants){String id=a.getAntennaName().name().replace("ANT","");boolean enabled=config.antennas.contains(id);a.setEnable(enabled);
            if(enabled){found.add(id);if(sdk.getAntennaPower(a.getAntennaName())!=config.parameters.getJSONObject("expected_antenna_power_dbm").getInt(id))throw new Exception("Power antena berbeda dari profil");}}
        if(!found.containsAll(config.antennas)||!sdk.setANT(ants))throw new Exception("Konfigurasi antena gagal");
        List<AntennaState> verified=sdk.getANT();if(verified==null)throw new Exception("Readback antena gagal");
        for(AntennaState a:verified){if(a.isEnable()!=config.antennas.contains(a.getAntennaName().name().replace("ANT","")))throw new Exception("Readback antena tidak cocok");}
        sdk.setInventoryCallback(t->{if(t!=null)sink.tag(t.getEPC(),t.getTid(),t.getAnt(),t.getRssi());});
        if(!sdk.startInventoryTag())throw new Exception("SDK inventory gagal");
    }
    synchronized Map<String,Integer> inputs(){Map<String,Integer> m=new HashMap<>();if(sdk!=null){List<GPIStateEntity> values=sdk.inputStatus();if(values==null)throw new IllegalStateException("GPI tidak tersedia");for(GPIStateEntity e:values)m.put(e.getGpiName(),e.getGpiState());}return m;}
    synchronized void output(int n,boolean on){if(simulation)return;if(sdk==null)throw new IllegalStateException("Radio belum siap");boolean ok;
        switch(n){case 1:ok=on?sdk.output1On():sdk.output1Off();break;case 2:ok=on?sdk.output2On():sdk.output2Off();break;case 3:ok=on?sdk.output3On():sdk.output3Off();break;case 4:ok=on?sdk.output4On():sdk.output4Off();break;default:throw new IllegalArgumentException("Output 1..4");}if(!ok)throw new IllegalStateException("GPO gagal");}
    synchronized void stop(){if(sdk!=null){try{if(!sdk.stopInventory())throw new IllegalStateException("Stop inventory tidak dikonfirmasi");}finally{sdk.free();sdk=null;}}}
}
