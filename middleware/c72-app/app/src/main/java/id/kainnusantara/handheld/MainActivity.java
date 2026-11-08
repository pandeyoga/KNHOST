package id.kainnusantara.handheld;

import android.content.Intent;
import android.os.Bundle;

/** Peluncur: UNPROVISIONED → Provisioning · READY → Login operator · AUTHENTICATED → Beranda tugas. */
public final class MainActivity extends BaseActivity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Class<?> next = !app.provisioned() ? ProvisionActivity.class : !app.loggedIn() ? LoginActivity.class : HomeActivity.class;
        startActivity(new Intent(this, next));
        finish();
    }
}
