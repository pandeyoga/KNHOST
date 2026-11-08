package id.kainnusantara.handheld;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;

import java.io.File;
import java.io.FileNotFoundException;

/**
 * Penyedia berkas MINIMAL (tanpa androidx) agar aplikasi kamera bisa menulis foto "produk belum dikenali" ke folder
 * privat aplikasi. Tidak diekspor; akses hanya lewat izin URI sementara pada intent kamera. Hanya nama berkas
 * sederhana di folder foto/ yang dilayani (tidak ada traversal path).
 */
public final class PhotoProvider extends ContentProvider {
    static final String AUTHORITY = BuildConfig.APPLICATION_ID + ".photos";

    static File dir(android.content.Context c) {
        File d = new File(c.getFilesDir(), "foto");
        if (!d.exists() && !d.mkdirs()) throw new IllegalStateException("Folder foto tidak bisa dibuat");
        return d;
    }

    static Uri uriFor(String name) { return Uri.parse("content://" + AUTHORITY + "/" + name); }

    @Override public boolean onCreate() { return true; }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        String name = uri.getLastPathSegment();
        if (name == null || !name.matches("[A-Za-z0-9_.-]{1,80}")) throw new FileNotFoundException("nama berkas tidak sah");
        File f = new File(dir(getContext()), name);
        int m = mode.contains("w") ? ParcelFileDescriptor.MODE_WRITE_ONLY | ParcelFileDescriptor.MODE_CREATE | ParcelFileDescriptor.MODE_TRUNCATE
                : ParcelFileDescriptor.MODE_READ_ONLY;
        return ParcelFileDescriptor.open(f, m);
    }

    @Override public Cursor query(Uri u, String[] p, String s, String[] a, String o) { return null; }
    @Override public String getType(Uri u) { return "image/jpeg"; }
    @Override public Uri insert(Uri u, ContentValues v) { return null; }
    @Override public int delete(Uri u, String s, String[] a) { return 0; }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { return 0; }
}
