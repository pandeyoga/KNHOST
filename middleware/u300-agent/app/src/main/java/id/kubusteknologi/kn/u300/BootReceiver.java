package id.kubusteknologi.kn.u300;
import android.content.*;
public final class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context,Intent intent){
        if(Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())&&new Provision(context).boot())context.startForegroundService(new Intent(context,AgentService.class));
    }
}
